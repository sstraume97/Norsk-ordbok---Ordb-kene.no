#!/usr/bin/env python3
"""
Parsing-modul for Ordbøkene-artikler (ord.uib.no) og Norsk Ordbank
(Språkbanken/Nasjonalbiblioteket).

Leser `article.tar.gz` (ett `article/<id>.json` per artikkel, verifisert
mot ekte data fra UiB) og bygger en enkel, gjenbrukbar `Article`-struktur
som `ordbok_til_stardict.py` bygger videre på. All rekursiv tolkning av
`body`-elementer (definisjoner, eksempler, faste uttrykk,
bøyningsformer, kryssreferanser) skjer her.

Skjemaet er ikke offentlig dokumentert i detalj - det er utledet empirisk
fra ekte artikler (f.eks. https://ord.uib.no/bm/article/54131.json og
.../54676.json) og fra referansefilene `word_class.json`/
`sub_word_class.json` (https://ord.uib.no/bm/fil/word_class.json).
Ukjente/uventede elementtyper ignoreres stille i stedet for å feile,
siden ordboka er stor og har mange kant-tilfeller.

Kryssreferanser (`article_ref`) rendres som en markør
`{{ref:<artikkel-id>:<tekst>}}` i den rå teksten - se `resolve_refs()`,
som erstatter markøren med endelig visningsform helt til slutt (etter
escaping).

Lisens på dataene: CC-BY 4.0 (UiB/Språkrådet, og Nasjonalbiblioteket for
Norsk Ordbank) - oppgi kilde.
"""

from __future__ import annotations

import csv
import io
import json
import re
import tarfile
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterator, Optional

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


# Fagfelt-koder ("domain") brukt til å sette emneetiketter foran
# forklaringer, f.eks. "i botanikk: ..." eller "i den katolske kirke:
# ...". Koder med prefiks "i_"/"o_" kombineres med "i "/"om " + oppslag
# (uten prefiks); koder uten prefiks settes inn direkte i setningsmalen.
# Satt sammen empirisk fra hyppigst brukte koder i kildedataene - ukjente
# koder faller tilbake til samme transkripsjon som `_fallback_entity()`.
DOMAIN_NAMES = {
    "bot": "botanikk", "zool": "zoologi", "mus": "musikk", "idr": "idrett",
    "filos": "filosofi", "rel": "religion", "kjem": "kjemi", "mat": "matematikk",
    "gramm": "grammatikk", "fys": "fysikk", "astron": "astronomi", "jus": "jus",
    "jur": "jus", "med": "medisin", "mil": "militærvesen", "bibl": "bibelen",
    "pol": "politikk", "myt": "mytologi", "biol": "biologi", "bio": "biologi",
    "fysiol": "fysiologi", "geol": "geologi", "psyk": "psykologi", "anat": "anatomi",
    "typ": "typografi", "teol": "teologi", "dial": "dialekt",
    "spraakv": "språkvitenskap", "gr_myt": "gresk mytologi",
    "norr_myt": "norrøn mytologi", "norr_forh": "norrøne forhold",
    "tekn_s": "teknikken", "kat_e": "katolske",
}


def _render_domain(domain_id: str) -> str:
    if domain_id.startswith("i_"):
        code = domain_id[2:]
        return f"i {DOMAIN_NAMES.get(code, _fallback_entity(code))}"
    if domain_id.startswith("o_"):
        code = domain_id[2:]
        return f"om {DOMAIN_NAMES.get(code, _fallback_entity(code))}"
    return DOMAIN_NAMES.get(domain_id, _fallback_entity(domain_id))


def _fallback_entity(entity_id: str) -> str:
    """Best-effort formatering av entitets-id-er som ikke finnes i
    ABBREV: `aa`/`ae`/`oe` transkriberes til `å`/`æ`/`ø`, og understrek
    blir mellomrom. Gir et lesbart (om enn uoffisielt) resultat i stedet
    for å vise rå kode med understreker."""
    text = entity_id
    for src, dst in (("aa", "å"), ("ae", "æ"), ("oe", "ø")):
        text = text.replace(src, dst)
    return text.replace("_", " ")


# Ordklassekoder (fra lemma.paradigm_info.tags[0]) -> lesbart navn på
# norsk. Kilde: https://ord.uib.no/bm/fil/word_class.json (offisiell
# kodeliste, felles for bokmål og nynorsk).
WORD_CLASS_NAMES = {
    "ABBR": "forkorting", "ADJ": "adjektiv", "ADP": "preposisjon",
    "ADV": "adverb", "CCONJ": "konjunksjon", "COMPPFX": "i sammensetting",
    "DET": "determinativ", "DET_Q": "tallord", "EXPR": "uttrykk",
    "INFM": "infinitivsmerke", "INTJ": "interjeksjon", "NOUN": "substantiv",
    "PFX": "prefiks", "PRON": "pronomen", "PROPN": "egennavn",
    "SCONJ": "subjunksjon", "SFX": "suffiks", "SYM": "symbol",
    "UNKN": "ukjent", "VERB": "verb", "VSTEM": "verbstamme",
}

# Kjønn/tall/grad-koder brukt i bøyingstagger -> lesbart navn.
GENDER_NAMES = {
    "Masc": "hankjønn", "Fem": "hunkjønn", "Neuter": "intetkjønn",
    "Masc/Fem": "felleskjønn",
}

# Bøyingstagger -> lesbart navn, brukt til å bygge bøyingstabeller.
TAG_LABELS = {
    "Sing": "entall", "Plur": "flertall",
    "Ind": "ubestemt form", "Def": "bestemt form",
    "Pos": "positiv", "Cmp": "komparativ", "Sup": "superlativ",
    "Inf": "infinitiv", "Pres": "presens", "Past": "preteritum",
    "Imp": "imperativ", "Nom": "nominativ", "Acc": "akkusativ",
    "Pass": "passiv", "<PerfPart>": "perfektum partisipp",
    "<PresPart>": "presens partisipp", "<SPass>": "s-passiv",
    **GENDER_NAMES,
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
class InflectionForm:
    tags: list[str]
    word_form: str


@dataclass
class InflectionTable:
    """`kind == "grid"`: substantiv-tabell som på ordbokene.no - to
    kolonnegrupper (`col_groups`, f.eks. entall/flertall), hver med de
    samme underkolonnene (`sub_cols`, f.eks. ubestemt form/bestemt
    form). `cells[(gruppe, underkolonne)]` er en liste med bøyde former
    (mer enn én ved sideformer, f.eks. "håpa, håpene"). `article` er
    ubestemt kjønnsartikkel (en/ei/et) satt foran ubestemt entallsform,
    hvis kjent. `kind == "list"`: enkel (merkelapp, bøyd form)-liste,
    brukt for ordklasser uten en naturlig 2D-tabell (verb, adjektiv
    m.m.)."""

    kind: str
    col_groups: list[str] = field(default_factory=list)
    sub_cols: list[str] = field(default_factory=list)
    cells: dict[tuple[str, str], list[str]] = field(default_factory=dict)
    article: Optional[str] = None
    rows: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class Article:
    article_id: int
    lemmas: list[str]
    lemma_display: list[str]
    word_class_code: str
    word_class: str
    pronunciation: Optional[str]
    etymology: Optional[str]
    senses: list[Sense]
    expressions: list[Expression]
    inflection_forms: list[InflectionForm]
    inflection_tables: list[tuple[str, InflectionTable]]

    @property
    def first_letter(self) -> str:
        return letter_bucket(self.lemmas[0] if self.lemmas else "")

    @property
    def inflection_word_forms(self) -> list[str]:
        """Flat, deduplisert liste av alle bøyde former (uavhengig av
        tabellstruktur) - brukt som ekstra oppslagsord i StarDict."""
        seen = set(self.lemmas)
        out = []
        for infl in self.inflection_forms:
            if infl.word_form not in seen:
                seen.add(infl.word_form)
                out.append(infl.word_form)
        return out


_ROMAN = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]


def _lemma_display_text(lemma: str, hgno: int) -> str:
    """Legger til homografnummer som romertall, f.eks. "trolle (I)",
    slik ordbokene.no viser det når samme staving har flere artikler."""
    if lemma and 1 <= hgno < len(_ROMAN):
        return f"{lemma} ({_ROMAN[hgno]})"
    return lemma


def letter_bucket(lemma: str) -> str:
    """Grupperingsbokstav for kapittelinndeling (A-Å, ellers '0-9')."""
    if not lemma:
        return "0-9"
    ch = lemma[0].upper()
    return ch if ch.isalpha() else "0-9"


# --- Kryssreferanser -------------------------------------------------
#
# `{{ref:<artikkel-id>:<tekst>}}` er en intern markør som overlever
# escaping (ingen av tegnene `{`, `}`, `:` er i noen escape-tabell), og
# løses til et faktisk lenkeformat helt til slutt av hver konsument.

_REF_RE = re.compile(r"\{\{ref:(\d+):(.*?)\}\}")


def resolve_refs(text: str, resolver: Callable[[int, str], str]) -> str:
    """Erstatter `{{ref:id:tekst}}`-markører i `text` med
    `resolver(article_id, tekst)`. Kalles av konsumentene *etter*
    HTML-/Markdown-escaping, slik at resolver kan sette inn klarert
    markup (lenker) uten at det blir escapet på nytt."""
    return _REF_RE.sub(lambda m: resolver(int(m.group(1)), m.group(2)), text)


# Elementtyper som er strukturelt identiske med "entity" (rent
# id-oppslag mot ABBREV/fallback) - bare ulike semantiske kategorier
# (språk, kryssreferanseord, grammatisk term, retorisk term, tidsuttrykk).
_ENTITY_LIKE_TYPES = {"entity", "language", "relation", "grammar", "rhetoric", "temporal"}


def _render_item(item: dict) -> str:
    t = item.get("type_")
    if t in _ENTITY_LIKE_TYPES:
        entity_id = item.get("id", "")
        resolved = ABBREV.get(entity_id, _fallback_entity(entity_id))
        # Språkforkortelser ("language") mangler ofte avsluttende punktum
        # i kildedataene (f.eks. id "eng" i stedet for "eng."), i
        # motsetning til samme forkortelse brukt som "entity" i
        # etymologi. Legg til punktum konsekvent for lesbarhet.
        if t == "language" and resolved and not resolved.endswith("."):
            resolved += "."
        return resolved
    if t == "domain":
        return _render_domain(item.get("id", ""))
    if t == "usage":
        return item.get("text", "")
    if t == "article_ref":
        lemmas = item.get("lemmas") or []
        text = ", ".join(
            _lemma_display_text(l.get("lemma", ""), l.get("hgno", 0) or 0)
            for l in lemmas
            if isinstance(l, dict)
        )
        article_id = item.get("article_id")
        if text and article_id is not None:
            return f"{{{{ref:{article_id}:{text}}}}}"
        return text
    if t == "lemma":
        return item.get("lemma", "")
    if t in ("pronunciation_guide", "quote_inset"):
        return _render_content(item.get("content", ""), item.get("items", []))
    if t == "fraction":
        return f"{item.get('numerator', '')}/{item.get('denominator', '')}"
    # Ukjent elementtype (f.eks. superscript/subscript, som allerede har
    # et lesbart "text"-felt): bruk tekst/id hvis det finnes, ellers tomt.
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


def _gender_code(lemma_obj: dict) -> Optional[str]:
    for pinfo in lemma_obj.get("paradigm_info", []) or []:
        for tag in pinfo.get("tags") or []:
            if tag in GENDER_NAMES:
                return tag
    return None


def _inflection_forms(lemma_obj: dict) -> list[InflectionForm]:
    forms: list[InflectionForm] = []
    for pinfo in lemma_obj.get("paradigm_info", []) or []:
        for infl in pinfo.get("inflection", []) or []:
            wf = infl.get("word_form")
            if wf:
                forms.append(InflectionForm(tags=infl.get("tags", []) or [], word_form=wf))
    return forms


# Ubestemt kjønnsartikkel satt foran ubestemt entallsform i
# bøyingstabellen, slik ordbokene.no gjør det (f.eks. "et håp").
ARTICLE_BY_GENDER = {"Masc": "en", "Fem": "ei", "Neuter": "et", "Masc/Fem": "en"}


def _build_inflection_table(
    word_class_code: str, forms: list[InflectionForm], gender_code: Optional[str] = None
) -> Optional[InflectionTable]:
    if not forms:
        return None

    if word_class_code == "NOUN":
        grid: dict[tuple[str, str], list[str]] = defaultdict(list)
        for infl in forms:
            tags = set(infl.tags)
            col = "flertall" if "Plur" in tags else "entall" if "Sing" in tags else None
            sub = "bestemt form" if "Def" in tags else "ubestemt form" if "Ind" in tags else None
            if col and sub and infl.word_form not in grid[(col, sub)]:
                grid[(col, sub)].append(infl.word_form)
        if grid:
            col_groups = ["entall", "flertall"]
            sub_cols = ["ubestemt form", "bestemt form"]
            cells = {(g, s): grid.get((g, s), []) for g in col_groups for s in sub_cols}
            if any(cells.values()):
                return InflectionTable(
                    kind="grid",
                    col_groups=col_groups,
                    sub_cols=sub_cols,
                    cells=cells,
                    article=ARTICLE_BY_GENDER.get(gender_code),
                )

    # Fallback for andre ordklasser (verb, adjektiv, pronomen m.m.): en
    # enkel (merkelapp, bøyd form)-liste i stedet for en 2D-tabell, siden
    # disse paradigmene ikke har en naturlig entall/flertall-grid.
    rows: list[tuple[str, str]] = []
    seen = set()
    for infl in forms:
        label = " ".join(TAG_LABELS.get(t, t) for t in infl.tags) or "-"
        key = (label, infl.word_form)
        if key in seen:
            continue
        seen.add(key)
        rows.append((label, infl.word_form))
    return InflectionTable(kind="list", rows=rows) if rows else None


def parse_article(raw: dict) -> Article:
    lemma_objs = raw.get("lemmas", []) or []
    lemmas = [l.get("lemma", "") for l in lemma_objs if l.get("lemma")]
    lemma_display = [
        _lemma_display_text(l.get("lemma", ""), l.get("hgno", 0) or 0)
        for l in lemma_objs
        if l.get("lemma")
    ]

    word_class_code = _word_class_code(lemma_objs[0]) if lemma_objs else ""
    word_class = WORD_CLASS_NAMES.get(word_class_code, word_class_code.lower())
    if word_class_code == "NOUN":
        gender_code = _gender_code(lemma_objs[0]) if lemma_objs else None
        if gender_code:
            word_class = f"{word_class} ({GENDER_NAMES[gender_code]})"

    # Bøyingstabell bygges PER stavemåte (lemma_obj) - en artikkel kan ha
    # flere alternative stavemåter (f.eks. "skår"/"score"), hver med sitt
    # eget fullstendige bøyingsparadigme som ikke skal blandes sammen.
    inflection_forms: list[InflectionForm] = []
    inflection_tables: list[tuple[str, InflectionTable]] = []
    for l in lemma_objs:
        forms = _inflection_forms(l)
        inflection_forms.extend(forms)
        table = _build_inflection_table(word_class_code, forms, _gender_code(l))
        if table:
            inflection_tables.append((l.get("lemma", ""), table))

    body = raw.get("body") or {}
    senses = _render_definitions(body.get("definitions", []))
    expressions = [_parse_expression(s) for s in _collect_sub_articles(body.get("definitions", []))]

    return Article(
        article_id=raw.get("article_id"),
        lemmas=lemmas,
        lemma_display=lemma_display,
        word_class_code=word_class_code,
        word_class=word_class,
        pronunciation=_render_content_list(body.get("pronunciation", []) or []),
        etymology=_render_content_list(body.get("etymology", []) or []),
        senses=senses,
        expressions=expressions,
        inflection_forms=inflection_forms,
        inflection_tables=inflection_tables,
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


# --- Norsk Ordbank (Språkbanken/NB) - sammensetningsanalyse ----------
#
# Bøyingsdata i Norsk Ordbank overlapper det vi allerede får fra
# article.tar.gz (samme kilde), så vi bruker den *kun* til
# sammensetningsanalyse (`leddanalyse.txt`), som ikke finnes i
# Ordbøkene-artiklene. Se https://www.nb.no/sprakbanken/ressurskatalog/
# (oai-nb-no-sbr-5 for bokmål, oai-nb-no-sbr-41 for nynorsk).


def load_compound_analysis(tar_path: Path) -> dict[str, list[str]]:
    """Leser sammensetningsanalyse-filen fra en Norsk Ordbank-tar.gz og
    bygger en oppslagstabell fra lemma (små bokstaver) til formaterte
    sammensetningsanalyser (f.eks. "troll + mann"). Enkle former uten
    forledd/etterledd ("simplex") hoppes over.

    Filnavnet varierer mellom målformer (f.eks. `leddanalyse.txt` for
    bokmål 2005, `leddanalyse_2012.txt` for nynorsk 2012), så vi finner
    medlemmet ved å lete etter "leddanalyse" i navnet i stedet for å
    anta én bestemt filnavnsform."""
    compounds: dict[str, list[str]] = defaultdict(list)
    with tarfile.open(tar_path, mode="r:gz") as tar:
        member_name = next(
            (m.name for m in tar.getmembers() if "leddanalyse" in m.name.lower()), None
        )
        if member_name is None:
            return {}
        f = tar.extractfile(member_name)
        if f is None:
            return {}
        reader = csv.DictReader(io.TextIOWrapper(f, encoding="iso-8859-1"), delimiter="\t")
        for row in reader:
            forledd = (row.get("FORLEDD") or "").strip()
            etterledd = (row.get("ETTERLEDD") or "").strip()
            word = (row.get("OPPSLAG") or "").strip().lower()
            if not forledd or not etterledd or not word:
                continue
            analysis = f"{forledd} + {etterledd}"
            if analysis not in compounds[word]:
                compounds[word].append(analysis)
    return dict(compounds)
