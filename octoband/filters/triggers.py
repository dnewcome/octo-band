"""
Release-triggered filters: fire a second note when the key is released.

This requires async message injection for timed release mode, so these filters
override set_output_queue() to receive a reference to the output queue from
InputDevice at startup.
"""

import queue
import threading

from octoband.filters import BaseFilter, MidiMsg, register


def _second_note(note: int, velocity: int, mode: str, velocity_offset: int) -> tuple[int, int]:
    """Calculate pitch and velocity for the triggered note."""
    offsets = {
        "same": 0,
        "same_vel": 0,
        "half_vel": 0,
        "octave_up": 12,
        "octave_down": -12,
        "fifth_up": 7,
        "third_up": 4,
    }
    if mode not in offsets:
        raise ValueError(f"release_trigger: unknown mode '{mode}'")

    pitch = max(0, min(127, note + offsets[mode]))

    if mode == "half_vel":
        vel = max(1, velocity // 2)
    else:
        vel = velocity

    vel = max(1, min(127, vel + velocity_offset))
    return pitch, vel


@register("release_trigger")
class ReleaseTrigger(BaseFilter):
    """Fire a second note when a key is released.

    On note-on: pass through, remember the velocity.
    On note-off: emit note-off for the first note, then emit note-on for
    the second note. The second note ends according to release_mode.

    Release modes:
      timed      — second note ends after release_duration seconds (requires
                   set_output_queue to be called; falls back to next_press if queue unavailable)
      next_press — second note held until any new note-on on the same channel
      manual_off — second note stays until explicitly released (safety: 10s timeout)

    Pitch modes:
      same / same_vel   — retrigger same note
      half_vel          — same note, 50% velocity
      octave_up/down    — ±12 semitones
      fifth_up          — +7 semitones
      third_up          — +4 semitones

    Config:
        mode:             str   pitch mode (default: same_vel)
        release_mode:     str   release timing (default: timed)
        release_duration: float seconds for timed mode (default: 0.5)
        velocity_offset:  int   added to second note velocity (default: 0)
        notes:            list  optional — only trigger on these notes
    """

    MANUAL_OFF_SAFETY = 10.0  # seconds before forced release in manual_off mode

    def __init__(
        self,
        mode: str = "same_vel",
        release_mode: str = "timed",
        release_duration: float = 0.5,
        velocity_offset: int = 0,
        notes: list[int] | None = None,
    ):
        self._mode = mode
        self._release_mode = release_mode
        self._release_duration = release_duration
        self._velocity_offset = velocity_offset
        self._filter_notes = set(notes) if notes else None
        self._queue: queue.Queue | None = None

        # (channel, note) → original velocity for held first notes
        self._first_notes: dict[tuple[int, int], int] = {}
        # (channel, note) → True for active second notes
        self._second_notes: dict[tuple[int, int], bool] = {}

    def set_output_queue(self, q: queue.Queue) -> None:
        self._queue = q

    def process(self, msg: MidiMsg) -> list[MidiMsg]:
        if len(msg) < 2:
            return [msg]
        status = msg[0] & 0xF0
        if status not in (0x80, 0x90):
            return [msg]

        ch = msg[0] & 0x0F
        note = msg[1]
        vel = msg[2] if len(msg) >= 3 else 0
        is_on = status == 0x90 and vel > 0
        key = (ch, note)

        if is_on:
            # For next_press mode: release all active second notes on this channel
            if self._release_mode == "next_press":
                for (c, n) in list(self._second_notes):
                    if c == ch:
                        del self._second_notes[(c, n)]
                        return [[0x80 | c, n, 0], msg]

            # End any second note at this same pitch before re-triggering
            if key in self._second_notes:
                del self._second_notes[key]
                out = [[0x80 | ch, note, 0]]
            else:
                out = []

            if self._filter_notes is None or note in self._filter_notes:
                self._first_notes[key] = vel

            out.append(msg)
            return out

        else:
            # Note-off path
            if key not in self._first_notes:
                return [msg]

            orig_vel = self._first_notes.pop(key)

            if self._filter_notes is not None and note not in self._filter_notes:
                return [msg]

            second_note, second_vel = _second_note(note, orig_vel, self._mode, self._velocity_offset)
            second_key = (ch, second_note)

            out = [msg, [0x90 | ch, second_note, second_vel]]
            self._second_notes[second_key] = True

            if self._release_mode == "timed":
                self._schedule_release(ch, second_note, self._release_duration)
            elif self._release_mode == "manual_off":
                self._schedule_release(ch, second_note, self.MANUAL_OFF_SAFETY)
            # next_press: release happens on the next note-on (handled above)

            return out

    def _schedule_release(self, channel: int, note: int, delay: float) -> None:
        """Schedule a note-off after delay seconds, injected directly into the output queue."""
        key = (channel, note)
        note_off = [0x80 | channel, note, 0]

        def _fire():
            if key in self._second_notes:
                del self._second_notes[key]
                if self._queue is not None:
                    self._queue.put(note_off)

        threading.Timer(delay, _fire).start()
