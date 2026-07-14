"""
Målrettede enhetstester for ordbok_parser.py mot ekte, lagrede artikler
(tests/fixtures/). Disse dokumenterer og beskytter konkret,
navngitt oppførsel - i motsetning til tests/test_stardict_golden.py,
som fanger opp ENHVER endring i det ferdige HTML-resultatet.
"""

from conftest import load_fixture
from ordbok_parser import parse_article


def test_trollmann_substantiv_med_kjonn_og_bøying():
    art = parse_article(load_fixture("trollmann"))
    assert art.word_class == "substantiv (hankjønn)"
    assert art.lemmas == ["trollmann"]

    assert len(art.inflection_tables) == 1
    lemma, table = art.inflection_tables[0]
    assert table.kind == "grid"
    assert table.article == "en"
    assert table.cells[("entall", "ubestemt form")] == ["trollmann"]
    assert table.cells[("entall", "bestemt form")] == ["trollmannen"]
    assert table.cells[("flertall", "ubestemt form")] == ["trollmenn"]
    assert table.cells[("flertall", "bestemt form")] == ["trollmennene"]


def test_trollmann_sammensetning_krever_norsk_ordbank():
    # Uten Norsk Ordbank-data skal ikke sammensetningsanalyse dukke opp
    # noe sted i Article - det hentes separat av load_compound_analysis().
    art = parse_article(load_fixture("trollmann"))
    assert not hasattr(art, "compound_analysis")


def test_trollmann_kryssreferanse_med_homografnummer():
    art = parse_article(load_fixture("trollmann"))
    sense_texts = [s.text for s in art.senses]
    assert any("{{ref:62363:trolle (I)}}" in t for t in sense_texts), sense_texts


def test_skaar_flere_stavemåter_egne_bøyingstabeller():
    # "skår"/"score" er alternative stavemåter av samme artikkel - hver
    # skal få sin EGEN bøyingstabell, ikke en sammenblandet en (dette
    # var en reell bug tidligere: siste stavemåte overskrev den første).
    art = parse_article(load_fixture("skaar"))
    assert art.lemmas == ["skår", "score"]
    assert len(art.inflection_tables) == 2

    by_lemma = dict(art.inflection_tables)
    assert by_lemma["skår"].cells[("entall", "ubestemt form")] == ["skår"]
    assert by_lemma["score"].cells[("entall", "ubestemt form")] == ["score"]


def test_haar_domain_entitet_gir_lesbar_tekst_ikke_rå_kode():
    # "i_bot" er en "domain"-type, strukturelt ulik "entity" - denne
    # testen fanger opp regresjonen der ukjente elementtyper lekket rå
    # koder med understreker rett i teksten.
    art = parse_article(load_fixture("haar"))
    sense_texts = " ".join(s.text for s in art.senses)
    assert "i botanikk" in sense_texts
    assert "i_bot" not in sense_texts


def test_haar_faste_uttrykk_har_full_forklaring():
    art = parse_article(load_fixture("haar"))
    by_lemma = {e.lemma: e for e in art.expressions}
    assert "et hår i suppa" in by_lemma
    assert by_lemma["et hår i suppa"].senses[0].text == "noe som er ubehagelig eller ubeleilig"


def test_fin_adjektiv_full_bøyingstabell():
    art = parse_article(load_fixture("fin"))
    assert art.word_class == "adjektiv"
    assert len(art.inflection_tables) == 1
    _, table = art.inflection_tables[0]
    assert table.kind == "adj"
    assert len(table.adj_rows) == 1
    row = table.adj_rows[0]
    assert row.positiv == {
        "hankjønn/hunkjønn": "fin",
        "intetkjønn": "fint",
        "bestemt form": "fine",
        "flertall": "fine",
    }
    assert row.komparativ == "finere"
    assert row.superlativ == {"ubestemt": "finest", "bestemt": "fineste"}


def test_haap_sideformer_i_samme_celle_ikke_overskrevet():
    # "håpa, håpene" - flere aksepterte bestemt-flertall-former skal
    # samles i én celle, ikke overskrive hverandre.
    art = parse_article(load_fixture("haap"))
    _, table = art.inflection_tables[0]
    assert table.cells[("flertall", "bestemt form")] == ["håpa", "håpene"]


def test_jamfore_flere_stavemåter_egne_lemmaer():
    art = parse_article(load_fixture("jamfore"))
    assert art.lemmas == ["jamføre", "jevnføre"]
    assert art.word_class == "verb"


def test_slaa_mange_faste_uttrykk():
    art = parse_article(load_fixture("slaa"))
    assert art.lemmas == ["slå"]
    assert len(art.expressions) > 30
    names = {e.lemma for e in art.expressions}
    assert "slå an" in names
