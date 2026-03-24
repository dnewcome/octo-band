from octoband.filters import BaseFilter, MidiMsg, register


def _is_cc(msg: MidiMsg, cc_number: int | None = None) -> bool:
    if len(msg) < 2:
        return False
    if (msg[0] & 0xF0) != 0xB0:
        return False
    return cc_number is None or msg[1] == cc_number


@register("breath_to_cc")
class BreathToCC(BaseFilter):
    """Remap one CC number to another (e.g. breath CC2 → expression CC11).

    Config:
        source_cc: int
        target_cc: int
    """

    def __init__(self, source_cc: int, target_cc: int):
        self._source = source_cc
        self._target = target_cc

    def process(self, msg: MidiMsg) -> list[MidiMsg]:
        if not _is_cc(msg, self._source):
            return [msg]
        return [[msg[0], self._target, msg[2]]]


@register("cc_to_note")
class CCToNote(BaseFilter):
    """Convert a CC crossing a threshold into a note on/off.

    When CC value rises to >= threshold: emit note-on.
    When CC value falls below threshold: emit note-off.

    Config:
        cc:        int   CC number to watch
        note:      int   note to emit
        threshold: int   default 64
        channel:   int   output channel 1-16, default same as input
    """

    def __init__(self, cc: int, note: int, threshold: int = 64, channel: int | None = None):
        self._cc = cc
        self._note = note
        self._threshold = threshold
        self._channel = (channel - 1) if channel is not None else None
        self._on = False

    def process(self, msg: MidiMsg) -> list[MidiMsg]:
        if not _is_cc(msg, self._cc):
            return [msg]

        ch = self._channel if self._channel is not None else (msg[0] & 0x0F)
        value = msg[2] if len(msg) >= 3 else 0

        if value >= self._threshold and not self._on:
            self._on = True
            return [[0x90 | ch, self._note, 127]]
        elif value < self._threshold and self._on:
            self._on = False
            return [[0x80 | ch, self._note, 0]]

        return []  # no state change, swallow the CC


@register("note_to_cc")
class NoteToCC(BaseFilter):
    """Convert note on/off into a CC message.

    note-on  → CC with velocity as value
    note-off → CC with value 0

    Config:
        cc:      int   CC number to emit
        channel: int   output channel 1-16, default same as input
        notes:   list  optional — only trigger on these notes (default: all)
    """

    def __init__(self, cc: int, channel: int | None = None, notes: list[int] | None = None):
        self._cc = cc
        self._channel = (channel - 1) if channel is not None else None
        self._notes = set(notes) if notes else None

    def process(self, msg: MidiMsg) -> list[MidiMsg]:
        if len(msg) < 2:
            return [msg]
        status = msg[0] & 0xF0
        if status not in (0x80, 0x90):
            return [msg]

        note = msg[1]
        if self._notes is not None and note not in self._notes:
            return [msg]

        ch = self._channel if self._channel is not None else (msg[0] & 0x0F)
        velocity = msg[2] if len(msg) >= 3 else 0

        # note-on with velocity > 0 → CC with velocity value
        # note-off (or velocity=0) → CC value 0
        if status == 0x90 and velocity > 0:
            return [[0xB0 | ch, self._cc, velocity]]
        else:
            return [[0xB0 | ch, self._cc, 0]]
