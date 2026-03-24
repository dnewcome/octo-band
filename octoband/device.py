"""InputDevice: owns one MIDI input port and a filter chain."""

import queue
import threading

import rtmidi

from octoband.config import ConfigError
from octoband.filters import BaseFilter, MidiMsg


def find_port(midi_in: rtmidi.MidiIn, spec: str) -> int:
    """Return the index of the first port whose name contains spec (case-insensitive)."""
    ports = midi_in.get_ports()
    spec_lower = spec.lower()
    for i, name in enumerate(ports):
        if spec_lower in name.lower():
            return i
    raise ConfigError(
        f"No MIDI input port matching '{spec}' found.\n"
        f"Available ports: {ports or '(none)'}"
    )


def run_chain(filters: list[BaseFilter], msg: MidiMsg) -> list[MidiMsg]:
    """Apply a filter chain to a single message. Each filter may expand or drop messages."""
    msgs = [msg]
    for f in filters:
        msgs = [out for m in msgs for out in f.process(m)]
    return msgs


class InputDevice:
    def __init__(
        self,
        name: str,
        port_spec: str,
        filters: list[BaseFilter],
        output_queue: queue.Queue,
    ):
        self._name = name
        self._port_spec = port_spec
        self._filters = filters
        self._output_queue = output_queue
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._midi_in: rtmidi.MidiIn | None = None
        self.message_count = 0

    def start(self) -> None:
        self._midi_in = rtmidi.MidiIn()
        port_index = find_port(self._midi_in, self._port_spec)
        self._midi_in.open_port(port_index)
        self._midi_in.set_callback(self._callback)
        self._thread = threading.Thread(target=self._run, name=f"device-{self._name}", daemon=True)
        self._thread.start()
        print(f"[octo-band] {self._name}: opened port matching '{self._port_spec}'")

    def stop(self) -> None:
        self._stop_event.set()
        if self._midi_in is not None:
            # cancel_callback must precede close_port to avoid ALSA deadlock
            self._midi_in.cancel_callback()
            self._midi_in.close_port()
        if self._thread is not None:
            self._thread.join(timeout=2.0)

    def _run(self) -> None:
        """Block until stop is requested. The actual work happens in the rtmidi callback thread."""
        self._stop_event.wait()

    def _callback(self, event, _data) -> None:
        raw_msg, _delta = event
        msgs = run_chain(self._filters, list(raw_msg))
        for msg in msgs:
            self._output_queue.put(msg)
        self.message_count += len(msgs)
