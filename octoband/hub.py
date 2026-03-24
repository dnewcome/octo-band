"""Hub: top-level coordinator. Owns the virtual output port and all input devices."""

import queue
import threading

import rtmidi

from octoband import config as cfg_module
from octoband.device import InputDevice
from octoband.filters import BaseFilter, MidiMsg

_SENTINEL = None  # signals the output thread to exit


def _apply_chain(filters: list[BaseFilter], msgs: list[MidiMsg]) -> list[MidiMsg]:
    for f in filters:
        msgs = [out for m in msgs for out in f.process(m)]
    return msgs


class Hub:
    def __init__(self, cfg: dict, dry_run: bool = False):
        self._cfg = cfg
        self._dry_run = dry_run
        self._queue: queue.Queue = queue.Queue(maxsize=512)
        self._devices: list[InputDevice] = []
        self._global_filters: list[BaseFilter] = []
        self._midi_out: rtmidi.MidiOut | None = None
        self._output_thread: threading.Thread | None = None
        self.total_out = 0

    def start(self) -> None:
        # Build global filter chain
        self._global_filters = cfg_module.build_global_filters(self._cfg)

        # Open virtual output port
        port_name = self._cfg["output"]["port_name"]
        self._midi_out = rtmidi.MidiOut()
        try:
            self._midi_out.open_virtual_port(port_name)
            print(f"[octo-band] Virtual MIDI port '{port_name}' opened")
        except NotImplementedError:
            print(
                "[octo-band] ERROR: Virtual MIDI ports are not supported on this platform.\n"
                "On Windows, install loopMIDI and create a port named "
                f"'{port_name}' manually, then re-run."
            )
            raise

        # Start output thread
        self._output_thread = threading.Thread(
            target=self._output_loop, name="output", daemon=True
        )
        self._output_thread.start()

        # Build and start input devices
        for name, device_cfg in self._cfg.get("devices", {}).items():
            filters = cfg_module.build_device_filters(device_cfg)
            device = InputDevice(
                name=name,
                port_spec=device_cfg["port"],
                filters=filters,
                output_queue=self._queue,
            )
            device.start()
            self._devices.append(device)

    def stop(self) -> None:
        # Stop all input devices first
        for device in self._devices:
            device.stop()

        # Signal output thread to drain and exit
        self._queue.put(_SENTINEL)
        if self._output_thread is not None:
            self._output_thread.join(timeout=2.0)

        if self._midi_out is not None:
            self._midi_out.close_port()

        counts = {d._name: d.message_count for d in self._devices}
        print(f"[octo-band] Stopped. Messages processed: in={counts} out={self.total_out}")

    def _output_loop(self) -> None:
        while True:
            msg = self._queue.get()
            if msg is _SENTINEL:
                break

            # Apply global processors
            msgs = _apply_chain(self._global_filters, [msg])

            for m in msgs:
                if self._dry_run:
                    print(f"[dry-run] {[hex(b) for b in m]}")
                else:
                    self._midi_out.send_message(m)
                self.total_out += 1
