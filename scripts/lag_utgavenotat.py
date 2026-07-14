#!/usr/bin/env python3
"""
Sammenligner en ny lemmaliste (fra --lemma-list-out i
ordbok_til_stardict.py) mot forrige lagrede lemmaliste, og skriver en
markdown-oppsummering av nye/fjernede oppslagsord til stdout - brukt
som innhold i GitHub Release-notatene av scripts/build.sh.

Bruk:
    python3 lag_utgavenotat.py Bokmålsordboka tmp/bm.lemmas.txt state/bm.lemmas.txt

Første argument er visningsnavnet, andre er den nye lemmalista fra
denne kjøringen, tredje er forrige kjørings lagrede lemmaliste (kan
mangle ved aller første kjøring - da vises bare totalantallet, uten
diff).
"""

import sys
from pathlib import Path

MAKS_VIST = 40


def les_lemmaer(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}


def formater_liste(ord_: list[str]) -> str:
    vist = ord_[:MAKS_VIST]
    tekst = ", ".join(f"`{o}`" for o in vist)
    if len(ord_) > MAKS_VIST:
        tekst += f" (og {len(ord_) - MAKS_VIST} til)"
    return tekst


def lag_notat(navn: str, nye_ord: set[str], gamle_ord: set[str]) -> str:
    linjer = [f"### {navn}"]
    antall = f"{len(nye_ord):,}".replace(",", " ") + " oppslagsord totalt"

    if not gamle_ord:
        linjer.append(antall + " (første kjøring med endringssporing - ingen sammenligning ennå)")
        return "\n\n".join(linjer)

    lagt_til = sorted(nye_ord - gamle_ord)
    fjernet = sorted(gamle_ord - nye_ord)
    antall += f" ({len(lagt_til)} nye, {len(fjernet)} fjernet siden forrige utgave)"
    linjer.append(antall)
    if lagt_til:
        linjer.append(f"**Nye ord:** {formater_liste(lagt_til)}")
    if fjernet:
        linjer.append(f"**Fjernet:** {formater_liste(fjernet)}")
    return "\n\n".join(linjer)


def main() -> None:
    if len(sys.argv) != 4:
        print(f"Bruk: {sys.argv[0]} visningsnavn ny-lemmaliste.txt forrige-lemmaliste.txt", file=sys.stderr)
        raise SystemExit(1)
    navn, new_path, old_path = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    print(lag_notat(navn, les_lemmaer(new_path), les_lemmaer(old_path)))


if __name__ == "__main__":
    main()
