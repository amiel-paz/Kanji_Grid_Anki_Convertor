from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .tiles import contains_kanji, plain_text_for_matching, replace_kanji_with_tiles


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
    eligible_ordinals_by_note_id, all_ordinals_by_note_id, source_cards_by_note_id_and_ordinal = (
        _eligible_front_card_ordinals(collection, source_card_ids)
    )
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
        kept_target_cards = _remove_ineligible_generated_cards(collection, target_note, eligible_ordinals)
        for target_card in kept_target_cards:
            source_card = source_cards_by_note_id_and_ordinal.get((note_id, int(target_card.ord)))
            if source_card is not None:
                _copy_card_scheduling(source_card, target_card, output_deck_id)
                _save_card(collection, target_card)
        stats.cards_created += len(kept_target_cards)
        stats.notes_created += 1

    return stats


@dataclass
class ScheduleSyncStats:
    deck_pairs_seen: int = 0
    cards_seen: int = 0
    cards_updated: int = 0
    cards_unmatched: int = 0


def sync_kanji_grid_scheduling(collection: Any) -> ScheduleSyncStats:
    stats = ScheduleSyncStats()
    for source_deck_name, target_deck_name in _kanji_grid_deck_pairs(collection):
        stats.deck_pairs_seen += 1
        source_cards_by_key = _source_cards_by_matching_key(collection, source_deck_name)
        for target_card_id in _find_cards(collection, f'deck:"{target_deck_name}"'):
            stats.cards_seen += 1
            target_card = collection.get_card(target_card_id)
            target_key = _card_matching_key(target_card)
            matching_source_cards = source_cards_by_key.get(target_key)
            if not matching_source_cards:
                stats.cards_unmatched += 1
                continue

            source_card = matching_source_cards.pop(0)
            output_deck_id = int(target_card.did)
            _copy_card_scheduling(source_card, target_card, output_deck_id)
            _save_card(collection, target_card)
            stats.cards_updated += 1

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
) -> tuple[dict[int, set[int]], dict[int, set[int]], dict[tuple[int, int], Any]]:
    eligible_ordinals_by_note_id: dict[int, set[int]] = {}
    all_ordinals_by_note_id: dict[int, set[int]] = {}
    source_cards_by_note_id_and_ordinal: dict[tuple[int, int], Any] = {}

    for card_id in card_ids:
        card = collection.get_card(card_id)
        note_id = int(card.nid)
        ordinal = int(card.ord)
        all_ordinals_by_note_id.setdefault(note_id, set()).add(ordinal)
        if contains_kanji(card.question()):
            eligible_ordinals_by_note_id.setdefault(note_id, set()).add(ordinal)
            source_cards_by_note_id_and_ordinal[(note_id, ordinal)] = card

    return eligible_ordinals_by_note_id, all_ordinals_by_note_id, source_cards_by_note_id_and_ordinal


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


def _remove_ineligible_generated_cards(collection: Any, note: Any, eligible_ordinals: set[int]) -> list[Any]:
    created_card_ids = list(note.card_ids()) if hasattr(note, "card_ids") else []
    if not created_card_ids:
        return []

    card_ids_to_remove = []
    kept_cards = []
    for card_id in created_card_ids:
        card = collection.get_card(card_id)
        if int(card.ord) in eligible_ordinals:
            kept_cards.append(card)
        else:
            card_ids_to_remove.append(card_id)

    if card_ids_to_remove:
        collection.remove_cards_and_orphaned_notes(card_ids_to_remove)

    return kept_cards


def _copy_card_scheduling(source_card: Any, target_card: Any, target_deck_id: int) -> None:
    target_card.did = target_deck_id
    source_due = getattr(source_card, "due", 0)
    source_odue = getattr(source_card, "odue", 0)
    source_odid = getattr(source_card, "odid", 0)
    if source_odid and source_odue:
        source_due = source_odue

    for attribute in (
        "type",
        "queue",
        "ivl",
        "factor",
        "reps",
        "lapses",
        "left",
        "flags",
    ):
        if hasattr(source_card, attribute) and hasattr(target_card, attribute):
            setattr(target_card, attribute, getattr(source_card, attribute))

    if hasattr(target_card, "due"):
        target_card.due = source_due
    if hasattr(target_card, "odue"):
        target_card.odue = 0
    if hasattr(target_card, "odid"):
        target_card.odid = 0


def _save_card(collection: Any, card: Any) -> None:
    if hasattr(collection, "update_card"):
        try:
            collection.update_card(card)
            return
        except TypeError:
            collection.update_card(card, False)
            return
    if hasattr(card, "flush"):
        card.flush()


def _kanji_grid_deck_pairs(collection: Any) -> list[tuple[str, str]]:
    deck_names = _deck_names(collection)
    pairs = []
    for deck_name in sorted(deck_names):
        source_name = _source_deck_name_for_kanji_grid_deck(deck_name, deck_names)
        if source_name is not None:
            pairs.append((source_name, deck_name))
    return pairs


def _deck_names(collection: Any) -> set[str]:
    decks = collection.decks
    if hasattr(decks, "all_names_and_ids"):
        return {str(deck.name) for deck in decks.all_names_and_ids()}
    if hasattr(decks, "all_names"):
        return {str(deck_name) for deck_name in decks.all_names()}
    if hasattr(decks, "decks"):
        return {str(deck.get("name", "")) for deck in decks.decks.values()}
    raise RuntimeError("This Anki version does not expose a supported deck listing API.")


def _source_deck_name_for_kanji_grid_deck(deck_name: str, deck_names: set[str]) -> str | None:
    if deck_name.endswith("::Kanji Grid"):
        source_name = deck_name.removesuffix("::Kanji Grid")
        return source_name if source_name in deck_names else None

    if not deck_name.endswith(" Kanji Grid"):
        return None

    source_name = deck_name.removesuffix(" Kanji Grid")
    if source_name in deck_names:
        return source_name

    nested_source_name = source_name.replace(" - ", "::")
    if nested_source_name in deck_names:
        return nested_source_name

    return None


def _source_cards_by_matching_key(collection: Any, source_deck_name: str) -> dict[tuple[tuple[str, ...], int], list[Any]]:
    cards_by_key: dict[tuple[tuple[str, ...], int], list[Any]] = {}
    for source_card_id in _find_cards(collection, f'deck:"{source_deck_name}"'):
        source_card = collection.get_card(source_card_id)
        cards_by_key.setdefault(_card_matching_key(source_card), []).append(source_card)
    return cards_by_key


def _card_matching_key(card: Any) -> tuple[tuple[str, ...], int]:
    note = card.note()
    normalized_fields = tuple(plain_text_for_matching(str(note[field_name])) for field_name in note.keys())
    return normalized_fields, int(card.ord)
