import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADDON_DIR = ROOT / "addon" / "kanji_grid_anki_converter"


def load_addon_duplicate_module():
    package_name = "kanji_grid_addon_under_test"
    package_spec = importlib.util.spec_from_file_location(
        package_name,
        ADDON_DIR / "__init__.py",
        submodule_search_locations=[str(ADDON_DIR)],
    )
    package = importlib.util.module_from_spec(package_spec)
    sys.modules[package_name] = package

    for module_name in ("tiles", "duplicate"):
        spec = importlib.util.spec_from_file_location(
            f"{package_name}.{module_name}",
            ADDON_DIR / f"{module_name}.py",
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[f"{package_name}.{module_name}"] = module
        spec.loader.exec_module(module)

    return sys.modules[f"{package_name}.duplicate"]


duplicate = load_addon_duplicate_module()


class FakeNote:
    def __init__(self, fields, tags=None):
        self._fields = dict(fields)
        self.tags = list(tags or [])

    def note_type(self):
        return tuple(self._fields.keys())

    def keys(self):
        return list(self._fields.keys())

    def __getitem__(self, name):
        return self._fields[name]

    def __setitem__(self, name, value):
        self._fields[name] = value


class FakeDecks:
    def __init__(self):
        self.created = {}

    def id_for_name(self, name):
        deck_id = len(self.created) + 100
        return self.created.setdefault(name, deck_id)


class FakeFilteredDecks(FakeDecks):
    def id_for_name(self, name):
        if "::" in name:
            raise RuntimeError("Filtered decks can not have child decks.")
        return super().id_for_name(name)


class FakeCollection:
    def __init__(self):
        self.decks = FakeDecks()
        self.source_notes = {
            1: FakeNote({"Expression": "漢字[かんじ]", "Meaning": "愛"}, ["source-tag"]),
            2: FakeNote({"Expression": "かな", "Meaning": "kana"}, []),
        }
        self.created_notes = []

    def find_notes(self, query):
        self.query = query
        return list(self.source_notes.keys())

    def get_note(self, note_id):
        return self.source_notes[note_id]

    def new_note(self, note_type):
        return FakeNote({field_name: "" for field_name in note_type})

    def add_note(self, note, deck_id):
        self.created_notes.append((deck_id, note))


class FakeFilteredCollection(FakeCollection):
    def __init__(self):
        super().__init__()
        self.decks = FakeFilteredDecks()


class AddonDuplicateTests(unittest.TestCase):
    def test_builds_output_deck_with_transformed_duplicate_notes(self):
        collection = FakeCollection()
        options = duplicate.ConversionOptions(
            source_deck_name="Japanese",
            output_deck_name="Japanese::Kanji Grid",
        )

        stats = duplicate.build_kanji_grid_deck(collection, options)

        self.assertEqual(stats.notes_seen, 2)
        self.assertEqual(stats.notes_created, 2)
        self.assertEqual(stats.output_deck_name, "Japanese::Kanji Grid")
        self.assertEqual(stats.fields_changed, 2)
        self.assertEqual(stats.replacements, 3)
        self.assertEqual(collection.query, 'deck:"Japanese"')
        self.assertEqual(collection.decks.created["Japanese::Kanji Grid"], 100)

        first_note = collection.created_notes[0][1]
        self.assertIn("kanji-grid-tile", first_note["Expression"])
        self.assertIn("[かんじ]", first_note["Expression"])
        self.assertIn("kanji-grid-tile", first_note["Meaning"])
        self.assertIn("source-tag", first_note.tags)
        self.assertIn("kanji-grid", first_note.tags)

        second_note = collection.created_notes[1][1]
        self.assertEqual(second_note["Expression"], "かな")
        self.assertIn("kanji-grid-no-mapped-kanji", second_note.tags)

    def test_rejects_overwriting_source_deck(self):
        with self.assertRaises(ValueError):
            duplicate.build_kanji_grid_deck(
                FakeCollection(),
                duplicate.ConversionOptions(
                    source_deck_name="Japanese",
                    output_deck_name="Japanese",
                ),
            )

    def test_falls_back_to_top_level_output_when_filtered_parent_rejects_child_deck(self):
        collection = FakeFilteredCollection()

        stats = duplicate.build_kanji_grid_deck(
            collection,
            duplicate.ConversionOptions(
                source_deck_name="Pass JLPT N3",
                output_deck_name="Pass JLPT N3::Kanji Grid",
            ),
        )

        self.assertEqual(stats.notes_created, 2)
        self.assertEqual(stats.output_deck_name, "Pass JLPT N3 Kanji Grid")
        self.assertIn("Pass JLPT N3 Kanji Grid", collection.decks.created)

    def test_default_output_deck_name_is_top_level(self):
        self.assertEqual(
            duplicate.default_output_deck_name("Parent::Child"),
            "Parent - Child Kanji Grid",
        )


if __name__ == "__main__":
    unittest.main()
