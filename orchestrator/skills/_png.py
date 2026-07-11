"""Tiny dependency-free PNG writer, used by FakeImageSkill for GPU-free runs."""

from __future__ import annotations

import struct
import zlib


def _chunk(tag: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + tag
        + data
        + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    )


def solid_png(r: int, g: int, b: int, size: int = 8) -> bytes:
    """Return bytes of a valid ``size`` x ``size`` solid-colour RGB PNG."""
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)  # 8-bit RGB
    row = b"\x00" + bytes([r, g, b]) * size  # filter byte + pixels
    raw = row * size
    idat = zlib.compress(raw, 9)
    return sig + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", idat) + _chunk(b"IEND", b"")
