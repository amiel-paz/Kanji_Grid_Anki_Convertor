from __future__ import annotations

from aqt import mw
from aqt.qt import QAction
from aqt.utils import qconnect, showCritical, showInfo, tooltip

from .dialog import KanjiGridDialog


def open_converter_dialog() -> None:
    if mw.col is None:
        showCritical("Open an Anki collection before running Kanji Grid conversion.")
        return

    dialog = KanjiGridDialog(mw)
    if not dialog.exec():
        return

    options = dialog.options()

    try:
        stats = dialog.run_conversion()
    except Exception as error:
        showCritical(f"Kanji Grid conversion failed:\n\n{error}")
        return

    mw.reset()
    tooltip("Kanji Grid deck created")
    showInfo(
        "Kanji Grid deck created.\n\n"
        f"Output deck: {options.output_deck_name}\n"
        f"Notes created: {stats.notes_created}\n"
        f"Fields changed: {stats.fields_changed}\n"
        f"Kanji replacements: {stats.replacements}"
    )


action = QAction("Create Kanji Grid Deck...", mw)
qconnect(action.triggered, open_converter_dialog)
mw.form.menuTools.addAction(action)
