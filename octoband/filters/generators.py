from octoband.filters import BaseFilter, MidiMsg, register


@register("chord_trigger")
class ChordTrigger(BaseFilter):
    """Expand a single note into a chord.

    On note-on for trigger_note: emit note-on for every note in chord.
    On note-off for trigger_note: emit note-off for every note in chord.
    All other messages pass through.

    Config:
        trigger_note: int
        chord:        [note, ...]  all notes including the root if desired
    """

    def __init__(self, trigger_note: int, chord: list[int]):
        self._trigger = trigger_note
        self._chord = chord

    def process(self, msg: MidiMsg) -> list[MidiMsg]:
        if len(msg) < 2:
            return [msg]
        status = msg[0] & 0xF0
        if status not in (0x80, 0x90):
            return [msg]
        if msg[1] != self._trigger:
            return [msg]

        ch = msg[0] & 0x0F
        vel = msg[2] if len(msg) >= 3 else 0
        is_on = status == 0x90 and vel > 0

        if is_on:
            return [[0x90 | ch, note, vel] for note in self._chord]
        else:
            return [[0x80 | ch, note, 0] for note in self._chord]


@register("arpeggiator")
class Arpeggiator(BaseFilter):
    """Placeholder. Requires a clock source — implementation deferred.

    Currently passes all messages through unchanged.
    """

    def __init__(self, **kwargs):
        pass

    def process(self, msg: MidiMsg) -> list[MidiMsg]:
        return [msg]
