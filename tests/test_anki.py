import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from kanji_grid_anki_converter.anki import FIELD_SEPARATOR, convert_apkg, list_deck_fields


class AnkiConversionTests(unittest.TestCase):
    def test_converts_selected_fields_inside_apkg_copy(self):
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            input_path = temp_dir / "input.apkg"
            output_path = temp_dir / "output.apkg"
            self._write_apkg(input_path)

            stats = convert_apkg(input_path, output_path, field_names=("Expression",))

            self.assertEqual(stats.notes_seen, 1)
            self.assertEqual(stats.notes_changed, 1)
            self.assertEqual(stats.fields_seen, 1)
            self.assertEqual(stats.fields_changed, 1)
            self.assertEqual(stats.replacements, 2)

            fields = self._read_note_fields(output_path)
            self.assertIn("kanji-grid-tile", fields[0])
            self.assertIn("[かんじ]", fields[0])
            self.assertEqual(fields[1], "Back 愛")

            with ZipFile(output_path, "r") as archive:
                self.assertIn("media", archive.namelist())
                self.assertIn("0", archive.namelist())

    def test_lists_model_fields(self):
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            input_path = temp_dir / "input.apkg"
            self._write_apkg(input_path)

            [deck_fields] = list_deck_fields(input_path)

            self.assertEqual(deck_fields.model_name, "Japanese")
            self.assertEqual(deck_fields.fields, ("Expression", "Meaning"))

    def _write_apkg(self, output_path: Path) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            collection_path = temp_dir / "collection.anki2"
            self._write_collection(collection_path)
            (temp_dir / "media").write_text(json.dumps({"0": "sound.mp3"}), encoding="utf-8")
            (temp_dir / "0").write_bytes(b"fake media")

            with ZipFile(output_path, "w") as archive:
                archive.write(collection_path, "collection.anki2")
                archive.write(temp_dir / "media", "media")
                archive.write(temp_dir / "0", "0")

    def _write_collection(self, collection_path: Path) -> None:
        model = {
            "1001": {
                "name": "Japanese",
                "flds": [{"name": "Expression"}, {"name": "Meaning"}],
            }
        }
        fields = FIELD_SEPARATOR.join(("漢字[かんじ]", "Back 愛"))

        with sqlite3.connect(collection_path) as connection:
            connection.execute("CREATE TABLE col (models TEXT NOT NULL, mod INTEGER NOT NULL)")
            connection.execute(
                "CREATE TABLE notes (id INTEGER PRIMARY KEY, mid INTEGER NOT NULL, flds TEXT NOT NULL, mod INTEGER NOT NULL, usn INTEGER NOT NULL, sfld TEXT)"
            )
            connection.execute("INSERT INTO col (models, mod) VALUES (?, 0)", (json.dumps(model),))
            connection.execute(
                "INSERT INTO notes (id, mid, flds, mod, usn, sfld) VALUES (1, 1001, ?, 0, 0, ?)",
                (fields, "漢字"),
            )
            connection.commit()

    def _read_note_fields(self, apkg_path: Path) -> list[str]:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            with ZipFile(apkg_path, "r") as archive:
                archive.extract("collection.anki2", temp_dir)
            with sqlite3.connect(temp_dir / "collection.anki2") as connection:
                [packed_fields] = connection.execute("SELECT flds FROM notes").fetchone()
            return packed_fields.split(FIELD_SEPARATOR)


if __name__ == "__main__":
    unittest.main()
