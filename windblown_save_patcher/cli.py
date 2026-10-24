# Copyright (C) 2026 damex
# SPDX-License-Identifier: MIT
"""
Command line entry point for Windblown save patcher.
"""

import argparse
import datetime
import logging
import pathlib
import zlib

import yaml

from windblown_save_patcher import config, errors, patch, storage

LOGGER = logging.getLogger(__name__)


def windblown_save_patcher_parse_arguments(argv: list[str] | None) -> bool:
    """
    Parse command line into dry run switch.

    >>> windblown_save_patcher_parse_arguments(["--dry-run"])
    True
    """
    parser = argparse.ArgumentParser(
        description="Set MetaFlag bits in Windblown saves from config.yml in project directory.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="show what would change, write nothing",
    )
    namespace = parser.parse_args(argv)
    dry_run: bool = namespace.dry_run
    return dry_run


def windblown_save_patcher_flag_names(
    flag_bits: dict[str, int],
    selected_bits: tuple[int, ...],
) -> str:
    """
    Name selected flag bits.

    >>> windblown_save_patcher_flag_names({"a": 1, "b": 2}, (2,))
    'b'
    """
    return ", ".join(
        flag_name for flag_name, flag_bit in flag_bits.items() if flag_bit in selected_bits
    )


def windblown_save_patcher_process_save(
    save_path: pathlib.Path,
    configuration: config.Configuration,
    dry_run: bool,
    backup_root: pathlib.Path,
) -> None:
    """
    Set configured flags in one save file.

    >>> configuration = config.Configuration((), {"a": 1}, pathlib.Path("b"))
    >>> save_path = pathlib.Path("/nonexistent.sav")
    >>> windblown_save_patcher_process_save(save_path, configuration, True, pathlib.Path("b"))
    Traceback (most recent call last):
    FileNotFoundError: [Errno 2] No such file or directory: '/nonexistent.sav'
    """
    result = patch.windblown_save_patcher_patch_save(
        save_path.read_bytes(),
        list(configuration.flag_bits.values()),
    )
    if result.copies != result.block_count:
        LOGGER.warning(
            "%s: found %d flag copies in %d blocks, missed copy can bring old flags back",
            save_path,
            result.copies,
            result.block_count,
        )
    if len(result.missing_bits) == 0:
        LOGGER.info(
            "%s: all flags already set (build %.8s)",
            save_path,
            result.git_hash,
        )
        return
    flag_names = windblown_save_patcher_flag_names(
        configuration.flag_bits,
        result.missing_bits,
    )
    if dry_run:
        LOGGER.info(
            "%s: would set %s in %d copies (build %.8s)",
            save_path,
            flag_names,
            result.copies,
            result.git_hash,
        )
        return
    backup = storage.windblown_save_patcher_backup(
        save_path,
        backup_root,
    )
    storage.windblown_save_patcher_write(
        save_path,
        result.data,
    )
    LOGGER.info(
        "%s: set %s in %d copies, backup in %s (build %.8s)",
        save_path,
        flag_names,
        result.copies,
        backup,
        result.git_hash,
    )


def windblown_save_patcher_load(configuration_path: pathlib.Path) -> config.Configuration:
    """
    Load configuration or exit.

    >>> windblown_save_patcher_load(pathlib.Path("/nonexistent/config.yml"))
    Traceback (most recent call last):
    SystemExit: 1
    """
    try:
        return config.windblown_save_patcher_load_configuration(configuration_path)
    except (errors.ConfigurationError, yaml.YAMLError, OSError) as error:
        LOGGER.error(
            "%s: %s",
            configuration_path,
            error,
        )
        raise SystemExit(1) from error


def main(argv: list[str] | None = None) -> None:
    """
    Set configured flags in configured saves.

    >>> main(["--unknown"])
    Traceback (most recent call last):
    SystemExit: 2
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
    )
    dry_run = windblown_save_patcher_parse_arguments(argv)
    configuration = windblown_save_patcher_load(config.windblown_save_patcher_configuration_path())
    backup_root = configuration.backup_directory / storage.windblown_save_patcher_timestamp(
        datetime.datetime.now(tz=datetime.UTC).astimezone()
    )
    failures = 0
    for save_path in configuration.saves:
        try:
            windblown_save_patcher_process_save(
                save_path,
                configuration,
                dry_run,
                backup_root,
            )
        except (errors.SaveFormatError, OSError, zlib.error) as error:
            LOGGER.error(
                "%s: %s",
                save_path,
                error,
            )
            failures += 1
    if failures > 0:
        raise SystemExit(1)
