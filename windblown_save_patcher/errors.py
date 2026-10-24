# Copyright (C) 2026 damex
# SPDX-License-Identifier: MIT
"""
Errors raised by Windblown save patcher.
"""


class SaveFormatError(Exception):
    """
    Save layout differs from expected.

    >>> str(SaveFormatError("bad magic"))
    'bad magic'
    """


class ConfigurationError(Exception):
    """
    Configuration content is invalid.

    >>> str(ConfigurationError("missing saves"))
    'missing saves'
    """
