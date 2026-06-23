from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .tiles import contains_mapped_kanji, replace_kanji_with_tiles


@dataclass(frozen=True)
class ConversionOptions:
    source_deck_name: str
    output_deck_name: str


@dataclass
class ConversionStats:
    output_deck_name: str = ""
    notes_seen: int = 0
    notes_created: int = 0
    cards_seen: int = 0
    cards_created: int = 0
    cards_skipped: int = 0
    fields_changed: int = 0
    replacements: int = 0


def build_kanji_grid_deck(collection: Any, options: ConversionOptions) -> ConversionStats:
    if options.source_deck_name == options.output_deck_name:
        raise ValueError("Output deck must be different from source deck.")

    output_deck_id, output_deck_name = _deck_id_with_filtered_deck_fallback(collection, options)
    source_card_ids = _find_cards(collection, f'deck:"{options.source_deck_name}"')
    eligible_ordinals_by_note_id, all_ordinals_by_note_id = _eligible_front_card_ordinals(collection, source_card_ids)
    stats = ConversionStats(
        output_deck_name=output_deck_name,
        notes_seen=len(all_ordinals_by_note_id),
        cards_seen=len(source_card_ids),
        cards_skipped=len(source_card_ids) - sum(len(ordinals) for ordinals in eligible_ordinals_by_note_id.values()),
    )

    for note_id, eligible_ordinals in eligible_ordinals_by_note_id.items():
        source_note = collection.get_note(note_id)
        target_note = collection.new_note(_note_type(source_note))

        for field_name in source_note.keys():
            value = source_note[field_name]
            result = replace_kanji_with_tiles(value)
            value = result.text
            if result.replacements:
                stats.fields_changed += 1
                stats.replacements += result.replacements
            target_note[field_name] = value

        target_note.tags = list(source_note.tags)
        if "kanji-grid" not in target_note.tags:
            target_note.tags.append("kanji-grid")

        _add_note(collection, target_note, output_deck_id)
        stats.cards_created += _remove_ineligible_generated_cards(collection, target_note, eligible_ordinals)
        stats.notes_created += 1

    return stats


def default_output_deck_name(source_deck_name: str) -> str:
    flattened_source_name = " - ".join(part.strip() for part in source_deck_name.split("::") if part.strip())
    return f"{flattened_source_name} Kanji Grid"


def _deck_id_with_filtered_deck_fallback(collection: Any, options: ConversionOptions) -> tuple[int, str]:
    try:
        return _deck_id(collection, options.output_deck_name), options.output_deck_name
    except Exception as error:
        if "filtered deck" not in str(error).lower():
            raise

        fallback_name = default_output_deck_name(options.source_deck_name)
        if fallback_name == options.output_deck_name:
            raise
        return _deck_id(collection, fallback_name), fallback_name


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


def _find_cards(collection: Any, query: str) -> list[int]:
    try:
        return list(collection.find_cards(query))
    except TypeError:
        return list(collection.find_cards(query, None, False))


def _eligible_front_card_ordinals(
    collection: Any,
    card_ids: list[int],
) -> tuple[dict[int, set[int]], dict[int, set[int]]]:
    eligible_ordinals_by_note_id: dict[int, set[int]] = {}
    all_ordinals_by_note_id: dict[int, set[int]] = {}

    for card_id in card_ids:
        card = collection.get_card(card_id)
        note_id = int(card.nid)
        ordinal = int(card.ord)
        all_ordinals_by_note_id.setdefault(note_id, set()).add(ordinal)
        if contains_mapped_kanji(card.question()):
            eligible_ordinals_by_note_id.setdefault(note_id, set()).add(ordinal)

    return eligible_ordinals_by_note_id, all_ordinals_by_note_id


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


def _remove_ineligible_generated_cards(collection: Any, note: Any, eligible_ordinals: set[int]) -> int:
    created_card_ids = list(note.card_ids()) if hasattr(note, "card_ids") else []
    if not created_card_ids:
        return len(eligible_ordinals)

    card_ids_to_remove = []
    kept_count = 0
    for card_id in created_card_ids:
        card = collection.get_card(card_id)
        if int(card.ord) in eligible_ordinals:
            kept_count += 1
        else:
            card_ids_to_remove.append(card_id)

    if card_ids_to_remove:
        collection.remove_cards_and_orphaned_notes(card_ids_to_remove)

    return kept_count
