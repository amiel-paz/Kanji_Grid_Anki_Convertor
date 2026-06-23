import importlib.util
import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADDON_DIR = ROOT / "addon" / "kanji_grid_anki_converter"


class FakeSignal:
    def connect(self, callback):
        self.callback = callback

    def emit(self, *args):
        self.callback(*args)


class FakeComboBox:
    def __init__(self, parent=None):
        self.items = []
        self.current_index = 0
        self.currentIndexChanged = FakeSignal()

    def addItem(self, text, data):
        self.items.append((text, data))

    def currentText(self):
        return self.items[self.current_index][0] if self.items else ""

    def setCurrentIndex(self, index):
        self.current_index = index
        self.currentIndexChanged.emit(index)


class FakeDialog:
    def __init__(self, parent=None):
        self.parent = parent

    def setWindowTitle(self, title):
        self.title = title

    def setMinimumWidth(self, width):
        self.minimum_width = width

    def accept(self):
        self.accepted = True

    def reject(self):
        self.rejected = True


class FakeButtonBox:
    class StandardButton:
        Cancel = 1
        Ok = 2

    def __init__(self, buttons):
        self.buttons = buttons
        self.accepted = FakeSignal()
        self.rejected = FakeSignal()


class FakeFormLayout:
    def __init__(self):
        self.rows = []

    def addRow(self, label, widget):
        self.rows.append((label, widget))


class FakeLineEdit:
    def __init__(self, parent=None):
        self.value = ""

    def text(self):
        return self.value

    def setText(self, value):
        self.value = value


class FakeVBoxLayout:
    def __init__(self, parent=None):
        self.items = []

    def addLayout(self, layout):
        self.items.append(layout)

    def addWidget(self, widget):
        self.items.append(widget)


class FakeDeck:
    def __init__(self, deck_id, name):
        self.id = deck_id
        self.name = name


class FakeDeckManager:
    def all_names_and_ids(self):
        return [FakeDeck(2, "JLPT N2 単語"), FakeDeck(1, "Core")]


class FakeCollection:
    decks = FakeDeckManager()


class FakeMainWindow:
    col = FakeCollection()


def load_dialog_module():
    package_name = "kanji_grid_dialog_under_test"
    package_spec = importlib.util.spec_from_file_location(
        package_name,
        ADDON_DIR / "__init__.py",
        submodule_search_locations=[str(ADDON_DIR)],
    )
    package = importlib.util.module_from_spec(package_spec)
    sys.modules[package_name] = package

    aqt_module = types.ModuleType("aqt")
    qt_module = types.ModuleType("aqt.qt")
    utils_module = types.ModuleType("aqt.utils")

    qt_module.QComboBox = FakeComboBox
    qt_module.QDialog = FakeDialog
    qt_module.QDialogButtonBox = FakeButtonBox
    qt_module.QFormLayout = FakeFormLayout
    qt_module.QLineEdit = FakeLineEdit
    qt_module.QVBoxLayout = FakeVBoxLayout
    utils_module.showCritical = lambda message: None

    old_modules = {name: sys.modules.get(name) for name in ("aqt", "aqt.qt", "aqt.utils")}
    sys.modules["aqt"] = aqt_module
    sys.modules["aqt.qt"] = qt_module
    sys.modules["aqt.utils"] = utils_module

    try:
        spec = importlib.util.spec_from_file_location(
            f"{package_name}.dialog",
            ADDON_DIR / "dialog.py",
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[f"{package_name}.dialog"] = module
        spec.loader.exec_module(module)
        return module
    finally:
        for name, module in old_modules.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


class AddonDialogTests(unittest.TestCase):
    def test_dialog_constructs_without_field_picker_widgets(self):
        dialog_module = load_dialog_module()

        dialog = dialog_module.KanjiGridDialog(FakeMainWindow())
        options = dialog.options()

        self.assertEqual(options.source_deck_name, "Core")
        self.assertEqual(options.output_deck_name, "Core Kanji Grid")

    def test_output_name_auto_updates_until_user_customizes_it(self):
        dialog_module = load_dialog_module()

        dialog = dialog_module.KanjiGridDialog(FakeMainWindow())
        dialog.deck_combo.setCurrentIndex(1)

        self.assertEqual(dialog.options().source_deck_name, "JLPT N2 単語")
        self.assertEqual(dialog.options().output_deck_name, "JLPT N2 単語 Kanji Grid")

        dialog.output_name.setText("My custom output")
        dialog.deck_combo.setCurrentIndex(0)

        self.assertEqual(dialog.options().source_deck_name, "Core")
        self.assertEqual(dialog.options().output_deck_name, "My custom output")


if __name__ == "__main__":
    unittest.main()
