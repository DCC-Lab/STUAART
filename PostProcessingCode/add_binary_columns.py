#!/usr/bin/env python3
"""
Add 24-bit binary representations of the HX711 raw counts as extra
columns to a STUAART CSV.

The firmware emits 7 columns:
    time(ms), reading 1, reading 2, reading 3, raw 1, raw 2, raw 3

This script appends 3 columns:
    bin 1, bin 2, bin 3

Each bin column is the 24-bit two's complement bit pattern of the
corresponding raw count. Useful for spotting HX711 corruption
signatures by eye (e.g. raw == -1 -> "111111111111111111111111",
raw == -8388608 -> "100000000000000000000000").

Usage:
    python add_binary_columns.py input.csv > output.csv
    cat input.csv | python add_binary_columns.py > output.csv
"""
from __future__ import annotations
import csv
import sys


def to_24bit_binary(raw_str: str) -> str:
    """24-bit two's complement of a signed int, as a 24-char string of 0/1."""
    return format(int(raw_str) & 0xFFFFFF, "024b")


def is_data_row(row: list[str]) -> bool:
    """A data row starts with an integer (the millis timestamp)."""
    try:
        int(row[0])
        return True
    except (ValueError, IndexError):
        return False


def main() -> int:
    src = open(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1] != "-" else sys.stdin
    reader = csv.reader(src)
    writer = csv.writer(sys.stdout)
    for row in reader:
        if not row:
            continue
        if is_data_row(row):
            try:
                bins = [to_24bit_binary(row[i]) for i in (4, 5, 6)]
            except (ValueError, IndexError):
                writer.writerow(row)
                continue
            writer.writerow(row + bins)
        else:
            writer.writerow(row + ["bin 1", "bin 2", "bin 3"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
