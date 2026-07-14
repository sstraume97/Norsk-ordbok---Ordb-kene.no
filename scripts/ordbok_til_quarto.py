#!/usr/bin/env python3
"""
Konverterer artikkeldata fra ord.uib.no (Ordbøkene, UiB/Språkrådet) til
Quarto-kapitler (`.qmd`), gruppert alfabetisk, for `book/bm/` og `book/nn/`.

Bruk:
    python3 ordbok_til_quarto.py article.tar.gz book/bm

Genererer én fil per bokstav (`a.qmd`, `b.qmd`, ..., `0-9.qmd`) i
mål-mappen. Filene er *generert innhold* - de committes ikke til git
(se .gitignore) og bygges på nytt hver gang workflowen kjører.

All parsing av selve artikkelstrukturen skjer i den delte modulen
`ordbok_parser.py`, som også brukes av `ordbok_til_stardict.py`.

Lisens på dataene: CC-BY 4.0 (UiB/Språkrådet) - oppgi kilde.
"""

import sys
from collections import defaultdict
from pathlib import Path

from ordbok_parser import Article, Expression, Sense, iterate_articles

# Norsk alfabetisk rekkefølge for kapittelinndeling.
LETTERS = list("ABCDEFGHIJKLMNOPQRSTUVWXYZÆØÅ") + ["0-9"]


def _md_escape(text: str) -> str:
    for ch in ("\\", "*", "_", "`", "|", "["):
        text = text.replace(ch, "\\" + ch)
    return text


def _render_examples_md(examples: list[str]) -> str:
    if not examples:
        return ""
    ex = "; ".join(_md_escape(e) for e in examples)
    return f"  \n  *Eksempel: {ex}*"


def _render_sense_md(sense: Sense, bullet_indent: str = "") -> list[str]:
    lines: list[str] = []
    if sense.text or sense.examples:
        line = f"{bullet_indent}- **{sense.number}.** {_md_escape(sense.text)}"
        line += _render_examples_md(sense.examples)
        lines.append(line)
    for sub in sense.subsenses:
        lines.extend(_render_sense_md(sub, bullet_indent + "  "))
    return lines


def _render_expression_md(article: Article, expr: Expression) -> list[str]:
    lines = [f"- **{_md_escape(expr.lemma)}**"]
    for sense in expr.senses:
        lines.extend(_render_sense_md(sense, "  "))
    return lines


def render_article_md(article: Article) -> list[str]:
    heading = ", ".join(article.lemmas) or "(uten oppslagsord)"
    lines = [f"## {_md_escape(heading)} {{#{article_anchor(article)}}}", ""]

    meta = []
    if article.word_class:
        meta.append(f"*{_md_escape(article.word_class)}*")
    if article.pronunciation:
        meta.append(f"uttale: {_md_escape(article.pronunciation)}")
    if article.etymology:
        meta.append(f"opphav: {_md_escape(article.etymology)}")
    if meta:
        lines.append(" &middot; ".join(meta))
        lines.append("")

    for sense in article.senses:
        lines.extend(_render_sense_md(sense))
    if article.senses:
        lines.append("")

    if article.inflections:
        forms = ", ".join(_md_escape(f) for f in article.inflections)
        lines.append(f"**Bøyningsformer:** {forms}")
        lines.append("")

    if article.expressions:
        lines.append("**Faste uttrykk:**")
        lines.append("")
        for expr in article.expressions:
            if not expr.lemma:
                continue
            lines.extend(_render_expression_md(article, expr))
        lines.append("")

    return lines


def article_anchor(article: Article) -> str:
    return f"art-{article.article_id}"


def generate(tar_path: Path, out_dir: Path, book_lang_label: str) -> None:
    by_letter: dict[str, list[Article]] = defaultdict(list)
    for article in iterate_articles(tar_path):
        if not article.lemmas:
            continue
        by_letter[article.first_letter].append(article)

    out_dir.mkdir(parents=True, exist_ok=True)
    for letter in LETTERS:
        articles = sorted(by_letter.get(letter, []), key=lambda a: (a.lemmas[0].lower(), a.article_id))
        path = out_dir / f"{_filename_for_letter(letter)}.qmd"
        with path.open("w", encoding="utf-8") as f:
            f.write(f"# {letter}\n\n")
            if not articles:
                f.write(f"Ingen oppslagsord i {book_lang_label} som starter på «{letter}» ennå.\n")
                continue
            for article in articles:
                f.write("\n".join(render_article_md(article)))
                f.write("\n\n")


def _filename_for_letter(letter: str) -> str:
    return "0-9" if letter == "0-9" else letter.lower()


def main() -> None:
    if len(sys.argv) != 4:
        print(f"Bruk: {sys.argv[0]} article.tar.gz utmappe spraaknavn", file=sys.stderr)
        raise SystemExit(1)
    generate(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3])


if __name__ == "__main__":
    main()
