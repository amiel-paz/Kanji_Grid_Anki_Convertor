from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
ADDON_DIR = ROOT / "addon" / "kanji_grid_anki_converter"
DIST_DIR = ROOT / "dist"
OUTPUT = DIST_DIR / "kanji_grid_anki_converter.ankiaddon"


def main() -> int:
    DIST_DIR.mkdir(exist_ok=True)
    if OUTPUT.exists():
        OUTPUT.unlink()

    with ZipFile(OUTPUT, "w", ZIP_DEFLATED) as archive:
        for path in sorted(ADDON_DIR.rglob("*")):
            if path.is_file():
                if "__pycache__" in path.parts or path.suffix == ".pyc":
                    continue
                archive.write(path, path.relative_to(ADDON_DIR).as_posix())

    print(OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
