from __future__ import annotations

from dataclasses import dataclass

from aqt.qt import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    Qt,
)
from aqt.utils import showCritical

from .duplicate import ConversionOptions, ConversionStats, build_kanji_grid_deck


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

        self.deck_combo = QComboBox(self)
        for choice in self._deck_choices:
            self.deck_combo.addItem(choice.name, choice.id)
        self.deck_combo.currentIndexChanged.connect(self._refresh_fields)

        self.output_name = QLineEdit(self)
        self.field_list = QListWidget(self)
        self.field_list.setMinimumHeight(180)

        self.select_all = QCheckBox("Select all fields", self)
        self.select_all.stateChanged.connect(self._toggle_all_fields)

        refresh_button = QPushButton("Refresh Fields", self)
        refresh_button.clicked.connect(self._refresh_fields)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(self._accept_if_valid)
        button_box.rejected.connect(self.reject)

        form = QFormLayout()
        form.addRow("Source deck", self.deck_combo)
        form.addRow("Output deck", self.output_name)

        controls = QHBoxLayout()
        controls.addWidget(self.select_all)
        controls.addStretch(1)
        controls.addWidget(refresh_button)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(QLabel("Fields to convert"))
        layout.addWidget(self.field_list)
        layout.addLayout(controls)
        layout.addWidget(button_box)

        self._refresh_fields()

    def options(self) -> ConversionOptions:
        source_name = self.deck_combo.currentText()
        selected_fields = []
        for index in range(self.field_list.count()):
            item = self.field_list.item(index)
            if item.checkState() == Qt.CheckState.Checked:
                selected_fields.append(item.text())

        return ConversionOptions(
            source_deck_name=source_name,
            output_deck_name=self.output_name.text().strip(),
            selected_fields=tuple(selected_fields),
        )

    def run_conversion(self) -> ConversionStats:
        return build_kanji_grid_deck(self._mw.col, self.options())

    def _load_decks(self) -> list[DeckChoice]:
        decks = self._mw.col.decks
        choices = []
        for deck in decks.all_names_and_ids():
            choices.append(DeckChoice(id=int(deck.id), name=str(deck.name)))
        return sorted(choices, key=lambda choice: choice.name.lower())

    def _refresh_fields(self) -> None:
        source_deck_name = self.deck_combo.currentText()
        if not source_deck_name:
            return

        if not self.output_name.text().strip():
            self.output_name.setText(f"{source_deck_name}::Kanji Grid")

        field_names = self._field_names_for_deck(source_deck_name)
        self.field_list.clear()
        for field_name in field_names:
            item = QListWidgetItem(field_name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if self._looks_like_main_field(field_name) else Qt.CheckState.Unchecked)
            self.field_list.addItem(item)

        if self.field_list.count() == 0:
            self.field_list.addItem("No notes found in this deck")
            self.field_list.item(0).setFlags(Qt.ItemFlag.NoItemFlags)

    def _field_names_for_deck(self, deck_name: str) -> list[str]:
        note_ids = self._mw.col.find_notes(f'deck:"{deck_name}"')
        ordered_fields: list[str] = []
        seen = set()

        for note_id in note_ids[:500]:
            note = self._mw.col.get_note(note_id)
            for field_name in note.keys():
                if field_name not in seen:
                    ordered_fields.append(field_name)
                    seen.add(field_name)

        return ordered_fields

    def _toggle_all_fields(self) -> None:
        state = Qt.CheckState.Checked if self.select_all.isChecked() else Qt.CheckState.Unchecked
        for index in range(self.field_list.count()):
            item = self.field_list.item(index)
            if item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                item.setCheckState(state)

    def _accept_if_valid(self) -> None:
        options = self.options()
        if not options.output_deck_name:
            showCritical("Enter an output deck name.")
            return
        if options.output_deck_name == options.source_deck_name:
            showCritical("Choose a different output deck name so the source deck stays untouched.")
            return
        if not options.selected_fields:
            showCritical("Select at least one field to convert.")
            return
        self.accept()

    def _looks_like_main_field(self, field_name: str) -> bool:
        normalized = field_name.lower()
        return normalized in {
            "expression",
            "sentence",
            "japanese",
            "word",
            "vocab",
            "vocabulary",
            "front",
            "term",
        }
