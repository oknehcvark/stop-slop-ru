#!/usr/bin/env python3
"""Русская типографика для stop-slop-ru (oknehcvark, MIT).

Неразрывные пробелы после коротких предлогов/союзов, перед тире и частицами,
между числом и единицей, в инициалах и сокращениях; «ёлочки», тире, многоточие.
Не трогает блоки кода, `inline code`, ссылки, e-mail; в режиме --html — теги,
<script>, <style>, <code>, <pre>.

  python3 typograf.py файл.md            # результат в stdout
  python3 typograf.py файл.md -i         # править файл на месте
  python3 typograf.py страница.html --html -i
  echo "текст" | python3 typograf.py -
"""
import argparse
import re
import sys

NB = " "

SHORT = (
    "в во к ко с со у о об обо и а но да или на по за из до от без для при про под над "
    "не ни"
).split()
# words that glue to the NEXT word
SHORT_RE = re.compile(
    r"(?<![\w\-])(" + "|".join(sorted(SHORT, key=len, reverse=True)) + r") +(?=\S)",
    re.IGNORECASE,
)
PARTICLE_RE = re.compile(r"(?<=\w) +(же|ли|бы|ль|б)(?!\w)", re.IGNORECASE)
DASH_SPACED_RE = re.compile(r"(?<=\S) +(?:-|–|—|--) +")
NUM_RANGE_RE = re.compile(r"(?<=\d) +(?:-|–|—) +(?=\d)")
NUM_UNIT_RE = re.compile(r"(?<=\d) +(?=[^\s\d\W]|[%₽$€°‰]|руб|коп)")
NUM_GROUP_RE = re.compile(r"(?<!\d)(\d{1,3})(?: (\d{3}))+(?!\d)")
SIGN_RE = re.compile(r"([№§]) *(?=\d)")
INITIALS_RE = re.compile(r"\b([А-ЯЁA-Z]\.) *([А-ЯЁA-Z]\.)? *(?=[А-ЯЁA-Z][а-яёa-z])")
ABBR_RE = re.compile(r"(?<![\w])(т\. ?е\.|т\. ?д\.|т\. ?п\.|т\. ?к\.|и др\.|г\.|гг\.|ул\.|д\.|стр\.|рис\.|см\.|им\.|с\.|пр\.) +(?=\S)")
ABBR_INNER_RE = re.compile(r"(?<![\w])т\. ?(е|д|п|к)\.")
ELLIPSIS_RE = re.compile(r"\.\.\.")
PROTECT_RE = re.compile(
    r"<[^>\n]+>|\]\([^)\s]+\)|https?://[^\s)]+|www\.[^\s)]+|[\w.+-]+@[\w-]+\.[\w.-]+|`[^`\n]*`|\{\{.*?\}\}"
)


def quotes(text: str) -> str:
    text = text.replace("“", '"').replace("”", '"').replace("„", '"')
    out, depth = [], 0
    for i, ch in enumerate(text):
        if ch != '"':
            out.append(ch)
            continue
        prev = text[i - 1] if i else " "
        opening = prev.isspace() or prev in "([{«„—–-/" or i == 0
        if opening:
            out.append("«" if depth == 0 else "„")
            depth += 1
        else:
            depth = max(depth - 1, 0)
            out.append("»" if depth == 0 else "“")
    return "".join(out)


def fix(text: str) -> str:
    keep = []

    def stash(m):
        keep.append(m.group(0))
        return f"\x00{len(keep) - 1}\x00"

    text = PROTECT_RE.sub(stash, text)
    text = ELLIPSIS_RE.sub("…", text)
    text = quotes(text)
    text = NUM_RANGE_RE.sub("–", text)
    text = DASH_SPACED_RE.sub(NB + "— ", text)
    text = NUM_GROUP_RE.sub(lambda m: m.group(0).replace(" ", NB), text)
    text = SIGN_RE.sub(lambda m: m.group(1) + NB, text)
    text = NUM_UNIT_RE.sub(NB, text)
    text = ABBR_INNER_RE.sub(lambda m: "т." + NB + m.group(1) + ".", text)
    text = ABBR_RE.sub(lambda m: m.group(1) + NB, text)
    text = INITIALS_RE.sub(
        lambda m: m.group(1) + (NB + m.group(2) if m.group(2) else "") + NB, text
    )
    for _ in range(2):  # «и в доме» — two short words in a row
        text = SHORT_RE.sub(lambda m: m.group(1) + NB, text)
    text = PARTICLE_RE.sub(lambda m: NB + m.group(1), text)
    return re.sub(r"\x00(\d+)\x00", lambda m: keep[int(m.group(1))], text)


def process_markdown(src: str) -> str:
    parts = re.split(r"(^```.*?^```[^\n]*$)", src, flags=re.M | re.S)
    return "".join(p if p.startswith("```") else fix(p) for p in parts)


def process_html(src: str) -> str:
    tag = re.compile(r"<(script|style|code|pre|textarea)\b.*?</\1\s*>|<!--.*?-->|<[^>]+>", re.S | re.I)
    out, pos = [], 0
    for m in tag.finditer(src):
        out.append(fix(src[pos:m.start()]).replace(NB, "&nbsp;"))
        out.append(m.group(0))
        pos = m.end()
    out.append(fix(src[pos:]).replace(NB, "&nbsp;"))
    res = "".join(out)
    # a short word right before an inline tag: «на <b>склад</b>»
    short_before_tag = re.compile(
        r"(?<![\w\-])(" + "|".join(sorted(SHORT, key=len, reverse=True)) + r") +(?=<(?:b|i|em|strong|a|span|u|s|mark)\b)",
        re.IGNORECASE,
    )
    return short_before_tag.sub(lambda m: m.group(1) + "&nbsp;", res)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", help="файл или - для stdin")
    ap.add_argument("--html", action="store_true", help="HTML: править только текст между тегами, &nbsp;")
    ap.add_argument("-i", "--in-place", action="store_true", help="записать результат в тот же файл")
    a = ap.parse_args()
    src = sys.stdin.read() if a.file == "-" else open(a.file, encoding="utf-8").read()
    res = process_html(src) if a.html else process_markdown(src)
    if a.in_place and a.file != "-":
        open(a.file, "w", encoding="utf-8").write(res)
    else:
        sys.stdout.write(res)


if __name__ == "__main__":
    main()
