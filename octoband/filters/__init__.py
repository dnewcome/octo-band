"""
Filter registry and base class.

A filter receives a single raw rtmidi message (list of 1-3 ints) and returns
a list of messages. Returning [] drops the message; returning multiple messages
expands it. This makes the chain composable: each filter is just a function on
a list, and the chain is a fold.

Raw message format from python-rtmidi:
  [status_byte, data1, data2]
  status_byte = (type_nibble << 4) | channel_nibble
  channel is 0-15 internally (MIDI channels 1-16 minus one)
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

# Type alias for clarity throughout the codebase
MidiMsg = list[int]

REGISTRY: dict[str, type["BaseFilter"]] = {}


def register(name: str):
    """Decorator to register a filter class under a config type name."""
    def decorator(cls):
        REGISTRY[name] = cls
        return cls
    return decorator


class BaseFilter(ABC):
    @abstractmethod
    def process(self, msg: MidiMsg) -> list[MidiMsg]:
        ...


def build_filter(spec: dict) -> BaseFilter:
    """Instantiate a filter from a config dict. Pops 'type' and passes the rest as kwargs."""
    spec = dict(spec)  # don't mutate caller's dict
    filter_type = spec.pop("type")
    if filter_type not in REGISTRY:
        raise ValueError(f"Unknown filter type: '{filter_type}'. Available: {sorted(REGISTRY)}")
    return REGISTRY[filter_type](**spec)


# Import submodules so their @register decorators fire
from octoband.filters import channel, notes, cc, generators  # noqa: E402, F401
