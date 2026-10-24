# Copyright (C) 2026 damex
# SPDX-License-Identifier: MIT
"""
Little-endian integers and LSB-first bit streams.
"""

import io

from windblown_save_patcher import errors


def windblown_save_patcher_unpack(data: bytes) -> int:
    """
    Decode little-endian integer.

    >>> windblown_save_patcher_unpack(b"\\x34\\x12")
    4660
    """
    return int.from_bytes(
        data,
        "little",
    )


def windblown_save_patcher_pack(value: int, size: int) -> bytes:
    """
    Encode little-endian integer.

    >>> windblown_save_patcher_pack(4660, 4)
    b'4\\x12\\x00\\x00'
    """
    return value.to_bytes(
        size,
        "little",
    )


def windblown_save_patcher_pack_u32(value: int) -> bytes:
    """
    Encode little-endian 32-bit integer.

    >>> windblown_save_patcher_pack_u32(4660)
    b'4\\x12\\x00\\x00'
    """
    return windblown_save_patcher_pack(
        value,
        4,
    )


class BitReader:
    """
    Read LSB-first bits from bytes.

    >>> BitReader(bytes((0b10110000,))).read(5)
    16
    """

    def __init__(self, data: bytes) -> None:
        """
        Wrap data at bit zero.

        >>> BitReader(b"").position
        0
        """
        self.stream = io.BytesIO(data)
        self.position = 0

    def read(self, width: int) -> int:
        """
        Read unsigned value.

        >>> BitReader(b"\\x34\\x12").read(16)
        4660
        """
        byte_offset, bit_offset = divmod(
            self.position,
            8,
        )
        self.stream.seek(byte_offset)
        chunk = self.stream.read((bit_offset + width + 7) // 8)
        if len(chunk) * 8 < bit_offset + width:
            raise errors.SaveFormatError(f"read past end at bit {self.position}")
        self.position += width
        return (windblown_save_patcher_unpack(chunk) >> bit_offset) & ((1 << width) - 1)

    def skip(self, width: int) -> None:
        """
        Advance without reading.

        >>> reader = BitReader(b"")
        >>> reader.skip(9)
        >>> reader.position
        9
        """
        self.position += width

    def seek(self, position: int) -> None:
        """
        Move to bit position.

        >>> reader = BitReader(b"")
        >>> reader.seek(17)
        >>> reader.position
        17
        """
        self.position = position

    def read_string(self) -> str:
        """
        Read length-prefixed string.

        >>> BitReader(b"\\x02\\x00ok").read_string()
        'ok'
        """
        length = self.read(16)
        encoded = bytes(self.read(8) for character_index in range(length))
        try:
            return encoded.decode("utf-8")
        except UnicodeDecodeError as error:
            raise errors.SaveFormatError(f"invalid UTF-8 before bit {self.position}") from error


def windblown_save_patcher_find_bit_pattern(
    data: bytes,
    pattern: int,
    width: int,
) -> list[int]:
    """
    Find bit offsets of pattern.

    >>> data = windblown_save_patcher_pack(0xABCD << 3, 3)
    >>> windblown_save_patcher_find_bit_pattern(data, 0xABCD, 16)
    [3]
    """
    needle = windblown_save_patcher_pack(
        pattern,
        width // 8,
    )
    value = windblown_save_patcher_unpack(data)
    offsets: list[int] = []
    for shift in range(8):
        shifted = windblown_save_patcher_pack(
            value >> shift,
            len(data),
        )
        position = shifted.find(needle)
        while position >= 0:
            if position * 8 + shift + width <= len(data) * 8:
                offsets.append(position * 8 + shift)
            position = shifted.find(
                needle,
                position + 1,
            )
    return sorted(offsets)


def windblown_save_patcher_set_bits(data: bytes, positions: list[int]) -> bytes:
    """
    Set bits at positions.

    >>> windblown_save_patcher_set_bits(bytes(2), [0, 9])
    b'\\x01\\x02'
    """
    value = windblown_save_patcher_unpack(data)
    for position in positions:
        value |= 1 << position
    return windblown_save_patcher_pack(
        value,
        len(data),
    )
