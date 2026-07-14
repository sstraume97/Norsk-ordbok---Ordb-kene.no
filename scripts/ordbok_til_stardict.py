#!/usr/bin/env python3
"""
Konverterer artikkeldata fra ord.uib.no (Ordbøkene, UiB/Språkrådet)
til PyGlossary-tabfile, som deretter kan bygges til StarDict.

Bruk:
    1. Last ned datafil:
       curl -O https://ord.uib.no/bm/fil/article.tar.gz   (bokmål)
       curl -O https://ord.uib.no/nn/fil/article.tar.gz   (nynorsk)

    2. Kjør skriptet:
       python3 ordbok_til_stardict.py article.tar.gz bokmaal.txt

    3. Bygg StarDict med PyGlossary:
       pip install pyglossary
       pyglossary bokmaal.txt bokmaal.ifo \
           --read-format=Tabfile --write-format=Stardict \
           --name "Bokmålsordboka"

Hvert lemma og alle bøyde former legges inn som alternative oppslagsord
(skilt med "|") som peker til samme definisjon, slik at f.eks. "husene"
treffer artikkelen for "hus". Faste uttrykk (idiomer, funnet som
sub_article i kildedataene, f.eks. "slå an" under "slå") får derimot sitt
eget oppslag med egen definisjon, siden de har en annen betydning enn
grunnordet.

All parsing av selve artikkelstrukturen skjer i den delte modulen
`ordbok_parser.py`, som også brukes av `ordbok_til_quarto.py`.

Lisens på dataene: CC-BY 4.0 (UiB/Språkrådet) - oppgi kilde.
"""

import html
import sys
from pathlib import Path

from ordbok_parser import Article, Expression, Sense, iterate_articles


def _render_examples(examples: list[str]) -> str:
    if not examples:
        return ""
    ex = "; ".join(html.escape(e) for e in examples)
    return f" <i>({ex})</i>"


def _render_sense(sense: Sense) -> str:
    line = html.escape(sense.text) if sense.text else ""
    line += _render_examples(sense.examples)
    subs = "".join(f"<li>{r}</li>" for s in sense.subsenses if (r := _render_sense(s)))
    if subs:
        line += f'<ol type="a">{subs}</ol>'
    return line.strip()


def _render_senses(senses: list[Sense]) -> str:
    items = [f"<li>{r}</li>" for s in senses if (r := _render_sense(s))]
    return f"<ol>{''.join(items)}</ol>" if items else ""


def _render_definition(article: Article) -> str:
    parts = []
    if article.word_class:
        parts.append(f"<b>{html.escape(article.word_class)}</b>")
    if article.pronunciation:
        parts.append(f"<i>uttale:</i> {html.escape(article.pronunciation)}")
    if article.etymology:
        parts.append(f"<i>opphav:</i> {html.escape(article.etymology)}")
    senses_html = _render_senses(article.senses)
    if senses_html:
        parts.append(senses_html)
    if article.expressions:
        names = ", ".join(html.escape(e.lemma) for e in article.expressions if e.lemma)
        if names:
            parts.append(f"<i>faste uttrykk:</i> {names}")
    return "<br>".join(p for p in parts if p)


def _render_expression_definition(article: Article, expr: Expression) -> str:
    grunnord = ", ".join(article.lemmas)
    parts = [f"<b>fast uttrykk</b> (av <i>{html.escape(grunnord)}</i>)"]
    senses_html = _render_senses(expr.senses)
    if senses_html:
        parts.append(senses_html)
    return "<br>".join(parts)


def _tabfile_line(headwords: list[str], definition: str) -> str:
    head = "|".join(h.replace("\t", " ").replace("\n", " ") for h in headwords if h)
    defn = definition.replace("\t", " ").replace("\n", " ")
    return f"{head}\t{defn}"


def convert(tar_path: Path, out_path: Path) -> None:
    with out_path.open("w", encoding="utf-8") as out:
        for article in iterate_articles(tar_path):
            if not article.lemmas:
                continue
            headwords = list(dict.fromkeys(article.lemmas + article.inflections))
            out.write(_tabfile_line(headwords, _render_definition(article)) + "\n")
            for expr in article.expressions:
                if not expr.lemma:
                    continue
                out.write(
                    _tabfile_line([expr.lemma], _render_expression_definition(article, expr)) + "\n"
                )


def main() -> None:
    if len(sys.argv) != 3:
        print(f"Bruk: {sys.argv[0]} article.tar.gz utfil.txt", file=sys.stderr)
        raise SystemExit(1)
    convert(Path(sys.argv[1]), Path(sys.argv[2]))


if __name__ == "__main__":
    main()
