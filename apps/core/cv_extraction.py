"""
Extraction de texte depuis les CV (PDF, Word) pour alimenter raw_cv_text
et permettre la recherche par mots-clés et le scoring ML.
Utilisé en amont du feature engineering (ml/feature_engineering.py).
"""
import logging
from io import BytesIO
from typing import Any

logger = logging.getLogger(__name__)


def _extract_text_from_pdf(file_or_bytes: Any) -> str:
    """Extrait le texte d'un PDF (fichier ou bytes). Retourne '' en cas d'erreur."""
    try:
        from pypdf import PdfReader
    except ImportError:
        logger.warning("cv_extraction: pypdf non installé, impossible d'extraire le PDF.")
        return ""
    try:
        if hasattr(file_or_bytes, 'read'):
            file_or_bytes.seek(0)
            reader = PdfReader(file_or_bytes)
        else:
            reader = PdfReader(BytesIO(file_or_bytes))
        parts = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                parts.append(text)
        return "\n".join(parts).strip() if parts else ""
    except Exception as e:
        logger.warning("cv_extraction: erreur extraction PDF: %s", e)
        return ""


def _extract_text_from_docx(file_or_bytes: Any) -> str:
    """Extrait le texte d'un document Word (fichier ou bytes). Retourne '' en cas d'erreur."""
    try:
        from docx import Document
    except ImportError:
        logger.warning("cv_extraction: python-docx non installé, impossible d'extraire le Word.")
        return ""
    try:
        if hasattr(file_or_bytes, 'read'):
            file_or_bytes.seek(0)
            doc = Document(file_or_bytes)
        else:
            doc = Document(BytesIO(file_or_bytes))
        parts = []
        for para in doc.paragraphs:
            if para.text.strip():
                parts.append(para.text)
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        parts.append(cell.text)
        return "\n".join(parts).strip() if parts else ""
    except Exception as e:
        logger.warning("cv_extraction: erreur extraction Word: %s", e)
        return ""


def extract_text_from_uploaded_file(uploaded_file: Any) -> str:
    """
    Extrait le texte brut d'un fichier CV (PDF ou Word).

    - Accepte un objet type Django UploadedFile (avec .read(), .name, .content_type)
      ou tout fichier-like (read, seek) ou bytes.
    - Remet le pointeur du fichier à 0 après lecture (seek(0)) pour permettre une sauvegarde ultérieure.
    - Retourne la chaîne de texte extraite, ou '' si format non supporté / erreur.
    - Utilisé pour remplir candidate.raw_cv_text en amont du scoring et de la recherche.
    """
    if uploaded_file is None:
        return ""
    name = getattr(uploaded_file, 'name', '') or ''
    content_type = (getattr(uploaded_file, 'content_type', '') or '').lower()
    is_pdf = (
        content_type == 'application/pdf'
        or name.lower().endswith('.pdf')
    )
    is_docx = (
        content_type in (
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/msword',
        )
        or name.lower().endswith('.docx')
        or name.lower().endswith('.doc')
    )
    if hasattr(uploaded_file, 'read'):
        if is_pdf:
            out = _extract_text_from_pdf(uploaded_file)
            if hasattr(uploaded_file, 'seek'):
                uploaded_file.seek(0)
            return out
        if is_docx:
            out = _extract_text_from_docx(uploaded_file)
            if hasattr(uploaded_file, 'seek'):
                uploaded_file.seek(0)
            return out
    if isinstance(uploaded_file, bytes):
        if is_pdf or content_type == 'application/pdf':
            return _extract_text_from_pdf(BytesIO(uploaded_file))
        if is_docx or 'word' in content_type or 'document' in content_type:
            return _extract_text_from_docx(BytesIO(uploaded_file))
    # Fallback par extension si content_type non fiable
    if name.lower().endswith('.pdf') and hasattr(uploaded_file, 'read'):
        try:
            uploaded_file.seek(0)
        except Exception:
            pass
        out = _extract_text_from_pdf(uploaded_file)
        if hasattr(uploaded_file, 'seek'):
            try:
                uploaded_file.seek(0)
            except Exception:
                pass
        return out
    if (name.lower().endswith('.docx') or name.lower().endswith('.doc')) and hasattr(uploaded_file, 'read'):
        try:
            uploaded_file.seek(0)
        except Exception:
            pass
        out = _extract_text_from_docx(uploaded_file)
        if hasattr(uploaded_file, 'seek'):
            try:
                uploaded_file.seek(0)
            except Exception:
                pass
        return out
    logger.debug("cv_extraction: format non supporté name=%s content_type=%s", name, content_type)
    return ""


# ---------------------------------------------------------------------------
# P8 — Shim de compatibilité : expose extract_cv() en s'appuyant sur
# extract_text_from_uploaded_file(). À remplacer par la v2 complète quand
# le fichier sera resynchronisé depuis OneDrive.
# ---------------------------------------------------------------------------
from dataclasses import dataclass, field
from enum import Enum


class ExtractionMethod(str, Enum):
    PYPDF = "pypdf"
    DOCX = "docx"
    PLAIN_TEXT = "plain_text"
    NONE = "none"


@dataclass
class ExtractionResult:
    text: str = ""
    method: ExtractionMethod = ExtractionMethod.NONE
    page_count: int = 0
    quality_score: float = 0.0
    ocr_used: bool = False
    warnings: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @property
    def is_sufficient(self) -> bool:
        return len(self.text.strip()) >= 100

    def to_dict(self) -> dict:
        return {
            "method": self.method.value,
            "page_count": self.page_count,
            "quality_score": round(self.quality_score, 3),
            "ocr_used": self.ocr_used,
            "char_count": len(self.text),
            "warnings": self.warnings,
        }


def extract_cv(source: Any, filename: str = "", content_type: str = "") -> ExtractionResult:
    """Shim minimal de compatibilité : renvoie un ExtractionResult basé sur
    l'API legacy. Pour les fonctionnalités v2 (OCR, multi-format avancé),
    le fichier disque doit être resynchronisé depuis l'éditeur."""
    result = ExtractionResult()
    text = extract_text_from_uploaded_file(source)
    result.text = text or ""
    if result.text:
        name = (filename or getattr(source, "name", "") or "").lower()
        if name.endswith(".pdf") or "pdf" in (content_type or ""):
            result.method = ExtractionMethod.PYPDF
        elif name.endswith((".docx", ".doc")) or "word" in (content_type or ""):
            result.method = ExtractionMethod.DOCX
        else:
            result.method = ExtractionMethod.PLAIN_TEXT
        total = len(result.text)
        if total >= 20:
            letter_ratio = sum(1 for c in result.text if c.isalpha()) / total
            length_bonus = min(1.0, total / 2000)
            result.quality_score = round(
                min(letter_ratio * 0.6 + length_bonus * 0.4, 1.0),
                3,
            )
    else:
        result.warnings.append("Aucun texte extrait du CV.")
    return result
