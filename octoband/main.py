"""CLI entry point."""

import argparse
import signal
import sys
import threading

import rtmidi

from octoband import config as cfg_module
from octoband.config import ConfigError
from octoband.hub import Hub


def list_ports() -> None:
    midi_in = rtmidi.MidiIn()
    midi_out = rtmidi.MidiOut()
    in_ports = midi_in.get_ports()
    out_ports = midi_out.get_ports()

    print("MIDI Input ports:")
    if in_ports:
        for i, name in enumerate(in_ports):
            print(f"  {i}: {name}")
    else:
        print("  (none)")

    print("\nMIDI Output ports:")
    if out_ports:
        for i, name in enumerate(out_ports):
            print(f"  {i}: {name}")
    else:
        print("  (none)")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="octo-band",
        description="Unified MIDI hub — aggregates controllers, applies filter chains, "
                    "exposes a single virtual MIDI device.",
    )
    parser.add_argument("--config", default="config.yaml", metavar="PATH",
                        help="Path to YAML config file (default: config.yaml)")
    parser.add_argument("--list-ports", action="store_true",
                        help="List available MIDI ports and exit")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print outgoing MIDI messages instead of sending them")
    args = parser.parse_args()

    if args.list_ports:
        list_ports()
        return

    try:
        cfg = cfg_module.load(args.config)
        cfg_module.validate(cfg)
    except ConfigError as e:
        print(f"[octo-band] Config error: {e}", file=sys.stderr)
        sys.exit(1)

    hub = Hub(cfg, dry_run=args.dry_run)

    stop_event = threading.Event()

    def _shutdown(signum, frame):
        print("\n[octo-band] Shutting down...")
        stop_event.set()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        hub.start()
    except ConfigError as e:
        print(f"[octo-band] Startup error: {e}", file=sys.stderr)
        sys.exit(1)
    except NotImplementedError:
        sys.exit(1)

    print("[octo-band] Running. Press Ctrl+C to stop.")
    stop_event.wait()
    hub.stop()


if __name__ == "__main__":
    main()
