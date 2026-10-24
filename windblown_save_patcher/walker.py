# Copyright (C) 2026 damex
# SPDX-License-Identifier: MIT
"""
Skip serialized values and locate fields by schema.
"""

import itertools

from windblown_save_patcher import bits, errors, schema


def windblown_save_patcher_user_type(
    code: int,
    type_table: dict[int, schema.TypeEntry],
) -> schema.TypeEntry:
    """
    Look up user type by type code.

    >>> type_table = {0: schema.TypeEntry("S", schema.TypeKind.STRUCT, 0, ())}
    >>> windblown_save_patcher_user_type(0x40, type_table).name
    'S'
    """
    type_index = code & ~schema.USER_TYPE_FLAG
    if type_index not in type_table:
        raise errors.SaveFormatError(f"unknown type index {type_index}")
    return type_table[type_index]


def windblown_save_patcher_skip_container(
    reader: bits.BitReader,
    descriptor: schema.Descriptor,
    type_table: dict[int, schema.TypeEntry],
) -> None:
    """
    Skip container value.

    >>> value = 1 | (2 << 1) | (0xAA << 17) | (0xBB << 25)
    >>> reader = bits.BitReader(bits.windblown_save_patcher_pack(value, 5))
    >>> list_descriptor = schema.Descriptor(code=41, element=schema.Descriptor(code=2))
    >>> windblown_save_patcher_skip_container(reader, list_descriptor, {})
    >>> reader.position
    33
    """
    if descriptor.element is None:
        raise errors.SaveFormatError(f"container {descriptor.code} lacks element type")
    if descriptor.code == schema.ContainerCode.FIXED_ARRAY:
        count = descriptor.length
    elif reader.read(1) == 0:
        return
    else:
        count = reader.read(16)
    entries = itertools.repeat(
        (descriptor.key, descriptor.element),
        count,
    )
    for key_descriptor, element_descriptor in entries:
        if key_descriptor is not None:
            windblown_save_patcher_skip_value(
                reader,
                key_descriptor,
                type_table,
            )
        windblown_save_patcher_skip_value(
            reader,
            element_descriptor,
            type_table,
        )


def windblown_save_patcher_skip_user_type(
    reader: bits.BitReader,
    entry: schema.TypeEntry,
    type_table: dict[int, schema.TypeEntry],
) -> None:
    """
    Skip enum, struct or class value.

    >>> reader = bits.BitReader(bytes(1))
    >>> class_entry = schema.TypeEntry("C", schema.TypeKind.CLASS, 0, ())
    >>> windblown_save_patcher_skip_user_type(reader, class_entry, {})
    >>> reader.position
    1
    """
    if entry.kind is schema.TypeKind.ENUM:
        reader.skip(schema.windblown_save_patcher_primitive_width(entry.underlying))
        return
    if entry.kind is schema.TypeKind.CLASS and reader.read(1) == 0:
        return
    for field in entry.fields:
        windblown_save_patcher_skip_value(
            reader,
            field.descriptor,
            type_table,
        )


def windblown_save_patcher_skip_value(
    reader: bits.BitReader,
    descriptor: schema.Descriptor,
    type_table: dict[int, schema.TypeEntry],
) -> None:
    """
    Skip one serialized value.

    >>> reader = bits.BitReader(bytes(8))
    >>> windblown_save_patcher_skip_value(reader, schema.Descriptor(code=7), {})
    >>> reader.position
    64
    """
    if descriptor.code & schema.USER_TYPE_FLAG != 0:
        windblown_save_patcher_skip_user_type(
            reader,
            windblown_save_patcher_user_type(
                descriptor.code,
                type_table,
            ),
            type_table,
        )
    elif descriptor.code in schema.ContainerCode:
        windblown_save_patcher_skip_container(
            reader,
            descriptor,
            type_table,
        )
    elif descriptor.code == schema.PrimitiveCode.STRING:
        if reader.read(1) == 0:
            reader.skip(8 * reader.read(16))
    else:
        reader.skip(schema.windblown_save_patcher_primitive_width(descriptor.code))


def windblown_save_patcher_seek_field(
    reader: bits.BitReader,
    entry: schema.TypeEntry,
    type_table: dict[int, schema.TypeEntry],
    field_name: str,
) -> schema.Descriptor:
    """
    Skip to named field.

    >>> fields = (schema.Field("a", schema.Descriptor(5)), schema.Field("b", schema.Descriptor(2)))
    >>> struct_entry = schema.TypeEntry("S", schema.TypeKind.STRUCT, 0, fields)
    >>> reader = bits.BitReader(bytes(5))
    >>> windblown_save_patcher_seek_field(reader, struct_entry, {}, "b")
    Descriptor(code=2, element=None, key=None, length=0)
    >>> reader.position
    32
    """
    for field in entry.fields:
        if field.name == field_name:
            return field.descriptor
        windblown_save_patcher_skip_value(
            reader,
            field.descriptor,
            type_table,
        )
    raise errors.SaveFormatError(f"{entry.name} has no field {field_name}")


def windblown_save_patcher_enter_user_type(
    reader: bits.BitReader,
    descriptor: schema.Descriptor,
    type_table: dict[int, schema.TypeEntry],
) -> schema.TypeEntry:
    """
    Enter struct or class value.

    >>> type_table = {0: schema.TypeEntry("S", schema.TypeKind.STRUCT, 0, ())}
    >>> descriptor = schema.Descriptor(0x40)
    >>> windblown_save_patcher_enter_user_type(bits.BitReader(b""), descriptor, type_table)
    TypeEntry(name='S', kind=<TypeKind.STRUCT: 3>, underlying=0, fields=())
    """
    if descriptor.code & schema.USER_TYPE_FLAG == 0:
        raise errors.SaveFormatError(f"type code {descriptor.code} is not user type")
    entry = windblown_save_patcher_user_type(
        descriptor.code,
        type_table,
    )
    if entry.kind is schema.TypeKind.CLASS and reader.read(1) == 0:
        raise errors.SaveFormatError(f"{entry.name} value is null")
    return entry


def windblown_save_patcher_find_field_offset(
    reader: bits.BitReader,
    type_table: dict[int, schema.TypeEntry],
    field_path: tuple[str, ...],
) -> int:
    """
    Locate nested field data.

    >>> root_fields = (
    ...     schema.Field("a", schema.Descriptor(5)),
    ...     schema.Field("s", schema.Descriptor(0x40)),
    ... )
    >>> type_table = {
    ...     0: schema.TypeEntry("S", schema.TypeKind.STRUCT, 0, ()),
    ...     1: schema.TypeEntry("R", schema.TypeKind.CLASS, 0, root_fields),
    ... }
    >>> windblown_save_patcher_find_field_offset(bits.BitReader(bytes(8)), type_table, ("s",))
    32
    """
    if len(type_table) == 0:
        raise errors.SaveFormatError("save body holds no types")
    entry = type_table[max(type_table)]
    for field_name in field_path:
        descriptor = windblown_save_patcher_seek_field(
            reader,
            entry,
            type_table,
            field_name,
        )
        entry = windblown_save_patcher_enter_user_type(
            reader,
            descriptor,
            type_table,
        )
    return reader.position
