from octoband.filters import BaseFilter, MidiMsg, register


def _is_note_on(msg: MidiMsg) -> bool:
    """True for note-on with non-zero velocity. velocity=0 is treated as note-off."""
    return len(msg) >= 3 and (msg[0] & 0xF0) == 0x90 and msg[2] > 0


def _is_note_off(msg: MidiMsg) -> bool:
    """True for explicit note-off or note-on with velocity 0."""
    if len(msg) < 2:
        return False
    status = msg[0] & 0xF0
    return status == 0x80 or (status == 0x90 and len(msg) >= 3 and msg[2] == 0)


@register("passthrough")
class Passthrough(BaseFilter):
    """No-op filter. Useful as an explicit placeholder in config."""

    def process(self, msg: MidiMsg) -> list[MidiMsg]:
        return [msg]


@register("transpose")
class Transpose(BaseFilter):
    """Shift note numbers by a fixed number of semitones.

    Config:
        semitones: int  (can be negative)
    """

    def __init__(self, semitones: int):
        self._semitones = semitones

    def process(self, msg: MidiMsg) -> list[MidiMsg]:
        if len(msg) < 2:
            return [msg]
        status = msg[0] & 0xF0
        if status not in (0x80, 0x90):
            return [msg]
        new_note = max(0, min(127, msg[1] + self._semitones))
        return [[msg[0], new_note] + msg[2:]]


@register("note_filter")
class NoteFilter(BaseFilter):
    """Whitelist or blacklist specific note numbers.

    Config:
        whitelist: [note, ...]   only these notes pass
        blacklist: [note, ...]   these notes are dropped
    (mutually exclusive)
    """

    def __init__(self, whitelist: list | None = None, blacklist: list | None = None):
        if whitelist is not None and blacklist is not None:
            raise ValueError("note_filter: use whitelist or blacklist, not both")
        self._whitelist = set(whitelist) if whitelist else None
        self._blacklist = set(blacklist) if blacklist else None

    def process(self, msg: MidiMsg) -> list[MidiMsg]:
        if len(msg) < 2:
            return [msg]
        status = msg[0] & 0xF0
        if status not in (0x80, 0x90):
            return [msg]
        note = msg[1]
        if self._whitelist is not None and note not in self._whitelist:
            return []
        if self._blacklist is not None and note in self._blacklist:
            return []
        return [msg]


@register("velocity_scale")
class VelocityScale(BaseFilter):
    """Scale note velocity by a factor, then clamp to a range.

    Config:
        factor:  float  (default 1.0)
        min_vel: int    (default 1)
        max_vel: int    (default 127)
    """

    def __init__(self, factor: float = 1.0, min_vel: int = 1, max_vel: int = 127):
        self._factor = factor
        self._min = min_vel
        self._max = max_vel

    def process(self, msg: MidiMsg) -> list[MidiMsg]:
        if len(msg) < 3:
            return [msg]
        status = msg[0] & 0xF0
        if status not in (0x80, 0x90):
            return [msg]
        vel = int(msg[2] * self._factor)
        vel = max(self._min, min(self._max, vel))
        return [[msg[0], msg[1], vel]]


@register("hold_latch")
class HoldLatch(BaseFilter):
    """Convert momentary note presses into toggles.

    First note-on: emit note-on, mark as held.
    Second note-on (while held): emit note-off, unmark.
    Note-offs for latched notes are always swallowed.
    Non-latched notes pass through unchanged.

    Config:
        notes: [note, ...]  notes to apply latch behaviour to
    """

    def __init__(self, notes: list[int]):
        self._latched = set(notes)
        self._held: set[int] = set()

    def process(self, msg: MidiMsg) -> list[MidiMsg]:
        if len(msg) < 2:
            return [msg]

        note = msg[1]
        if note not in self._latched:
            return [msg]

        if _is_note_on(msg):
            if note in self._held:
                # second press: release
                self._held.discard(note)
                return [[0x80 | (msg[0] & 0x0F), note, 0]]
            else:
                # first press: hold
                self._held.add(note)
                return [msg]

        if _is_note_off(msg):
            # swallow note-off for latched notes
            return []

        return [msg]


@register("double_trigger")
class DoubleTrigger(BaseFilter):
    """Fire an additional note alongside the original.

    Config:
        offset: int   semitone offset for the doubled note (e.g. 12 for octave up)
        notes:  list  optional — only trigger on these notes (default: all)
    """

    def __init__(self, offset: int, notes: list[int] | None = None):
        self._offset = offset
        self._notes = set(notes) if notes else None

    def process(self, msg: MidiMsg) -> list[MidiMsg]:
        if len(msg) < 3:
            return [msg]
        status = msg[0] & 0xF0
        if status not in (0x80, 0x90):
            return [msg]
        note = msg[1]
        if self._notes is not None and note not in self._notes:
            return [msg]
        doubled = max(0, min(127, note + self._offset))
        extra = [msg[0], doubled, msg[2]]
        return [msg, extra]
