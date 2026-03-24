# octo-band

A unified MIDI hub that aggregates multiple physical controllers, applies
configurable processing, and exposes a single virtual MIDI device to your DAW
or hardware synth.

---

## Problem

Live electronic performance with multiple controllers (foot pedals, keyboards,
percussion pads, MIDI harmonica) means:

- A hardware MIDI host box or per-input DAW configuration every session
- Manual routing and channel filtering in Ableton (or equivalent)
- Custom MIDI behaviors (hold/release, double-trigger, breath-to-CC, etc.)
  scattered across different tools with no single source of truth
- Re-doing all of this for every new rig or session

---

## Goal

One Python process. One config file. One virtual MIDI device out.

The virtual device presents multiple channels, each representing a logical
"zone" of the rig. The DAW sees a single tidy input and doesn't need to know
anything about the physical controller topology.

---

## Architecture

```
Physical Devices          octo-band process              Virtual MIDI Out
─────────────────         ─────────────────────          ────────────────
Foot controller  ──────►  Input listener                 ┌──────────────┐
Keyboard/pad     ──────►  per-device filter chain   ───► │  octo-band   │
MIDI harmonica   ──────►  global processor           │   │  virtual     │──► DAW
(any USB/DIN)    ──────►  channel router             │   │  port        │
                          output queue            ───┘   └──────────────┘
```

### Layers

1. **Input listeners** — one thread per physical device, reads raw MIDI
2. **Filter chain** — per-device, ordered list of processors applied in sequence
3. **Global processors** — cross-device logic (e.g. combine foot-hold + note)
4. **Channel router** — maps processed events onto output channels
5. **Virtual MIDI port** — single output consumed by DAW or next device

---

## Configuration File

Single YAML file (e.g. `config.yaml`). Top-level sections:

```yaml
devices:
  foot_controller:
    port: "Behringer FCB1010 MIDI 1"   # substring match on system port name
    filters:
      - type: channel_map
        from: 1
        to: 10                          # remap to drums channel
      - type: hold_latch                # toggle note-on/off from momentary press
        notes: [60, 62]
      - type: cc_to_note               # convert CC pedal to note trigger
        cc: 64
        note: 48

  harmonica:
    port: "Harmonicist"
    filters:
      - type: breath_to_cc             # map breath pressure to CC 11 (expression)
        source_cc: 2
        target_cc: 11
      - type: transpose
        semitones: -12

  keyboard:
    port: "Arturia MiniLab"
    filters:
      - type: channel_remap
        map: { 1: 1, 2: 2 }

output:
  port_name: "octo-band"              # name of the created virtual port
  default_channel: 1

global_processors:
  - type: chord_trigger               # one note triggers a chord
    trigger_note: 36
    chord: [36, 40, 43]
```

### Built-in Filter Types (initial set)

| Filter | Description |
|---|---|
| `channel_map` | Rewrite MIDI channel on messages |
| `note_filter` | Whitelist/blacklist specific notes |
| `transpose` | Shift notes by N semitones |
| `velocity_scale` | Scale velocity by a factor or clamp range |
| `hold_latch` | Convert momentary press to toggle note on/off |
| `cc_to_note` | Convert CC value crossing threshold to note on/off |
| `note_to_cc` | Convert note on/off to CC message |
| `breath_to_cc` | Map breath/pressure CC to another CC |
| `double_trigger` | Fire two notes (or same note twice) from one input |
| `arpeggiator` | Simple step arpeggiator driven by held notes |
| `chord_trigger` | Single note expands to a chord |
| `delay` | Delay message by N ms |
| `passthrough` | No-op, useful for testing |

---

## Implementation Stack

- **Language**: Python 3.11+
- **MIDI I/O**: `python-rtmidi` — cross-platform, supports virtual port creation
  on macOS and Linux (ALSA). On Windows, use loopMIDI as the virtual port.
- **Config parsing**: `PyYAML`
- **Concurrency**: `threading` — one thread per input device, shared output queue
- **CLI**: `argparse` or `click` for `--config`, `--list-ports`, `--dry-run`

### Why not `mido`?

`mido` is cleaner but delegates port creation to the backend anyway (`rtmidi`).
Using `python-rtmidi` directly gives us more control over virtual port lifecycle
and avoids an extra abstraction layer.

---

## Project Layout

```
octo-band/
├── PLAN.md
├── README.md
├── config.yaml              # example / default config
├── pyproject.toml
├── octoband/
│   ├── __init__.py
│   ├── main.py              # entry point, CLI
│   ├── hub.py               # Hub class: owns device threads + output port
│   ├── device.py            # InputDevice: reads one port, runs filter chain
│   ├── router.py            # channel routing logic
│   ├── filters/
│   │   ├── __init__.py      # registry, base class
│   │   ├── channel.py       # channel_map, channel_remap
│   │   ├── notes.py         # transpose, note_filter, hold_latch, double_trigger
│   │   ├── cc.py            # cc_to_note, note_to_cc, breath_to_cc
│   │   └── generators.py    # arpeggiator, chord_trigger
│   └── config.py            # config loading + validation
└── tests/
    ├── test_filters.py
    └── test_config.py
```

---

## Filter Plugin System

Filters are classes registered by name. The config loader resolves `type:` to a
class, instantiates with the remaining keys as kwargs, and appends to the chain.

```python
class BaseFilter:
    def process(self, msg) -> list[MidiMessage]:
        """Return 0..N messages for each input message."""
        ...
```

A filter returns a list so it can drop, pass, or expand messages (e.g. chord
trigger returns multiple note-ons). This makes composition clean — each filter
is just a function on a list.

Custom filters can be added by dropping a module in a `plugins/` directory and
declaring `type: my_plugin.MyFilter` in the config.

---

## Open Questions / Future Work

- **State persistence**: save hold-latch state across restarts? Probably not needed.
- **Live reload**: watch config file and reload without restarting? Useful for
  live tweaking during a set.
- **BPM sync**: arpeggiator needs a clock — derive from MIDI clock messages or
  an internal tempo? Config option for both.
- **GUI**: a minimal TUI (using `textual` or `curses`) showing live event flow
  per device would help with debugging during setup.
- **Windows support**: virtual MIDI on Windows requires loopMIDI; document the
  setup step.
- **Web config editor**: long-term, a small Flask/FastAPI local server + browser
  UI for editing config without touching YAML.

---

## Milestones

1. **Core plumbing** — read from real ports, write to virtual port, passthrough only
2. **Filter chain** — base class + `channel_map`, `transpose`, `passthrough`
3. **Hold/trigger filters** — `hold_latch`, `cc_to_note`, `double_trigger`
4. **Breath/expressive filters** — `breath_to_cc`, `velocity_scale`
5. **Generative filters** — `chord_trigger`, `arpeggiator` (with clock)
6. **Config validation** — clear errors for bad port names, unknown filter types
7. **`--list-ports` and `--dry-run`** — essential for live setup sanity checks
8. **Example configs** — one per controller type, one full rig config
