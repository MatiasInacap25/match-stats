"""Maps team names from fixture feeds (fixturedownload, OpenLigaDB) to football-data.co.uk names."""

import re
import unicodedata

# Tokens that carry no identity in club names: legal forms, prefixes and sponsor-free filler.
_DROP_TOKENS = frozenset(
    ["fc", "cf", "afc", "sc", "sv", "vfl", "vfb", "tsg", "ac", "as", "ssc", "us", "rc", "ca", "cd", "ud", "rcd", "og", "stade", "de", "the"]
)

# Source name -> football-data name, for names normalize() cannot reconcile.
# Each target is a current-season football-data team (checked by the test suite).
ALIASES: dict[str, str] = {
    # Premier League
    "Man Utd": "Man United",
    "Spurs": "Tottenham",
    "Nottingham Forest": "Nott'm Forest",
    # La Liga
    "Athletic Club": "Ath Bilbao",
    "Atlético de Madrid": "Ath Madrid",
    "Atletico Madrid": "Ath Madrid",
    "Deportivo Alavés": "Alaves",
    "R. Racing Club": "Santander",
    "RC Deportivo": "La Coruna",
    "RCD Espanyol de Barcelona": "Espanol",
    "Rayo Vallecano": "Vallecano",
    "Real Betis": "Betis",
    "Real Sociedad": "Sociedad",
    # Serie A
    "Internazionale": "Inter",
    "AC Milan": "Milan",
    # Ligue 1
    "AJ Auxerre": "Auxerre",
    "Angers SCO": "Angers",
    "Estac Troyes": "Troyes",
    "Havre Athletic Club": "Le Havre",
    "LOSC Lille": "Lille",
    "OGC Nice": "Nice",
    "Olympique Lyonnais": "Lyon",
    "Olympique de Marseille": "Marseille",
    "Paris Saint-Germain": "Paris SG",
    "RC Strasbourg Alsace": "Strasbourg",
    "Stade Brestois 29": "Brest",
    "Stade Rennais FC": "Rennes",
    # Bundesliga
    "1. FSV Mainz 05": "Mainz",
    "Bayer 04 Leverkusen": "Leverkusen",
    "Borussia Dortmund": "Dortmund",
    "Borussia Mönchengladbach": "M'gladbach",
    "Eintracht Frankfurt": "Ein Frankfurt",
    "FC Bayern München": "Bayern Munich",
    "Hamburger SV": "Hamburg",
    "Sport-Club Freiburg": "Freiburg",
    # Championship
    "Birmingham City": "Birmingham",
    "Blackburn Rovers": "Blackburn",
    "Bolton Wanderers": "Bolton",
    "Cardiff City": "Cardiff",
    "Charlton Athletic": "Charlton",
    "Derby County": "Derby",
    "Lincoln City": "Lincoln",
    "Norwich City": "Norwich",
    "Preston North End": "Preston",
    "Queens Park Rangers": "QPR",
    "Stoke City": "Stoke",
    "Swansea City": "Swansea",
    "West Bromwich Albion": "West Brom",
    "West Ham United": "West Ham",
    "Wolverhampton Wanderers": "Wolves",
    # Eredivisie
    "ADO Den Haag": "Den Haag",
    "AZ": "AZ Alkmaar",
    "Excelsior Rotterdam": "Excelsior",
    "Fortuna Sittard": "For Sittard",
    "N.E.C. Nijmegen": "Nijmegen",
    "PEC Zwolle": "Zwolle",
    "PSV": "PSV Eindhoven",
    # Süper Lig
    "Istanbul Basaksehir": "Buyuksehyr",
    "Göztepe": "Goztep",
    "Çaykur Rizespor": "Rizespor",
    # Primeira Liga
    "Académico": "Academico Viseu",
    "Estoril Praia": "Estoril",
    "Estrela Amadora": "Estrela",
    "Marítimo M.": "Maritimo",
    "SC Braga": "Sp Braga",
    "SL Benfica": "Benfica",
    "Sporting CP": "Sp Lisbon",
    "Vitória SC": "Guimaraes",
    # UEFA competitions
    "Atleti": "Ath Madrid",
    "B. Dortmund": "Dortmund",
    "Bayern München": "Bayern Munich",
    "Leipzig": "RB Leipzig",
    "Braga": "Sp Braga",
    "Paris": "Paris SG",
}


def normalize(name: str) -> str:
    """Lowercase, accents removed, punctuation and digits-only tokens and filler tokens dropped."""
    decomposed = unicodedata.normalize("NFKD", name.lower())
    without_accents = "".join(char for char in decomposed if not unicodedata.combining(char))
    tokens = re.findall(r"[^\W\d_]+", without_accents)
    return " ".join(token for token in tokens if token not in _DROP_TOKENS)


def resolve(name: str, known: set[str]) -> str | None:
    """The football-data name for a source name, among `known` names; None when it cannot be told apart."""
    alias = ALIASES.get(name.strip())
    if alias is not None:
        return alias if alias in known else None

    key = normalize(name)
    if not key:
        return None
    matches = [candidate for candidate in known if normalize(candidate) == key]
    return matches[0] if len(matches) == 1 else None
