# Copyright (C) 2026 damex
# SPDX-License-Identifier: MIT
"""
Gzip streams in Windblown save layout.
"""

import struct
import zlib

GZIP_MAGIC = b"\x1f\x8b\x08"
GZIP_HEADER = bytes((0x1F, 0x8B, 0x08, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x0A))
GZIP_AUTODETECT_WBITS = 47


def windblown_save_patcher_compress(data: bytes) -> bytes:
    """
    Gzip data like game writer.

    >>> windblown_save_patcher_decompress(windblown_save_patcher_compress(b"windblown"))
    b'windblown'
    """
    compressor = zlib.compressobj(
        9,
        zlib.DEFLATED,
        -zlib.MAX_WBITS,
    )
    deflated = compressor.compress(data) + compressor.flush()
    trailer = struct.pack(
        "<II",
        zlib.crc32(data),
        len(data) & 0xFFFFFFFF,
    )
    return GZIP_HEADER + deflated + trailer


def windblown_save_patcher_decompress(data: bytes) -> bytes:
    """
    Gunzip data.

    >>> windblown_save_patcher_decompress(windblown_save_patcher_compress(b"windblown"))
    b'windblown'
    """
    return zlib.decompress(
        data,
        GZIP_AUTODETECT_WBITS,
    )
