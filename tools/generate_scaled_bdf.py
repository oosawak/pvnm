#!/usr/bin/env python3
"""Generate intermediate Biwidth BDF sizes from b24.bdf.

The generated fonts are comparison fonts for PVNM. They keep the source BDF's
logical glyph set and scale each bitmap to the requested pixel size.
"""
from __future__ import annotations

import argparse
from pathlib import Path


def _row_to_bits(row: str, width: int) -> list[int]:
    nbytes = (width + 7) // 8
    value = int(row.strip() or "0", 16)
    total_bits = nbytes * 8
    return [(value >> (total_bits - 1 - i)) & 1 for i in range(width)]


def _bits_to_row(bits: list[int]) -> str:
    nbytes = (len(bits) + 7) // 8
    total_bits = nbytes * 8
    value = 0
    for i, bit in enumerate(bits):
        if bit:
            value |= 1 << (total_bits - 1 - i)
    return f"{value:0{nbytes * 2}X}"


def _ceil_div(a: int, b: int) -> int:
    return (a + b - 1) // b


def _scale_bitmap(rows: list[str], sw: int, sh: int,
                  dw: int, dh: int) -> list[str]:
    src = [_row_to_bits(row, sw) for row in rows[:sh]]
    while len(src) < sh:
        src.append([0] * sw)

    dst_rows: list[str] = []
    for y in range(dh):
        sy0 = (y * sh) // dh
        sy1 = max(sy0 + 1, _ceil_div((y + 1) * sh, dh))
        out: list[int] = []
        for x in range(dw):
            sx0 = (x * sw) // dw
            sx1 = max(sx0 + 1, _ceil_div((x + 1) * sw, dw))
            on = 0
            for sy in range(min(sy1, sh)):
                if sy < sy0:
                    continue
                for sx in range(min(sx1, sw)):
                    if sx >= sx0 and src[sy][sx]:
                        on = 1
                        break
                if on:
                    break
            out.append(on)
        dst_rows.append(_bits_to_row(out))
    return dst_rows


def _advance_for(src_width: int, size: int) -> int:
    return size if src_width > 12 else max(1, size // 2)


def _update_header_line(line: str, size: int) -> str:
    if line.startswith("FONT "):
        return (f"FONT -Efont-Biwidth-Medium-R-Normal--{size}-"
                f"{size * 10}-75-75-P-{size * 5}-ISO10646-1")
    if line.startswith("SIZE "):
        return f"SIZE {size} 75 75"
    if line.startswith("FONTBOUNDINGBOX "):
        return f"FONTBOUNDINGBOX {size} {size} 0 -2"
    if line.startswith("PIXEL_SIZE "):
        return f"PIXEL_SIZE {size}"
    if line.startswith("POINT_SIZE "):
        return f"POINT_SIZE {size * 10}"
    if line.startswith("AVERAGE_WIDTH "):
        return f"AVERAGE_WIDTH {size * 5}"
    if line.startswith("FONT_ASCENT "):
        return f"FONT_ASCENT {max(1, size - 2)}"
    if line.startswith("FONT_DESCENT "):
        return "FONT_DESCENT 2"
    return line


def _convert_char(block: list[str], size: int) -> list[str]:
    try:
        dwidth_i = next(i for i, line in enumerate(block)
                        if line.startswith("DWIDTH "))
        bbx_i = next(i for i, line in enumerate(block)
                     if line.startswith("BBX "))
        bitmap_i = next(i for i, line in enumerate(block)
                        if line.startswith("BITMAP"))
        end_i = next(i for i, line in enumerate(block)
                     if line.startswith("ENDCHAR"))
    except StopIteration:
        return block

    dwidth_x = int(block[dwidth_i].split()[1])
    bbx_parts = block[bbx_i].split()
    sw = int(bbx_parts[1])
    sh = int(bbx_parts[2])

    dw = _advance_for(dwidth_x, size)
    bw = _advance_for(sw, size)
    bh = size
    rows = block[bitmap_i + 1:end_i]
    scaled = _scale_bitmap(rows, sw, sh, bw, bh)

    out = list(block[:bitmap_i + 1])
    out[dwidth_i] = f"DWIDTH {dw} 0"
    out[bbx_i] = f"BBX {bw} {bh} 0 -2"
    out.extend(scaled)
    out.extend(block[end_i:])
    return out


def generate(source: Path, dest: Path, size: int) -> None:
    lines = source.read_text(encoding="ascii").splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.startswith("STARTCHAR "):
            out.append(_update_header_line(line, size))
            i += 1
            continue

        block: list[str] = []
        while i < len(lines):
            block.append(lines[i])
            if lines[i].startswith("ENDCHAR"):
                i += 1
                break
            i += 1
        out.extend(_convert_char(block, size))

    dest.write_text("\n".join(out) + "\n", encoding="ascii")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("sizes", nargs="+", type=int)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    for size in args.sizes:
        dest = args.output_dir / f"b{size}.bdf"
        generate(args.source, dest, size)
        print(dest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
