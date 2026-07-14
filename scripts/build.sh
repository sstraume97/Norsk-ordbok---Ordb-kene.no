#!/usr/bin/env bash
# Laster ned article.tar.gz for bokmål og nynorsk fra ord.uib.no,
# bygger StarDict-ordbøker med pyglossary, og hopper over bygget
# hvis kildedataene ikke er endret siden forrige kjøring.
#
# Forventer å kjøres fra repo-roten. Output:
#   dist/bm-stardict.zip
#   dist/nn-stardict.zip
#   state/bm.sha256, state/nn.sha256 (oppdatert hvis noe endret seg)
#
# Setter GITHUB_OUTPUT "changed=true|false" hvis miljøvariabelen finnes
# (dvs. når skriptet kjøres inne i en GitHub Actions-jobb).
#
# Sett FORCE_REBUILD=true for å tvinge bygg/release selv om
# kildedataene hos ord.uib.no ikke har endret seg siden forrige kjøring
# (f.eks. etter endringer i konverteringsskriptene) - brukes av
# workflow_dispatch-inputen "force" i .github/workflows/Build.yml.

set -euo pipefail

declare -A NAMES=( ["bm"]="Bokmålsordboka" ["nn"]="Nynorskordboka" )

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib_ordbank.sh"

FORCE_REBUILD="${FORCE_REBUILD:-false}"

mkdir -p dist tmp state

CHANGED=false
for d in bm nn; do
    echo "== ${d}: laster ned article.tar.gz =="
    curl -sSL --fail -o "tmp/${d}.tar.gz" "https://ord.uib.no/${d}/fil/article.tar.gz"

    NEW_HASH=$(sha256sum "tmp/${d}.tar.gz" | cut -d' ' -f1)
    OLD_HASH=$(cat "state/${d}.sha256" 2>/dev/null || echo "")
    echo "   ny hash:  ${NEW_HASH}"
    echo "   forrige:  ${OLD_HASH:-<ingen>}"

    if [ "${NEW_HASH}" != "${OLD_HASH}" ]; then
        CHANGED=true
    fi
    echo "${NEW_HASH}" > "tmp/${d}.sha256.new"
done

if [ "${FORCE_REBUILD}" = "true" ] && [ "${CHANGED}" = false ]; then
    echo "FORCE_REBUILD=true - bygger på nytt selv om kildedata er uendret."
    CHANGED=true
fi

if [ -n "${GITHUB_OUTPUT:-}" ]; then
    echo "changed=${CHANGED}" >> "${GITHUB_OUTPUT}"
fi

if [ "${CHANGED}" = false ]; then
    echo "Ingen endringer i datagrunnlaget hos ord.uib.no - hopper over bygg."
    exit 0
fi

for d in bm nn; do
    navn="${NAMES[$d]}"

    hent_ordbank "${d}" "tmp/${d}-ordbank.tar.gz"
    ORDBANK_ARG=()
    if [ -f "tmp/${d}-ordbank.tar.gz" ]; then
        ORDBANK_ARG=("tmp/${d}-ordbank.tar.gz")
    fi

    echo "== ${d}: konverterer til tabfile =="
    python3 "${SCRIPT_DIR}/ordbok_til_stardict.py" "tmp/${d}.tar.gz" "tmp/${d}.txt" "${ORDBANK_ARG[@]}"

    echo "== ${d}: bygger StarDict med pyglossary =="
    rm -rf "tmp/${d}-stardict"
    mkdir -p "tmp/${d}-stardict"
    pyglossary "tmp/${d}.txt" "tmp/${d}-stardict/${d}.ifo" \
        --read-format=Tabfile --write-format=Stardict \
        --write-options 'dictzip=True' \
        --name "${navn}"

    echo "== ${d}: zipper =="
    (cd "tmp/${d}-stardict" && zip -q -r "../../dist/${d}-stardict.zip" .)

    mv "tmp/${d}.sha256.new" "state/${d}.sha256"
done

echo "Ferdig. Nye filer i dist/: $(ls dist)"
