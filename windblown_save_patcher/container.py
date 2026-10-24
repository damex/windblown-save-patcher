# Copyright (C) 2026 damex
# SPDX-License-Identifier: MIT
"""
Windblown save file container with SHA1 sections.
"""

import dataclasses
import hashlib
import io

from windblown_save_patcher import bits, compression, errors

MAGIC = b"MTWB"
SHA1_SIZE = 20
SAVE_HEADER_TAIL_SIZE = 9


@dataclasses.dataclass(frozen=True, slots=True)
class SaveContainer:
    """
    Outer save file sections.

    >>> SaveContainer(1, b"", bytes(20), bytes(9), b"").version
    1
    """

    version: int
    header_gzip: bytes
    git_hash: bytes
    tail: bytes
    body_gzip: bytes


def windblown_save_patcher_read_container(data: bytes) -> SaveContainer:
    """
    Split save file into sections.

    >>> container = SaveContainer(1, b"h", bytes(20), bytes(9), compression.GZIP_MAGIC)
    >>> data = windblown_save_patcher_build_container(container)
    >>> windblown_save_patcher_read_container(data) == container
    True
    """
    stream = io.BytesIO(data)
    if stream.read(len(MAGIC)) != MAGIC:
        raise errors.SaveFormatError("save lacks MTWB magic")
    version = bits.windblown_save_patcher_unpack(stream.read(1))
    header_length = bits.windblown_save_patcher_unpack(stream.read(4))
    header_hash = stream.read(SHA1_SIZE)
    header_gzip = stream.read(header_length)
    if hashlib.sha1(header_gzip).digest() != header_hash:
        raise errors.SaveFormatError("header hash mismatch")
    rest_hash = stream.read(SHA1_SIZE)
    rest = stream.read()
    if hashlib.sha1(rest).digest() != rest_hash:
        raise errors.SaveFormatError("body hash mismatch")
    rest_stream = io.BytesIO(rest)
    git_hash = rest_stream.read(SHA1_SIZE)
    tail = rest_stream.read(SAVE_HEADER_TAIL_SIZE)
    body_gzip = rest_stream.read()
    if not body_gzip.startswith(compression.GZIP_MAGIC):
        raise errors.SaveFormatError("body gzip not found after save header")
    return SaveContainer(
        version=version,
        header_gzip=header_gzip,
        git_hash=git_hash,
        tail=tail,
        body_gzip=body_gzip,
    )


def windblown_save_patcher_build_container(container: SaveContainer) -> bytes:
    """
    Assemble save file with hashes.

    >>> container = SaveContainer(1, b"h", bytes(20), bytes(9), b"")
    >>> windblown_save_patcher_build_container(container).startswith(MAGIC)
    True
    """
    rest = container.git_hash + container.tail + container.body_gzip
    return b"".join(
        (
            MAGIC,
            bytes((container.version,)),
            bits.windblown_save_patcher_pack_u32(len(container.header_gzip)),
            hashlib.sha1(container.header_gzip).digest(),
            container.header_gzip,
            hashlib.sha1(rest).digest(),
            rest,
        )
    )


def windblown_save_patcher_split_blocks(body: bytes) -> list[bytes]:
    """
    Split body into size-prefixed blocks.

    >>> windblown_save_patcher_split_blocks(b"\\x01\\x00\\x00\\x00A\\x00\\x00\\x00\\x00")
    [b'\\x01\\x00\\x00\\x00A', b'\\x00\\x00\\x00\\x00']
    """
    stream = io.BytesIO(body)
    blocks: list[bytes] = []
    while stream.tell() < len(body):
        size_bytes = stream.read(4)
        payload = stream.read(bits.windblown_save_patcher_unpack(size_bytes))
        if len(payload) != bits.windblown_save_patcher_unpack(size_bytes):
            raise errors.SaveFormatError(f"block at byte {stream.tell()} is truncated")
        blocks.append(size_bytes + payload)
    return blocks
