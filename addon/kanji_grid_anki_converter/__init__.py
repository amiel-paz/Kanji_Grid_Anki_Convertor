from __future__ import annotations

import traceback

from aqt import mw
from aqt.qt import QAction
from aqt.utils import qconnect, showCritical, showInfo, tooltip

from pathlib import Path


def open_converter_dialog() -> None:
    try:
        if mw.col is None:
            showCritical("Open an Anki collection before running Kanji Grid conversion.")
            return

        from .dialog import KanjiGridDialog

        dialog = KanjiGridDialog(mw)
        dialog_result = dialog.exec() if hasattr(dialog, "exec") else dialog.exec_()
        if not dialog_result:
            return

        options = dialog.options()

        stats = dialog.run_conversion()

        mw.reset()
        tooltip("Kanji Grid deck created")
        showInfo(
            "Kanji Grid deck created.\n\n"
            f"Output deck: {options.output_deck_name}\n"
            f"Notes created: {stats.notes_created}\n"
            f"Fields changed: {stats.fields_changed}\n"
            f"Kanji replacements: {stats.replacements}"
        )
    except Exception:
        details = traceback.format_exc()
        _write_last_error(details)
        showCritical(f"Kanji Grid conversion failed:\n\n{details}")


def _write_last_error(details: str) -> None:
    try:
        Path(__file__).with_name("last_error.txt").write_text(details, encoding="utf-8")
    except Exception:
        pass


action = QAction("Create Kanji Grid Deck...", mw)
qconnect(action.triggered, open_converter_dialog)
mw.form.menuTools.addAction(action)
