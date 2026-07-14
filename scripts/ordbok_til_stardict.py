#!/usr/bin/env python3
"""
Konverterer artikkeldata fra ord.uib.no (Ordbøkene, UiB/Språkrådet)
til PyGlossary-tabfile, som deretter kan bygges til StarDict.

Bruk:
    1. Last ned datafil:
       curl -O https://ord.uib.no/bm/fil/article.tar.gz   (bokmål)
       curl -O https://ord.uib.no/nn/fil/article.tar.gz   (nynorsk)

    2. Kjør skriptet (Norsk Ordbank-arkivet er valgfritt, for
       sammensetningsanalyse - se scripts/ordbok_parser.py):
       python3 ordbok_til_stardict.py article.tar.gz bokmaal.txt [norsk_ordbank.tar.gz]

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
grunnordet. Bøyingsformer vises også som en tabell/liste i definisjonen
(entall/flertall x ubestemt/bestemt for substantiv, ellers en enkel
liste), og kryssreferanser (f.eks. "trolle (I)") vises i kursiv.

All parsing av selve artikkelstrukturen skjer i `ordbok_parser.py`.

Lisens på dataene: CC-BY 4.0 (UiB/Språkrådet, og Nasjonalbiblioteket for
Norsk Ordbank) - oppgi kilde.
"""

import html
import sys
from pathlib import Path
from typing import Optional

from ordbok_parser import (
    Article,
    Expression,
    InflectionTable,
    Sense,
    iterate_articles,
    load_compound_analysis,
    resolve_refs,
)


def _ref_resolver(article_id: int, text: str) -> str:
    # StarDict-lesere har ingen felles standard for interne kryssoppslag,
    # så kryssreferanser vises i kursiv i stedet for som klikkbar lenke.
    return f"<i>{text}</i>"


def _escape(text: str) -> str:
    return resolve_refs(html.escape(text), _ref_resolver)


def _render_examples(examples: list[str]) -> str:
    if not examples:
        return ""
    ex = "; ".join(_escape(e) for e in examples)
    return f"<br><b>Eksempel</b><br><i>{ex}</i>"


def _render_sense(sense: Sense) -> str:
    line = _escape(sense.text) if sense.text else ""
    line += _render_examples(sense.examples)
    subs = "".join(f"<li>{r}</li>" for s in sense.subsenses if (r := _render_sense(s)))
    if subs:
        line += f'<ol type="a">{subs}</ol>'
    return line.strip()


def _render_senses(senses: list[Sense]) -> str:
    items = [f"<li>{r}</li>" for s in senses if (r := _render_sense(s))]
    return f"<ol>{''.join(items)}</ol>" if items else ""


# Inline stiling siden StarDict-lesere ikke garantert støtter <style>-
# blokker - matcher rutenett/gråtoner-oppsettet på ordbokene.no.
_TABLE_STYLE = 'style="border-collapse:collapse;margin:4px 0"'
_TH_STYLE = 'style="border:1px solid #999;background:#f0f0f0;padding:3px 10px;text-align:center"'
_TD_STYLE = 'style="border:1px solid #999;padding:3px 10px;text-align:center"'


def _render_inflection_table(lemma: str, table: InflectionTable, show_label: bool) -> str:
    label = f"<i>{html.escape(lemma)}:</i> " if show_label else ""
    if table.kind == "grid":
        top = "".join(
            f'<th {_TH_STYLE} colspan="{len(table.sub_cols)}">{html.escape(g)}</th>'
            for g in table.col_groups
        )
        sub = "".join(
            f'<th {_TH_STYLE}><i>{html.escape(s)}</i></th>'
            for _ in table.col_groups
            for s in table.sub_cols
        )
        cells = []
        for g in table.col_groups:
            for s in table.sub_cols:
                forms = table.cells.get((g, s), [])
                text = ", ".join(html.escape(f) for f in forms) if forms else "-"
                if g == "entall" and s == "ubestemt form" and table.article and forms:
                    text = f'<i style="color:#777">{html.escape(table.article)}</i> {text}'
                cells.append(f"<td {_TD_STYLE}>{text}</td>")
        data_row = "<tr>" + "".join(cells) + "</tr>"
        return f'{label}<table {_TABLE_STYLE}><tr>{top}</tr><tr>{sub}</tr>{data_row}</table>'
    rows = "".join(
        f'<tr><td {_TD_STYLE}>{html.escape(l)}</td><td {_TD_STYLE}>{html.escape(f)}</td></tr>'
        for l, f in table.rows
    )
    return f'{label}<table {_TABLE_STYLE}>{rows}</table>'


def _render_inflection_tables(article: Article) -> str:
    if not article.inflection_tables:
        return ""
    show_label = len(article.inflection_tables) > 1
    return "".join(_render_inflection_table(lemma, t, show_label) for lemma, t in article.inflection_tables)


def _render_expression_inline(expr: Expression) -> str:
    name = f"<b>{html.escape(expr.lemma)}</b>"
    senses_html = _render_senses(expr.senses)
    return f"{name}<br>{senses_html}" if senses_html else name


def _render_expressions_section(article: Article) -> str:
    items = [_render_expression_inline(e) for e in article.expressions if e.lemma]
    if not items:
        return ""
    return "<b>Faste uttrykk</b><br>" + "<br>".join(items)


def _render_definition(article: Article, compounds: dict[str, list[str]]) -> str:
    parts = []
    if article.word_class:
        parts.append(f"<b>{html.escape(article.word_class)}</b>")
    if article.pronunciation:
        parts.append(f"<b>Uttale:</b> {_escape(article.pronunciation)}")
    if article.etymology:
        parts.append(f"<b>Opphav:</b> {_escape(article.etymology)}")

    tables_html = _render_inflection_tables(article)
    if tables_html:
        parts.append(tables_html)

    senses_html = _render_senses(article.senses)
    if senses_html:
        parts.append(f"<b>Betydning og bruk</b>{senses_html}")
    expr_html = _render_expressions_section(article)
    if expr_html:
        parts.append(expr_html)

    ordbokene_html = "<br>".join(p for p in parts if p)

    # Sammensetningsanalysen kommer fra en helt annen kilde (Norsk
    # Ordbank/Nasjonalbiblioteket, ikke Ordbøkene/UiB) - skilt ut med
    # delelinje og egen tittel i stedet for å blandes inn i artikkelen.
    comp = []
    for lemma in article.lemmas:
        comp.extend(compounds.get(lemma.lower(), []))
    comp = list(dict.fromkeys(comp))
    if not comp:
        return ordbokene_html

    ordbank_html = f"<b>Fra Norsk Ordbank</b><br><b>Sammensetning:</b> {_escape(' / '.join(comp))}"
    return f"{ordbokene_html}<hr>{ordbank_html}"


def _render_expression_definition(article: Article, expr: Expression) -> str:
    grunnord = ", ".join(article.lemma_display)
    parts = [f"<b>fast uttrykk</b> (av <i>{html.escape(grunnord)}</i>)"]
    senses_html = _render_senses(expr.senses)
    if senses_html:
        parts.append(senses_html)
    return "<br>".join(parts)


def _tabfile_line(headwords: list[str], definition: str) -> str:
    head = "|".join(h.replace("\t", " ").replace("\n", " ") for h in headwords if h)
    defn = definition.replace("\t", " ").replace("\n", " ")
    return f"{head}\t{defn}"


def convert(tar_path: Path, out_path: Path, ordbank_path: Optional[Path] = None) -> None:
    compounds = load_compound_analysis(ordbank_path) if ordbank_path else {}
    with out_path.open("w", encoding="utf-8") as out:
        for article in iterate_articles(tar_path):
            if not article.lemmas:
                continue
            headwords = list(dict.fromkeys(article.lemmas + article.inflection_word_forms))
            out.write(_tabfile_line(headwords, _render_definition(article, compounds)) + "\n")
            for expr in article.expressions:
                if not expr.lemma:
                    continue
                out.write(
                    _tabfile_line([expr.lemma], _render_expression_definition(article, expr)) + "\n"
                )


def main() -> None:
    if len(sys.argv) not in (3, 4):
        print(f"Bruk: {sys.argv[0]} article.tar.gz utfil.txt [norsk_ordbank.tar.gz]", file=sys.stderr)
        raise SystemExit(1)
    ordbank_path = Path(sys.argv[3]) if len(sys.argv) == 4 else None
    convert(Path(sys.argv[1]), Path(sys.argv[2]), ordbank_path)


if __name__ == "__main__":
    main()
