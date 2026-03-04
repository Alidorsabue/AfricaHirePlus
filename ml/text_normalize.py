"""
Normalisation de texte pour le matching ATS : insensible à la casse, aux accents,
aux apostrophes et aux pluriels courants. Permet de matcher "Gestion d'Informations"
avec le critère "gestion information".
"""
import re
import unicodedata


def normalize_for_match(text: str) -> str:
    """
    Normalise un texte pour la comparaison : minuscules, suppression des accents,
    apostrophes remplacées par un espace, espaces multiples fusionnés.
    """
    if not text or not isinstance(text, str):
        return ""
    # Minuscules
    text = text.lower().strip()
    # Suppression des accents (NFD puis retrait des caractères combinants)
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    # Apostrophes et guillemets → espace (pour "d'informations" → "d informations")
    text = re.sub(r"[\u0027\u2019\u2018\u00b4']", " ", text)
    # Espaces multiples → un seul
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _token_matches_text(token: str, normalized_text: str) -> bool:
    """
    Vérifie si un token (mot) apparaît dans le texte normalisé.
    Gère le pluriel courant : "information" matche "informations".
    """
    if not token or not normalized_text:
        return False
    if token in normalized_text:
        return True
    # Pluriel FR/EN : token + "s" ou token + "es" dans le texte
    if (token + "s") in normalized_text or (token + "es") in normalized_text:
        return True
    # Texte au pluriel, critère au singulier : token sans "s" final
    if token.endswith("s") and token[:-1] in normalized_text:
        return True
    if token.endswith("es") and token[:-2] in normalized_text:
        return True
    return False


def keyword_matches_text(keyword: str, normalized_text: str) -> bool:
    """
    Vérifie si un mot-clé (éventuellement multi-mots) est présent dans le texte normalisé.
    Insensible à la casse/accents/apostrophes ; gère les pluriels.
    Ex. keyword "gestion information" et texte "Gestion d'Informations" → True.
    """
    keyword_norm = normalize_for_match(keyword)
    if not keyword_norm:
        return False
    tokens = [t for t in keyword_norm.split() if len(t) >= 2]
    if not tokens:
        return keyword_norm in normalized_text
    # Tous les tokens doivent apparaître (ou leur pluriel)
    return all(_token_matches_text(t, normalized_text) for t in tokens)
