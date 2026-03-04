"""
Matching sémantique : similarité entre le profil candidat (CV, compétences, expérience)
et l'offre (titre, description, exigences). Utilisé pour l'analyse sémantique et le scoring ML.

- Par défaut : TF-IDF + similarité cosinus (léger, multilingue, pas de GPU).
- Optionnel : sentence-transformers pour des embeddings sémantiques (si installé).
"""
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def _normalize_text(text: str) -> str:
    """Réduit espaces et caractères parasites pour améliorer le vectorisation."""
    if not text or not isinstance(text, str):
        return ""
    text = re.sub(r"\s+", " ", text.strip())
    return text.strip()[:50_000]  # limiter la taille pour perf


def _job_text(application: Any) -> str:
    """Texte côté offre : titre + description + exigences."""
    job = application.job_offer
    parts = [
        str(job.title or ""),
        str(job.description or ""),
        str(job.requirements or ""),
        str(job.benefits or ""),
    ]
    return _normalize_text(" ".join(parts))


def _candidate_text(application: Any) -> str:
    """Texte côté candidat : CV extrait, résumé, compétences, poste, expériences."""
    c = application.candidate
    parts = [
        str(c.raw_cv_text or ""),
        str(c.summary or ""),
        " ".join(c.skills or []),
        str(c.current_position or ""),
        str(c.education_level or ""),
        str(c.location or ""),
    ]
    for e in (c.experience or []):
        if isinstance(e, dict):
            parts.append(str(e.get("job_title") or ""))
            parts.append(str(e.get("responsibilities") or ""))
            parts.append(str(e.get("company_name") or ""))
    for edu in (c.education or []):
        if isinstance(edu, dict):
            parts.append(str(edu.get("discipline") or ""))
            parts.append(str(edu.get("institution") or ""))
    return _normalize_text(" ".join(parts))


def semantic_similarity_tfidf(job_text: str, candidate_text: str) -> float:
    """
    Similarité sémantique (0–1) via TF-IDF + cosinus.
    Fonctionne en multilingue (FR/EN), pas de GPU requis.
    """
    if not job_text.strip() or not candidate_text.strip():
        return 0.0
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
    except ImportError:
        logger.warning("ml.semantic_matching: scikit-learn non installé, similarité TF-IDF indisponible.")
        return 0.0
    try:
        vectorizer = TfidfVectorizer(
            max_features=10_000,
            ngram_range=(1, 2),
            min_df=1,
            strip_accents="unicode",
            lowercase=True,
        )
        matrix = vectorizer.fit_transform([job_text, candidate_text])
        sim = cosine_similarity(matrix[0:1], matrix[1:2])[0, 0]
        return round(float(max(0.0, min(1.0, sim))), 4)
    except Exception as e:
        logger.warning("ml.semantic_matching: erreur TF-IDF: %s", e)
        return 0.0


_SENTENCE_MODEL: Any = None
_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"


def _get_sentence_model() -> Any:
    """Charge et met en cache le modèle sentence-transformers (une fois par process)."""
    global _SENTENCE_MODEL
    if _SENTENCE_MODEL is None:
        try:
            from sentence_transformers import SentenceTransformer
            _SENTENCE_MODEL = SentenceTransformer(_MODEL_NAME)
        except Exception as e:
            logger.warning("ml.semantic_matching: chargement modèle %s: %s", _MODEL_NAME, e)
    return _SENTENCE_MODEL


def _semantic_similarity_embeddings(job_text: str, candidate_text: str) -> float | None:
    """
    Similarité via embeddings (sentence-transformers). Optionnel.
    Retourne None si la lib n'est pas installée ou en erreur.
    Modèle chargé une seule fois par process (cache).
    """
    try:
        from sklearn.metrics.pairwise import cosine_similarity
    except ImportError:
        return None
    model = _get_sentence_model()
    if model is None:
        return None
    try:
        emb_job = model.encode([job_text[:8000]], normalize_embeddings=True)
        emb_cand = model.encode([candidate_text[:8000]], normalize_embeddings=True)
        sim = float(cosine_similarity(emb_job, emb_cand)[0, 0])
        return round(max(0.0, min(1.0, sim)), 4)
    except Exception as e:
        logger.warning("ml.semantic_matching: erreur embeddings %s: %s", _MODEL_NAME, e)
        return None


def compute_semantic_similarity(application: Any) -> float:
    """
    Calcule le score de matching sémantique (0–1) entre l'offre et le profil candidat.
    Utilise les embeddings si sentence-transformers est disponible, sinon TF-IDF + cosinus.
    """
    job_text = _job_text(application)
    candidate_text = _candidate_text(application)
    if not job_text or not candidate_text:
        return 0.0
    # Essai embeddings (sémantique profond) puis fallback TF-IDF
    sim_emb = _semantic_similarity_embeddings(job_text, candidate_text)
    if sim_emb is not None:
        return sim_emb
    return semantic_similarity_tfidf(job_text, candidate_text)
