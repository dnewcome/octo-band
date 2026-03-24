"""Unit tests for filters. No MIDI hardware required."""

import pytest

from octoband.filters.notes import Passthrough, Transpose, NoteFilter, VelocityScale, HoldLatch, DoubleTrigger
from octoband.filters.channel import ChannelMap, ChannelRemap
from octoband.filters.cc import BreathToCC, CCToNote, NoteToCC
from octoband.filters.generators import ChordTrigger


# ---------------------------------------------------------------------------
# Passthrough
# ---------------------------------------------------------------------------

def test_passthrough_returns_message_unchanged():
    msg = [0x90, 60, 100]
    assert Passthrough().process(msg) == [msg]


# ---------------------------------------------------------------------------
# Transpose
# ---------------------------------------------------------------------------

def test_transpose_shifts_note_on():
    f = Transpose(semitones=2)
    assert f.process([0x90, 60, 100]) == [[0x90, 62, 100]]

def test_transpose_shifts_note_off():
    f = Transpose(semitones=-3)
    assert f.process([0x80, 60, 0]) == [[0x80, 57, 0]]

def test_transpose_clamps_at_zero():
    f = Transpose(semitones=-10)
    assert f.process([0x90, 3, 100]) == [[0x90, 0, 100]]

def test_transpose_clamps_at_127():
    f = Transpose(semitones=10)
    assert f.process([0x90, 125, 100]) == [[0x90, 127, 100]]

def test_transpose_ignores_cc():
    f = Transpose(semitones=5)
    msg = [0xB0, 11, 64]
    assert f.process(msg) == [msg]


# ---------------------------------------------------------------------------
# NoteFilter
# ---------------------------------------------------------------------------

def test_note_filter_whitelist_passes_listed():
    f = NoteFilter(whitelist=[60, 62])
    assert f.process([0x90, 60, 100]) == [[0x90, 60, 100]]

def test_note_filter_whitelist_blocks_unlisted():
    f = NoteFilter(whitelist=[60, 62])
    assert f.process([0x90, 61, 100]) == []

def test_note_filter_blacklist_blocks_listed():
    f = NoteFilter(blacklist=[60])
    assert f.process([0x90, 60, 100]) == []

def test_note_filter_blacklist_passes_unlisted():
    f = NoteFilter(blacklist=[60])
    assert f.process([0x90, 61, 100]) == [[0x90, 61, 100]]

def test_note_filter_rejects_both_whitelist_and_blacklist():
    with pytest.raises(ValueError):
        NoteFilter(whitelist=[60], blacklist=[62])

def test_note_filter_passes_cc_unchanged():
    f = NoteFilter(whitelist=[60])
    msg = [0xB0, 11, 64]
    assert f.process(msg) == [msg]


# ---------------------------------------------------------------------------
# VelocityScale
# ---------------------------------------------------------------------------

def test_velocity_scale_applies_factor():
    f = VelocityScale(factor=0.5)
    result = f.process([0x90, 60, 100])
    assert result == [[0x90, 60, 50]]

def test_velocity_scale_clamps_to_max():
    f = VelocityScale(factor=2.0, max_vel=100)
    result = f.process([0x90, 60, 80])
    assert result[0][2] == 100

def test_velocity_scale_clamps_to_min():
    f = VelocityScale(factor=0.01, min_vel=10)
    result = f.process([0x90, 60, 50])
    assert result[0][2] == 10


# ---------------------------------------------------------------------------
# HoldLatch
# ---------------------------------------------------------------------------

def test_hold_latch_first_press_emits_note_on():
    f = HoldLatch(notes=[60])
    result = f.process([0x90, 60, 100])
    assert result == [[0x90, 60, 100]]

def test_hold_latch_second_press_emits_note_off():
    f = HoldLatch(notes=[60])
    f.process([0x90, 60, 100])          # first press
    result = f.process([0x90, 60, 100]) # second press
    assert result[0][0] & 0xF0 == 0x80  # note-off status
    assert result[0][1] == 60

def test_hold_latch_swallows_note_off_while_held():
    f = HoldLatch(notes=[60])
    f.process([0x90, 60, 100])      # press
    result = f.process([0x80, 60, 0])  # physical release — should be swallowed
    assert result == []

def test_hold_latch_passes_unlatch_notes():
    f = HoldLatch(notes=[60])
    msg = [0x90, 62, 100]
    assert f.process(msg) == [msg]

def test_hold_latch_velocity_zero_treated_as_note_off():
    f = HoldLatch(notes=[60])
    f.process([0x90, 60, 100])
    # velocity=0 note-on should be swallowed (it's the physical note-off)
    result = f.process([0x90, 60, 0])
    assert result == []


# ---------------------------------------------------------------------------
# DoubleTrigger
# ---------------------------------------------------------------------------

def test_double_trigger_emits_two_notes():
    f = DoubleTrigger(offset=12)
    result = f.process([0x90, 60, 100])
    assert len(result) == 2
    assert result[0][1] == 60
    assert result[1][1] == 72

def test_double_trigger_only_on_specified_notes():
    f = DoubleTrigger(offset=12, notes=[60])
    result = f.process([0x90, 62, 100])
    assert result == [[0x90, 62, 100]]


# ---------------------------------------------------------------------------
# ChannelMap
# ---------------------------------------------------------------------------

def test_channel_map_rewrites_channel():
    f = ChannelMap(from_ch=1, to_ch=10)
    result = f.process([0x90, 60, 100])  # ch 1 note-on
    assert (result[0][0] & 0x0F) == 9    # channel 10 = index 9

def test_channel_map_ignores_other_channels():
    f = ChannelMap(from_ch=1, to_ch=10)
    msg = [0x91, 60, 100]  # channel 2
    assert f.process(msg) == [msg]

def test_channel_map_ignores_sysex():
    f = ChannelMap(from_ch=1, to_ch=10)
    msg = [0xF0, 0x7E, 0xF7]
    assert f.process(msg) == [msg]


# ---------------------------------------------------------------------------
# ChannelRemap
# ---------------------------------------------------------------------------

def test_channel_remap_multiple_channels():
    f = ChannelRemap(map={1: 3, 2: 4})
    r1 = f.process([0x90, 60, 100])  # ch 1 → ch 3
    r2 = f.process([0x91, 60, 100])  # ch 2 → ch 4
    assert (r1[0][0] & 0x0F) == 2    # index 2 = channel 3
    assert (r2[0][0] & 0x0F) == 3    # index 3 = channel 4


# ---------------------------------------------------------------------------
# BreathToCC
# ---------------------------------------------------------------------------

def test_breath_to_cc_rewrites_cc_number():
    f = BreathToCC(source_cc=2, target_cc=11)
    result = f.process([0xB0, 2, 80])
    assert result == [[0xB0, 11, 80]]

def test_breath_to_cc_passes_other_ccs():
    f = BreathToCC(source_cc=2, target_cc=11)
    msg = [0xB0, 7, 100]
    assert f.process(msg) == [msg]


# ---------------------------------------------------------------------------
# CCToNote
# ---------------------------------------------------------------------------

def test_cc_to_note_fires_note_on_at_threshold():
    f = CCToNote(cc=64, note=48, threshold=64)
    result = f.process([0xB0, 64, 64])
    assert result == [[0x90, 48, 127]]

def test_cc_to_note_fires_note_off_below_threshold():
    f = CCToNote(cc=64, note=48, threshold=64)
    f.process([0xB0, 64, 64])  # trigger on
    result = f.process([0xB0, 64, 0])
    assert result == [[0x80, 48, 0]]

def test_cc_to_note_no_repeat_while_held():
    f = CCToNote(cc=64, note=48, threshold=64)
    f.process([0xB0, 64, 100])
    result = f.process([0xB0, 64, 127])  # still above threshold
    assert result == []


# ---------------------------------------------------------------------------
# ChordTrigger
# ---------------------------------------------------------------------------

def test_chord_trigger_expands_note_on():
    f = ChordTrigger(trigger_note=60, chord=[60, 63, 67])
    result = f.process([0x90, 60, 100])
    assert len(result) == 3
    notes = [m[1] for m in result]
    assert notes == [60, 63, 67]

def test_chord_trigger_releases_all_on_note_off():
    f = ChordTrigger(trigger_note=60, chord=[60, 63, 67])
    result = f.process([0x80, 60, 0])
    assert len(result) == 3
    assert all((m[0] & 0xF0) == 0x80 for m in result)

def test_chord_trigger_passes_other_notes():
    f = ChordTrigger(trigger_note=60, chord=[60, 63, 67])
    msg = [0x90, 62, 100]
    assert f.process(msg) == [msg]
