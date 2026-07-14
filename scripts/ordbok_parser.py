#!/usr/bin/env python3
"""
Delt parsing-modul for Ordbøkene-artikler (ord.uib.no).

Leser `article.tar.gz` (ett `article/<id>.json` per artikkel, verifisert
mot ekte data fra UiB) og bygger en enkel, gjenbrukbar `Article`-struktur
som både `ordbok_til_stardict.py` (StarDict) og `ordbok_til_quarto.py`
(Quarto-bok) bygger videre på. All rekursiv tolkning av `body`-elementer
(definisjoner, eksempler, faste uttrykk, kryssreferanser) skjer her, slik
at de to konsumentene ikke dupliserer denne logikken.

Skjemaet er ikke offentlig dokumentert i detalj - det er utledet empirisk
fra ekte artikler (f.eks. https://ord.uib.no/bm/article/54131.json og
.../54676.json). Ukjente/uventede elementtyper ignoreres stille i stedet
for å feile, siden ordboka er stor og har mange kant-tilfeller.

Lisens på dataene: CC-BY 4.0 (UiB/Språkrådet) - oppgi kilde.
"""

from __future__ import annotations

import json
import tarfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, Optional

# Vanlige forkortelser/entiteter brukt i etymologi og forklaringer.
# Listen er satt sammen empirisk (hyppigst brukte id-er i kildedataene) -
# det finnes ingen offentlig, fullstendig kodeliste fra UiB. Id-er som
# ikke er i tabellen faller tilbake til `_fallback_entity()` i stedet for
# å feile eller vise rå understreker.
ABBREV = {
    "el": "el.", "e_l": "e.l.", "jf": "jf.", "fl": "fl.",
    "dvs": "dvs.", "osv": "osv.", "ogs": "også", "s_d": "s.d.",
    "if": "if.", "i_rel": "i rel.", "mots": "mots.", "sms": "sms.",
    "adj": "adj.", "adv": "adv.", "subst": "subst.", "prep": "prep.",
    "eg": "eg.", "overf": "overf.", "trans": "trans.", "intrans": "intrans.",
    "refl": "refl.", "upers": "upers.", "poet": "poet.", "dial": "dial.",
    "gm": "gm.", "foreld": "foreld.", "sj": "sj.", "spes": "spes.",
    "off": "off.", "hist": "hist.", "gl": "gl.", "muntl": "muntl.",
    "skriftl": "skriftl.", "vulg": "vulg.", "neds": "neds.", "form": "form.",
    "f_eks": "f.eks.", "o_l": "o.l.", "forh": "forh.", "trol": "trol.",
    "saerl": "særl.", "besl": "besl.", "gj": "gj.", "fork": "fork.",
    "bl_a": "bl.a.", "egl": "egl.", "o_a": "o.a.", "utenl": "utenl.",
    "uttr": "uttr.", "bf": "bf.", "bet": "bet.", "m": "m.", "oppr": "oppr.",
    "pers": "pers.", "nyd": "nyd.", "pga": "pga.",
}


def _fallback_entity(entity_id: str) -> str:
    """Best-effort formatering av entitets-id-er som ikke finnes i
    ABBREV: `aa`/`ae`/`oe` transkriberes til `å`/`æ`/`ø`, og understrek
    blir mellomrom. Gir et lesbart (om enn uoffisielt) resultat i stedet
    for å vise rå kode med understreker."""
    text = entity_id
    for src, dst in (("aa", "å"), ("ae", "æ"), ("oe", "ø")):
        text = text.replace(src, dst)
    return text.replace("_", " ")

# Ordklassekoder (fra lemma.paradigm_info.tags[0]) -> lesbart navn på norsk.
WORD_CLASS_NAMES = {
    "NOUN": "substantiv", "VERB": "verb", "ADJ": "adjektiv", "ADV": "adverb",
    "PREP": "preposisjon", "PRON": "pronomen", "DET": "determinativ",
    "CCONJ": "konjunksjon", "SCONJ": "subjunksjon", "INTJ": "interjeksjon",
    "SYM": "symbol", "EXPR": "fast uttrykk", "NUM": "tallord",
    "ABBR": "forkortelse", "MWE": "flerordsuttrykk",
}


@dataclass
class Sense:
    number: str
    text: str
    examples: list[str] = field(default_factory=list)
    subsenses: list["Sense"] = field(default_factory=list)


@dataclass
class Expression:
    lemma: str
    senses: list[Sense]


@dataclass
class Article:
    article_id: int
    lemmas: list[str]
    word_class: str
    pronunciation: Optional[str]
    etymology: Optional[str]
    senses: list[Sense]
    expressions: list[Expression]
    inflections: list[str]

    @property
    def first_letter(self) -> str:
        return letter_bucket(self.lemmas[0] if self.lemmas else "")


def letter_bucket(lemma: str) -> str:
    """Grupperingsbokstav for kapittelinndeling (A-Å, ellers '0-9')."""
    if not lemma:
        return "0-9"
    ch = lemma[0].upper()
    return ch if ch.isalpha() else "0-9"


def _render_item(item: dict) -> str:
    t = item.get("type_")
    if t == "entity":
        entity_id = item.get("id", "")
        return ABBREV.get(entity_id, _fallback_entity(entity_id))
    if t == "usage":
        return item.get("text", "")
    if t == "article_ref":
        lemmas = item.get("lemmas") or []
        return ", ".join(l.get("lemma", "") for l in lemmas if isinstance(l, dict))
    if t == "lemma":
        return item.get("lemma", "")
    # Ukjent elementtype: bruk tekst/id hvis det finnes, ellers tomt.
    return item.get("text") or item.get("id") or ""


def _render_content(content: str, items: list[dict]) -> str:
    """Erstatter hvert '$' i `content` med tilhørende renderte `items[i]`."""
    if not content:
        return ""
    parts = content.split("$")
    out = [parts[0]]
    for i, part in enumerate(parts[1:]):
        if i < len(items):
            out.append(_render_item(items[i]))
        out.append(part)
    return "".join(out).strip()


def _render_explanation(expl: dict) -> str:
    return _render_content(expl.get("content", ""), expl.get("items", []))


def _render_example(ex: dict) -> str:
    quote = ex.get("quote") or {}
    text = _render_content(quote.get("content", ""), quote.get("items", []))
    expl = ex.get("explanation") or {}
    expl_text = _render_content(expl.get("content", ""), expl.get("items", []))
    if expl_text:
        return f"{text} ({expl_text})"
    return text


def _render_definition(defn: dict, prefix: str) -> Sense:
    explanations: list[str] = []
    examples: list[str] = []
    subsenses: list[Sense] = []
    n = 0
    for el in defn.get("elements", []):
        t = el.get("type_")
        if t == "explanation":
            text = _render_explanation(el)
            if text:
                explanations.append(text)
        elif t == "example":
            text = _render_example(el)
            if text:
                examples.append(text)
        elif t == "definition":
            n += 1
            subsenses.append(_render_definition(el, f"{prefix}{chr(96 + n)}"))
        # Andre typer (f.eks. "compound_list", "explanation_relation") hoppes
        # stille over - de dukker opp i noen artikler, men er ikke
        # nødvendige for et brukbart oppslag.
    return Sense(number=prefix, text="; ".join(explanations), examples=examples, subsenses=subsenses)


def _render_definitions(defs: list[dict]) -> list[Sense]:
    """Toppnivå-`definitions` er ofte bare en wrapper rundt de faktiske,
    nummererte betydningene (nestet som `definition`-elementer uten egen
    forklaringstekst på wrapper-nivået). Håndter begge tilfeller."""
    senses: list[Sense] = []
    n = 0
    for d in defs:
        elements = d.get("elements", [])
        nested_defs = [e for e in elements if e.get("type_") == "definition"]
        direct_content = [e for e in elements if e.get("type_") in ("explanation", "example")]
        if nested_defs and not direct_content:
            for nd in nested_defs:
                n += 1
                senses.append(_render_definition(nd, str(n)))
        else:
            n += 1
            senses.append(_render_definition(d, str(n)))
    return senses


def _render_content_list(items: list[dict]) -> Optional[str]:
    parts = [_render_content(i.get("content", ""), i.get("items", [])) for i in items]
    parts = [p for p in parts if p]
    return "; ".join(parts) if parts else None


def _collect_sub_articles(node: Any) -> Iterator[dict]:
    """Finn alle `sub_article`-noder (faste uttrykk/idiomer) hvor som helst
    i `body`-treet."""
    if isinstance(node, dict):
        if node.get("type_") == "sub_article":
            yield node
        for v in node.values():
            yield from _collect_sub_articles(v)
    elif isinstance(node, list):
        for v in node:
            yield from _collect_sub_articles(v)


def _parse_expression(sub: dict) -> Expression:
    art = sub.get("article") or {}
    lemma_objs = art.get("lemmas", [])
    lemma_text = ", ".join(
        l.get("lemma", "") for l in lemma_objs if isinstance(l, dict) and l.get("lemma")
    )
    if not lemma_text:
        lemma_text = ", ".join(sub.get("lemmas", []) or [])
    body = art.get("body") or {}
    senses = _render_definitions(body.get("definitions", []))
    return Expression(lemma=lemma_text, senses=senses)


def _word_class_code(lemma_obj: dict) -> str:
    for pinfo in lemma_obj.get("paradigm_info", []) or []:
        tags = pinfo.get("tags") or []
        if tags:
            return tags[0]
    return ""


def _inflections(lemma_obj: dict) -> list[str]:
    forms: list[str] = []
    for pinfo in lemma_obj.get("paradigm_info", []) or []:
        for infl in pinfo.get("inflection", []) or []:
            wf = infl.get("word_form")
            if wf:
                forms.append(wf)
    return forms


def parse_article(raw: dict) -> Article:
    lemma_objs = raw.get("lemmas", []) or []
    lemmas = [l.get("lemma", "") for l in lemma_objs if l.get("lemma")]

    word_class_code = _word_class_code(lemma_objs[0]) if lemma_objs else ""
    word_class = WORD_CLASS_NAMES.get(word_class_code, word_class_code.lower())

    seen = set(lemmas)
    inflections: list[str] = []
    for l in lemma_objs:
        for form in _inflections(l):
            if form not in seen:
                seen.add(form)
                inflections.append(form)

    body = raw.get("body") or {}
    senses = _render_definitions(body.get("definitions", []))
    expressions = [_parse_expression(s) for s in _collect_sub_articles(body.get("definitions", []))]

    return Article(
        article_id=raw.get("article_id"),
        lemmas=lemmas,
        word_class=word_class,
        pronunciation=_render_content_list(body.get("pronunciation", []) or []),
        etymology=_render_content_list(body.get("etymology", []) or []),
        senses=senses,
        expressions=expressions,
        inflections=inflections,
    )


def iterate_articles(tar_path: Path) -> Iterator[Article]:
    """Åpner `article.tar.gz` og yielder én `Article` per `article/<id>.json`."""
    with tarfile.open(tar_path, mode="r:gz") as tar:
        for member in tar:
            if not member.isfile() or not member.name.endswith(".json"):
                continue
            f = tar.extractfile(member)
            if f is None:
                continue
            raw = json.load(f)
            if not raw.get("lemmas") or not raw.get("article_id"):
                continue
            yield parse_article(raw)
