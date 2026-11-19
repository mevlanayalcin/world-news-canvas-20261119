#!/usr/bin/env python3
"""Copy the committed 1024x1024 entry.png into MAKEFUN_OUTPUT_DIR.

Standard library only. No network. Deterministic: the same source bytes are
written on every run.

The source may be a PNG or a JPEG: the gate tells them apart by the first
bytes and keeps the name entry.png either way. Both are validated before
copying, so a truncated or corrupt file never reaches the output:

  PNG  - signature, chunk CRCs, IHDR geometry/format, IDAT decompression,
         exact scanline count and a clean IEND with no trailing data.
  JPEG - SOI, every segment length, the frame header's geometry, at least one
         scan, entropy-coded data walked to its end marker, and a clean EOI
         with no trailing data.
"""

import hashlib
import os
import struct
import sys
import zlib
from pathlib import Path

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
JPEG_SOI = b"\xff\xd8"
JPEG_EOI = b"\xff\xd9"
WIDTH = 1024
HEIGHT = 1024
LIMIT = 1048576
VALID_COLOR_TYPES = {2: 3, 6: 4}
SOF_MARKERS = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
               0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}


def fail(message):
    print("main.py: " + message, file=sys.stderr)
    raise SystemExit(1)


def validate_png(data):
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
    return "PNG", width, height


def jpeg_segment(data, pos):
    """Read one marker at pos (which must point at 0xFF); return marker and next pos."""
    if data[pos] != 0xFF:
        fail("entry.png has a broken JPEG marker at byte %d" % pos)
    while pos < len(data) and data[pos] == 0xFF:
        pos += 1
    if pos >= len(data):
        fail("entry.png ends inside a JPEG marker")
    marker = data[pos]
    return marker, pos + 1


def validate_jpeg(data):
    if len(data) > LIMIT:
        fail("entry.png is %d bytes, over the %d byte limit" % (len(data), LIMIT))
    if not data.endswith(JPEG_EOI):
        fail("entry.png does not end with a JPEG end-of-image marker")

    size = len(data)
    pos = 2
    width = height = None
    frames = 0
    scans = 0
    while True:
        marker, pos = jpeg_segment(data, pos)
        if marker == 0xD9:
            break
        if marker == 0xD8:
            fail("entry.png has an unexpected second JPEG start marker")
        if marker == 0x01 or 0xD0 <= marker <= 0xD7:
            continue
        if pos + 2 > size:
            fail("entry.png is truncated inside a JPEG segment")
        length = struct.unpack(">H", data[pos:pos + 2])[0]
        if length < 2 or pos + length > size:
            fail("entry.png has an invalid JPEG segment length")
        body = data[pos + 2:pos + length]
        if marker in SOF_MARKERS:
            if len(body) < 6:
                fail("entry.png has a short JPEG frame header")
            height, width = struct.unpack(">HH", body[1:5])
            components = body[5]
            if components != 3:
                fail("entry.png is not a three-component JPEG")
            if len(body) != 6 + 3 * components:
                fail("entry.png has a malformed JPEG frame header")
            frames += 1
        if marker == 0xDA:
            if width is None:
                fail("entry.png has JPEG scan data before its frame header")
            scan_components = body[0] if body else 0
            if scan_components == 0 or len(body) != 4 + 2 * scan_components:
                fail("entry.png has a malformed JPEG scan header")
            scans += 1
            pos += length
            while True:
                if pos + 1 >= size:
                    fail("entry.png JPEG scan data is truncated")
                if data[pos] != 0xFF:
                    pos += 1
                    continue
                following = data[pos + 1]
                if following == 0x00 or 0xD0 <= following <= 0xD7:
                    pos += 2
                    continue
                break
            continue
        pos += length

    if pos != size:
        fail("entry.png has trailing data after the JPEG end marker")
    if not frames or width is None:
        fail("entry.png has no JPEG frame header")
    if not scans:
        fail("entry.png has no JPEG image data")
    if (width, height) != (WIDTH, HEIGHT):
        fail("entry.png is %dx%d, expected %dx%d" % (width, height, WIDTH, HEIGHT))
    return "JPEG", width, height


def validate(data):
    if data.startswith(PNG_SIGNATURE):
        return validate_png(data)
    if data.startswith(JPEG_SOI):
        return validate_jpeg(data)
    fail("entry.png is neither a PNG nor a JPEG file")


def main():
    root = Path(__file__).resolve().parent
    source = root / "entry.png"
    if not source.is_file():
        fail("missing %s" % source)

    data = source.read_bytes()
    kind, width, height = validate(data)
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

    print("entry.png %s %dx%d %d bytes sha256=%s -> %s"
          % (kind, width, height, len(data), digest, destination))


if __name__ == "__main__":
    main()
