# Copyright (C) 2026 damex
# SPDX-License-Identifier: MIT
"""
Set MetaFlag bits in every save copy.
"""

import dataclasses
import io

from windblown_save_patcher import bits, compression, container, errors, flags


@dataclasses.dataclass(frozen=True, slots=True)
class PatchResult:
    """
    Patched save bytes and summary.

    >>> PatchResult(data=b"", missing_bits=(1,), copies=3, block_count=3, git_hash="").copies
    3
    """

    data: bytes
    missing_bits: tuple[int, ...]
    copies: int
    block_count: int
    git_hash: str


def windblown_save_patcher_patch_copies(
    data: bytes,
    mask: flags.FlagMask,
    flag_bits: list[int],
) -> tuple[bytes, list[int]]:
    """
    Set flag bits in every MetaFlagMask copy within data.

    >>> windblown_save_patcher_patch_copies(b"\\xa5", flags.FlagMask(0, 8, 0xA5), [1])
    (b'\\xa7', [0])
    """
    offsets = bits.windblown_save_patcher_find_bit_pattern(
        data,
        mask.value,
        mask.width,
    )
    patched_data = bits.windblown_save_patcher_set_bits(
        data,
        flags.windblown_save_patcher_flag_positions(
            offsets,
            flag_bits,
        ),
    )
    return patched_data, offsets


def windblown_save_patcher_patch_nested_block(
    block: bytes,
    mask: flags.FlagMask,
    flag_bits: list[int],
) -> tuple[bytes, int]:
    """
    Patch flag copies inside nested gzip block.

    >>> mask = flags.FlagMask(0, 8, 1)
    >>> patched_block, copies = windblown_save_patcher_patch_nested_block(bytes(16), mask, [0])
    >>> copies
    0
    """
    stream = io.BytesIO(block)
    stream.seek(4)
    frame_field = stream.read(4)
    nested_gzip = stream.read(bits.windblown_save_patcher_unpack(stream.read(4)))
    trailer = stream.read()
    if not nested_gzip.startswith(compression.GZIP_MAGIC):
        return block, 0
    inner = compression.windblown_save_patcher_decompress(nested_gzip)
    patched_inner, offsets = windblown_save_patcher_patch_copies(
        inner,
        mask,
        flag_bits,
    )
    if patched_inner == inner:
        return block, len(offsets)
    patched_gzip = compression.windblown_save_patcher_compress(patched_inner)
    nested_length = bits.windblown_save_patcher_pack_u32(len(patched_gzip))
    payload = frame_field + nested_length + patched_gzip + trailer
    return bits.windblown_save_patcher_pack_u32(len(payload)) + payload, len(offsets)


def windblown_save_patcher_apply_flags(
    body: bytes,
    mask: flags.FlagMask,
    flag_bits: list[int],
) -> tuple[bytes, int, int]:
    """
    Set flag bits in every MetaFlagMask copy, count copies and blocks.

    >>> body = b"\\x04\\x00\\x00\\x00\\xa5\\x00\\x00\\x00"
    >>> windblown_save_patcher_apply_flags(body, flags.FlagMask(32, 8, 0xA5), [1])
    (b'\\x04\\x00\\x00\\x00\\xa7\\x00\\x00\\x00', 1, 1)
    """
    oversized_bits = [flag_bit for flag_bit in flag_bits if flag_bit >= mask.width]
    if len(oversized_bits) > 0:
        raise errors.SaveFormatError(f"flag bits {oversized_bits} exceed mask width {mask.width}")
    patched_body, offsets = windblown_save_patcher_patch_copies(
        body,
        mask,
        flag_bits,
    )
    if mask.offset not in offsets:
        raise errors.SaveFormatError("pattern search missed save meta flags")
    blocks: list[bytes] = []
    copies = len(offsets)
    for block in container.windblown_save_patcher_split_blocks(patched_body):
        patched_block, nested_copies = windblown_save_patcher_patch_nested_block(
            block,
            mask,
            flag_bits,
        )
        blocks.append(patched_block)
        copies += nested_copies
    return b"".join(blocks), copies, len(blocks)


def windblown_save_patcher_patch_save(data: bytes, flag_bits: list[int]) -> PatchResult:
    """
    Set missing flag bits in save bytes.

    >>> windblown_save_patcher_patch_save(b"", [1])
    Traceback (most recent call last):
    windblown_save_patcher.errors.SaveFormatError: save lacks MTWB magic
    """
    save_container = container.windblown_save_patcher_read_container(data)
    body = compression.windblown_save_patcher_decompress(save_container.body_gzip)
    mask = flags.windblown_save_patcher_locate_flags(body)
    missing_bits = [flag_bit for flag_bit in flag_bits if (mask.value >> flag_bit) & 1 == 0]
    patched_body, copies, block_count = windblown_save_patcher_apply_flags(
        body,
        mask,
        missing_bits,
    )
    if len(missing_bits) == 0:
        return PatchResult(
            data=data,
            missing_bits=(),
            copies=copies,
            block_count=block_count,
            git_hash=save_container.git_hash.hex(),
        )
    patched_data = container.windblown_save_patcher_build_container(
        dataclasses.replace(
            save_container,
            body_gzip=compression.windblown_save_patcher_compress(patched_body),
        )
    )
    patched_container = container.windblown_save_patcher_read_container(patched_data)
    patched_mask = flags.windblown_save_patcher_locate_flags(
        compression.windblown_save_patcher_decompress(patched_container.body_gzip)
    )
    if any((patched_mask.value >> flag_bit) & 1 == 0 for flag_bit in flag_bits):
        raise errors.SaveFormatError("patched save lost requested flags")
    return PatchResult(
        data=patched_data,
        missing_bits=tuple(missing_bits),
        copies=copies,
        block_count=block_count,
        git_hash=save_container.git_hash.hex(),
    )
