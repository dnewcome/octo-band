# octo-band

An octopus has eight arms and uses all of them at once.

A human performer has two hands, two feet, and a mouth — five independent
control vectors. With latches, cross-device triggers, and breath control layered
on top, you can push that number much higher without growing any new limbs.

octo-band is a MIDI hub that wires all of your physical controllers together,
applies a configurable chain of filters and transformations, and presents a
single clean virtual MIDI device to your DAW or synth rig. One config file
describes the entire setup. One port comes out the other side.

---

## The Setup Problem

Running multiple controllers simultaneously — foot pedals, keyboards, percussion
pads, MIDI harmonica — creates compounding configuration overhead:

- A hardware MIDI host box if you're going dawless, or per-device input routing
  in Ableton (or your DAW of choice)
- Channel filtering and remapping for every device
- Custom behaviors like hold/latch, double-trigger, and breath-to-expression
  spread across different tools with no single source of truth
- All of it to redo from scratch when the rig changes

The result is that the configuration *becomes* the instrument, and it lives
nowhere.

---

## How It Works

```
Physical Controllers       octo-band              Virtual MIDI Out
────────────────────       ─────────────          ────────────────
Foot pedals        ──────► filter chain  ───────► octo-band port ──► DAW
Keyboard / pads    ──────► filter chain      ▲
MIDI harmonica     ──────► filter chain      │
(any USB or DIN)   ──────► filter chain      │
                           cross-device ─────┘
                           processors
```

Each physical device gets its own filter chain. Filters can remap channels,
transpose notes, transform CC messages, or generate new events entirely. A
second layer of global processors handles cross-device logic — a foot pedal
holding a latch while the keyboard plays, or the harmonica's breath shaping the
expression of whatever the hands are doing.

---

## Control Vectors

The goal is to maximize the number of things you can control independently and
simultaneously:

| Body part | Device | What it does |
|---|---|---|
| Left foot | Foot controller | Latches, scene switches, bass triggers |
| Right foot | Expression pedal | Volume, filter sweep, CC continuous |
| Left hand | Keyboard / pad | Melody, chords, velocity-sensitive hits |
| Right hand | Percussion pad | Drums, one-shot samples, mutes |
| Mouth | MIDI harmonica | Breath pressure → expression, pitch bend |
| — | Latches | Freeze a state so a limb can move on |
| — | Cross-device logic | Combine inputs for emergent behavior |

Latches are what make this scale. A foot press that toggles a hold frees up
that foot for the next action. A breath-controlled latch can sustain a chord
while both hands move to something else entirely.

---

## Configuration

Everything lives in a single YAML file:

```yaml
devices:
  foot_controller:
    port: "FCB1010"                    # substring match on system port name
    filters:
      - type: hold_latch               # momentary press becomes toggle
        notes: [60, 62]
      - type: cc_to_note               # expression pedal fires a note
        cc: 64
        note: 48

  harmonica:
    port: "Harmonicist"
    filters:
      - type: breath_to_cc             # breath pressure → expression
        source_cc: 2
        target_cc: 11
      - type: transpose
        semitones: -12

  keyboard:
    port: "MiniLab"
    filters:
      - type: channel_map
        from: 1
        to: 3

global_processors:
  - type: chord_trigger
    trigger_note: 36
    chord: [36, 40, 43]

output:
  port_name: "octo-band"
```

---

## Installation

```bash
pip install octo-band
```

Or from source:

```bash
git clone https://github.com/dnewcome/octo-band
cd octo-band
pip install -e .
```

### Platform notes

- **Linux / macOS**: virtual MIDI ports are created natively via ALSA / CoreMIDI
- **Windows**: install [loopMIDI](https://www.tobias-erichsen.de/software/loopmidi.html)
  first to provide virtual port infrastructure

---

## Usage

```bash
# List available MIDI ports
octo-band --list-ports

# Run with a config file
octo-band --config my-rig.yaml

# Dry run — print events without outputting MIDI
octo-band --config my-rig.yaml --dry-run
```

---

## Built-in Filters

| Filter | Description |
|---|---|
| `channel_map` | Rewrite MIDI channel |
| `note_filter` | Whitelist or blacklist specific notes |
| `transpose` | Shift notes by N semitones |
| `velocity_scale` | Scale or clamp velocity range |
| `hold_latch` | Convert momentary press to toggle note on/off |
| `cc_to_note` | CC crossing a threshold fires a note on/off |
| `note_to_cc` | Note on/off fires a CC message |
| `breath_to_cc` | Map one CC to another (pressure, expression) |
| `double_trigger` | One note fires two (unison, octave, harmony) |
| `chord_trigger` | One note expands to a full chord |
| `arpeggiator` | Step arpeggiator over held notes, clock-synced |
| `delay` | Delay messages by N milliseconds |

Custom filters can be added as Python modules in a `plugins/` directory.

---

## Name

An octopus coordinates eight independent arms simultaneously, each capable of
acting on its own while still contributing to a unified goal. That's the model
here: many control inputs, each doing something distinct, all converging on a
single coherent instrument.
