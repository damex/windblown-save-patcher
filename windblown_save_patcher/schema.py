# Copyright (C) 2026 damex
# SPDX-License-Identifier: MIT
"""
Windblown save schema types and reader.
"""

import dataclasses
import enum

from windblown_save_patcher import bits, errors

USER_TYPE_FLAG = 0x40


class TypeKind(enum.IntEnum):
    """
    Schema type kind.

    >>> TypeKind(4).name
    'CLASS'
    """

    ENUM = 0b010
    STRUCT = 0b011
    CLASS = 0b100


class ContainerCode(enum.IntEnum):
    """
    Schema container type code.

    >>> ContainerCode(42).name
    'DICTIONARY'
    """

    ARRAY = 40
    LIST = 41
    DICTIONARY = 42
    SET = 43
    FIXED_ARRAY = 44


class PrimitiveCode(enum.IntEnum):
    """
    Schema primitive type code.

    >>> PrimitiveCode(11).name
    'STRING'
    """

    BOOLEAN = 1
    BYTE = 2
    INT32 = 5
    UINT32 = 6
    INT64 = 7
    UINT64 = 8
    UINT16 = 10
    STRING = 11
    ASSET_GUID = 12
    DOUBLE = 14


PRIMITIVE_WIDTHS = {
    PrimitiveCode.BOOLEAN: 1,
    PrimitiveCode.BYTE: 8,
    PrimitiveCode.INT32: 32,
    PrimitiveCode.UINT32: 32,
    PrimitiveCode.INT64: 64,
    PrimitiveCode.UINT64: 64,
    PrimitiveCode.UINT16: 16,
    PrimitiveCode.ASSET_GUID: 64,
    PrimitiveCode.DOUBLE: 64,
}


@dataclasses.dataclass(frozen=True, slots=True)
class Descriptor:
    """
    Field type descriptor.

    >>> Descriptor(code=5).code
    5
    """

    code: int
    element: "Descriptor | None" = None
    key: "Descriptor | None" = None
    length: int = 0


@dataclasses.dataclass(frozen=True, slots=True)
class Field:
    """
    Named schema field.

    >>> Field(name="flags", descriptor=Descriptor(code=2)).name
    'flags'
    """

    name: str
    descriptor: Descriptor


@dataclasses.dataclass(frozen=True, slots=True)
class TypeEntry:
    """
    Schema type definition.

    >>> TypeEntry(name="A", kind=TypeKind.ENUM, underlying=2, fields=()).underlying
    2
    """

    name: str
    kind: TypeKind
    underlying: int
    fields: tuple[Field, ...]


def windblown_save_patcher_type_kind(header: int) -> TypeKind:
    """
    Decode schema type kind.

    >>> windblown_save_patcher_type_kind(52)
    <TypeKind.CLASS: 4>
    """
    kind_value = header & 0b111
    if kind_value not in TypeKind:
        raise errors.SaveFormatError(f"unknown type kind {kind_value}")
    return TypeKind(kind_value)


def windblown_save_patcher_primitive_width(code: int) -> int:
    """
    Get primitive value width in bits.

    >>> windblown_save_patcher_primitive_width(5)
    32
    """
    if code not in PRIMITIVE_WIDTHS:
        raise errors.SaveFormatError(f"unknown primitive code {code}")
    return PRIMITIVE_WIDTHS[PrimitiveCode(code)]


def windblown_save_patcher_read_descriptor(reader: bits.BitReader) -> Descriptor:
    """
    Read field type descriptor.

    >>> reader = bits.BitReader(bytes((44, 8, 3, 0, 0, 0)))
    >>> descriptor = windblown_save_patcher_read_descriptor(reader)
    >>> descriptor.code, descriptor.element, descriptor.length
    (44, Descriptor(code=8, element=None, key=None, length=0), 3)
    """
    code = reader.read(8)
    match code:
        case ContainerCode.ARRAY | ContainerCode.LIST | ContainerCode.SET:
            return Descriptor(
                code=code,
                element=windblown_save_patcher_read_descriptor(reader),
            )
        case ContainerCode.DICTIONARY:
            value_descriptor = windblown_save_patcher_read_descriptor(reader)
            key_descriptor = windblown_save_patcher_read_descriptor(reader)
            return Descriptor(
                code=code,
                element=value_descriptor,
                key=key_descriptor,
            )
        case ContainerCode.FIXED_ARRAY:
            element_descriptor = windblown_save_patcher_read_descriptor(reader)
            return Descriptor(
                code=code,
                element=element_descriptor,
                length=reader.read(32),
            )
        case _:
            return Descriptor(code=code)


def windblown_save_patcher_read_field(reader: bits.BitReader) -> Field:
    """
    Read schema field.

    >>> value = (1 << 1) | (0x61 << 17) | (5 << 25)
    >>> reader = bits.BitReader(bits.windblown_save_patcher_pack(value, 5))
    >>> windblown_save_patcher_read_field(reader)
    Field(name='a', descriptor=Descriptor(code=5, element=None, key=None, length=0))
    """
    reader.skip(1)
    name = reader.read_string()
    return Field(
        name=name,
        descriptor=windblown_save_patcher_read_descriptor(reader),
    )


def windblown_save_patcher_read_type(reader: bits.BitReader) -> TypeEntry:
    """
    Read schema type definition.

    >>> value = 50 | (1 << 9) | (0x41 << 25) | (2 << 33)
    >>> reader = bits.BitReader(bits.windblown_save_patcher_pack(value, 6))
    >>> windblown_save_patcher_read_type(reader)
    TypeEntry(name='A', kind=<TypeKind.ENUM: 2>, underlying=2, fields=())
    """
    kind = windblown_save_patcher_type_kind(reader.read(9))
    name = reader.read_string()
    if kind is TypeKind.ENUM:
        return TypeEntry(
            name=name,
            kind=kind,
            underlying=reader.read(8),
            fields=(),
        )
    field_count = reader.read(32)
    return TypeEntry(
        name=name,
        kind=kind,
        underlying=0,
        fields=tuple(
            windblown_save_patcher_read_field(reader) for field_index in range(field_count)
        ),
    )


def windblown_save_patcher_read_schema(reader: bits.BitReader) -> dict[int, TypeEntry]:
    """
    Read block schema.

    >>> value = (1 << 48) | (50 << 64) | (1 << 73) | (0x41 << 89) | (2 << 97)
    >>> reader = bits.BitReader(bits.windblown_save_patcher_pack(value, 14))
    >>> windblown_save_patcher_read_schema(reader)
    {0: TypeEntry(name='A', kind=<TypeKind.ENUM: 2>, underlying=2, fields=())}
    """
    reader.skip(32 + 16)
    type_count = reader.read(16)
    return {
        type_index: windblown_save_patcher_read_type(reader) for type_index in range(type_count)
    }
