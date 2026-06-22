from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import json
import shutil
import sqlite3
import tempfile
import time
from zipfile import ZIP_DEFLATED, ZipFile

from .tiles import replace_kanji_with_tiles

FIELD_SEPARATOR = "\x1f"
COLLECTION_FILENAMES = ("collection.anki21", "collection.anki2")


@dataclass(frozen=True)
class DeckField:
    model_id: int
    model_name: str
    fields: tuple[str, ...]


@dataclass
class ConversionStats:
    notes_seen: int = 0
    notes_changed: int = 0
    fields_seen: int = 0
    fields_changed: int = 0
    replacements: int = 0
    kanji_counts: dict[str, int] = field(default_factory=dict)
    missing_field_names: tuple[str, ...] = ()

    def merge_kanji_counts(self, counts: dict[str, int]) -> None:
        for kanji, count in counts.items():
            self.kanji_counts[kanji] = self.kanji_counts.get(kanji, 0) + count


def default_output_path(input_path: Path) -> Path:
    return input_path.with_name(f"{input_path.stem}.kanji-grid{input_path.suffix}")


def list_deck_fields(input_path: str | Path) -> tuple[DeckField, ...]:
    input_path = Path(input_path)
    with tempfile.TemporaryDirectory() as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        collection_path = _extract_collection(input_path, temp_dir)
        with sqlite3.connect(collection_path) as connection:
            return tuple(_load_deck_fields(connection))


def convert_apkg(
    input_path: str | Path,
    output_path: str | Path | None = None,
    *,
    field_names: tuple[str, ...] | list[str] | None = None,
) -> ConversionStats:
    input_path = Path(input_path)
    if output_path is None:
        output_path = default_output_path(input_path)
    output_path = Path(output_path)

    if input_path.resolve() == output_path.resolve():
        raise ValueError("Output path must be different from input path.")

    selected_field_names = tuple(field_names or ())

    with tempfile.TemporaryDirectory() as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        extract_dir = temp_dir / "deck"
        extract_dir.mkdir()

        with ZipFile(input_path, "r") as archive:
            _extract_archive_safely(archive, extract_dir)

        collection_path = _find_collection_file(extract_dir)
        stats = _convert_collection(collection_path, selected_field_names)
        _write_apkg(extract_dir, output_path)

    return stats


def _extract_collection(input_path: Path, temp_dir: Path) -> Path:
    with ZipFile(input_path, "r") as archive:
        collection_name = _find_collection_name(archive.namelist())
        archive.extract(collection_name, temp_dir)
    return temp_dir / collection_name


def _find_collection_name(names: list[str]) -> str:
    for filename in COLLECTION_FILENAMES:
        if filename in names:
            return filename
    raise ValueError("No supported Anki collection file found in the .apkg.")


def _find_collection_file(extract_dir: Path) -> Path:
    for filename in COLLECTION_FILENAMES:
        candidate = extract_dir / filename
        if candidate.exists():
            return candidate
    raise ValueError("No supported Anki collection file found in the .apkg.")


def _load_deck_fields(connection: sqlite3.Connection) -> list[DeckField]:
    models = _load_models(connection)
    fields: list[DeckField] = []
    for model_id, model in sorted(models.items(), key=lambda item: item[1].get("name", "")):
        field_names = tuple(field["name"] for field in model.get("flds", []))
        fields.append(
            DeckField(
                model_id=int(model_id),
                model_name=model.get("name", str(model_id)),
                fields=field_names,
            )
        )
    return fields


def _convert_collection(collection_path: Path, selected_field_names: tuple[str, ...]) -> ConversionStats:
    stats = ConversionStats()

    with sqlite3.connect(collection_path) as connection:
        models = _load_models(connection)
        model_field_names = {
            int(model_id): tuple(field["name"] for field in model.get("flds", []))
            for model_id, model in models.items()
        }
        selected_lookup = set(selected_field_names)
        matched_field_names: set[str] = set()

        rows = connection.execute("SELECT id, mid, flds FROM notes").fetchall()
        now = int(time.time())

        for note_id, model_id, packed_fields in rows:
            stats.notes_seen += 1
            field_values = packed_fields.split(FIELD_SEPARATOR)
            field_names = model_field_names.get(int(model_id), ())
            changed = False

            for index, value in enumerate(field_values):
                field_name = field_names[index] if index < len(field_names) else f"Field {index + 1}"
                if selected_lookup and field_name not in selected_lookup:
                    continue

                if field_name in selected_lookup:
                    matched_field_names.add(field_name)

                stats.fields_seen += 1
                result = replace_kanji_with_tiles(value)
                if result.replacements == 0:
                    continue

                field_values[index] = result.text
                changed = True
                stats.fields_changed += 1
                stats.replacements += result.replacements
                stats.merge_kanji_counts(dict(result.kanji_counts))

            if changed:
                stats.notes_changed += 1
                connection.execute(
                    "UPDATE notes SET flds = ?, mod = ?, usn = -1 WHERE id = ?",
                    (FIELD_SEPARATOR.join(field_values), now, note_id),
                )

        try:
            connection.execute("UPDATE col SET mod = ?", (int(time.time() * 1000),))
        except sqlite3.OperationalError:
            pass

        connection.commit()

    if selected_lookup:
        missing = tuple(field_name for field_name in selected_field_names if field_name not in matched_field_names)
        stats.missing_field_names = missing

    return stats


def _load_models(connection: sqlite3.Connection) -> dict[str, dict]:
    row = connection.execute("SELECT models FROM col LIMIT 1").fetchone()
    if row is None:
        raise ValueError("The Anki collection has no model metadata.")
    return json.loads(row[0])


def _write_apkg(extract_dir: Path, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_output = output_path.with_suffix(f"{output_path.suffix}.tmp")
    if temp_output.exists():
        temp_output.unlink()

    with ZipFile(temp_output, "w", ZIP_DEFLATED) as archive:
        for path in sorted(extract_dir.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(extract_dir).as_posix())

    shutil.move(temp_output, output_path)


def _extract_archive_safely(archive: ZipFile, destination: Path) -> None:
    destination = destination.resolve()
    for member in archive.infolist():
        target = (destination / member.filename).resolve()
        if destination != target and destination not in target.parents:
            raise ValueError(f"Refusing to extract unsafe archive path: {member.filename}")
        archive.extract(member, destination)
