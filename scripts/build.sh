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

set -euo pipefail

declare -A NAMES=( ["bm"]="Bokmålsordboka" ["nn"]="Nynorskordboka" )

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

if [ -n "${GITHUB_OUTPUT:-}" ]; then
    echo "changed=${CHANGED}" >> "${GITHUB_OUTPUT}"
fi

if [ "${CHANGED}" = false ]; then
    echo "Ingen endringer i datagrunnlaget hos ord.uib.no - hopper over bygg."