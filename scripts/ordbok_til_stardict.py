#!/usr/bin/env python3
"""
Konverterer artikkeldata fra ord.uib.no (Ordbøkene, UiB/Språkrådet)
til PyGlossary-tabfile, som deretter kan bygges til StarDict.

Bruk:
    1. Last ned datafil:
       curl -O https://ord.uib.no/bm/fil/article.tar.gz   (bokmål)
       curl -O https://ord.uib.no/nn/fil/article.tar.gz   (nynorsk)

    2. Kjør skriptet (tar også en mappe med .json-filer):
       python3 ordbok_til_stardict.py article.tar.gz bokmaal.txt

    3. Bygg StarDict med PyGlossary:
       pip install pyglossary
       pyglossary bokmaal.txt bokmaal.ifo \
           --read-format=Tabfile --write-format=Stardict \
           --name "Bokmålsordboka"

Bøyde former og faste uttrykk (sub-artikler) legges inn som
synonymer (.syn), slik at oppslag på f.eks. "husene" eller
"fra A til B" treffer riktig artikkel.

Lisens på dataene: CC-BY 4.0 (UiB/Språkrådet) - oppgi kilde.
"""

import html
import json
import sys
import tarfile
import gzip
from pathlib import Path

# Vanlige forkortelser brukt i entity/relation/grammar/language-elementer.
# Ukjente id-er vises som de er.
ABBREV = {
    "el": "el.", "e_l": "e.l.", "jf": "jf.", "fl": "fl.",
    "dvs": "dvs.", "osv": "osv.", "ogs": "også", "s_d": "s.d.",
    "if": "if.", "i_rel": "i rel.", "mots": "mots.", "sms": "sms.",
    "adj": "adj.", "adv": "adv.", "subst": "subst.", "prep": "prep.",
    "eg": "eg.", "overf": "overf.", "trans": "trans.", "intrans": "intrans.",
    "refl": "refl.", "upers": "upers.", "poet": "poet.", "dial": "dial.",