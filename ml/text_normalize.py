"""
Normalisation et matching tolérant pour l'ATS — version durcie.

Stratégie de matching (chaîne en cascade pour ne JAMAIS rejeter un bon CV pour un
problème orthographique ou linguistique) :

    1. Exact match (rapide, plus strict)
    2. Pluriel/singulier (FR + EN)
    3. Stemming léger FR/EN (radical des mots : développeur/développé/développement)
    4. Synonymes techniques (développeur ↔ developer, RH ↔ ressources humaines)
    5. Fuzzy matching (rapidfuzz si disponible, sinon difflib)

Toutes les comparaisons sont insensibles à la casse, aux accents, aux apostrophes et
aux pluriels courants.
"""
from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

# rapidfuzz est optionnel : si absent, on tombe sur difflib (plus lent mais identique en logique)
try:
    from rapidfuzz import fuzz as _rf_fuzz  # type: ignore
    _HAS_RAPIDFUZZ = True
except ImportError:  # pragma: no cover
    _rf_fuzz = None
    _HAS_RAPIDFUZZ = False


# ─────────────────────────────────────────────────────────────
# DICTIONNAIRE DE SYNONYMES (FR ↔ EN + variantes techniques)
# ─────────────────────────────────────────────────────────────
# Format : { terme_canonique: [variantes...] }
# Une recherche sur n'importe quelle variante matchera le terme canonique.

_SYNONYMS_RAW: dict[str, list[str]] = {
    # Métiers tech (FR ↔ EN)
    "developpeur": ["developer", "dev", "programmer", "programmeur", "codeur", "engineer logiciel", "ingenieur logiciel"],
    "analyste": ["analyst"],
    "data scientist": ["data analyst", "data engineer", "ds", "scientifique des donnees"],
    "data engineer": ["ingenieur data", "ingenieur donnees", "etl engineer"],
    "ingenieur": ["engineer", "ing", "eng"],
    "architecte": ["architect", "solution architect", "architecte solution"],
    "chef de projet": ["project manager", "pm", "project lead", "responsable projet"],
    "product owner": ["po", "product manager", "responsable produit"],
    "responsable": ["lead", "manager", "head", "chef", "directeur", "director"],
    "consultant": ["consultant", "advisor", "conseil"],
    "administrateur": ["admin", "administrator", "sysadmin"],
    "designer": ["graphiste", "ui designer", "ux designer", "ux/ui"],
    # Domaines
    "ressources humaines": ["rh", "hr", "human resources", "people", "talent"],
    "intelligence artificielle": ["ia", "ai", "artificial intelligence"],
    "apprentissage automatique": ["ml", "machine learning"],
    "apprentissage profond": ["dl", "deep learning"],
    "traitement du langage": ["nlp", "natural language processing", "tal", "traitement automatique langue"],
    "vision par ordinateur": ["cv", "computer vision", "vision artificielle"],
    "business intelligence": ["bi", "informatique decisionnelle"],
    "supply chain": ["chaine logistique", "logistique", "supply"],
    "monitoring evaluation": ["m&e", "suivi evaluation", "suivi-evaluation", "monitoring et evaluation"],
    "transfert monetaire": ["cash assistance", "cva", "cash voucher assistance", "aide monetaire"],
    # Frameworks / outils (variantes orthographiques)
    "javascript": ["js", "ecmascript", "es6", "es2015", "es2020"],
    "typescript": ["ts"],
    "nodejs": ["node js", "node.js", "node"],
    "postgresql": ["postgres", "psql"],
    "kubernetes": ["k8s"],
    "google cloud": ["gcp", "google cloud platform"],
    "amazon web services": ["aws"],
    "microsoft azure": ["azure"],
    "continuous integration": ["ci/cd", "ci cd", "cicd", "integration continue", "deploiement continu"],
    "rest api": ["api rest", "restful", "rest"],
    # Niveaux d'études
    "master": ["msc", "m.sc", "mba", "maitrise", "master 2"],
    "licence": ["bachelor", "bsc", "b.sc", "bac+3", "bac +3"],
    "doctorat": ["phd", "ph.d", "doctorate"],
    "ingenieur": ["engineer", "ing"],
    "baccalaureat": ["bac"],
    # Soft skills
    "communication": ["communicant", "communicante"],
    "leadership": ["manager", "management", "encadrement"],
    "autonomie": ["autonome", "self-driven", "self-starter"],
    "rigueur": ["rigorous", "meticuleux"],
    "creativite": ["creative", "creatif", "innovation"],
    "esprit d'equipe": ["team player", "teamwork", "travail d equipe", "esprit equipe"],
}


def _normalize_simple(s: str) -> str:
    """Normalisation rapide pour clé de synonymes (lowercase + sans accent)."""
    s = (s or "").lower().strip()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[\u0027\u2019\u2018\u00b4']", " ", s)
    return re.sub(r"\s+", " ", s).strip()


# Index inverse : variante normalisée → terme canonique normalisé
_SYNONYM_INDEX: dict[str, str] = {}
for _canonical, _variants in _SYNONYMS_RAW.items():
    _canonical_norm = _normalize_simple(_canonical)
    _SYNONYM_INDEX[_canonical_norm] = _canonical_norm
    for _v in _variants:
        _v_norm = _normalize_simple(_v)
        if _v_norm:
            _SYNONYM_INDEX[_v_norm] = _canonical_norm


def _canonical_synonym(token: str) -> str | None:
    """Retourne la forme canonique d'un token si un synonyme connu existe, sinon None."""
    if not token:
        return None
    norm = _normalize_simple(token)
    return _SYNONYM_INDEX.get(norm)


# ─────────────────────────────────────────────────────────────
# STEMMING LÉGER FR + EN (sans bibliothèque externe)
# ─────────────────────────────────────────────────────────────

# Suffixes français à supprimer pour obtenir un pseudo-radical
_FR_SUFFIXES = (
    "issement", "issements", "issants", "issante", "issants", "issant",
    "ements", "ements", "ement", "ements",
    "ables", "able", "ibles", "ible",
    "trices", "trice", "teurs", "teur",
    "tions", "tion", "sions", "sion",
    "ances", "ance", "ences", "ence",
    "iennes", "ienne", "iens", "ien",
    "euses", "euse", "eurs", "eur",
    "ières", "ière", "iers", "ier",
    "elles", "elle", "iels", "iel",
    "alement", "ales", "ale", "aux",
    "ifs", "ive", "ives", "if",
    "ée", "ées", "és", "er", "ir", "re",
    "ent", "ant",
    "s", "e",
)

# Suffixes anglais
_EN_SUFFIXES = (
    "ization", "ational", "fulness", "ousness", "iveness",
    "ization", "ation", "ement", "ation", "ment",
    "ingly", "edly",
    "ible", "able",
    "ness", "ment", "ship",
    "tion", "sion",
    "ance", "ence",
    "ing", "ed", "er", "or", "est",
    "ly", "ic", "al",
    "es", "s",
)


def _stem_token(token: str) -> str:
    """
    Stemming très léger : supprime les suffixes FR/EN les plus communs.
    Conserve au moins 3 caractères pour éviter sur-tronquage.

    Exemples :
      développeur → developp / développement → developp
      managing → manag / managed → manag / manager → manag
    """
    if not token or len(token) <= 4:
        return token
    t = token
    # FR
    for suffix in _FR_SUFFIXES:
        if t.endswith(suffix) and len(t) - len(suffix) >= 3:
            t = t[: -len(suffix)]
            break
    # EN
    for suffix in _EN_SUFFIXES:
        if t.endswith(suffix) and len(t) - len(suffix) >= 3:
            t = t[: -len(suffix)]
            break
    return t


# ─────────────────────────────────────────────────────────────
# NORMALISATION PRINCIPALE
# ─────────────────────────────────────────────────────────────

def normalize_for_match(text: str) -> str:
    """
    Normalise un texte pour la comparaison :
      - Minuscules
      - Suppression des accents
      - Apostrophes / guillemets → espace ("d'informations" → "d informations")
      - Espaces multiples fusionnés
    """
    if not text or not isinstance(text, str):
        return ""
    text = text.lower().strip()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r"[\u0027\u2019\u2018\u00b4']", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ─────────────────────────────────────────────────────────────
# FUZZY MATCHING (rapidfuzz si dispo, sinon difflib)
# ─────────────────────────────────────────────────────────────

def _ratio(a: str, b: str) -> float:
    """Ratio de similarité 0–1. Utilise rapidfuzz (token_set_ratio) si dispo, sinon SequenceMatcher."""
    if not a or not b:
        return 0.0
    if _HAS_RAPIDFUZZ:
        # token_set_ratio est résistant à l'ordre et aux mots manquants
        return _rf_fuzz.token_set_ratio(a, b) / 100.0  # type: ignore[union-attr]
    return SequenceMatcher(None, a, b).ratio()


def fuzzy_match(token: str, text: str, threshold: float = 0.85) -> bool:
    """
    Cherche un mot proche de `token` dans `text` (déjà normalisé).
    Renvoie True si on trouve une sous-chaîne d'au moins même longueur que `token`
    avec un ratio >= threshold.
    """
    if not token or not text:
        return False
    token_len = len(token)
    if token_len < 4:  # Trop court pour fuzzy ; risque de faux positif
        return False
    # On scanne par fenêtre coulissante de la même taille que token (±20 %)
    min_len = max(3, int(token_len * 0.8))
    max_len = int(token_len * 1.2) + 1
    text_words = text.split()
    for word in text_words:
        if min_len <= len(word) <= max_len:
            if _ratio(token, word) >= threshold:
                return True
    return False


# ─────────────────────────────────────────────────────────────
# MATCHING TOKEN (chaîne : exact → pluriel → stem → synonyme → fuzzy)
# ─────────────────────────────────────────────────────────────

def _token_matches_text(token: str, normalized_text: str, fuzzy: bool = True) -> bool:
    """
    Vérifie qu'un token apparaît dans le texte normalisé, avec tolérance maximale.
    Ordre : exact → pluriel → stem → synonyme → fuzzy.
    """
    if not token or not normalized_text:
        return False

    # 1) Match exact
    if token in normalized_text:
        return True
    # 2) Pluriels courants
    if (token + "s") in normalized_text or (token + "es") in normalized_text:
        return True
    if token.endswith("s") and token[:-1] in normalized_text:
        return True
    if token.endswith("es") and token[:-2] in normalized_text:
        return True
    # 3) Stem du token : chercher si la racine apparaît dans le texte
    stem = _stem_token(token)
    if stem and stem != token and len(stem) >= 4 and stem in normalized_text:
        return True
    # 4) Synonyme : si le token a une forme canonique connue, on cherche aussi
    canonical = _canonical_synonym(token)
    if canonical and canonical != token and canonical in normalized_text:
        return True
    # Recherche inverse : si un synonyme du token est dans le texte (parcours léger)
    norm_token = _normalize_simple(token)
    for variant, _can in _SYNONYM_INDEX.items():
        if _can == norm_token and variant in normalized_text:
            return True
    # 5) Fuzzy matching (dernière chance, seuil élevé pour éviter faux positifs)
    if fuzzy and fuzzy_match(token, normalized_text, threshold=0.88):
        return True
    return False


def keyword_matches_text(keyword: str, normalized_text: str, fuzzy: bool = True) -> bool:
    """
    Vérifie si un mot-clé (mono ou multi-mots) est présent dans le texte normalisé.
    Chaîne de fallback : exact, pluriels, stem, synonymes, fuzzy.

    Pour un mot-clé multi-tokens (ex. "data engineer"), TOUS les tokens doivent matcher
    individuellement (chacun avec sa chaîne complète de tolérance).
    """
    keyword_norm = normalize_for_match(keyword)
    if not keyword_norm:
        return False
    # Cas particulier : la forme exacte du mot-clé entier apparaît dans le texte
    if keyword_norm in normalized_text:
        return True
    # Multi-token : tous doivent matcher
    tokens = [t for t in keyword_norm.split() if len(t) >= 2]
    if not tokens:
        return keyword_norm in normalized_text
    return all(_token_matches_text(t, normalized_text, fuzzy=fuzzy) for t in tokens)


def keyword_similarity(keyword: str, text: str) -> float:
    """
    Renvoie un score 0–1 de similarité entre `keyword` et `text` (ratio fuzzy global).
    Utile pour scorer une « proximité » plutôt que prendre une décision binaire.
    """
    if not keyword or not text:
        return 0.0
    a = normalize_for_match(keyword)
    b = normalize_for_match(text)
    if not a or not b:
        return 0.0
    return round(_ratio(a, b), 4)
