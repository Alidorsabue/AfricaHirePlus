# Analyse : écart entre le score ATS AfricaHire+ et ChatGPT

## Contexte

- **ChatGPT** (utilisé comme ATS) : analyse complète JD vs CV → score **78–82 %** (mots-clés majeurs détectés : Cash assistance, CVA, M&E, Data analysis, Power BI, SPSS, UNICEF, etc.).
- **AfricaHire+** : score affiché **~20 %** pour la même candidature.

## Pourquoi AfricaHire+ donne un score beaucoup plus bas

### 1. Source des mots-clés différente

| | ChatGPT | AfricaHire+ |
|---|--------|-------------|
| **Source des mots-clés** | Tout le texte de l’offre (description + exigences) | **Uniquement les règles de screening** créées manuellement par le recruteur |
| **Couverture** | Tous les termes importants du JD | Seulement les mots-clés ajoutés dans les règles |

Si le recruteur n’a pas créé de règles « Mots-clés » avec la liste complète (Cash assistance, CVA, Monitoring & Evaluation, Power BI, SPSS, UNICEF…), AfricaHire+ ne cherche que les quelques termes configurés → score faible.

### 2. Fallback actuel trop limité

Quand **aucune règle « keywords »** n’existe, le code utilise un fallback dans `ml/feature_engineering.py` :

- Extraction des mots depuis **`job.requirements` uniquement** (pas la description).
- Mots de **plus de 3 caractères**, **30 premiers mots** seulement.
- Pas de n-grammes (ex. « Cash assistance », « Monitoring & Evaluation » sont ignorés en tant que phrases).

Résultat : peu de termes, pas de expressions clés → **keyword_match_score** reste bas.

### 3. Score affiché = uniquement règles / critères

Le score de présélection affiché vient de :

- **PreselectionSettings.criteria_json** (critères pondérés), **ou**
- **ScreeningRule** (keywords, min_experience, education_level…).

Il **ne** repose **pas** par défaut sur une analyse « JD complet vs CV complet » comme ChatGPT. Le module ML (similarité sémantique + keyword match amélioré) existe mais :

- Le score ML est utilisé surtout via l’API « Prédire le score » (recruteur).
- En création de candidature, c’est **compute_screening_score** ou **compute_weighted_score** qui fixe le score affiché.

Donc même avec un bon CV, si les règles/critères sont peu nombreux ou mal alignés sur le JD, le score reste bas (ex. 20 %).

### 4. Aucune règle = aucun score

Si l’offre n’a **aucune** règle de screening et **aucun** critère de présélection :

- `compute_screening_score` retourne `None`.
- `compute_preselection` ne met à jour ni le score ni le statut.
- La candidature peut rester sans score ou avec un affichage par défaut peu parlant.

## Corrections mises en place

1. **Extraction automatique des mots-clés depuis toute l’offre**  
   Nouveau module (ex. `ml/jd_keywords.py`) : extraction de termes et n-grammes pertinents depuis **titre + description + exigences** de l’offre, pour alimenter le matching ATS même sans règles.

2. **Amélioration de `_keyword_match_score`**  
   Utilisation de ces mots-clés « JD » en fallback (ou en complément) pour le matching CV, au lieu des 30 mots des `requirements` uniquement.

3. **Score ATS « JD vs CV » en fallback**  
   Quand il n’y a **pas** de règles (ou pas de critères), calcul d’un score de type ATS (mots-clés JD + similarité sémantique) et utilisation comme **preselection_score** (ou score affiché). Ainsi, chaque candidature obtient un score cohérent avec une analyse « offre complète vs CV ».

4. **Alignement avec une analyse type ChatGPT**  
   Le score affiché reflète mieux la correspondance entre le **texte intégral de l’offre** et le **CV + profil**, proche du comportement d’un ATS qui analyse tout le JD.

## Résumé

- **Problème** : le score AfricaHire+ dépend des **règles/critères configurés** ; peu ou pas de règles ⇒ score bas ou absent, alors que ChatGPT analyse tout le JD.
- **Solution** : extraction automatique des mots-clés depuis toute l’offre, matching enrichi CV vs JD, et utilisation d’un **score ATS (JD vs CV)** lorsque les règles de présélection sont absentes, pour obtenir un résultat proche de 70–80 % quand le CV correspond bien à l’offre.

## Moteur de scoring v2 (mai 2026)

Le moteur `apps/jobs/scoring_engine.py` a été enrichi pour rapprocher encore le scoring d'un comportement type ATS expert :

### Nouveautés
- **Scoring graduel (`partial credit`)** : un candidat à 3 ans d'expérience pour un poste qui en demande 5 obtient désormais 60 % du poids du critère au lieu de 0 % (activé par défaut, désactivable via `partial: false` par critère).
- **Nouveaux opérateurs** :
  - `range` — fenêtre `[min, max]` avec scoring graduel hors fenêtre selon la distance.
  - `similar_to` — similarité textuelle fuzzy (SequenceMatcher), seuil configurable via `threshold` (défaut 0.75).
  - `skills_match` — matching d'une liste de compétences requises avec tolérance orthographique (similarité ≥ 0.80), ratio passable via `min_match` (défaut 0.5).
- **Catégories** : chaque critère peut porter une `category` ; le résultat agrège un score normalisé par catégorie (utile pour les radars d'évaluation RH).
- **Indice de confiance** : ratio critères évalués / critères attendus, retourné dans `confidence` (0–1).

### Schéma de sortie `compute_weighted_score`
```json
{
  "total_score": 78.0,
  "confidence": 1.0,
  "categories": {
    "experience": {"earned": 24.0, "possible": 30.0, "score": 80.0},
    "education": {"earned": 40.0, "possible": 40.0, "score": 100.0}
  },
  "details": [
    {
      "criterion": "experience_years",
      "category": "experience",
      "passed": false,
      "ratio": 0.8,
      "weight_awarded": 24.0,
      "weight_max": 30,
      "mandatory": false
    }
  ],
  "mandatory_failed": false
}
```

### Compatibilité
- `validate_criteria_json` (importé par `apps/jobs/serializers.py`) reste exporté et accepte les nouveaux opérateurs.
- Les clés v1 (`total_score`, `details[*].criterion/passed/weight_awarded`, `mandatory_failed`) sont préservées : aucune migration nécessaire côté frontend ou base.
- Les enrichissements v2 (`ratio`, `category`, `weight_max`, `mandatory`, `confidence`, `categories`) sont additifs.
