# Kanji Grid Anki Converter

Convert an existing Anki `.apkg` deck into a new deck where mapped kanji are rendered as Kanji Grid four-corner tiles. The converter preserves the original notes, models, cards, scheduling data, media files, and furigana text; it only changes selected note fields in a copied deck.

The bundled mapping covers the same canonical set as the Kanji Grid memorizer app: all Joyo kanji plus the Jinmeiyo supplemental set, 2,999 entries total.

## Usage

Install the CLI from the repo root:

```bash
python3 -m pip install -e .
```

Then convert a deck:

```bash
kanji-grid-anki input.apkg
```

By default, the output is written beside the input as:

```text
input.kanji-grid.apkg
```

Restrict conversion to specific note fields by passing `--field` more than once:

```bash
kanji-grid-anki input.apkg \
  --field Expression \
  --field Sentence \
  --output output.apkg
```

List fields in a deck without converting it:

```bash
kanji-grid-anki input.apkg --list-fields
```

For source-checkout use without installing:

```bash
PYTHONPATH=src python3 -m kanji_grid_anki_converter input.apkg
```

## Furigana

The converter leaves furigana readings intact. For HTML ruby markup, kanji inside `<rt>` and `<rp>` tags are skipped. For common Anki bracket-style furigana such as `漢字[かんじ]`, the kanji are replaced and the bracketed reading remains unchanged.

## Development

Run tests with:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```
