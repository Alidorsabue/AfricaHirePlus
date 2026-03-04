# Architecture ML — AfricaHirePlus

Documentation technique interne pour l’intégration du Machine Learning (scoring prédictif, ranking intelligent). L’architecture est **ML-ready** : la logique rule-based actuelle reste inchangée ; le ML s’ajoute en parallèle et peut être activé par configuration.

---

## 1. Modèle MLScore

**Table :** `applications_mlscore`

| Champ | Type | Description |
|-------|------|-------------|
| `application` | FK → Application | Candidature concernée |
| `model_version` | VARCHAR(64) | Version du modèle (ex. `20250226-stub`, `v1.0.0`) |
| `predicted_score` | FLOAT | Score prédit 0–100 |
| `confidence_score` | FLOAT (nullable) | Confiance du modèle 0–1 |
| `features_json` | JSON | Features utilisées (feature store) |
| `ml_explanation_json` | JSON (nullable) | Réservé pour SHAP / explications IA |
| `created_at` | DATETIME | Date/heure de la prédiction (traçabilité) |

Chaque prédiction enregistre **model_version** et **date** pour reproductibilité et audit.

---

## 2. Feature store interne

**Fonction :** `ml.feature_engineering.extract_features(application)`

Retourne un dictionnaire de features, par exemple :

```json
{
  "years_experience": 6,
  "education_level": 3,
  "technical_score": 75,
  "keyword_match_score": 0.82,
  "previous_job_similarity": 0.67
}
```

- **years_experience** : depuis `candidate.experience_years`
- **education_level** : entier 0–5 (mapping bac → doctorat)
- **technical_score** : dérivé du score rule-based (criteria_json ou preselection_score)
- **keyword_match_score** : overlap mots-clés offre / CV (0–1)
- **previous_job_similarity** : similarité titre offre / poste actuel et expériences (0–1)

Ces valeurs sont sauvegardées dans `MLScore.features_json` à chaque prédiction.

---

## 3. Scoring hybride

Formule :

```text
final_score = (rule_based_score × rule_based_weight) + (ml_score × ml_weight)
```

Les poids sont **configurables** dans `SelectionSettings` :

- `rule_based_weight` (défaut 0.6)
- `ml_weight` (défaut 0.4)

En mode HYBRID, les poids sont normalisés (somme = 1) s’ils sont tous deux renseignés.  
Logique : `ml.hybrid_scoring.compute_hybrid_score()` et `get_hybrid_weights()`.

---

## 4. Dossier ML (`/ml/`)

| Fichier | Rôle |
|---------|------|
| `feature_engineering.py` | `extract_features(application)` — feature store |
| `inference.py` | `predict_score(application)` — prédiction (stub puis vrai modèle) |
| `model_registry.py` | Version courante, `load_model(version)` (stub) |
| `training.py` | Pipeline d’entraînement (structure : `prepare_training_data`, `train_model`, `run_training_pipeline`) |
| `hybrid_scoring.py` | Calcul du score hybride et récupération des poids |

Le modèle est **fictif** au départ (combinaison linéaire des features). Remplacer par un vrai modèle (joblib, ONNX, etc.) dans `inference.py` et `model_registry.py` après entraînement.

---

## 5. Versioning

Chaque prédiction enregistre :

- **model_version** : chaîne (ex. `20250226-stub`)
- **created_at** : date/heure de la prédiction

Cela permet :

- Audit et conformité
- Comparaison de modèles (A/B)
- Re-training avec les mêmes versions

---

## 6. Explication IA

Le champ **ml_explanation_json** sur `MLScore` est prévu pour une future intégration (SHAP, feature importance, etc.).  
Le stub renvoie un placeholder avec `feature_contributions` et `model_version`.

---

## 7. Mode de scoring (SelectionSettings)

**Champ :** `scoring_mode` (choix) :

| Valeur | Comportement |
|--------|----------------|
| `RULE_BASED` | Score = score rule-based uniquement (comportement actuel) |
| `HYBRID` | Score = combinaison rule_based_weight × rule + ml_weight × ML |
| `ML_ONLY` | Score = dernier score ML enregistré (fallback sur rule-based si pas de prédiction) |

API : les champs `scoring_mode`, `rule_based_weight`, `ml_weight` sont exposés dans `selection_settings` (lecture/écriture) sur l’offre.

---

## 8. API — Prédiction de score

**Endpoint :** `POST /api/v1/applications/{id}/predict-score/`

- **Permissions :** recruteur / tenant (IsTenantOrSuperAdmin)
- **Effet :**
  1. Extrait les features (`extract_features`)
  2. Appelle le modèle (`predict_score`)
  3. Crée un enregistrement **MLScore** (model_version, predicted_score, confidence_score, features_json, ml_explanation_json)
  4. Log et traçabilité (application_id, model_version, user_id)
- **Réponse 201 :**

```json
{
  "application_id": 123,
  "predicted_score": 72.5,
  "confidence_score": 0.5,
  "model_version": "20250226-stub",
  "features": { ... },
  "ml_score_id": 1,
  "created_at": "2025-02-26T12:00:00Z"
}
```

---

## 9. Sécurité, logs et traçabilité

- **Logs :**  
  - `ml.feature_engineering` : DEBUG (features par application)  
  - `ml.inference` : INFO (application_id, model_version, predicted_score)  
  - `applications.views` : INFO pour chaque appel `predict-score` (application_id, model_version, user_id) — **audit**

- **Traçabilité :**  
  Chaque prédiction est stockée dans `MLScore` avec `model_version` et `created_at`.  
  Pas de table d’audit dédiée pour l’instant ; les logs + contenu de `MLScore` constituent l’audit trail.

---

## 10. Intégration dans le flux de sélection

Lors du calcul du **score de sélection** (`_compute_selection_score_for_application` dans `apps.jobs.services`) :

- **RULE_BASED :** score = score rule-based uniquement.
- **HYBRID :** score rule-based + dernier MLScore (s’il existe) avec les poids configurés.
- **ML_ONLY :** score = dernier `MLScore.predicted_score` (sinon fallback rule-based).

Aucun appel automatique au modèle à ce stade : le score ML est utilisé **s’il a déjà été calculé** (via `POST /applications/{id}/predict-score/`). Un cron ou un trigger pour lancer la prédiction sur les nouvelles candidatures peut être ajouté plus tard.

---

## Résumé des fichiers modifiés / ajoutés

| Fichier | Action |
|---------|--------|
| `apps/applications/models.py` | Modèle **MLScore** |
| `apps/applications/admin.py` | Admin **MLScore** |
| `apps/applications/views.py` | **ApplicationPredictScoreView** |
| `apps/applications/urls.py` | Route `predict-score` |
| `apps/jobs/models.py` | **ScoringMode**, **rule_based_weight**, **ml_weight** |
| `apps/jobs/services.py` | Intégration scoring_mode / hybride dans `_compute_selection_score_for_application` |
| `apps/jobs/serializers.py` | Exposition scoring_mode et poids dans selection_settings |
| `ml/` | Package **feature_engineering**, **inference**, **model_registry**, **training**, **hybrid_scoring** |
| `docs/ML_ARCHITECTURE.md` | Ce document |

Migrations : `applications.0006_ml_score_model`, `jobs.0007_selectionsettings_scoring_mode` (si pas déjà appliquée).
