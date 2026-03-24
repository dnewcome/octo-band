"""Unit tests for config loading and validation."""

import pytest
import yaml

from octoband.config import load, validate, build_device_filters, ConfigError
from octoband.filters import build_filter
from octoband.filters.notes import Transpose


_MINIMAL_VALID = """
devices:
  keyboard:
    port: "SomePort"
    filters:
      - type: passthrough
output:
  port_name: "octo-band"
"""

_NO_OUTPUT = """
devices:
  keyboard:
    port: "SomePort"
    filters: []
"""

_MISSING_PORT = """
devices:
  keyboard:
    filters: []
output:
  port_name: "octo-band"
"""

_UNKNOWN_FILTER = """
devices:
  keyboard:
    port: "SomePort"
    filters:
      - type: nonexistent_filter
output:
  port_name: "octo-band"
"""


def _cfg(yaml_str: str) -> dict:
    return yaml.safe_load(yaml_str)


def test_validate_accepts_minimal_valid_config():
    validate(_cfg(_MINIMAL_VALID))  # should not raise


def test_validate_raises_on_missing_output_port_name():
    with pytest.raises(ConfigError, match="output.port_name"):
        validate(_cfg(_NO_OUTPUT))


def test_validate_raises_on_missing_device_port():
    with pytest.raises(ConfigError, match="missing required field: port"):
        validate(_cfg(_MISSING_PORT))


def test_validate_raises_on_unknown_filter_type():
    with pytest.raises(ConfigError, match="nonexistent_filter"):
        validate(_cfg(_UNKNOWN_FILTER))


def test_build_filter_creates_transpose():
    f = build_filter({"type": "transpose", "semitones": 5})
    assert isinstance(f, Transpose)
    result = f.process([0x90, 60, 100])
    assert result[0][1] == 65


def test_build_filter_raises_on_unknown_type():
    with pytest.raises(ValueError, match="Unknown filter type"):
        build_filter({"type": "made_up"})


def test_build_device_filters_empty():
    filters = build_device_filters({"port": "x", "filters": []})
    assert filters == []


def test_build_device_filters_multiple():
    device_cfg = {
        "port": "x",
        "filters": [
            {"type": "transpose", "semitones": 2},
            {"type": "passthrough"},
        ],
    }
    filters = build_device_filters(device_cfg)
    assert len(filters) == 2


def test_load_raises_on_missing_file():
    with pytest.raises(ConfigError, match="not found"):
        load("/nonexistent/path/config.yaml")
