from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .tiles import replace_kanji_with_tiles


@dataclass(frozen=True)
class ConversionOptions:
    source_deck_name: str
    output_deck_name: str
    selected_fields: tuple[str, ...]


@dataclass
class ConversionStats:
    notes_seen: int = 0
    notes_created: int = 0
    fields_changed: int = 0
    replacements: int = 0


def build_kanji_grid_deck(collection: Any, options: ConversionOptions) -> ConversionStats:
    if options.source_deck_name == options.output_deck_name:
        raise ValueError("Output deck must be different from source deck.")
    if not options.selected_fields:
        raise ValueError("Select at least one field to convert.")

    output_deck_id = _deck_id(collection, options.output_deck_name)
    source_note_ids = collection.find_notes(f'deck:"{options.source_deck_name}"')
    selected_fields = set(options.selected_fields)
    stats = ConversionStats(notes_seen=len(source_note_ids))

    for note_id in source_note_ids:
        source_note = collection.get_note(note_id)
        target_note = collection.new_note(_note_type(source_note))
        note_changed = False

        for field_name in source_note.keys():
            value = source_note[field_name]
            if field_name in selected_fields:
                result = replace_kanji_with_tiles(value)
                value = result.text
                if result.replacements:
                    note_changed = True
                    stats.fields_changed += 1
                    stats.replacements += result.replacements
            target_note[field_name] = value

        target_note.tags = list(source_note.tags)
        if "kanji-grid" not in target_note.tags:
            target_note.tags.append("kanji-grid")
        if not note_changed and "kanji-grid-no-mapped-kanji" not in target_note.tags:
            target_note.tags.append("kanji-grid-no-mapped-kanji")

        _add_note(collection, target_note, output_deck_id)
        stats.notes_created += 1

    return stats


def _deck_id(collection: Any, deck_name: str) -> int:
    decks = collection.decks
    if hasattr(decks, "id"):
        return int(decks.id(deck_name))

    if hasattr(decks, "id_for_name"):
        deck_id = decks.id_for_name(deck_name)
        if deck_id is not None:
            return int(deck_id)

    if hasattr(decks, "add_normal_deck_with_name"):
        result = decks.add_normal_deck_with_name(deck_name)
        return int(getattr(result, "id", result))

    if hasattr(decks, "new_deck") and hasattr(decks, "add_deck"):
        deck = decks.new_deck()
        deck.name = deck_name
        result = decks.add_deck(deck)
        return int(getattr(result, "id", deck.id))

    raise RuntimeError("This Anki version does not expose a supported deck creation API.")


def _note_type(note: Any) -> Any:
    if hasattr(note, "note_type"):
        return note.note_type()
    return note.model()


def _add_note(collection: Any, note: Any, deck_id: int) -> None:
    try:
        collection.add_note(note, deck_id)
    except TypeError:
        collection.decks.select(deck_id)
        collection.add_note(note)
