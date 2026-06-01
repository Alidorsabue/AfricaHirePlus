# Durcissement de la chaîne de matching — anti-élimination des bons CV

Ce document décrit les renforcements appliqués à AfricaHire+ pour qu'aucun bon CV ne soit éliminé à cause d'une faille technique (mauvaise extraction OCR, vocabulaire différent entre offre et candidat, sigles techniques trop courts, fautes de frappe, profil incomplet, etc.).

## Vue d'ensemble

La chaîne de matching passe par 4 modules dont chacun a été durci en v2 :

```
CV téléversé (PDF/DOCX/...)
       │
       ▼
apps/core/cv_extraction.py  ──► texte brut + score qualité
       │
       ▼
apps/core/cv_parser.py      ──► skills/exp/edu/langues structurés
       │
       ▼
ml/jd_keywords.py           ──► mots-clés JD pondérés IDF + référentiel tech
       │
       ▼
ml/text_normalize.py        ──► matching tolérant (fuzzy + stem + synonymes)
       │
       ▼
ml/feature_engineering.py   ──► features ML + needs_human_review()
       │
       ▼
ml/inference.py             ──► score ML + recovery boost + confidence
       │
       ▼
apps/jobs/services.py       ──► safety net : pas de rejet auto si CV mal extrait
```

## Failles corrigées

### Faille #1 — Stop words pollués (`ml/jd_keywords.py`)

**Avant** : la liste contenait des fragments d'une offre humanitaire spécifique (`concentrera`, `assurera`, `imo`, `op`, `nutri`, `structura`, `analy`). Ces mots supprimaient à tort des termes pertinents sur d'autres offres.

**Après** : trois listes séparées et auditées :
- `_STOP_WORDS_EN` — mots vides anglais
- `_STOP_WORDS_FR` — mots vides français
- `_STOP_WORDS_BUSINESS` — mots métier neutres (poste, mission, profil…)

### Faille #2 — Sigles techniques courts éliminés

**Avant** : le filtre `len(token) >= 3` jetait AWS, SQL, BI, ETL, R, AI, ML, NLP, ERP, CRM, HR, JS…

**Après** : référentiel `TECH_SKILLS` de 200+ compétences (whitelist) qui contourne les filtres de longueur. La fonction `_is_technical_token` accepte aussi les tokens contenant chiffres/symboles (`C++`, `.NET`, `ES6`, `Vue.js`) ou en MAJUSCULES significatives (`AWS`, `REST`).

### Faille #3 — Pondération uniforme des mots-clés

**Avant** : tous les mots-clés extraits avaient le même poids.

**Après** : pondération **IDF heuristique** (inverse de la fréquence). Les mots rares (donc discriminants) remontent en tête de liste, les mots communs descendent.

### Faille #4 — Matching sans tolérance

**Avant** : `keyword_matches_text` ne gérait que les pluriels `+s` / `+es`.

**Après** : chaîne de fallback en cascade :

```
exact → pluriel/singulier → stem FR/EN → synonyme → fuzzy match (rapidfuzz)
```

- **Stem** : `développeur`/`développement`/`développé` partagent la même racine
- **Synonymes** : 60+ entrées (FR↔EN, sigles, variantes) — `RH ↔ ressources humaines`, `JS ↔ JavaScript`, `ML ↔ apprentissage automatique`
- **Fuzzy** : seuil élevé (0.88) avec `rapidfuzz.token_set_ratio` pour rester précis tout en tolérant fautes de frappe

### Faille #5 — Profil candidat non rempli

**Avant** : un candidat dont le CV regorge de compétences mais qui n'a pas pris le temps de remplir le champ `skills` du formulaire voyait `skills_match` retourner 0.

**Après** : nouveau module `apps/core/cv_parser.py` qui extrait depuis `raw_cv_text` :
- `skills` (référentiel TECH_SKILLS + détection par section)
- `experience_years` (phrase explicite OU agrégation des périodes 2018-2024)
- `education_level` (régex hiérarchique + détection par section)
- `languages` (référentiel multilingue + niveaux)
- `emails`, `phones`

Branché dans `apps/applications/services.py.get_or_create_candidate` : **les champs vides du formulaire sont automatiquement enrichis avec les données du CV**, sans jamais écraser une donnée saisie par le candidat.

### Faille #6 — CV mal extrait = rejet automatique

**Avant** : un CV scanné mal OCR-isé (`quality_score < 0.3`) → matching keyword bas → rejet automatique. Le candidat était éliminé pour une faille technique, pas humaine.

**Après** : safety net en deux niveaux :

1. **Feature `cv_quality_score`** dans `feature_engineering.py` — le modèle ML « voit » la qualité d'extraction.
2. **`needs_human_review()`** — détermine si une candidature mérite une revue manuelle plutôt qu'un rejet auto. Critères :
   - `cv_quality_score < 0.4`
   - `profile_completeness < 0.3`
   - `keyword_match_score == 0` alors que `candidate.skills` contient ≥3 compétences
3. **`_apply_status_with_safety_net()`** dans `apps/jobs/services.py` — si `needs_review`, la candidature reste en statut `APPLIED` (revue manuelle requise) au lieu de `REJECTED_PRESELECTION`.

### Faille #7 — Score ML linéaire arbitraire

**Avant** : `min(years * 2, 20)` plafonnait l'expérience à l'équivalent de 10 ans. Confidence figée à 0.5.

**Après** : `ml/inference.py` v2 :
- **Aucun plafond arbitraire** sur l'expérience
- **`_recovery_boost`** : additif 0–15 points pour rattraper les candidats pénalisés par :
  - CV de mauvaise qualité mais profil technique solide
  - 0 keyword matché mais similarité sémantique forte (vocabulaire différent)
  - Matching faible mais expérience et éducation excellentes
- **Confiance calculée** : pondération de `cv_quality_score`, `profile_completeness` et cohérence keyword/semantic
- **Contributions par feature** : audit trail pour le RH (proto-SHAP)

## Nouvelles fonctions exportées

```python
# ml/jd_keywords.py
extract_suggested_criteria(job)  # ajoute "skills" : list[str] strict (référentiel)
extract_required_skills(job)     # NOUVEAU : skills techniques uniquement

# ml/text_normalize.py
keyword_matches_text(kw, text, fuzzy=True)  # nouvelle option fuzzy
keyword_similarity(kw, text)                # NOUVEAU : score 0-1
fuzzy_match(token, text, threshold=0.85)    # NOUVEAU

# ml/feature_engineering.py
extract_features(application)               # +3 features (cv_quality_score, profile_completeness, has_low_quality_cv)
needs_human_review(application)             # NOUVEAU : (bool, raisons[])

# apps/core/cv_parser.py (NOUVEAU MODULE)
parse_cv(raw_text) -> ParsedCV
extract_skills(raw_text)
extract_experience_years(raw_text)
extract_education_level(raw_text)
extract_languages(raw_text)
enrich_candidate_from_cv(candidate, raw_text)
```

## Tests

Couverture nouvelle :
- `apps/core/tests_cv_extraction.py` — moteur d'extraction multi-format (déjà existant)
- `apps/core/tests_cv_parser.py` — parser CV (skills, exp, edu, langues, contact)
- `ml/tests_hardening.py` — failles fermées (stop words, sigles, fuzzy, stemming, synonymes)
- `apps/jobs/tests_scoring.py` — scoring graduel (déjà existant)

## Dépendances ajoutées

```
rapidfuzz>=3.5,<4.0    # fuzzy matching 10–100× plus rapide que difflib
```

Toutes les autres dépendances (pdfminer.six, pytesseract, pdf2image, docx2txt, odfpy, striprtf) sont **lazy-importées** : pas de crash si absentes, juste un warning au log.

## Compatibilité

- API publique de `extract_keywords_from_job(job)` et `extract_suggested_criteria(job)` : **préservée**
- API publique de `normalize_for_match`, `keyword_matches_text` : **préservée** (ajout d'un paramètre `fuzzy=True` optionnel)
- Schéma de sortie de `extract_features` : **enrichi** (3 nouveaux champs additifs)
- Schéma de sortie de `predict_score` : **préservé** (3 valeurs, dict d'explication enrichi)
- Aucune migration de base de données requise
