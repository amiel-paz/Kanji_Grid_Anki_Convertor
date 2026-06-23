from __future__ import annotations

from dataclasses import dataclass
from html import escape
from html.parser import HTMLParser
from importlib import resources
import json
from typing import Mapping

SKIPPED_HTML_TAGS = {"rt", "rp", "script", "style"}


@dataclass(frozen=True)
class ReplacementResult:
    text: str
    replacements: int
    kanji_counts: Mapping[str, int]


def load_tile_codes() -> Mapping[str, str]:
    data_file = resources.files(__package__).joinpath("data/kanji_tile_codes.json")
    with data_file.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload["codes"]


def load_tile_colors() -> tuple[str, ...]:
    data_file = resources.files(__package__).joinpath("data/kanji_tile_codes.json")
    with data_file.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return tuple(payload["colors"])


TILE_CODES = load_tile_codes()
TILE_COLORS = load_tile_colors()


def contains_kanji(text: str) -> bool:
    return any(_is_kanji_codepoint(char) for char in text)


def _is_kanji_codepoint(char: str) -> bool:
    codepoint = ord(char)
    return (
        0x3400 <= codepoint <= 0x4DBF
        or 0x4E00 <= codepoint <= 0x9FFF
        or 0xF900 <= codepoint <= 0xFAFF
        or 0x20000 <= codepoint <= 0x2A6DF
        or 0x2A700 <= codepoint <= 0x2B73F
        or 0x2B740 <= codepoint <= 0x2B81F
        or 0x2B820 <= codepoint <= 0x2CEAF
        or 0x2CEB0 <= codepoint <= 0x2EBEF
        or 0x30000 <= codepoint <= 0x323AF
    )


def replace_kanji_with_tiles(text: str, tile_codes: Mapping[str, str] = TILE_CODES) -> ReplacementResult:
    parser = _KanjiTileHTMLParser(tile_codes)
    parser.feed(text)
    parser.close()
    return ReplacementResult(
        text=parser.output,
        replacements=parser.replacements,
        kanji_counts=dict(parser.kanji_counts),
    )


def plain_text_for_matching(text: str) -> str:
    parser = _PlainTextHTMLParser()
    parser.feed(text)
    parser.close()
    return parser.output


def build_tile_html(kanji: str, code: str) -> str:
    if len(code) != 4 or any(digit not in "01234567" for digit in code):
        raise ValueError(f"Invalid Kanji Grid tile code for {kanji!r}: {code!r}")

    colors = [TILE_COLORS[int(digit)] for digit in code]
    cells = "".join(
        f"<span aria-hidden=\"true\" style=\"position:absolute;{position}width:50%;height:50%;background:{color};\"></span>"
        for color, position in zip(
            colors,
            ("left:0;top:0;", "right:0;top:0;", "left:0;bottom:0;", "right:0;bottom:0;"),
        )
    )
    escaped_kanji = escape(kanji, quote=True)
    escaped_code = escape(code, quote=True)

    return (
        f"<span class=\"kanji-grid-tile\" data-kanji-grid-code=\"{escaped_code}\" "
        f"aria-label=\"{escaped_kanji} Kanji Grid tile code {escaped_code}\" "
        "style=\"display:inline-block;position:relative;width:1.42em;height:1.42em;vertical-align:-0.18em;"
        "margin:0 0.04em;border:1px solid #d1d5db;border-radius:0.18em;overflow:hidden;"
        "background:#ffffff;line-height:1;box-sizing:border-box;\">"
        f"{cells}"
        "<span aria-hidden=\"true\" "
        "style=\"position:absolute;left:50%;top:50%;display:flex;width:76%;height:76%;"
        "transform:translate(-50%,-50%);align-items:center;justify-content:center;"
        "border-radius:0.14em;background:#ffffff;color:#111827;"
        "font-family:'Hiragino Mincho ProN','Yu Mincho','Noto Serif CJK JP',serif;"
        "font-size:0.88em;font-weight:600;line-height:1;\">"
        f"{escaped_kanji}</span></span>"
    )


def _replace_text_segment(text: str, tile_codes: Mapping[str, str]) -> ReplacementResult:
    output: list[str] = []
    counts: dict[str, int] = {}
    replacements = 0

    for char in text:
        code = tile_codes.get(char)
        if code is None:
            output.append(char)
            continue

        output.append(build_tile_html(char, code))
        counts[char] = counts.get(char, 0) + 1
        replacements += 1

    return ReplacementResult("".join(output), replacements, counts)


class _KanjiTileHTMLParser(HTMLParser):
    def __init__(self, tile_codes: Mapping[str, str]) -> None:
        super().__init__(convert_charrefs=False)
        self._tile_codes = tile_codes
        self._parts: list[str] = []
        self._tag_stack: list[str] = []
        self._tile_skip_depth = 0
        self.replacements = 0
        self.kanji_counts: dict[str, int] = {}

    @property
    def output(self) -> str:
        return "".join(self._parts)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._parts.append(self.get_starttag_text() or _format_start_tag(tag, attrs))
        self._tag_stack.append(tag.lower())
        if self._tile_skip_depth > 0 or _is_kanji_grid_tile(attrs):
            self._tile_skip_depth += 1

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._parts.append(self.get_starttag_text() or _format_start_tag(tag, attrs, self_closing=True))

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        for index in range(len(self._tag_stack) - 1, -1, -1):
            if self._tag_stack[index] == lowered:
                del self._tag_stack[index:]
                break
        if self._tile_skip_depth > 0:
            self._tile_skip_depth -= 1
        self._parts.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if self._tile_skip_depth > 0 or any(tag in SKIPPED_HTML_TAGS for tag in self._tag_stack):
            self._parts.append(data)
            return

        result = _replace_text_segment(data, self._tile_codes)
        self._parts.append(result.text)
        self.replacements += result.replacements
        for kanji, count in result.kanji_counts.items():
            self.kanji_counts[kanji] = self.kanji_counts.get(kanji, 0) + count

    def handle_entityref(self, name: str) -> None:
        self._parts.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self._parts.append(f"&#{name};")

    def handle_comment(self, data: str) -> None:
        self._parts.append(f"<!--{data}-->")

    def handle_decl(self, decl: str) -> None:
        self._parts.append(f"<!{decl}>")

    def handle_pi(self, data: str) -> None:
        self._parts.append(f"<?{data}>")


class _PlainTextHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []

    @property
    def output(self) -> str:
        return "".join(self._parts)

    def handle_data(self, data: str) -> None:
        self._parts.append(data)


def _format_start_tag(
    tag: str,
    attrs: list[tuple[str, str | None]],
    *,
    self_closing: bool = False,
) -> str:
    formatted_attrs = []
    for name, value in attrs:
        if value is None:
            formatted_attrs.append(name)
        else:
            formatted_attrs.append(f'{name}="{escape(value, quote=True)}"')
    suffix = " /" if self_closing else ""
    if not formatted_attrs:
        return f"<{tag}{suffix}>"
    return f"<{tag} {' '.join(formatted_attrs)}{suffix}>"


def _is_kanji_grid_tile(attrs: list[tuple[str, str | None]]) -> bool:
    for name, value in attrs:
        if name.lower() == "data-kanji-grid-code":
            return True
        if name.lower() == "class" and value:
            classes = {part.strip() for part in value.split()}
            if "kanji-grid-tile" in classes:
                return True
    return False
