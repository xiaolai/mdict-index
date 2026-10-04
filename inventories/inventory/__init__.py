"""Lexical inventories built from the parsed dictionaries (see inventories/README.md)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent   # the repository: shared inputs live there
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))
from build_structured import STRUCTURED  # noqa: E402,F401  the parsed dictionaries, where the build writes them
DATA = ROOT / "inventories" / "data"                   # everything built; git-ignored (dictionary content)

# The publisher of each dictionary: evidence from two editions of one publisher is one voice.
# Oxford is three voices, by design: its learner's line (OALD, OCD), its dictionaries of current
# English (ODE, NOAD) and the OED are compiled by separate editorial teams.
PUBLISHER = {"oald": "oxford-learners", "oalecd": "oxford-learners", "ocd": "oxford-learners",
             "ode": "oxford", "noad": "oxford", "odecn": "oxford", "oed": "oxford-oed",
             "ldoce": "longman", "ldoce-ec": "longman", "cobuild": "collins", "cobuild-ec": "collins", "ced": "collins",
             "cald": "cambridge", "mwaled": "merriam-webster", "mwu": "merriam-webster", "mwc": "merriam-webster",
             "med": "macmillan", "ahd": "houghton-mifflin", "chambers": "chambers", "ncecd": "ncecd", "yhdcd": "yhdcd",
             "peu": "oxford", "cepd": "cambridge", "lpd": "longman", "etym": "etymonline"}
