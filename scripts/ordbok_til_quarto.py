#!/usr/bin/env python3
"""
Konverterer artikkeldata fra ord.uib.no (Ordbøkene, UiB/Språkrådet) til
Quarto-kapitler (`.qmd`), gruppert alfabetisk, for `book/bm/` og `book/nn/`.

Bruk:
    python3 ordbok_til_quarto.py article.tar.gz book/bm Bokmålsordboka [norsk_ordbank.tar.gz]

Genererer én fil per bokstav (`a.qmd`, `b.qmd`, ..., `0-9.qmd`) i
mål-mappen. Filene er *generert innhold* - de committes ikke til git
(se .gitignore) og bygges på nytt hver gang workflowen kjører.

Bøyingsformer vises som en tabell (entall/flertall x ubestemt/bestemt
for substantiv, ellers en enkel liste), og kryssreferanser (f.eks.
"trolle (I)") blir ekte Quarto-kryssreferanser til riktig kapittel.
Norsk Ordbank (valgfritt tredje argument) gir i tillegg
sammensetningsanalyse (f.eks. "troll + mann") der det finnes.

All parsing av selve artikkelstrukturen skjer i den delte modulen
`ordbok_parser.py`, som også brukes av `ordbok_til_stardict.py`.

Lisens på dataene: CC-BY 4.0 (UiB/Språkrådet, og Nasjonalbiblioteket for
Norsk Ordbank) - oppgi kilde.
"""

import sys
from collections import defaultdict
from pathlib import Path
from typing import Callable, Optional

from ordbok_parser import (
    Article,
    Expression,
    InflectionTable,
    Sense,
    iterate_articles,
    load_compound_analysis,
    resolve_refs,
)

# Norsk alfabetisk rekkefølge for kapittelinndeling.
LETTERS = list("ABCDEFGHIJKLMNOPQRSTUVWXYZÆØÅ") + ["0-9"]

RefResolver = Callable[[int, str], str]


def _md_escape(text: str) -> str:
    for ch in ("\\", "*", "_", "`", "|", "["):
        text = text.replace(ch, "\\" + ch)
    return text


def _escape(text: str, resolve: RefResolver) -> str:
    return resolve_refs(_md_escape(text), resolve)


def _render_examples_md(examples: list[str], resolve: RefResolver) -> str:
    if not examples:
        return ""
    ex = "; ".join(_escape(e, resolve) for e in examples)
    return f"  \n  *Eksempel: {ex}*"


def _render_sense_md(sense: Sense, resolve: RefResolver, bullet_indent: str = "") -> list[str]:
    lines: list[str] = []
    if sense.text or sense.examples:
        line = f"{bullet_indent}- **{sense.number}.** {_escape(sense.text, resolve)}"
        line += _render_examples_md(sense.examples, resolve)
        lines.append(line)
    for sub in sense.subsenses:
        lines.extend(_render_sense_md(sub, resolve, bullet_indent + "  "))
    return lines


def _render_expression_md(expr: Expression, resolve: RefResolver) -> list[str]:
    lines = [f"- **{_md_escape(expr.lemma)}**"]
    for sense in expr.senses:
        lines.extend(_render_sense_md(sense, resolve, "  "))
    return lines


def _render_inflection_table_md(lemma: str, table: InflectionTable, show_label: bool) -> list[str]:
    lines: list[str] = []
    if show_label:
        lines.append(f"**{_md_escape(lemma)}**")
        lines.append("")
    if table.kind == "grid":
        headers = [f"{g} – {s}" for g in table.col_groups for s in table.sub_cols]
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("|" + "---|" * len(headers))
        cells = []
        for g in table.col_groups:
            for s in table.sub_cols:
                forms = table.cells.get((g, s), [])
                text = ", ".join(_md_escape(f) for f in forms) if forms else "-"
                if g == "entall" and s == "ubestemt form" and table.article and forms:
                    text = f"*{_md_escape(table.article)}* {text}"
                cells.append(text)
        lines.append("| " + " | ".join(cells) + " |")
    else:
        lines.append("| Form | Bøyd form |")
        lines.append("|---|---|")
        for label, form in table.rows:
            lines.append(f"| {_md_escape(label)} | {_md_escape(form)} |")
    lines.append("")
    return lines


def _render_inflection_tables_md(article: Article) -> list[str]:
    if not article.inflection_tables:
        return []
    show_label = len(article.inflection_tables) > 1
    lines: list[str] = []
    for lemma, table in article.inflection_tables:
        lines.extend(_render_inflection_table_md(lemma, table, show_label))
    return lines


def render_article_md(article: Article, resolve: RefResolver, compounds: dict[str, list[str]]) -> list[str]:
    heading = ", ".join(article.lemma_display) or "(uten oppslagsord)"
    lines = [f"## {_md_escape(heading)} {{#{article_anchor(article)}}}", ""]

    meta = []
    if article.word_class:
        meta.append(f"*{_md_escape(article.word_class)}*")
    if article.pronunciation:
        meta.append(f"uttale: {_escape(article.pronunciation, resolve)}")
    if article.etymology:
        meta.append(f"opphav: {_escape(article.etymology, resolve)}")
    if meta:
        lines.append(" &middot; ".join(meta))
        lines.append("")

    comp = []
    for lemma in article.lemmas:
        comp.extend(compounds.get(lemma.lower(), []))
    comp = list(dict.fromkeys(comp))
    if comp:
        lines.append(f"**Sammensetning:** {_md_escape(' / '.join(comp))}")
        lines.append("")

    lines.extend(_render_inflection_tables_md(article))

    for sense in article.senses:
        lines.extend(_render_sense_md(sense, resolve))
    if article.senses:
        lines.append("")

    if article.expressions:
        lines.append("**Faste uttrykk:**")
        lines.append("")
        for expr in article.expressions:
            if not expr.lemma:
                continue
            lines.extend(_render_expression_md(expr, resolve))
        lines.append("")

    return lines


def article_anchor(article: Article) -> str:
    return f"art-{article.article_id}"


def _filename_for_letter(letter: str) -> str:
    return "0-9" if letter == "0-9" else letter.lower()


def generate(
    tar_path: Path,
    out_dir: Path,
    book_lang_label: str,
    ordbank_path: Optional[Path] = None,
) -> None:
    compounds = load_compound_analysis(ordbank_path) if ordbank_path else {}

    by_letter: dict[str, list[Article]] = defaultdict(list)
    id_to_file: dict[int, str] = {}
    for article in iterate_articles(tar_path):
        if not article.lemmas:
            continue
        by_letter[article.first_letter].append(article)
        id_to_file[article.article_id] = f"{_filename_for_letter(article.first_letter)}.qmd"

    def resolve(article_id: int, text: str) -> str:
        target = id_to_file.get(article_id)
        return f"[{text}]({target}#{'art-' + str(article_id)})" if target else text

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
                f.write("\n".join(render_article_md(article, resolve, compounds)))
                f.write("\n\n")


def main() -> None:
    if len(sys.argv) not in (4, 5):
        print(f"Bruk: {sys.argv[0]} article.tar.gz utmappe spraaknavn [norsk_ordbank.tar.gz]", file=sys.stderr)
        raise SystemExit(1)
    ordbank_path = Path(sys.argv[4]) if len(sys.argv) == 5 else None
    generate(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], ordbank_path)


if __name__ == "__main__":
    main()
