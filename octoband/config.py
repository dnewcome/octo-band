"""Config loading and validation."""

import yaml
from octoband.filters import build_filter, BaseFilter


class ConfigError(Exception):
    pass


def load(path: str) -> dict:
    try:
        with open(path) as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        raise ConfigError(f"Config file not found: {path}")
    except yaml.YAMLError as e:
        raise ConfigError(f"YAML parse error in {path}: {e}")


def validate(cfg: dict) -> None:
    if not isinstance(cfg, dict):
        raise ConfigError("Config must be a YAML mapping at the top level")

    output = cfg.get("output")
    if not output or not output.get("port_name"):
        raise ConfigError("Config missing required field: output.port_name")

    for name, device in cfg.get("devices", {}).items():
        if not device.get("port"):
            raise ConfigError(f"Device '{name}' is missing required field: port")
        for spec in device.get("filters", []):
            if "type" not in spec:
                raise ConfigError(f"Device '{name}': filter entry missing 'type' field: {spec}")
            try:
                build_filter(dict(spec))
            except ValueError as e:
                raise ConfigError(f"Device '{name}': {e}")

    for spec in cfg.get("global_processors", []):
        if "type" not in spec:
            raise ConfigError(f"global_processors: filter entry missing 'type' field: {spec}")
        try:
            build_filter(dict(spec))
        except ValueError as e:
            raise ConfigError(f"global_processors: {e}")


def build_device_filters(device_cfg: dict) -> list[BaseFilter]:
    return [build_filter(dict(spec)) for spec in device_cfg.get("filters", [])]


def build_global_filters(cfg: dict) -> list[BaseFilter]:
    return [build_filter(dict(spec)) for spec in cfg.get("global_processors", [])]
