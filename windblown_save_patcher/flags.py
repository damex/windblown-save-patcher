# Copyright (C) 2026 damex
# SPDX-License-Identifier: MIT
"""
Locate MetaFlagMask in save body.
"""

import dataclasses
import itertools

from windblown_save_patcher import bits, errors, schema, walker

FLAG_WORD_BITS = 64
FLAG_MASK_TYPE_NAME = "Quantum.MetaFlagMask"
FLAG_MASK_FIELD_NAME = "_values"
FLAG_FIELD_PATH = ("meta", "flags")


@dataclasses.dataclass(frozen=True, slots=True)
class FlagMask:
    """
    MetaFlagMask location and value in save body.

    >>> FlagMask(offset=32, width=192, value=0).width
    192
    """

    offset: int
    width: int
    value: int


def windblown_save_patcher_flag_mask_width(type_table: dict[int, schema.TypeEntry]) -> int:
    """
    Get MetaFlagMask width in bits.

    >>> values = schema.Field("_values", schema.Descriptor(44, schema.Descriptor(8), None, 3))
    >>> mask_entry = schema.TypeEntry(FLAG_MASK_TYPE_NAME, schema.TypeKind.STRUCT, 0, (values,))
    >>> windblown_save_patcher_flag_mask_width({0: mask_entry})
    192
    """
    for entry in type_table.values():
        if entry.name != FLAG_MASK_TYPE_NAME:
            continue
        for field in entry.fields:
            if field.name == FLAG_MASK_FIELD_NAME:
                return field.descriptor.length * FLAG_WORD_BITS
    raise errors.SaveFormatError(f"schema lacks {FLAG_MASK_TYPE_NAME}.{FLAG_MASK_FIELD_NAME}")


def windblown_save_patcher_locate_flags(body: bytes) -> FlagMask:
    """
    Locate save meta MetaFlagMask.

    >>> windblown_save_patcher_locate_flags(bytes(16))
    Traceback (most recent call last):
    windblown_save_patcher.errors.SaveFormatError: save body holds no types
    """
    reader = bits.BitReader(body)
    type_table = schema.windblown_save_patcher_read_schema(reader)
    offset = walker.windblown_save_patcher_find_field_offset(
        reader,
        type_table,
        FLAG_FIELD_PATH,
    )
    width = windblown_save_patcher_flag_mask_width(type_table)
    reader.seek(offset)
    return FlagMask(
        offset=offset,
        width=width,
        value=reader.read(width),
    )


def windblown_save_patcher_flag_positions(offsets: list[int], flag_bits: list[int]) -> list[int]:
    """
    Combine mask offsets with flag bits.

    >>> windblown_save_patcher_flag_positions([0, 100], [1, 2])
    [1, 2, 101, 102]
    """
    return [
        offset + flag_bit
        for offset, flag_bit in itertools.product(
            offsets,
            flag_bits,
        )
    ]
