# Copyright (C) 2026 damex
# SPDX-License-Identifier: MIT
"""
Load patcher configuration from YAML.
"""

import collections.abc
import dataclasses
import os
import pathlib

import yaml

from windblown_save_patcher import errors

APPLICATION_NAME = "windblown-save-patcher"
CONFIGURATION_KEYS = frozenset({"backup_directory", "flags", "saves"})
BACKUP_DIRECTORY_NAME = "backups"
CONFIGURATION_FILE_NAME = "config.yml"


@dataclasses.dataclass(frozen=True, slots=True)
class Configuration:
    """
    Validated patcher configuration.

    >>> Configuration((), {"a": 1}, pathlib.Path("backups")).flag_bits
    {'a': 1}
    """

    saves: tuple[pathlib.Path, ...]
    flag_bits: dict[str, int]
    backup_directory: pathlib.Path


def windblown_save_patcher_xdg_directory(
    environment: collections.abc.Mapping[str, str],
    variable: str,
    fallback: pathlib.Path,
) -> pathlib.Path:
    """
    Get application directory under XDG base.

    >>> fallback = pathlib.Path("/f")
    >>> windblown_save_patcher_xdg_directory({"XDG_DATA_HOME": "/data"}, "XDG_DATA_HOME", fallback)
    PosixPath('/data/windblown-save-patcher')
    >>> windblown_save_patcher_xdg_directory({"XDG_DATA_HOME": "data"}, "XDG_DATA_HOME", fallback)
    PosixPath('/f/windblown-save-patcher')
    """
    value = environment.get(variable)
    if value is None or not pathlib.Path(value).is_absolute():
        return fallback / APPLICATION_NAME
    return pathlib.Path(value) / APPLICATION_NAME


def windblown_save_patcher_configuration_path() -> pathlib.Path:
    """
    Get user config file path.

    >>> path = windblown_save_patcher_configuration_path()
    >>> path.parent.name, path.name
    ('windblown-save-patcher', 'config.yml')
    """
    configuration_directory = windblown_save_patcher_xdg_directory(
        os.environ,
        "XDG_CONFIG_HOME",
        pathlib.Path.home() / ".config",
    )
    return configuration_directory / CONFIGURATION_FILE_NAME


def windblown_save_patcher_backup_directory() -> pathlib.Path:
    """
    Get user backup directory.

    >>> directory = windblown_save_patcher_backup_directory()
    >>> directory.parent.name, directory.name
    ('windblown-save-patcher', 'backups')
    """
    data_directory = windblown_save_patcher_xdg_directory(
        os.environ,
        "XDG_DATA_HOME",
        pathlib.Path.home() / ".local" / "share",
    )
    return data_directory / BACKUP_DIRECTORY_NAME


def windblown_save_patcher_resolve_path(text: str, base_directory: pathlib.Path) -> pathlib.Path:
    """
    Resolve configured path against config directory.

    >>> windblown_save_patcher_resolve_path("saves/a.sav", pathlib.Path("/configs"))
    PosixPath('/configs/saves/a.sav')
    """
    return base_directory / pathlib.Path(text).expanduser()


def windblown_save_patcher_parse_saves(
    value: object,
    base_directory: pathlib.Path,
) -> tuple[pathlib.Path, ...]:
    """
    Validate save path list.

    >>> windblown_save_patcher_parse_saves(["/a.sav"], pathlib.Path("/configs"))
    (PosixPath('/a.sav'),)
    """
    if not isinstance(value, list) or len(value) == 0:
        raise errors.ConfigurationError(
            "Please make sure that saves lists at least one save file path."
        )
    paths: list[pathlib.Path] = []
    for entry in value:
        if not isinstance(entry, str):
            raise errors.ConfigurationError(
                f"Please make sure that save entry {entry!r} is a path string."
            )
        paths.append(
            windblown_save_patcher_resolve_path(
                entry,
                base_directory,
            )
        )
    return tuple(paths)


def windblown_save_patcher_parse_flags(value: object) -> dict[str, int]:
    """
    Validate flag name to bit mapping.

    >>> windblown_save_patcher_parse_flags({"a": 1})
    {'a': 1}
    """
    if not isinstance(value, dict) or len(value) == 0:
        raise errors.ConfigurationError(
            "Please make sure that flags maps at least one flag name to bit index."
        )
    flag_bits: dict[str, int] = {}
    for flag_name, flag_bit in value.items():
        if not isinstance(flag_name, str) or isinstance(flag_bit, bool):
            raise errors.ConfigurationError(
                f"Please make sure that flag {flag_name!r} maps to bit index."
            )
        if not isinstance(flag_bit, int) or flag_bit < 0:
            raise errors.ConfigurationError(
                f"Please make sure that flag {flag_name} bit index is non-negative integer."
            )
        flag_bits[flag_name] = flag_bit
    return flag_bits


def windblown_save_patcher_parse_backup_directory(
    value: object,
    base_directory: pathlib.Path,
) -> pathlib.Path:
    """
    Validate backup directory.

    >>> windblown_save_patcher_parse_backup_directory("old", pathlib.Path("/configs"))
    PosixPath('/configs/old')
    """
    if value is None:
        return windblown_save_patcher_backup_directory()
    if not isinstance(value, str):
        raise errors.ConfigurationError(
            "Please make sure that backup_directory is a path string."
        )
    return windblown_save_patcher_resolve_path(
        value,
        base_directory,
    )


def windblown_save_patcher_parse_configuration(
    document: object,
    base_directory: pathlib.Path,
) -> Configuration:
    """
    Validate configuration document.

    >>> document = {"saves": ["/a.sav"], "flags": {"a": 1}}
    >>> windblown_save_patcher_parse_configuration(document, pathlib.Path("/")).saves
    (PosixPath('/a.sav'),)
    """
    if not isinstance(document, dict):
        raise errors.ConfigurationError("Please make sure that configuration is a mapping.")
    unknown_keys = sorted(
        str(document_key) for document_key in document if document_key not in CONFIGURATION_KEYS
    )
    if len(unknown_keys) > 0:
        raise errors.ConfigurationError(
            f"Please make sure that configuration holds only known keys, found {unknown_keys}."
        )
    return Configuration(
        saves=windblown_save_patcher_parse_saves(
            document.get("saves"),
            base_directory,
        ),
        flag_bits=windblown_save_patcher_parse_flags(document.get("flags")),
        backup_directory=windblown_save_patcher_parse_backup_directory(
            document.get("backup_directory"),
            base_directory,
        ),
    )


def windblown_save_patcher_load_configuration(path: pathlib.Path) -> Configuration:
    """
    Load configuration file.

    >>> import tempfile
    >>> with tempfile.TemporaryDirectory() as directory:
    ...     path = pathlib.Path(directory, "config.yml")
    ...     text = "---\\nsaves:\\n  - a.sav\\nflags:\\n  a: 1\\n"
    ...     byte_count = path.write_text(text, encoding="utf-8")
    ...     windblown_save_patcher_load_configuration(path).flag_bits
    {'a': 1}
    """
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise errors.ConfigurationError(
            "Config file not found. Please create it as shown in README."
        ) from error
    document: object = yaml.safe_load(text)
    return windblown_save_patcher_parse_configuration(
        document,
        path.resolve().parent,
    )
