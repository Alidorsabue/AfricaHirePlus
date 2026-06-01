# P10 — Renforcement modules Candidature & Candidats

Ce document résume les améliorations apportées aux modules `apps.applications`
et `apps.candidates` lors de la phase P10. Tous les changements sont rétro-compatibles
côté frontend (les anciens endpoints conservent leur signature) sauf le durcissement
des permissions, qui bloque uniquement des appels qui n'auraient jamais dû passer.

> 24 tests P10 dédiés + 133 tests totaux passent sans régression
> (`apps.applications.tests_p10_hardening`, `apps.applications.tests_ats`,
> `apps.tests.*`, `apps.emails.*`).

---

## 1. Sécurité (A1, A2)

### Permissions strictes
La classe `IsTenantOrSuperAdmin` (et `IsRecruiterOrAdmin`) vérifie maintenant
**explicitement** que le rôle de l'utilisateur est `recruiter` ou `super_admin`.
Avant : tout user authentifié passait, le filtrage reposait sur `get_queryset()`.
Conséquence : un candidat qui appelle `GET /api/v1/applications/` ou
`POST /api/v1/candidates/` reçoit maintenant un **403** (au lieu de potentiellement
créer ou consulter des données).

Nouvelle classe `IsOwnerCandidate` pour le contrôle objet-level côté candidat.

### Anti-usurpation à la soumission
`PublicApplySerializer.validate()` refuse qu'un candidat soumette une candidature
avec un `email` différent de l'adresse de son compte. Super-admin et recruteurs
gardent la possibilité de postuler pour un tiers (intégration ATS).

### Sérializer split
- `ApplicationSerializer` : lecture recruteur complète.
- `ApplicationWriteSerializer` : POST/PATCH recruteur, **scores et flags d'override
  désormais en `read_only`**. Il faut passer par :
  - `PATCH /applications/<id>/status/` (audit + state machine)
  - `POST /applications/<id>/manual-override/` (audit)
  - `POST /applications/<id>/run-screening/` (audit)
- `ApplicationCandidateSerializer` : vue candidat « RGPD-safe » (sans `notes`,
  `*_score_details`, `manual_override_reason`, etc.).

`ApplicationDetailView` choisit dynamiquement le sérializer selon la méthode HTTP.

---

## 2. Validation (A3)

`PublicApplySerializer` introduit :

| Champ                       | Règle                                                            |
| --------------------------- | ---------------------------------------------------------------- |
| `resume`                    | ≤ `CV_MAX_SIZE_MB` (10 Mo), extension ∈ `.pdf, .doc, .docx, .odt, .rtf, .txt`, MIME contrôlé, **blacklist `.exe`/`.bat`/`.sh`/`.js`/`.html`/`.php`/…** |
| `cover_letter_document`     | ≤ `COVER_LETTER_MAX_SIZE_MB` (5 Mo), mêmes contraintes           |
| `experience_years`          | 0 ≤ valeur ≤ 70                                                  |
| `date_of_birth`             | ≥ 1900, âge ∈ [15..100]                                          |
| `linkedin_url`              | doit contenir `linkedin.com`                                     |
| `cover_letter` (texte)      | ≤ 20 000 caractères                                              |
| `signature_text`            | doit contenir le prénom, le nom ou l'email du candidat           |

Les mêmes bornes (experience_years/date_of_birth/linkedin_url) sont aussi
appliquées à `CandidateProfileSerializer`.

Réglable via env :
```env
CV_MAX_SIZE_MB=10
COVER_LETTER_MAX_SIZE_MB=5
```

---

## 3. Audit log (A3, A5)

Nouveau modèle `ApplicationAuditLog` (table `applications_audit_log`) :

| Champ            | Description                                                        |
| ---------------- | ------------------------------------------------------------------ |
| `application`    | FK candidature                                                     |
| `actor`          | FK User (null si système)                                          |
| `action`         | `status_change`, `manual_override`, `score_override`, `withdrawn`, `run_screening`, `note_updated` |
| `payload_before` | JSON snapshot AVANT                                                 |
| `payload_after`  | JSON snapshot APRÈS                                                 |
| `reason`         | Motif libre                                                         |
| `ip_address`     | IP de l'acteur (XFF-aware)                                          |
| `user_agent`     | UA tronqué à 255 chars                                              |
| `created_at`     | Indexé pour requêtes timeline                                       |

**Tous** les changements sensibles passent désormais par le helper
`apps.applications.services.record_audit_log()`, appelé automatiquement par :
- `transition_status()` — toute mise à jour de statut
- `apply_manual_override()`
- `withdraw_application()`
- `ApplicationRunScreeningView`
- `ApplicationNoteListCreateView` (création de note)

Consultation : `GET /api/v1/applications/<id>/audit/` (recruteur).

L'admin Django expose le log en **lecture seule** (pas d'add/edit, suppression
réservée au superuser).

---

## 4. Workflow (A4)

### Machine d'état

`apps.applications.services.ALLOWED_TRANSITIONS` impose les transitions
légitimes. Exemples :

```
applied        → preselected, rejected_preselection, shortlisted, rejected, withdrawn
preselected    → shortlisted, rejected_preselection, rejected_selection, rejected, withdrawn
shortlisted    → interview, rejected_selection, rejected, withdrawn, offer
interview      → offer, rejected_selection, rejected, withdrawn, shortlisted
offer          → hired, rejected, withdrawn, interview
hired          → (terminal)
rejected       → (terminal)
withdrawn      → (terminal)
```

`transition_status(application, new_status, force=False)` lève
`InvalidStatusTransition` si la cible n'est pas atteignable.
Un super-admin peut passer `force=True` (utile pour la correction de données).

### Retrait par le candidat
Nouvel endpoint **`POST /api/v1/applications/<id>/withdraw/`** (rôle candidat).
Refusé si la candidature est dans un statut terminal (`hired`, `rejected`,
`withdrawn`). Tracé dans l'audit log.

### Bulk status
**`POST /api/v1/applications/bulk-status/`** (recruteur, max 500 IDs par appel) :
```json
{
  "application_ids": [1, 2, 3],
  "status": "rejected",
  "reason": "Profil non retenu"
}
```
Retourne `{updated: [...], errors: [{id, detail}]}` (transitions refusées listées
individuellement, sans bloquer l'ensemble).

---

## 5. Performance (A7)

- `MyCandidateProfileView.patch()` : `bulk_update()` au lieu d'une boucle de `save()`.
- `MLScore` : conservation des **20 dernières prédictions** par candidature
  (`MLSCORE_MAX_PER_APPLICATION`, configurable).
- Indexes Candidate : `(company, is_anonymized)`, `(company, created_at)`,
  `(company, updated_at)` pour accélérer les requêtes de pool.

---

## 6. Unicité / normalisation (A8)

- `Candidate.save()` force `email = email.lower().strip()` avant insertion.
- Migration `0006_p10_hardening` normalise les emails existants (RunPython).
- L'`unique_together = (company, email)` devient effectivement case-insensitive.

---

## 7. RGPD (A9)

### Vue candidat « safe »
`MyApplicationsListView` retourne désormais `ApplicationCandidateSerializer`,
qui n'expose **plus** :
- `preselection_score`, `selection_score`
- `preselection_score_details`, `selection_score_details`
- `notes` (champ texte)
- `manual_override_reason`
- `is_manually_adjusted`, `manually_added_to_shortlist`, `screening_score`

### Portabilité (art. 20)
**`GET /api/v1/candidates/me/export/`** (rôle candidat) — JSON exhaustif
téléchargeable contenant tous les profils + candidatures + horodatages.

### Droit à l'effacement (art. 17)
- **Candidat** : `DELETE /api/v1/candidates/me/` — anonymise **tous** les profils
  liés au user (vide identifiants, supprime le CV, nullifie `user_id`, marque
  `is_anonymized=True`).
- **Recruteur** : `POST /api/v1/candidates/<id>/anonymize/` — anonymise un
  candidat à la demande, même sans compte plateforme.
- **Admin Django** : action de masse "Anonymiser les candidats sélectionnés".

Les candidatures sont **conservées** (statuts, scores agrégés) pour la
transparence RH, mais les données identifiantes sont vidées.

---

## 8. Rate limiting (A4)

Throttles DRF configurés via `settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']`,
surchargables par env :

| Scope            | Défaut       | Variables env                 |
| ---------------- | ------------ | ----------------------------- |
| `public_apply`   | 10/heure     | `THROTTLE_PUBLIC_APPLY=10/hour` |
| `export`         | 20/heure     | `THROTTLE_EXPORT=20/hour`       |
| `bulk_status`    | 60/heure     | `THROTTLE_BULK_STATUS=60/hour`  |
| `predict_score`  | 120/heure    | `THROTTLE_PREDICT_SCORE=120/hour` |
| Global anonyme   | 60/min       | `THROTTLE_ANON=60/min`          |
| Global user      | 300/min      | `THROTTLE_USER=300/min`         |

Vues protégées : `PublicApplyView`, `ExportApplicationsExcelView`,
`ExportShortlistedExcelView`, `ExportCandidatesExcelView`,
`ApplicationBulkStatusView`, `ApplicationPredictScoreView`.

---

## 9. Fonctionnalités RH (A9)

### Notes internes
Nouveau modèle `ApplicationNote` (table `applications_note`) :
- Plusieurs notes horodatées par candidature, signées par leur auteur.
- Champ `is_pinned` pour épingler les notes importantes.
- Recruteur uniquement : `GET/POST /applications/<id>/notes/`,
  `GET/PATCH/DELETE /applications/notes/<id>/`.
- **Invisible côté candidat** (test dédié `InternalNoteTestCase`).

### Tags candidat
`Candidate.tags` (JSONField) — liste de mots-clés libres (top-talent, rappeler-2025-03,
remote-ok…). Limité à 30 tags par candidat, dédoublonnage case-insensitive,
trim automatique.
Endpoint dédié : **`PATCH /api/v1/candidates/<id>/tags/`**.

---

## 10. Tests (A10)

Nouveau fichier `apps/applications/tests_p10_hardening.py` — **24 tests** couvrant :

- `PermissionsHardeningTestCase` (4 tests) : candidats bloqués sur endpoints recruteur.
- `WriteSerializerRestrictionTestCase` : scores non modifiables via write API.
- `WorkflowStateMachineTestCase` (5 tests) : transitions, withdraw candidat, etc.
- `ManualOverrideAuditTestCase` : audit log créé.
- `CandidateEmailNormalizationTestCase` (2 tests) : lowercase + unicité.
- `CandidateRgpdTestCase` (3 tests) : mine masque, export, anonymisation.
- `FileValidationTestCase` (2 tests) : .exe rejeté, taille rejetée.
- `TagsAndBulkStatusTestCase` (3 tests) : tags, bulk-status, anti-DoS 500.
- `InternalNoteTestCase` (3 tests) : ajout recruteur, accès candidat refusé, body vide.

Lancer :
```bash
python manage.py test apps.applications.tests_p10_hardening --keepdb
```

---

## 11. Endpoints récapitulatifs

### Candidatures (`/api/v1/applications/`)
| Méthode | Route                                | Rôle      | Notes |
| ------- | ------------------------------------ | --------- | ----- |
| GET     | `/`                                  | recruteur | liste |
| POST    | `/`                                  | recruteur | création directe |
| GET     | `/mine/`                             | candidat  | **RGPD-safe** (sans champs internes) |
| GET     | `/my-application/`                   | candidat  | mon application pour une offre |
| POST    | `/bulk-status/`                      | recruteur | bulk-update, max 500 |
| GET/PATCH/DELETE | `/<id>/`                    | recruteur | PATCH ignore les scores |
| GET     | `/<id>/ats-breakdown/`               | recruteur | |
| PATCH   | `/<id>/status/`                      | recruteur | **state machine** + audit |
| POST    | `/<id>/manual-override/`             | recruteur | + audit |
| POST    | `/<id>/run-screening/`               | recruteur | + audit |
| POST    | `/<id>/predict-score/`               | recruteur | + MLScore cap |
| **POST**| **`/<id>/withdraw/`**                | candidat  | **nouveau** |
| GET/POST| `/<id>/notes/`                       | recruteur | **nouveau** |
| GET/PATCH/DELETE | `/notes/<id>/`              | recruteur | **nouveau** |
| GET     | `/<id>/audit/`                       | recruteur | **nouveau** |
| POST    | `/public/apply/`                     | candidat  | throttle 10/heure |
| GET     | `/export/xlsx/`                      | recruteur | throttle 20/heure |
| GET     | `/export/shortlisted/xlsx/`          | recruteur | throttle 20/heure |

### Candidats (`/api/v1/candidates/`)
| Méthode | Route                  | Rôle      | Notes |
| ------- | ---------------------- | --------- | ----- |
| GET     | `/`                    | recruteur | liste pool |
| POST    | `/`                    | recruteur | création |
| GET/PATCH| `/me/`                | candidat  | mon profil |
| **DELETE**| **`/me/`**           | candidat  | **anonymisation RGPD** |
| **GET** | **`/me/export/`**      | candidat  | **portabilité art. 20** |
| GET/PATCH/DELETE| `/<id>/`       | recruteur | détail |
| **PATCH**| **`/<id>/tags/`**     | recruteur | **nouveau** |
| **POST**| **`/<id>/anonymize/`** | recruteur | **anonymisation RGPD** |
| GET     | `/export/xlsx/`        | recruteur | throttle |

---

## 12. Migrations

- `apps/applications/migrations/0007_p10_hardening.py`  
  → crée `ApplicationAuditLog` et `ApplicationNote`.
- `apps/candidates/migrations/0006_p10_hardening.py`  
  → ajoute `tags`, `is_anonymized`, `anonymized_at`, indexes, normalise les emails
  en lowercase via RunPython.

Application :
```bash
python manage.py migrate
```

Idempotent et réversible (suppression des tables + retrait des colonnes).
