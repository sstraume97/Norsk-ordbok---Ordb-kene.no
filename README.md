# ordboker-stardict

Automatisk genererte StarDict-ordbøker (`.ifo`/`.idx`/`.dict.dz`/`.syn`) av
Bokmålsordboka og Nynorskordboka fra [Ordbøkene.no](https://ordbokene.no),
bygget ukentlig med GitHub Actions.

## Hvordan det henger sammen

Data hentes fra UiBs offisielle nedlastingsside for ordlister
(<https://ord.uib.no/ord_1_Ordlister.html>), *ikke* API-et
(<https://ord.uib.no/ord_2_API.html>). Grunnen:

- `article.tar.gz` inneholder **alle** artikler i ett steg, og UiB oppgir
  selv at filen "oppdateres hver uke, natt til mandag" - perfekt for en
  ukentlig cron-jobb.
- API-et (`/api/suggest`, `/api/articles`, `/dict/article/{id}.json`) er
  laget for enkeltoppslag/autocomplete i en levende app. Å bygge en full
  ordbok via API-et ville krevd å iterere over titusenvis av artikkel-ID-er
  med separate HTTP-kall - unødvendig tregt og unødvendig belastende for
  UiBs servere når hele datasettet allerede ligger klart som fil.
### Kjøreplan

1. **`.github/workflows/build.yml`** kjører hver mandag kl. 05:00 UTC
   (og kan også trigges manuelt via "Run workflow").
2. **`scripts/build.sh`** laster ned `article.tar.gz` for `bm` og `nn`,
   sammenligner SHA-256 med forrige kjøring (lagret i `state/`), og
   avbryter tidlig hvis ingenting er endret - da lages ingen ny release.
3. Ved endring: **`scripts/ordbok_til_stardict.py`** konverterer JSON til
   PyGlossary-tabfiler, og `pyglossary` bygger StarDict-filene.
4. Ferdige ordbøker zippes til `dist/bm-stardict.zip` og
   `dist/nn-stardict.zip`, og publiseres som en
   [GitHub Release](../../releases) merket med datoen.
5. `state/*.sha256` committes tilbake til repoet, slik at neste kjøring
   vet om noe har endret seg.

### Stabil nedlastingslenke

Fordi hver release markeres `make_latest: true`, kan du alltid peke til:

```
https://github.com/<bruker>/<repo>/releases/latest/download/bm-stardict.zip 