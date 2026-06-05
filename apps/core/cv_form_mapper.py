"""
cv_form_mapper — Convertit le texte brut d'un CV en structure du formulaire de candidature.

Complète `cv_parser` (champs simples) avec l'extraction de listes structurées
(formation, expériences, références) et le mapping vers les clés du formulaire frontend.
"""
from __future__ import annotations

import re
from typing import Any

from apps.core.cv_parser import (
    ParsedCV,
    _find_section,
    _normalize,
    parse_cv,
)

# Mapping langues parser → formulaire frontend
_LANG_TO_FORM: dict[str, str] = {
    "français": "french",
    "anglais": "english",
    "espagnol": "spanish",
    "allemand": "other",
    "italien": "other",
    "portugais": "portuguese",
    "arabe": "arabic",
    "chinois": "other",
    "japonais": "other",
    "russe": "other",
    "swahili": "swahili",
    "wolof": "other",
    "bambara": "other",
    "lingala": "lingala",
    "haoussa": "other",
    "yoruba": "other",
    "amharique": "other",
}

_PROF_TO_FORM: dict[str, str] = {
    "natif": "fluent",
    "courant": "fluent",
    "professionnel": "proficient",
    "intermediaire": "intermediate",
    "basique": "basic",
    "non précisé": "intermediate",
}

_MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
_MONTH_ALIASES: dict[str, int] = {}
for _i, _m in enumerate(_MONTH_NAMES, start=1):
    _MONTH_ALIASES[_m.lower()] = _i
    _MONTH_ALIASES[_m.lower()[:3]] = _i
for _fr, _i in [
    ("janvier", 1), ("fevrier", 2), ("février", 2), ("mars", 3), ("avril", 4),
    ("mai", 5), ("juin", 6), ("juillet", 7), ("aout", 8), ("août", 8),
    ("septembre", 9), ("octobre", 10), ("novembre", 11), ("decembre", 12), ("décembre", 12),
]:
    _MONTH_ALIASES[_fr] = _i

_PERIOD_RE = re.compile(
    r"(?:(\w+)\s+)?(\d{4})\s*(?:[-–à/]|to|au)\s*(?:(\w+)\s+)?(\d{4}|pr[eé]sent|present|today|aujourd|en\s+cours|now)",
    re.IGNORECASE,
)
_YEAR_RANGE_RE = re.compile(r"(\d{4})\s*[-–]\s*(\d{4}|pr[eé]sent|present|en\s+cours)", re.IGNORECASE)
_LINKEDIN_RE = re.compile(r"https?://(?:www\.)?linkedin\.com/in/[\w\-./%]+", re.IGNORECASE)
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

_DEGREE_KEYWORDS: list[tuple[str, str]] = [
    (r"\bdoctorat\b|\bph\.?d\b|\bphd\b", "doctorate"),
    (r"\bmaster\b|\bma[iî]trise\b|\bmsc\b|\bmba\b", "master"),
    (r"\blicence\b|\bbachelor\b|\bbsc\b|\bba\b", "bachelor"),
    (r"\bbts\b|\bdut\b", "other"),
    (r"\bbac\b|\bbaccalaur[eé]at\b", "other"),
]

_EDU_INSTITUTION_RE = re.compile(
    r"(?:universit[eé]|école|ecole|institut|facult[eé]|campus|sup[eé]rieur|school|college|university)",
    re.IGNORECASE,
)


def _parse_month_name(raw: str | None) -> str:
    if not raw:
        return ""
    key = _normalize(str(raw).strip())
    idx = _MONTH_ALIASES.get(key) or _MONTH_ALIASES.get(key[:3])
    if idx and 1 <= idx <= 12:
        return _MONTH_NAMES[idx - 1]
    return ""


def _detect_degree_type(text: str) -> str:
    low = text.lower()
    for pattern, dtype in _DEGREE_KEYWORDS:
        if re.search(pattern, low, re.IGNORECASE):
            return dtype
    return ""


def _detect_education_type(text: str) -> str:
    low = text.lower()
    if re.search(r"\bbts\b|\bdut\b", low):
        return "bts_dut"
    if re.search(r"\bbac\b|\bbaccalaur", low):
        return "baccalaureat"
    if re.search(r"\blyc[eé]e\b|\bhigh\s+school\b", low):
        return "high_school"
    if _EDU_INSTITUTION_RE.search(text):
        return "university_graduate"
    return "other"


def _detect_discipline(text: str) -> str:
    low = text.lower()
    mapping = [
        ("informatique", "computer_science"), ("computer science", "computer_science"),
        ("data science", "computer_science"), ("g[eé]nie civil", "civil_engineering"),
        ("commerce", "commerce"), ("management", "commerce"), ("m[eé]decine", "medicine"),
        ("droit", "law"), ("law", "law"),
    ]
    for pat, val in mapping:
        if re.search(pat, low):
            return val
    return "other"


def extract_education_entries(raw_text: str) -> list[dict[str, str]]:
    """Extrait des entrées de formation depuis la section Formation du CV."""
    section = _find_section(raw_text, "education")
    if not section:
        return []

    blocks = re.split(r"\n\s*\n|\n(?=\d{4}\s*[-–])", section)
    entries: list[dict[str, str]] = []
    for block in blocks:
        block = block.strip()
        if len(block) < 8:
            continue
        years = _YEAR_RANGE_RE.search(block)
        start_year = years.group(1) if years else ""
        end_raw = years.group(2) if years else ""
        end_year = "" if end_raw and re.search(r"pr[eé]sent|present|en\s+cours", end_raw, re.I) else (end_raw or "")

        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        institution = ""
        for ln in lines:
            if _EDU_INSTITUTION_RE.search(ln) or re.search(r"\b(ESG|HEC|MIT|EPFL|ULB|UNIKIN|UPN)\b", ln, re.I):
                institution = ln
                break
        if not institution and lines:
            institution = lines[0]

        degree_type = _detect_degree_type(block)
        entries.append({
            "education_type": _detect_education_type(block),
            "degree_type": degree_type,
            "discipline": _detect_discipline(block),
            "other_specializations": "",
            "country": "",
            "institution": institution[:255],
            "city_campus": "",
            "study_level": "completed",
            "enrollment_status": "full_time",
            "start_year": start_year,
            "end_year": end_year,
        })
    return entries[:8]


def extract_experience_entries(raw_text: str) -> list[dict[str, str]]:
    """Extrait des entrées d'expérience professionnelle depuis le CV."""
    section = _find_section(raw_text, "experience")
    if not section:
        return []

    blocks = re.split(r"\n\s*\n|\n(?=(?:(?:\w+\s+)?\d{4}\s*[-–]))", section)
    entries: list[dict[str, str]] = []
    for block in blocks:
        block = block.strip()
        if len(block) < 10:
            continue

        period = _PERIOD_RE.search(block)
        start_month = _parse_month_name(period.group(1) if period else None)
        start_year = period.group(2) if period else ""
        end_month = _parse_month_name(period.group(3) if period else None)
        end_raw = period.group(4) if period else ""
        end_year = ""
        if end_raw and not re.search(r"pr[eé]sent|present|today|aujourd|en\s+cours|now", end_raw, re.I):
            end_year = end_raw

        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue

        job_title = lines[0][:255]
        company_name = ""
        for ln in lines[1:4]:
            if period and period.group(0) in ln:
                continue
            if re.search(r"\b(sarl|sa|sas|ltd|inc|gmbh|group|groupe|corp)\b", ln, re.I) or (
                len(ln) < 80 and not ln.startswith("•") and not ln.startswith("-")
            ):
                company_name = ln[:255]
                break

        responsibilities = "\n".join(
            ln for ln in lines[1:]
            if ln != company_name and not _PERIOD_RE.search(ln)
        )[:2000]

        entries.append({
            "employment_status": "currently_employed" if not end_year else "",
            "employment_type": "full_time",
            "employment_type_details": "",
            "job_title": job_title,
            "job_contract_type": "",
            "job_level": "",
            "responsibilities": responsibilities,
            "start_month": start_month,
            "start_year": start_year,
            "start_day": "",
            "end_month": end_month,
            "end_year": end_year,
            "end_day": "",
            "company_name": company_name,
            "company_sector": "",
            "country": "",
            "city": "",
            "department": "",
            "manager_name": "",
        })
    return entries[:12]


def extract_references(raw_text: str) -> list[dict[str, str]]:
    """Extrait des personnes de référence depuis le CV."""
    section = _find_section(raw_text, "references") if False else None
    # Section références pas dans _SECTION_PATTERNS — détection manuelle
    ref_patterns = [
        r"\br[eé]f[eé]rences?\b", r"\breferences?\b", r"\bpersonnes?\s+de\s+r[eé]f[eé]rence\b",
    ]
    section_text = ""
    for pat in ref_patterns:
        m = re.search(rf"(?im)^\s*({pat})\s*[:\-]?\s*$", raw_text)
        if m:
            start = m.end()
            next_hdr = re.search(
                r"(?im)^\s*(comp[eé]tences?|langues?|skills?|exp[eé]rience|formation|education)\s*[:\-]?\s*$",
                raw_text[start:],
            )
            end = start + next_hdr.start() if next_hdr else min(start + 2000, len(raw_text))
            section_text = raw_text[start:end].strip()
            break

    if not section_text:
        return []

    blocks = re.split(r"\n\s*\n|\n(?=[A-ZÀ-Ÿ][a-zà-ÿ]+ [A-ZÀ-Ÿ])", section_text)
    refs: list[dict[str, str]] = []
    for block in blocks:
        block = block.strip()
        if len(block) < 5:
            continue
        emails = _EMAIL_RE.findall(block)
        phones = []
        for p in re.findall(r"(?:\+\d{1,3}[\s.\-]?)?(?:\(?\d{2,4}\)?[\s.\-]?){2,5}\d{2,4}", block):
            digits = re.sub(r"\D", "", p)
            if 7 <= len(digits) <= 16:
                phones.append(p.strip())

        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        name_line = lines[0] if lines else ""
        parts = name_line.split()
        first_name = parts[0] if parts else ""
        last_name = " ".join(parts[1:]) if len(parts) > 1 else ""

        org = ""
        title = ""
        for ln in lines[1:]:
            if _EMAIL_RE.search(ln) or re.search(r"\d{7,}", ln):
                continue
            if not org:
                org = ln[:255]
            elif not title:
                title = ln[:255]

        refs.append({
            "first_name": first_name[:100],
            "last_name": last_name[:100],
            "organization": org,
            "job_title": title,
            "phone": phones[0] if phones else "",
            "email": emails[0] if emails else "",
        })
    return refs[:6]


def _map_languages(parsed_langs: list[dict[str, str]]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for item in parsed_langs:
        lang_key = (item.get("language") or "").lower()
        form_lang = _LANG_TO_FORM.get(lang_key, "other")
        prof = _PROF_TO_FORM.get((item.get("proficiency") or "").lower(), "intermediate")
        result.append({
            "language": form_lang,
            "speaking_proficiency": prof,
            "reading_proficiency": prof,
            "writing_proficiency": prof,
        })
    return result


def _extract_linkedin(raw_text: str) -> str:
    m = _LINKEDIN_RE.search(raw_text)
    return m.group(0) if m else ""


def _guess_current_position(experience: list[dict[str, str]]) -> str:
    for exp in experience:
        if exp.get("job_title") and not exp.get("end_year"):
            return exp["job_title"]
    if experience and experience[0].get("job_title"):
        return experience[0]["job_title"]
    return ""


def build_form_data_from_cv_text(raw_text: str) -> dict[str, Any]:
    """
    Construit un dict prêt pour le formulaire de candidature à partir du texte CV.
    Ne lève pas d'exception.
    """
    parsed: ParsedCV = parse_cv(raw_text)
    try:
        education = extract_education_entries(raw_text)
    except Exception:
        education = []
    try:
        experience = extract_experience_entries(raw_text)
    except Exception:
        experience = []
    try:
        references = extract_references(raw_text)
    except Exception:
        references = []
    languages = _map_languages(parsed.languages)

    skills = parsed.skills or []
    linkedin = _extract_linkedin(raw_text)
    phone = parsed.phones[0] if parsed.phones else ""
    email = parsed.emails[0] if parsed.emails else ""

    return {
        "title": "",
        "first_name": "",
        "last_name": "",
        "preferred_name": "",
        "date_of_birth": None,
        "gender": "",
        "email": email,
        "phone": phone,
        "cell_number": phone,
        "address": "",
        "address_line2": "",
        "city": "",
        "country": "",
        "postcode": "",
        "nationality": "",
        "second_nationality": "",
        "linkedin_url": linkedin,
        "portfolio_url": "",
        "summary": "",
        "skills": skills,
        "experience_years": parsed.experience_years,
        "education_level": parsed.education_level or "",
        "current_position": _guess_current_position(experience),
        "location": "",
        "education": education,
        "experience": experience,
        "languages": languages,
        "references": references,
        "parsed_meta": {
            "confidence": parsed.confidence,
            "warnings": parsed.warnings,
        },
    }


def candidate_to_form_data(candidate: Any) -> dict[str, Any]:
    """Convertit un profil candidat Django en structure formulaire."""
    skills = getattr(candidate, "skills", None) or []
    if isinstance(skills, str):
        skills = [s.strip() for s in skills.split(",") if s.strip()]

    dob = getattr(candidate, "date_of_birth", None)
    date_of_birth = dob.isoformat() if dob else None

    return {
        "title": getattr(candidate, "title", "") or "",
        "first_name": getattr(candidate, "first_name", "") or "",
        "last_name": getattr(candidate, "last_name", "") or "",
        "preferred_name": getattr(candidate, "preferred_name", "") or "",
        "date_of_birth": date_of_birth,
        "gender": getattr(candidate, "gender", "") or "",
        "email": getattr(candidate, "email", "") or "",
        "phone": getattr(candidate, "phone", "") or "",
        "cell_number": getattr(candidate, "cell_number", "") or "",
        "address": getattr(candidate, "address", "") or "",
        "address_line2": getattr(candidate, "address_line2", "") or "",
        "city": getattr(candidate, "city", "") or "",
        "country": getattr(candidate, "country", "") or "",
        "postcode": getattr(candidate, "postcode", "") or "",
        "nationality": getattr(candidate, "nationality", "") or "",
        "second_nationality": getattr(candidate, "second_nationality", "") or "",
        "linkedin_url": getattr(candidate, "linkedin_url", "") or "",
        "portfolio_url": getattr(candidate, "portfolio_url", "") or "",
        "summary": getattr(candidate, "summary", "") or "",
        "skills": skills,
        "experience_years": getattr(candidate, "experience_years", None),
        "education_level": getattr(candidate, "education_level", "") or "",
        "current_position": getattr(candidate, "current_position", "") or "",
        "location": getattr(candidate, "location", "") or "",
        "education": getattr(candidate, "education", None) or [],
        "experience": getattr(candidate, "experience", None) or [],
        "languages": getattr(candidate, "languages", None) or [],
        "references": getattr(candidate, "references", None) or [],
        "parsed_meta": {"source": "candidate_profile"},
    }


def compute_section_confidence(
    form_data: dict[str, Any],
    parsed_confidence: dict[str, float] | None = None,
    source: str = "upload",
) -> dict[str, float]:
    """
    Score de confiance 0–1 par rubrique du formulaire de candidature.
    Clés alignées sur FORM_SECTIONS du frontend (sauf signature).
    """
    parsed_confidence = parsed_confidence or {}
    edu = form_data.get("education") or []
    exp = form_data.get("experience") or []
    langs = form_data.get("languages") or []
    refs = form_data.get("references") or []
    skills = form_data.get("skills") or []

    if source == "last_application":
        has_personal = bool(
            form_data.get("email") or form_data.get("phone") or form_data.get("cell_number")
        )
        return {
            "personalDetails": 0.95 if has_personal else 0.0,
            "education": 0.95 if edu else 0.0,
            "experience": 0.95 if exp else 0.0,
            "skills": 0.95 if skills else 0.0,
            "languages": 0.95 if langs else 0.0,
            "references": 0.9 if refs else 0.0,
            "documents": 0.95,
        }

    personal_scores: list[float] = []
    if form_data.get("email"):
        personal_scores.append(0.8)
    if form_data.get("phone") or form_data.get("cell_number"):
        personal_scores.append(0.75)
    if form_data.get("linkedin_url"):
        personal_scores.append(0.85)
    personal = sum(personal_scores) / len(personal_scores) if personal_scores else 0.0

    edu_conf = float(parsed_confidence.get("education_level") or 0.0)
    if edu:
        edu_conf = max(edu_conf, min(0.85, 0.55 + len(edu) * 0.08))

    exp_conf = float(parsed_confidence.get("experience_years") or 0.0)
    if exp:
        exp_conf = max(exp_conf, min(0.85, 0.5 + len(exp) * 0.06))

    skills_conf = float(parsed_confidence.get("skills") or 0.0) if skills else 0.0
    langs_conf = float(parsed_confidence.get("languages") or 0.0) if langs else 0.0
    refs_conf = min(0.75, 0.45 + len(refs) * 0.1) if refs else 0.0

    return {
        "personalDetails": round(personal, 2),
        "education": round(edu_conf, 2),
        "experience": round(exp_conf, 2),
        "skills": round(skills_conf, 2),
        "languages": round(langs_conf, 2),
        "references": round(refs_conf, 2),
        "documents": 0.85,
    }


def merge_form_data(primary: dict[str, Any], secondary: dict[str, Any]) -> dict[str, Any]:
    """
    Fusionne deux sources : primary (profil structuré) prioritaire,
    secondary (parsing CV) pour combler les champs vides.
    """
    merged = dict(primary)
    scalar_keys = [
        "title", "first_name", "last_name", "preferred_name", "gender",
        "email", "phone", "cell_number", "address", "address_line2",
        "city", "country", "postcode", "nationality", "second_nationality",
        "linkedin_url", "portfolio_url", "summary", "education_level",
        "current_position", "location",
    ]
    for key in scalar_keys:
        if not merged.get(key) and secondary.get(key):
            merged[key] = secondary[key]

    if not merged.get("date_of_birth") and secondary.get("date_of_birth"):
        merged["date_of_birth"] = secondary["date_of_birth"]
    if merged.get("experience_years") in (None, "", 0) and secondary.get("experience_years"):
        merged["experience_years"] = secondary["experience_years"]

    if not merged.get("skills") and secondary.get("skills"):
        merged["skills"] = secondary["skills"]
    elif merged.get("skills") and secondary.get("skills"):
        existing = {str(s).lower() for s in merged["skills"]}
        merged["skills"] = list(merged["skills"]) + [
            s for s in secondary["skills"] if str(s).lower() not in existing
        ]

    for list_key in ("education", "experience", "languages", "references"):
        if not merged.get(list_key) and secondary.get(list_key):
            merged[list_key] = secondary[list_key]

    return merged
