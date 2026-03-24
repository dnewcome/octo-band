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

Each physical device gets its own ordered filter chain. Messages flow through
each filter in sequence — a filter can pass a message through, modify it, drop
it entirely, or expand it into multiple messages. A second layer of global
processors sits at the output and sees everything from all devices, enabling
cross-device behaviors.

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
# List available MIDI ports on your system
octo-band --list-ports

# Run with a config file
octo-band --config my-rig.yaml

# Dry run — print outgoing MIDI messages instead of sending them
# Useful for verifying filter behaviour before connecting a DAW
octo-band --config my-rig.yaml --dry-run
```

---

## Configuration

Everything lives in a single YAML file. Run `octo-band --list-ports` first to
find the exact names of your devices, then use any substring of those names in
the `port` field — matching is case-insensitive.

```yaml
devices:

  foot_controller:
    port: "FCB1010"             # substring of the system port name
    filters:
      - type: foot_latch        # monophonic latch: one note held at a time
        heel_note: 36
      - type: channel_map
        from_ch: 1
        to_ch: 10               # remap to drums channel

  harmonica:
    port: "Harmonicist"
    filters:
      - type: breath_to_cc
        source_cc: 2            # breath controller default CC
        target_cc: 11           # expression
      - type: transpose
        semitones: -12

  keyboard:
    port: "MiniLab"
    filters:
      - type: release_trigger   # second note fires on key release
        mode: fifth_up
        release_mode: timed
        release_duration: 0.4

global_processors:
  - type: chord_trigger
    trigger_note: 60
    chord: [60, 63, 67]

output:
  port_name: "octo-band"       # name of the virtual MIDI port
```

### Structure

- **`devices`** — one entry per physical controller. Each has a `port`
  substring and a list of `filters` applied in order.
- **`global_processors`** — another filter list applied to all output messages
  after per-device chains, regardless of which device sent them.
- **`output.port_name`** — the name of the virtual MIDI port that appears in
  your DAW.

---

## Filters

Filters are the building blocks of octo-band. Each filter receives a MIDI
message and returns zero or more messages — it can pass, modify, drop, or
expand. Chains are applied in order; the output of each filter feeds the next.

---

### Channel Routing

**`channel_map`** — Rewrite all messages from one channel to another.

```yaml
- type: channel_map
  from_ch: 1       # source channel (1–16)
  to_ch: 10        # destination channel (1–16)
```

**`channel_remap`** — Rewrite multiple channels at once using a mapping dict.

```yaml
- type: channel_remap
  map:
    1: 3
    2: 4
```

---

### Note Transforms

**`transpose`** — Shift all note numbers by a fixed number of semitones.
Result is clamped to 0–127.

```yaml
- type: transpose
  semitones: -12   # one octave down
```

**`note_filter`** — Whitelist or blacklist specific notes. Use one or the
other, not both.

```yaml
- type: note_filter
  whitelist: [36, 38, 40, 42]   # only these notes pass

# or:
- type: note_filter
  blacklist: [60]                # drop middle C, pass everything else
```

**`velocity_scale`** — Multiply velocity by a factor, then clamp to a range.

```yaml
- type: velocity_scale
  factor: 0.8        # scale down
  min_vel: 5         # floor (default 1)
  max_vel: 110       # ceiling (default 127)
```

---

### CC Transforms

**`breath_to_cc`** — Remap one CC number to another. Designed for breath
controllers (CC2 → expression CC11) but works for any CC-to-CC remap.

```yaml
- type: breath_to_cc
  source_cc: 2
  target_cc: 11
```

**`cc_to_note`** — Convert a CC message into a note on/off. When the CC value
rises to or above `threshold`, a note-on fires. When it falls back below,
a note-off fires. Useful for turning an expression pedal or sustain pedal into
a trigger.

```yaml
- type: cc_to_note
  cc: 64             # sustain pedal
  note: 48           # note to fire
  threshold: 64      # default
  channel: 1         # output channel (default: same as input)
```

**`note_to_cc`** — Convert note on/off into a CC message. Note-on sends the
velocity as the CC value; note-off sends CC value 0.

```yaml
- type: note_to_cc
  cc: 11
  notes: [60, 62]    # optional: only convert these notes
```

---

### Latches

Latches are what separate a foot controller from a typing keyboard. They let
one physical action hold a state so the performer's body can move on to
something else.

**`hold_latch`** — Per-note toggle latch. First press sends note-on and holds.
Second press sends note-off and releases. Note-offs from the controller are
swallowed — the note stays on until the next press. Multiple notes can be
independently latched at the same time.

```yaml
- type: hold_latch
  notes: [60, 62, 65]   # these specific notes become toggles
```

```
Press  60  →  note-on  60  (held)
Press  62  →  note-on  62  (held, 60 still held)
Press  60  →  note-off 60  (released, 62 still held)
Release physical key  →  swallowed
```

**`foot_latch`** — Monophonic latch. Only one note is held at a time. Pressing
a new note releases the previous one and latches the new one. A dedicated
`heel_note` acts as a mute key — it silences the current note without
triggering a new one. All note-offs from the controller are swallowed. Well
suited to a bass-note foot controller where you want clean single-note control
with a quick mute.

```yaml
- type: foot_latch
  heel_note: 36      # default C2
```

```
Press 48  →  note-on  48           (latched)
Press 50  →  note-off 48, note-on 50  (replaced)
Press 36  →  note-off 50           (muted, nothing new)
Release any key  →  swallowed
```

---

### Triggers

**`double_trigger`** — Fire two notes simultaneously on a single key press.
The second note is offset by a fixed number of semitones. Useful for instant
octave doubling, power chords, or thickening a bass line.

```yaml
- type: double_trigger
  offset: 12           # semitone offset for second note (12 = octave up)
  notes: [36, 38]      # optional: only double these notes
```

**`release_trigger`** — Fire a second note when a key is *released*, not when
it is pressed. The key-press note plays normally; the key-release fires a new
note. This creates a roll or re-attack effect — the note re-triggers every time
you lift a finger.

The second note's pitch is set by `mode`:

| Mode | Pitch |
|---|---|
| `same_vel` | Same note, same velocity (default) |
| `half_vel` | Same note, 50% velocity |
| `octave_up` | +12 semitones |
| `octave_down` | −12 semitones |
| `fifth_up` | +7 semitones |
| `third_up` | +4 semitones |

The second note's duration is set by `release_mode`:

| Release mode | Behaviour |
|---|---|
| `timed` | Ends after `release_duration` seconds (default 0.5) |
| `next_press` | Held until the next key-on on the same channel |
| `manual_off` | Held indefinitely (10s safety timeout) |

```yaml
- type: release_trigger
  mode: fifth_up
  release_mode: timed
  release_duration: 0.4
  velocity_offset: -20    # optional: adjust second note velocity
  notes: [48, 50, 52]     # optional: only trigger on these notes
```

```
Press 60  →  note-on  60  (first note plays)
Release 60  →  note-off 60, note-on 67  (fifth fires on release)
(0.4s later)  →  note-off 67  (timed release)
```

---

### Generators

**`chord_trigger`** — Expand a single note into a chord. One note-on becomes
note-ons for all notes in the chord; one note-off releases all of them.

```yaml
- type: chord_trigger
  trigger_note: 60
  chord: [60, 63, 67]   # root, minor third, fifth
```

**`passthrough`** — No-op. Passes all messages unchanged. Useful as a
placeholder while building a config.

```yaml
- type: passthrough
```

---

## Example Rigs

### Bass foot pedal with monophonic latch

```yaml
devices:
  bass_pedals:
    port: "FCB1010"
    filters:
      - type: foot_latch
        heel_note: 36
      - type: transpose
        semitones: -12
      - type: channel_map
        from_ch: 1
        to_ch: 2

output:
  port_name: "octo-band"
```

Press a pedal, that bass note sustains until you press another or hit the heel
key. Transpose puts it in the right register. Channel 2 keeps it routed
separately in the DAW.

---

### Harmonica with breath expression

```yaml
devices:
  harmonica:
    port: "Harmonicist"
    filters:
      - type: breath_to_cc
        source_cc: 2
        target_cc: 11
      - type: velocity_scale
        factor: 1.2
        max_vel: 127

output:
  port_name: "octo-band"
```

Breath pressure controls expression (CC11) continuously. Velocity is boosted
slightly since harmonicas tend to send conservatively.

---

### Keyboard with release re-triggers

```yaml
devices:
  keys:
    port: "MiniLab"
    filters:
      - type: release_trigger
        mode: octave_up
        release_mode: next_press

output:
  port_name: "octo-band"
```

Every key press plays the note normally. Every key release fires the note an
octave higher, and that upper note is held until the next key press. Creates a
natural call-and-response texture from a single hand.

---

## Name

An octopus coordinates eight independent arms simultaneously, each capable of
acting on its own while still contributing to a unified goal. That's the model
here: many control inputs, each doing something distinct, all converging on a
single coherent instrument.
