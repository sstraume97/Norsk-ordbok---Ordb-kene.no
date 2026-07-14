# ordboker-stardict

Automatisk genererte StarDict-ordbøker (`.ifo`/`.idx`/`.dict.dz`/`.syn`) av
Bokmålsordboka og Nynorskordboka fra [Ordbøkene.no](https://ordbokene.no),
samt en nettleselig/nedlastbar [Quarto](https://quarto.org)-bok med hele
ordboka. Begge bygges **månedlig** med GitHub Actions.

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
både StarDict- og Quarto-genereringen bygger videre på.

### StarDict - `.github/workflows/Build.yml`

1. Kjører kl. 05:00 UTC 1. i hver måned (og kan trigges manuelt via
   "Run workflow").
2. `scripts/build.sh` laster ned `article.tar.gz` for `bm` og `nn`,
   sammenligner SHA-256 med forrige kjøring (lagret i `state/`), og
   avbryter tidlig hvis ingenting er endret - da lages ingen ny release.
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
   [GitHub Release](../../releases) merket med datoen.
5. `state/*.sha256` committes tilbake til repoet, slik at neste kjøring
   vet om noe har endret seg.

#### Stabil nedlastingslenke

Fordi hver release markeres `make_latest: true`, kan du alltid peke til:

```
https://github.com/sstraume97/Norsk-ordbok---Ordb-kene.no/releases/latest/download/bm-stardict.zip
https://github.com/sstraume97/Norsk-ordbok---Ordb-kene.no/releases/latest/download/nn-stardict.zip
```

### Quarto-bok - `.github/workflows/quarto-book.yml`

Kjører uavhengig av StarDict-jobben, kl. 07:00 UTC 1. i hver måned:

1. Laster ned `article.tar.gz` for `bm` og `nn` på nytt (egen kopi, ikke
   avhengig av at StarDict-jobben har kjørt).
2. `scripts/ordbok_til_quarto.py` genererer ett Quarto-kapittel per
   bokstav (A-Å + "0-9") i `book/bm/` og `book/nn/` - disse er generert
   innhold og committes ikke (se `.gitignore`).
3. Bygger nettsiden (`quarto render book --to html`) - **dette steget må
   lykkes**, ellers feiler jobben.
4. Bygger PDF og EPUB av hele boka (`--to pdf` / `--to epub`) som egne
   steg med `continue-on-error: true`. Boka er stor (alle artikler i
   begge målformer), så disse kan i sjeldne tilfeller mislykkes (f.eks.
   pga. minnebruk i LaTeX) - da hopper vi bare over dem for denne
   måneden i stedet for å blokkere nettsidepubliseringen. Forrige
   måneds PDF/EPUB blir da liggende urørt på siden til neste vellykkede
   bygg.
5. Publiserer `book/_book/` til GitHub Pages.

Nettsiden har en egen [Last ned](book/nedlasting.qmd)-side med lenker
til siste StarDict-filer og bokas egen PDF/EPUB.

**Engangsoppsett:** for at Pages-publiseringen skal virke må du sette
**Settings → Pages → Source: GitHub Actions** i repoet. Dette er en
repo-innstilling som må gjøres manuelt i GitHub-grensesnittet.

## Kildekode

- `scripts/ordbok_parser.py` - delt parsing av `article.tar.gz` til en
  enkel `Article`-struktur (lemmaer, ordklasse, uttale, etymologi,
  betydninger, faste uttrykk, bøyningsformer).
- `scripts/ordbok_til_stardict.py` - `Article` → PyGlossary-tabfile
  (HTML-formatert definisjon).
- `scripts/ordbok_til_quarto.py` - `Article` → Quarto-kapitler
  (Markdown), gruppert alfabetisk.
- `scripts/build.sh` - orkestrerer nedlasting, endringssjekk og
  StarDict-bygg.
- `book/` - Quarto-bokprosjekt (`_quarto.yml`, `index.qmd`,
  `nedlasting.qmd`, samt generert innhold i `bm/`/`nn/`).

## Lisens på dataene

Ordboksdataene er CC-BY 4.0 (Universitetet i Bergen / Språkrådet) - oppgi
kilde ved videre bruk. Se <https://ord.uib.no/ord_1_Ordlister.html>.
