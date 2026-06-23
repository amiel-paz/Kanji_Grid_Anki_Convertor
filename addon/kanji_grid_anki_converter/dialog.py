from __future__ import annotations

from dataclasses import dataclass

from aqt.qt import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QVBoxLayout,
)
from aqt.utils import showCritical

from .duplicate import ConversionOptions, ConversionStats, build_kanji_grid_deck, default_output_deck_name


@dataclass(frozen=True)
class DeckChoice:
    id: int
    name: str


class KanjiGridDialog(QDialog):
    def __init__(self, parent) -> None:
        super().__init__(parent)
        self._mw = parent
        self._deck_choices = self._load_decks()

        self.setWindowTitle("Create Kanji Grid Deck")
        self.setMinimumWidth(520)
        self._auto_output_name = ""

        self.deck_combo = QComboBox(self)
        for choice in self._deck_choices:
            self.deck_combo.addItem(choice.name, choice.id)
        self.deck_combo.currentIndexChanged.connect(self._refresh_output_name)

        self.output_name = QLineEdit(self)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(self._accept_if_valid)
        button_box.rejected.connect(self.reject)

        form = QFormLayout()
        form.addRow("Source deck", self.deck_combo)
        form.addRow("Output deck", self.output_name)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(button_box)

        self._refresh_output_name()

    def options(self) -> ConversionOptions:
        source_name = self.deck_combo.currentText()
        return ConversionOptions(
            source_deck_name=source_name,
            output_deck_name=self.output_name.text().strip(),
        )

    def run_conversion(self) -> ConversionStats:
        return build_kanji_grid_deck(self._mw.col, self.options())

    def _load_decks(self) -> list[DeckChoice]:
        decks = self._mw.col.decks
        choices = []
        for deck in decks.all_names_and_ids():
            choices.append(DeckChoice(id=int(deck.id), name=str(deck.name)))
        return sorted(choices, key=lambda choice: choice.name.lower())

    def _refresh_output_name(self, *_ignored) -> None:
        source_deck_name = self.deck_combo.currentText()
        if not source_deck_name:
            return

        current_output_name = self.output_name.text().strip()
        if current_output_name and current_output_name != self._auto_output_name:
            return

        self._auto_output_name = default_output_deck_name(source_deck_name)
        self.output_name.setText(self._auto_output_name)

    def _accept_if_valid(self) -> None:
        options = self.options()
        if not options.output_deck_name:
            showCritical("Enter an output deck name.")
            return
        if options.output_deck_name == options.source_deck_name:
            showCritical("Choose a different output deck name so the source deck stays untouched.")
            return
        self.accept()
