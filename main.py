#!/usr/bin/env python3
"""Copy the committed 1024x1024 entry.png into MAKEFUN_OUTPUT_DIR.

Standard library only. No network. Deterministic: the same source bytes are
written on every run.

The source is validated before copying: PNG signature, chunk CRCs, IHDR
geometry/format, IDAT decompression, exact scanline count and a clean IEND.
"""

import hashlib
import os
import struct
import sys
import zlib
from pathlib import Path

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
WIDTH = 1024
HEIGHT = 1024
LIMIT = 1048576
VALID_COLOR_TYPES = {2: 3, 6: 4}


def fail(message):
    print("main.py: " + message, file=sys.stderr)
    raise SystemExit(1)


def validate_png(data):
    if not data.startswith(PNG_SIGNATURE):
        fail("entry.png is not a PNG file")
    if len(data) > LIMIT:
        fail("entry.png is %d bytes, over the %d byte limit" % (len(data), LIMIT))

    pos = len(PNG_SIGNATURE)
    chunks = []
    idat = []
    while pos + 12 <= len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        kind = data[pos + 4:pos + 8]
        end = pos + 12 + length
        if end > len(data):
            fail("entry.png has a truncated %s chunk" % kind.decode("latin-1"))
        body = data[pos + 8:pos + 8 + length]
        expected_crc = struct.unpack(">I", data[pos + 8 + length:end])[0]
        actual_crc = zlib.crc32(kind + body) & 0xFFFFFFFF
        if actual_crc != expected_crc:
            fail("entry.png has a bad CRC in the %s chunk" % kind.decode("latin-1"))
        chunks.append((kind, body))
        if kind == b"IDAT":
            idat.append(body)
        if kind == b"IEND":
            break
        pos = end

    if not chunks or chunks[0][0] != b"IHDR":
        fail("entry.png does not start with IHDR")
    if chunks[-1][0] != b"IEND" or chunks[-1][1]:
        fail("entry.png does not end with a clean IEND")
    if pos + 12 + struct.unpack(">I", data[pos:pos + 4])[0] != len(data):
        fail("entry.png has trailing data after IEND")

    if len(chunks[0][1]) != 13:
        fail("entry.png has an invalid IHDR length")
    width, height, depth, color, comp, filt, interlace = struct.unpack(
        ">IIBBBBB", chunks[0][1]
    )
    if (width, height) != (WIDTH, HEIGHT):
        fail("entry.png is %dx%d, expected %dx%d" % (width, height, WIDTH, HEIGHT))
    if depth != 8 or color not in VALID_COLOR_TYPES or comp != 0 or filt != 0 or interlace != 0:
        fail("entry.png uses an unsupported PNG format")
    if not idat:
        fail("entry.png has no image data")

    try:
        raw = zlib.decompress(b"".join(idat))
    except zlib.error as exc:
        fail("entry.png image data is corrupt: %s" % exc)
    stride = 1 + width * VALID_COLOR_TYPES[color]
    if len(raw) != height * stride:
        fail("entry.png decompresses to the wrong size")
    return width, height


def main():
    root = Path(__file__).resolve().parent
    source = root / "entry.png"
    if not source.is_file():
        fail("missing %s" % source)

    data = source.read_bytes()
    width, height = validate_png(data)
    digest = hashlib.sha256(data).hexdigest()

    out_dir = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")).expanduser()
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        fail("cannot create %s: %s" % (out_dir, exc))
    if not out_dir.is_dir():
        fail("%s is not a directory" % out_dir)

    destination = out_dir / "entry.png"
    temporary = out_dir / ".entry.png.tmp"
    try:
        with open(temporary, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    except OSError as exc:
        try:
            temporary.unlink()
        except OSError:
            pass
        fail("cannot write %s: %s" % (destination, exc))

    print("entry.png %dx%d %d bytes sha256=%s -> %s" % (width, height, len(data), digest, destination))


if __name__ == "__main__":
    main()
