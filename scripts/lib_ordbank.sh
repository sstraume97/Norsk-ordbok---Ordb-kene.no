#!/usr/bin/env bash
# Hjelpefunksjon for å hente Norsk Ordbank (Språkbanken/NB) - brukes av
# scripts/build.sh for å hente sammensetningsanalyse (leddanalyse.txt,
# se scripts/ordbok_parser.py).
#
# Beste innsats: feiler stille (lager ikke filen, men returnerer 0) hvis
# nedlasting mislykkes, siden dette bare er en supplerende berikelse -
# ikke kjernedata. Bøyingsdata i Norsk Ordbank overlapper det vi
# allerede får fra article.tar.gz, så vi bruker den kun til
# sammensetningsanalyse.
#
# Kilde: https://www.nb.no/sprakbanken/ressurskatalog/oai-nb-no-sbr-5/
# (bokmål 2005) og .../oai-nb-no-sbr-41/ (nynorsk 2012), CC-BY 4.0.

declare -A ORDBANK_CATALOG=(
    ["bm"]="https://www.nb.no/sprakbanken/ressurskatalog/oai-nb-no-sbr-5/"
    ["nn"]="https://www.nb.no/sprakbanken/ressurskatalog/oai-nb-no-sbr-41/"
)
declare -A ORDBANK_PATTERN=(
    ["bm"]="norsk_ordbank_nob_2005"
    ["nn"]="norsk_ordbank_nno_2012"
)

hent_ordbank() {
    local d="$1" out="$2"
    echo "== ${d}: henter Norsk Ordbank (sammensetningsanalyse, beste innsats) =="
    local url
    url=$(curl -sSL "${ORDBANK_CATALOG[$d]}" \
        | grep -oP "https://www\.nb\.no/sbfil/leksikalske_databaser/ordbank/[0-9]{8}_${ORDBANK_PATTERN[$d]}\.tar\.gz" \
        | sort -r | head -1) || true
    if [ -n "${url}" ] && curl -sSL --fail -o "${out}" "${url}"; then
        echo "   OK: ${url}"
    else
        echo "   Kunne ikke hente Norsk Ordbank for ${d} - fortsetter uten sammensetningsanalyse."
        rm -f "${out}"
    fi
}
