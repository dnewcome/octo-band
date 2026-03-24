from octoband.filters import BaseFilter, MidiMsg, register


def _is_voice_msg(status: int) -> bool:
    """True for channel-voice messages (0x80–0xEF)."""
    return 0x80 <= status <= 0xEF


def _set_channel(status: int, channel: int) -> int:
    """Rewrite the channel nibble, preserving the type nibble."""
    return (status & 0xF0) | (channel & 0x0F)


@register("channel_map")
class ChannelMap(BaseFilter):
    """Rewrite all messages from one channel to another.

    Config:
        from_ch: source MIDI channel (1-16)
        to_ch:   destination MIDI channel (1-16)
    """

    def __init__(self, from_ch: int, to_ch: int):
        self._from = from_ch - 1  # store as 0-15
        self._to = to_ch - 1

    def process(self, msg: MidiMsg) -> list[MidiMsg]:
        if not msg or not _is_voice_msg(msg[0]):
            return [msg]
        if (msg[0] & 0x0F) != self._from:
            return [msg]
        return [[_set_channel(msg[0], self._to)] + msg[1:]]


@register("channel_remap")
class ChannelRemap(BaseFilter):
    """Rewrite channels via an arbitrary mapping dict.

    Config:
        map: { from_ch: to_ch, ... }  (MIDI channels 1-16)
    """

    def __init__(self, map: dict):
        # store internally as 0-15
        self._map = {int(k) - 1: int(v) - 1 for k, v in map.items()}

    def process(self, msg: MidiMsg) -> list[MidiMsg]:
        if not msg or not _is_voice_msg(msg[0]):
            return [msg]
        ch = msg[0] & 0x0F
        if ch not in self._map:
            return [msg]
        return [[_set_channel(msg[0], self._map[ch])] + msg[1:]]
