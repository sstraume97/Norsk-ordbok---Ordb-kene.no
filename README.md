# ordboker-stardict

Automatisk genererte StarDict-ordbøker (`.ifo`/`.idx`/`.dict.dz`/`.syn`) av
Bokmålsordboka og Nynorskordboka fra [Ordbøkene.no](https://ordbokene.no),
samt to nettleselige/nedlastbare [Quarto](https://quarto.org)-bøker (én
per målform) med hele ordboka. Alt bygges **månedlig** med GitHub Actions.

## Hvordan det henger sammen

Data hentes fra UiBs offisielle nedlastingsside for ordlister
(<https://ord.uib.no/ord_1_Ordlister.html>), *ikke* API-et
(<https://ord.uib.no/ord_2_API.html>). Grunnen:

- `article.tar.gz` inneholder **alle** artikler i ett steg (ett
  `article/<id>.json` per artikkel), og UiB oppgir selv at filen
  "oppdateres hver uke, natt til mandag" - mer enn hyppig nok for en
  månedlig jobb.
- API-et (`/api/suggest`, `/api/articles`, `/dict/article/{id}.json`) er
  laget for enkeltoppslag/autocomplete i en levende app. Å bygge en full
  ordbok via API-et ville krevd å iterere over titusenvis av artikkel-ID-er
  med separate HTTP-kall - unødvendig tregt og unødvendig belastende for
  UiBs servere når hele datasettet allerede ligger klart som fil.

All parsing av selve artikkelstrukturen (rekursiv tolkning av
definisjoner, eksempler, faste uttrykk/idiomer, bøyningsformer,
kryssreferanser) ligger i én delt modul, `scripts/ordbok_parser.py`, som
både StarDict- og Quarto-genereringen bygger videre på. Dette gir samme
detaljnivå som selve ordbokene.no:

- **Bøyingstabell**, ikke bare en flat liste: substantiv får en ekte
  entall/flertall × ubestemt/bestemt-tabell (som på ordbokene.no), andre
  ordklasser (verb, adjektiv m.m.) får en enkel merkelapp/bøyd-form-liste.
  Ordklassenavn og bøyingsmerkelapper er hentet fra UiBs offisielle
  kodelister (`word_class.json`/`sub_word_class.json`).
- **Kryssreferanser** (f.eks. "trolle (I)", med homografnummer som
  romertall) blir ekte klikkbare lenker i Quarto-boka, og kursiv tekst i
  StarDict.
- **Sammensetningsanalyse** (f.eks. "troll + mann" for "trollmann") hentes
  fra **Norsk Ordbank** (Nasjonalbiblioteket/Språkbanken) - se eget avsnitt
  under.

### Norsk Ordbank (sammensetningsanalyse)

[Norsk Ordbank](https://www.nb.no/sprakbanken/ressurskatalog/oai-nb-no-sbr-5/)
(bokmål) og [tilsvarende for nynorsk](https://www.nb.no/sprakbanken/ressurskatalog/oai-nb-no-sbr-41/)
er et separat morfologisk leksikon fra Nasjonalbiblioteket/Språkbanken.
Bøyingsdataene der overlapper det vi allerede får fra `article.tar.gz`
(samme underliggende paradigmesystem), så vi bruker Norsk Ordbank *kun*
til `leddanalyse.txt` (sammensetningsanalyse - hvilke ord en
sammensetning er bygget av), som ikke finnes i Ordbøkene-artiklene.

`scripts/lib_ordbank.sh` finner og laster ned siste tilgjengelige
tar.gz-fil for hvert målform automatisk (filnavnene er datostemplet, så
vi henter alltid det nyeste treffet fra ressurskatalogsiden). Dette er
**beste innsats**: begge byggejobbene fortsetter uten
sammensetningsanalyse hvis nedlastingen skulle mislykkes, siden det bare
er en supplerende berikelse - ikke kjernedata. Lisens: CC-BY 4.0
(Nasjonalbiblioteket/Språkrådet/Universitetet i Bergen).

### StarDict - `.github/workflows/Build.yml`

1. Kjører kl. 05:00 UTC 1. i hver måned (og kan trigges manuelt via
   "Run workflow").
2. `scripts/build.sh` laster ned `article.tar.gz` for `bm` og `nn`,
   sammenligner SHA-256 med forrige kjøring (lagret i `state/`), og
   avbryter tidlig hvis ingenting er endret - da lages ingen ny release.
   - Manuell kjøring har en `force`-avkryssingsboks ("Run workflow") som
     tvinger et nytt bygg/release selv om kildedataene hos ord.uib.no er
     uendret - nyttig etter endringer i konverteringsskriptene selv
     (f.eks. formattering), siden hash-sjekken bare ser på kildedataene.
3. Ved endring: `scripts/ordbok_til_stardict.py` konverterer JSON til
   PyGlossary-tabfiler, og `pyglossary` bygger StarDict-filene
   (komprimert med `dictzip`).
   - Hvert lemma og alle bøyde former er alternative oppslagsord som
     peker til samme definisjon (f.eks. treffer "husene" artikkelen for
     "hus").
   - Faste uttrykk (idiomer, f.eks. "slå an" under "slå") får sitt eget
     oppslag med egen definisjon, siden de har en annen betydning enn
     grunnordet.
4. Ferdige ordbøker zippes til `dist/bm-stardict.zip` og
   `dist/nn-stardict.zip`, og publiseres som en
   [GitHub Release](../../releases) merket med datoen (via `gh release
   create`/`gh release upload` - idempotent, så en release som allerede
   finnes for dagens dato får oppdaterte filer i stedet for å feile).
5. `state/*.sha256` committes tilbake til repoet, slik at neste kjøring
   vet om noe har endret seg.

#### Nedlastingslenker

Hver release inneholder fire filer: `bm-stardict.zip`/`nn-stardict.zip`
(faste navn) og daterte kopier `bm-stardict-ÅÅÅÅ-MM-DD.zip`/
`nn-stardict-ÅÅÅÅ-MM-DD.zip` (utgaven fra en bestemt kjøring).

Fordi hver release markeres `--latest`, kan du alltid peke til siste
utgave med de faste filnavnene:

```
https://github.com/sstraume97/Norsk-ordbok---Ordb-kene.no/releases/latest/download/bm-stardict.zip
https://github.com/sstraume97/Norsk-ordbok---Ordb-kene.no/releases/latest/download/nn-stardict.zip
```

Vil du ha en bestemt tidligere utgave, bruk den daterte filen fra
[Releases](../../releases) i stedet.

### Quarto-bok - `.github/workflows/quarto-book.yml`

Kjører uavhengig av StarDict-jobben, kl. 07:00 UTC 1. i hver måned:

1. Laster ned `article.tar.gz` for `bm` og `nn` på nytt (egen kopi, ikke
   avhengig av at StarDict-jobben har kjørt).
2. `scripts/ordbok_til_quarto.py` genererer ett Quarto-kapittel per
   bokstav (A-Å + "0-9") i `book/bm/` og `book/nn/` - disse er generert
   innhold og committes ikke (se `.gitignore`).
3. Bygger **to separate** nettsteder - `quarto render book/bm --to html`
   og `quarto render book/nn --to html` - **disse to stegene må
   lykkes**, ellers feiler jobben. Bokmålsordboka og Nynorskordboka er
   bevisst to uavhengige Quarto-bokprosjekter, ikke ett kombinert: en
   tidligere versjon med én bok for begge målformer (~220 000
   oppslagsord i ett prosjekt) gikk tom for minne under rendering
   (Deno/V8-heap på ~8 GB) etter over en time, og hadde i tillegg et
   bug med kolliderende kryssreferanse-ID-er på tvers av målformene
   (samme artikkel-id kan eksistere uavhengig i både bm og nn). Å dele
   opp per målform løser ID-kollisjonen fullstendig; `search: false` er
   også satt i begge `_quarto.yml` for å holde minnebruken nede.
4. Bygger PDF og EPUB av hver bok (`--to pdf` / `--to epub`) som egne
   steg med `continue-on-error: true`. Bøkene er store, så disse kan i
   sjeldne tilfeller mislykkes (f.eks. pga. minnebruk i LaTeX) - da
   hopper vi bare over dem for denne måneden i stedet for å blokkere
   nettsidepubliseringen. Forrige måneds PDF/EPUB blir da liggende
   urørt på siden til neste vellykkede bygg.
5. Setter sammen `site/` (`book/index.html` som forside, pluss
   `book/bm/_book/` → `site/bm/` og `book/nn/_book/` → `site/nn/`) og
   publiserer det til GitHub Pages.

Forsiden (`book/index.html`, en enkel statisk side - ikke en egen
Quarto-bok) lenker til hver av de to bøkene. Hver bok har sin egen
[Last ned](book/bm/nedlasting.qmd)-side med lenker til sin StarDict-fil
og sin egen PDF/EPUB.

**Engangsoppsett:** for at Pages-publiseringen skal virke må du sette
**Settings → Pages → Source: GitHub Actions** i repoet. Dette er en
repo-innstilling som må gjøres manuelt i GitHub-grensesnittet.

## Kildekode

- `scripts/ordbok_parser.py` - delt parsing av `article.tar.gz` til en
  `Article`-struktur (lemmaer m/homografnummer, ordklasse, uttale,
  etymologi, betydninger, faste uttrykk, bøyingstabeller,
  kryssreferanse-markører), samt lasting av Norsk Ordbanks
  sammensetningsanalyse.
- `scripts/ordbok_til_stardict.py` - `Article` → PyGlossary-tabfile
  (HTML-formatert definisjon, med bøyingstabell som HTML-tabell).
- `scripts/ordbok_til_quarto.py` - `Article` → Quarto-kapitler
  (Markdown, med bøyingstabell som Markdown-tabell og ekte
  kryssreferanselenker), gruppert alfabetisk.
- `scripts/build.sh` - orkestrerer nedlasting, endringssjekk og
  StarDict-bygg.
- `scripts/lib_ordbank.sh` - delt hjelpefunksjon for å hente Norsk
  Ordbank (brukes av `build.sh` og `quarto-book.yml`).
- `book/index.html` - statisk forside som lenker til de to bøkene.
- `book/bm/`, `book/nn/` - to separate Quarto-bokprosjekter (egen
  `_quarto.yml`/`index.qmd`/`nedlasting.qmd` per målform, samt generert
  kapittelinnhold som ikke committes).

## Lisens på dataene

Ordboksdataene er CC-BY 4.0 (Universitetet i Bergen / Språkrådet) - oppgi
kilde ved videre bruk. Se <https://ord.uib.no/ord_1_Ordlister.html>.
Sammensetningsanalysen er fra Norsk Ordbank, også CC-BY 4.0
(Nasjonalbiblioteket/Språkbanken) - se
<https://www.nb.no/sprakbanken/ressurskatalog/oai-nb-no-sbr-5/>.
