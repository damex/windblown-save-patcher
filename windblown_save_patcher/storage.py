# Copyright (C) 2026 damex
# SPDX-License-Identifier: MIT
"""
Back up and replace save files.
"""

import datetime
import pathlib
import shutil


def windblown_save_patcher_backup(
    save_path: pathlib.Path,
    backup_root: pathlib.Path,
) -> pathlib.Path:
    """
    Copy save file once per run.

    >>> import tempfile
    >>> with tempfile.TemporaryDirectory() as directory:
    ...     root = pathlib.Path(directory)
    ...     (root / "Steam_1").mkdir()
    ...     byte_count = (root / "Steam_1" / "1.sav").write_bytes(b"save")
    ...     backup = windblown_save_patcher_backup(root / "Steam_1" / "1.sav", root / "backups")
    ...     backup.relative_to(root).as_posix(), backup.read_bytes()
    ('backups/Steam_1/1.sav', b'save')
    """
    destination = backup_root / save_path.parent.name / save_path.name
    if not destination.exists():
        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        shutil.copy2(
            save_path,
            destination,
        )
    return destination


def windblown_save_patcher_write(save_path: pathlib.Path, data: bytes) -> None:
    """
    Replace save file atomically.

    >>> import tempfile
    >>> with tempfile.TemporaryDirectory() as directory:
    ...     save_path = pathlib.Path(directory, "1.sav")
    ...     windblown_save_patcher_write(save_path, b"save")
    ...     save_path.read_bytes()
    b'save'
    """
    temporary_path = save_path.with_name(f"{save_path.name}.patcher-tmp")
    temporary_path.write_bytes(data)
    temporary_path.replace(save_path)


def windblown_save_patcher_timestamp(moment: datetime.datetime) -> str:
    """
    Format backup directory name.

    >>> windblown_save_patcher_timestamp(datetime.datetime(2026, 10, 25, tzinfo=datetime.UTC))
    '20261025_000000'
    """
    return moment.strftime("%Y%m%d_%H%M%S")
