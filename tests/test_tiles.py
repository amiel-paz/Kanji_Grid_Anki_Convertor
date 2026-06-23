import unittest

from kanji_grid_anki_converter.tiles import TILE_CODES, build_tile_html, contains_kanji, replace_kanji_with_tiles


class TileReplacementTests(unittest.TestCase):
    def test_bundled_mapping_matches_known_canonical_codes(self):
        self.assertEqual(TILE_CODES["亜"], "0062")
        self.assertEqual(TILE_CODES["愛"], "1424")
        self.assertEqual(TILE_CODES["響"], "0610")
        self.assertEqual(len(TILE_CODES), 2999)

    def test_replaces_plain_kanji_and_leaves_bracket_furigana_text(self):
        result = replace_kanji_with_tiles("漢字[かんじ]")

        self.assertEqual(result.replacements, 2)
        self.assertIn("kanji-grid-tile", result.text)
        self.assertIn("[かんじ]", result.text)

    def test_detects_any_kanji_for_front_filtering(self):
        self.assertTrue(contains_kanji("捕まる"))
        self.assertTrue(contains_kanji("𠮷野"))
        self.assertFalse(contains_kanji("まる"))

    def test_skips_html_ruby_reading_tags(self):
        result = replace_kanji_with_tiles("<ruby>漢<rt>漢</rt></ruby>")

        self.assertEqual(result.replacements, 1)
        self.assertIn("<rt>漢</rt>", result.text)
        self.assertIn("kanji-grid-tile", result.text)

    def test_tile_html_contains_four_colored_cells_and_center_kanji(self):
        html = build_tile_html("愛", "1424")

        self.assertEqual(html.count('aria-hidden="true"'), 5)
        self.assertIn('data-kanji-grid-code="1424"', html)
        self.assertIn("display:inline-block;position:relative;width:1.24em;height:1.24em;vertical-align:-0.10em", html)
        self.assertIn("display:flex;width:80%;height:80%", html)
        self.assertIn("font-size:0.68em", html)
        self.assertIn("left:0;top:0;width:50%;height:50%", html)
        self.assertIn("愛", html)

    def test_already_converted_tile_html_is_not_replaced_again(self):
        html = build_tile_html("愛", "1424")
        result = replace_kanji_with_tiles(html)

        self.assertEqual(result.replacements, 0)
        self.assertEqual(result.text, html)


if __name__ == "__main__":
    unittest.main()
