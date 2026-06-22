from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .anki import convert_apkg, default_output_path, list_deck_fields


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="kanji-grid-anki",
        description="Convert kanji in an Anki .apkg deck into Kanji Grid tile HTML.",
    )
    parser.add_argument("input", type=Path, help="Input .apkg deck")
    parser.add_argument("-o", "--output", type=Path, help="Output .apkg path")
    parser.add_argument(
        "--field",
        action="append",
        default=[],
        help="Note field name to convert. Repeat to convert multiple fields. Defaults to all fields.",
    )
    parser.add_argument(
        "--list-fields",
        action="store_true",
        help="List note models and fields in the input deck without converting it.",
    )

    args = parser.parse_args(argv)

    try:
        if args.list_fields:
            for deck_field in list_deck_fields(args.input):
                field_list = ", ".join(deck_field.fields) if deck_field.fields else "(no fields)"
                print(f"{deck_field.model_name} [{deck_field.model_id}]: {field_list}")
            return 0

        output_path = args.output or default_output_path(args.input)
        stats = convert_apkg(args.input, output_path, field_names=tuple(args.field))

    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(f"Wrote {output_path}")
    print(f"Notes changed: {stats.notes_changed}/{stats.notes_seen}")
    print(f"Fields changed: {stats.fields_changed}/{stats.fields_seen}")
    print(f"Kanji replacements: {stats.replacements}")

    if stats.missing_field_names:
        missing = ", ".join(stats.missing_field_names)
        print(f"Warning: requested field name(s) not found: {missing}", file=sys.stderr)

    return 0
