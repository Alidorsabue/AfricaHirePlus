# Renforcement du module Tests techniques (mai 2026)

> Document de référence pour le hardening du module `apps/tests/` : tests
> d'évaluation des candidats (QCM, code, fichier, etc.). Ce document accompagne
> la migration `0006_hardening_p1_p6` et la nouvelle batterie de tests unitaires.

## Contexte

Avant ce chantier, le module `apps/tests/` présentait des failles classées en 7
axes (P1 → P7). La faille la plus grave (P1) : **tout candidat authentifié
pouvait récupérer les bonnes réponses** d'un test via `GET /api/v1/tests/<id>/`
(la permission `IsRecruiterOrAdmin` n'imposait que `is_authenticated`, et le
queryset ne filtrait pas pour les candidats). Le serializer `QuestionSerializer`
exposait `correct_answer` et `options[i].correct=True` — fuite catastrophique.

## P1 — Sécurité

### Endpoint dédié candidat (sans réponses)

- Nouveau serializer `CandidateQuestionSerializer` : strictement épuré.
  - `correct_answer` JAMAIS sérialisé.
  - Helper `_strip_correct_flag_from_options()` qui ne garde que les clés
    whitelistées (`id`, `label`, `value`, `image`, `attachment_url`).
- Nouveau serializer `CandidateTestSerializer` : sans `access_code` ni
  `passing_score` ni `company`.
- Nouveau endpoint `GET /api/v1/tests/<pk>/take/?application_id=<id>` :
  - `IsCandidate` uniquement.
  - Vérifie l'éligibilité (statut Application ∈ SHORTLISTED / INTERVIEW / OFFER).
  - Vérifie l'appartenance multi-tenant.
  - Retourne questions servies via `CandidateQuestionSerializer` + métadonnées
    de session (`seconds_left`, `status`).
- Ancien endpoint `GET /api/v1/tests/<pk>/` désormais strictement réservé aux
  recruteurs (queryset vide pour les candidats).

### Statut Application obligatoire

Toutes les actions candidat (`/start-session/`, `/auto-save/`, `/tab-switch/`,
`/upload-file/`, `/submit-answers/`, `/<pk>/take/`) passent par
`_ensure_candidate_can_take()` qui exige :

- Le candidat soit propriétaire de l'Application.
- `app.status ∈ {SHORTLISTED, INTERVIEW, OFFER}`.
- Le test appartienne à la company de l'offre.
- Le test (s'il a un `job_offer_id`) corresponde à l'offre de l'Application.

### Verrou anti-modification post-soumission

Nouveau `CandidateTestResult.is_finalized` (property) = True si
`is_completed` ou status ∈ {SUBMITTED, SCORED, EXPIRED}. Refus à 403/400 :

- `AutoSaveTestAnswersView` : verrou actif → impossible d'écraser les réponses
  après soumission.
- `UploadAnswerFileView` : verrou actif.
- `SubmitTestAnswersView` : re-soumission refusée (400).
- `TabSwitchView` : événements ignorés silencieusement (réponse 200 pour
  ne pas perturber le frontend).

### Whitelist upload de fichier réponse

`UploadAnswerFileView` :

- Taille max : **25 Mo**.
- Extensions **interdites** : `.exe`, `.bat`, `.cmd`, `.sh`, `.ps1`, `.msi`,
  `.com`, `.scr`, `.vbs`, `.jar`, `.dll`.
- Extensions **autorisées** : `.pdf`, `.docx`, `.xlsx`, `.pptx`, `.csv`, `.txt`,
  `.md`, `.json`, `.zip`, code (py/js/ts/java/cpp/…), images (png/jpg/…),
  fichiers métier (`.pbix`, `.twbx`, `.ipynb`).
- Préfixes MIME autorisés : `application/pdf`, `application/vnd.openxmlformats-officedocument…`,
  `application/zip`, `application/json`, `text/`, `image/`, `application/octet-stream`.

### Traçabilité IP

- `CandidateTestResult.client_ip` (1ère IP vue, audit) **est désormais rempli**
  par `_record_session_ip()` à chaque appel d'action.
- Nouveau champ `CandidateTestResult.last_seen_ip` : dernière IP vue (détection
  de changement de réseau pendant la session).
- Récupération via X-Forwarded-For (proxy-aware) avec fallback REMOTE_ADDR.

## P2 — Intégrité du scoring

### Bug QCM_MULTI sur-coché corrigé

**Avant** : si correct=[A,B] et candidat=[A,B,C,D,E] → ratio = good/total = 2/2
= **100 %**. Cocher tout payait.

**Maintenant** : `ratio = max(0, (good - wrong) / total_correct)`. Cocher tout
donne souvent 0 ou pénalise sévèrement. Tests verrouillés dans
`GradeQuestionQCMMultiBugFixTestCase`.

### Tolérance numérique configurable

Nouveau champ `Question.numeric_tolerance` (float, optionnel).

- Default : `0.01` (±1 %, comme avant).
- `0` : égalité stricte.
- `0.05` : ±5 %, etc.
- Si la bonne réponse est 0 et la tolérance > 0, on tolère `|user| <= tol`.

### `pending_review_points` exposé

Nouveau champ `CandidateTestResult.pending_review_points` qui agrège les points
en attente de notation manuelle (open_text / code / file_upload). Plus de
confusion : un test à 100 pts dont 70 en open_text affichera désormais
`score = 30, pending_review_points = 70` au lieu de simplement `30/100`.

### `is_passed` automatique

Nouveau champ `CandidateTestResult.is_passed` (BooleanField nullable).
Calculé automatiquement à la soumission ET après chaque review manuelle :

- `True` si `score >= test.passing_score`.
- `False` sinon.
- `None` si `passing_score` non défini.

### `total_score` synchronisé

`recompute_test_total_score(test)` : appelé automatiquement dans
`TestWriteSerializer.create()` et `.update()`. `Test.total_score` reflète
toujours la somme des points des questions.

### `Answer.is_correct` + `pending_manual_review` stockés

Avant : `Answer.score_obtained` seul, info perdue.
Maintenant : chaque ligne `Answer` stocke `is_correct` (True/False/None) et
`pending_manual_review`. Sert aux rapports détaillés et au workflow review.

## P3 — Validation stricte

`QuestionWriteSerializer.validate()` refuse désormais :

- QCM avec < 2 options.
- QCM avec IDs d'options en doublon.
- QCM choix unique avec plusieurs `correct: true`.
- QCM sans option marquée correcte ET sans `correct_answer` (piège : tout 0).
- Numérique sans `correct_answer`.
- Numérique avec `correct_answer` non-numérique.
- Numérique avec `numeric_tolerance` négative.
- Vrai/Faux sans `correct_answer`.
- `points = 0` (incompatible avec `MinValueValidator(1)` sur le modèle).

`TestWriteSerializer` :

- `duration_minutes = 0` refusé (validateur min=1).
- `passing_score < 0` refusé.
- `company` non éditable par le client (recruteur : forcé via `perform_create`).
- `total_score` recalculé automatiquement.

`Test` (modèle) :

- `UniqueConstraint(company, access_code)` conditionnel (uniquement si
  `access_code` non vide) → 2 tests ne peuvent pas partager le même code dans
  la même company.

## P4 — Workflow

### Expiration automatique des sessions abandonnées

Nouveau service `expire_session_if_needed(result)` :

- Vérifie si `started_at + duration_minutes < now()` et marque EXPIRED.
- Trace dans `TestAuditLog`.
- Appelé en début de chaque vue de session (`start`, `auto-save`, `submit`,
  `take`) → expiration "lazy" sans dépendre d'un cron.

Nouvelle management command `python manage.py expire_abandoned_sessions` :

- Parcourt toutes les sessions IN_PROGRESS et expire celles dont le timer est
  dépassé.
- Option `--notify` : envoie un email au candidat.
- Option `--dry-run` : simulation.
- À planifier toutes les 5–15 min (cron, Celery beat, Railway Schedule).

### Notifications email

Nouveau module `apps/emails/services.py` :

- `send_test_invitation(grant)` : email candidat avec lien token unique.
- `send_test_submitted_notification(result)` : email recruteur quand un
  candidat soumet (avec score, points en attente, verdict, suspicion).
- `send_test_expired_notification(result)` : email candidat en cas
  d'expiration auto.

Toutes ces fonctions sont **best-effort** (try/except, `fail_silently=True`) —
ne bloquent jamais la requête principale.

## P5 — Anti-triche avancé

### Token unique par candidat (`TestAccessGrant`)

Nouveau modèle `apps.tests.models.TestAccessGrant` :

- `token` : `secrets.token_urlsafe(32)` (entropie ~256 bits).
- `is_revoked`, `revoked_at`, `used_at`, `expires_at`.
- `unique_together(test, application)`.
- Endpoint `POST /api/v1/tests/check-access/` accepte désormais
  `{ token: "..." }` (priorité sur le `{ email, code, test_id }` legacy).

Avantages vs `Test.access_code` partagé :

- Révocation individuelle possible (1 candidat sans toucher les autres).
- Traçabilité de la première utilisation (`used_at`).
- Expiration par candidat.
- Lien personnalisé envoyé par email (cf P4).

### Shuffle / pool de questions

Nouveaux champs `Test` :

- `shuffle_questions` (bool) : ordre aléatoire stable par candidat.
- `shuffle_options` (bool) : options de QCM mélangées (à implémenter côté
  frontend pour préserver l'ordre stocké).
- `questions_per_session` (PositiveSmallInteger) : si défini, N questions
  tirées au hasard parmi toutes celles du test (pool).

Service `determine_question_order(test, result)` :

- Seed = `result.id` → ordre **stable** (refresh F5 = même ordre).
- Ordre stocké dans `CandidateTestResult.question_order` (audit + cohérence
  multi-requêtes).

## P6 — Performance + audit

### Optimisations

- `grade_test_answers()` : `select_related('section')` → fin du N+1.
- `submit_test_result()` : un seul parcours des questions (vs deux avant) ;
  `Answer` créés en `bulk_create` + `bulk_update`.
- `MyAvailableTestsView` : préchargement des Tests par company en un coup, plus
  de N+M.

### Audit log (`TestAuditLog`)

Nouveau modèle qui trace :

- `STATUS_CHANGE` : soumission, expiration auto.
- `MANUAL_REVIEW` : ajustement d'un score (open_text / code / file).
- `SCORE_OVERRIDE` : modification manuelle directe d'un score session.
- `FLAG_TOGGLED` : (réservé) modification du flag suspect.
- `ACCESS_REVOKED` : (réservé) révocation de token.

Chaque entrée stocke `old_value`, `new_value`, `actor`, `reason`, `client_ip`,
`created_at`. Permet d'expliquer pourquoi un score affiché diffère de la
soumission initiale (review manuelle, ré-évaluation).

### Review manuelle d'une réponse (`manual_review_answer`)

Nouveau service + endpoint `POST /api/v1/tests/answers/<answer_id>/review/` :

- Body : `{ score: 7.5, is_correct: true, reason: "Bonne approche" }`.
- Recalcule le score total de la session à partir de la table `Answer`
  (source de vérité, plus du `answers` JSON).
- Met à jour `is_passed` et `pending_review_points`.
- Trace dans `TestAuditLog`.
- Permission `IsRecruiterOrAdmin` + check multi-tenant.

## P7 — Tests unitaires

Trois nouveaux fichiers de tests dans `apps/tests/` :

### `tests_services.py` (~30 tests)

- `GradeQuestionTestCase` : tous les types de question (QCM single, true/false,
  open text, code, file).
- `GradeQuestionQCMMultiBugFixTestCase` : **verrouille le fix P2**
  (sur-cochage → 0).
- `NumericToleranceTestCase` : tolérance configurable, cas correct=0,
  cas invalides.
- `GradeTestAnswersTestCase` : pipeline complet, formats de clés
  (`id`/`str(id)`/`question_<id>`).
- `SubmitTestResultTestCase` : persistance, `is_passed`, `client_ip`,
  audit log.
- `ExpireSessionTestCase` : expiration auto, idempotence.
- `ManualReviewAnswerTestCase` : recalcul score, audit, clamp min/max.
- `QuestionOrderTestCase` : shuffle stable, pool < total.
- `RecomputeTotalScoreTestCase` : sync `Test.total_score`.

### `tests_serializers.py` (~20 tests)

- `CandidateSerializerSecurityTestCase` : **vérifie qu'aucune
  `correct_answer` ne fuit** pour QCM, open_text, numérique, et que les
  options sont strippées du flag `correct`.
- `RecruiterSerializerExposesCorrectAnswerTestCase` : le serializer recruteur
  doit continuer à exposer (test contre-régression).
- `QuestionWriteValidationTestCase` : tous les cas de validation P3.
- `TestWriteValidationTestCase` : duration / passing_score.

### `tests_views.py` (~15 tests)

- `CandidateAccessToTestDetailTestCase` : candidat **rejeté** sur
  `GET /tests/<id>/`, **accepté** sur `/tests/<id>/take/` avec questions
  sans correct_answer.
- `CandidateMustBeShortlistedTestCase` : candidat APPLIED → 403,
  REJECTED → 403, SHORTLISTED → 200.
- `PostSubmissionLockTestCase` : auto-save / submit refusés après SCORED.
- `UploadFileSecurityTestCase` : `.exe`, `.bat`, `.sh` refusés ; `.pdf`
  accepté ; > 25 Mo refusé.
- `TimerExpirationTestCase` : submit après deadline → 400.
- `TestAccessGrantTokenTestCase` : token P5, révocation, expiration,
  `used_at`.
- `MultiTenantIsolationTestCase` : candidat ne peut pas passer le test
  d'une autre company.
- `ClientIPRecordingTestCase` : IP enregistrée à l'ouverture de session.

Lancement : `python manage.py test apps.tests`.

## Migration & déploiement

Migration générée : `apps/tests/migrations/0006_hardening_p1_p6.py`.

### Étapes

1. `python manage.py migrate tests 0006`
2. (Optionnel) Planifier `python manage.py expire_abandoned_sessions --notify`
   en cron toutes les 10 min.
3. Mise à jour du frontend : utiliser `/api/v1/tests/<id>/take/?application_id=...`
   au lieu de `/api/v1/tests/<id>/` pour les candidats (sinon 403/404).
4. Communiquer aux recruteurs la nouvelle option "shuffle questions" et le
   nouveau champ `passing_score` qui détermine désormais le verdict.

### Compatibilité ascendante

- L'ancien `Test.access_code` continue de fonctionner (mode legacy de
  `CheckTestAccessView`).
- Les anciennes `Question.question_type` legacy (`single_choice`,
  `multiple_choice`, `number`, `boolean`, `text`) sont toujours supportées
  par le scoring.
- Les `Answer` existants restent compatibles (les nouveaux champs `is_correct`
  / `pending_manual_review` sont nullable / default).

## Modèles modifiés / ajoutés

```
Test
├─ + shuffle_questions: bool
├─ + shuffle_options: bool
├─ + questions_per_session: int?
└─ + UniqueConstraint(company, access_code) conditionnel

Question
├─ + numeric_tolerance: float?
└─ * points: MinValueValidator(1)

CandidateTestResult
├─ + is_passed: bool?
├─ + pending_review_points: Decimal?
├─ + last_seen_ip: IP
├─ + question_order: JSON
└─ + property is_finalized

Answer
├─ + is_correct: bool?
└─ + pending_manual_review: bool

+ TestAccessGrant  (P5)
+ TestAuditLog     (P6)
```

## Endpoints modifiés / ajoutés

| Méthode | URL | Avant | Après |
|---|---|---|---|
| GET | `/tests/<pk>/` | recruteur + candidat (FAILLE) | **recruteur uniquement** |
| GET | `/tests/<pk>/take/?application_id=…` | — | **nouveau candidat-safe** |
| POST | `/tests/check-access/` | email+code | email+code OU token P5 |
| POST | `/tests/upload-file/` | tout fichier | whitelist + max 25 Mo |
| POST | `/tests/auto-save/` | tout statut | refusé si is_finalized |
| POST | `/tests/submit-answers/` | sans is_passed | + `is_passed` + `pending_review_points` |
| POST | `/tests/answers/<id>/review/` | — | **nouveau, review manuelle recruteur** |

## Notes pour le frontend

- Adapter `TechnicalTest.tsx` : remplacer `testsApi.get(id)` (qui retournera
  désormais 403 pour les candidats) par un nouvel appel
  `testsApi.takeAsCandidate(testId, applicationId)`.
- Afficher `pending_review_points` dans le récap de fin de test
  (« Votre score initial : X / Y. Z points sont en attente de notation
  manuelle par le recruteur. »).
- Afficher le verdict `is_passed` (réussi / échec / en attente).
- Pour les recruteurs : ajouter un bouton "Noter cette réponse" sur chaque
  question open_text / code / file_upload du rapport, qui appelle
  `POST /tests/answers/<id>/review/`.

## P8 — Rôle Correcteur externe (mai 2026)

> Ajouté dans la migration `0007_corrector_role`. Permet à un recruteur de
> déléguer la correction des tests techniques à un expert métier externe,
> **sans lui créer de compte plateforme** et **sans qu'il puisse identifier
> les candidats**.

### Concept

Le correcteur est une **identité fonctionnelle** (un simple email) à laquelle
on associe un **token magique** (`secrets.token_urlsafe(48)` → ~64 chars). Le
recruteur lui envoie un lien : il clique, accède à l'interface, note les
réponses. Pas d'inscription, pas de mot de passe.

L'interface présente les soumissions de manière **strictement anonyme** :
chaque candidat est identifié par un code court unique au test
(`C-A3F9B2C1`). Aucun nom, email, téléphone, photo ou CV n'est exposé.

### Modèle de données

```
CorrectorAssignment
├─ email              # identité fonctionnelle
├─ full_name          # optionnel, pour personnaliser l'email
├─ token              # 48 octets URL-safe, unique, indexé
├─ test (FK)          # un correcteur ne corrige qu'un test
├─ company (FK)       # multi-tenant
├─ all_candidates: bool    # True → voit toutes les sessions SCORED
├─ assigned_applications (M2M)  # si all_candidates=False
├─ assigned_by, revoked_by, assigned_at, revoked_at
├─ expires_at         # défaut 30j, configurable, peut être None
├─ first_used_at, last_used_at, use_count
└─ is_revoked

CandidateTestResult
└─ + display_code     # 'C-A3F9B2C1' anonymisé, généré lazy
```

### Périmètre de visibilité

| Configuration | Ce que voit le correcteur |
|---|---|
| `all_candidates=True` (défaut) | Toutes les sessions SCORED du test, y compris **les soumissions futures** |
| `all_candidates=False` + 3 applications assignées | Uniquement les 3 sessions correspondantes |
| Détail d'une session hors périmètre | **404** systématique |
| Tentative de noter une réponse hors périmètre | **403** systématique |

### Endpoints

**Côté recruteur** (auth JWT) :

| Méthode | URL | Description |
|---|---|---|
| GET | `/tests/<test_id>/correctors/` | Liste des correcteurs du test |
| POST | `/tests/<test_id>/correctors/` | Créer une assignation + envoyer l'email |
| PATCH | `/correctors/<id>/` | Mettre à jour scope/expiration |
| DELETE | `/correctors/<id>/` | Révoquer (token invalide immédiatement) |

Payload POST :

```json
{
  "email": "expert@cabinet-rh.com",
  "full_name": "Marie Expert",
  "assigned_application_ids": [12, 17, 23],   // null/absent = tous
  "expires_in_days": 30
}
```

**Côté correcteur** (auth token `?token=…` OU header `X-Corrector-Token`) :

| Méthode | URL | Description |
|---|---|---|
| POST | `/tests/correctors/auth/check/` | Validation token + contexte |
| GET | `/tests/correctors/sessions/` | Liste anonymisée des sessions à corriger |
| GET | `/tests/correctors/sessions/<id>/` | Détail anonymisé avec toutes les réponses |
| POST | `/tests/correctors/answers/<id>/review/` | Modifier le score d'une réponse |

Toutes les vues correcteur ont `authentication_classes = []` pour empêcher un
JWT valide de court-circuiter la vérification du token.

### Anonymisation : ce qui ne fuit JAMAIS

Les serializers `CorrectorSessionListSerializer`, `CorrectorSessionDetailSerializer`,
`CorrectorAnswerSerializer` **n'exposent jamais** :

- `application.candidate.first_name`, `last_name`
- `application.candidate.email`, `phone`, `photo`, `cv_file`
- `application.id` (côté payload — l'URL utilise `result.id` neutre)
- Aucun champ free-text issu du profil candidat

Ce qui est exposé :
- `display_code` (ex. `C-A3F9B2C1`)
- Score, max_score, status, submitted_at, is_passed, is_flagged, tab_switch_count
- Titre du test + description + job role (titre de l'offre seulement)
- Pour chaque réponse : `question_text`, `question_options`,
  `question_correct_answer` (oui, le correcteur a besoin du corrigé pour noter),
  `response` du candidat, `score_obtained`, `is_correct`, `file_url`

> **Note de sécurité** : le `file_url` (uploads candidat) peut techniquement
> contenir le nom du fichier original. Tu peux durcir plus tard en renommant
> les fichiers à l'upload (`tests/answers/%Y/%m/<uuid>.ext`).

### Possibilité de modifier les réponses auto-corrigées

Le correcteur peut **modifier le score de TOUTES les questions**, y compris :

- QCM (single / multi)
- Vrai/Faux
- Numérique

Pas seulement les `pending_manual_review`. C'est utile quand :

- L'énoncé est ambigu (le candidat a une interprétation valide non prévue).
- Une bonne réponse alternative a été acceptée par le correcteur.
- Le candidat a écrit une justification dans un autre champ que celui attendu.

Chaque modification :

1. Met à jour `Answer.score_obtained` (clamp 0 ↔ `question.points`).
2. Recalcule `CandidateTestResult.score` à partir de la **table `Answer`**
   (source de vérité — plus du JSON `answers`).
3. Met à jour `pending_review_points` et `is_passed`.
4. Crée un `TestAuditLog` avec `action='corrector_review'`,
   `corrector=<assignment>`, et `actor=None` (le correcteur n'est pas un User).

### Email d'invitation

Service `send_corrector_invitation(assignment)` (best-effort, fail-silent) :

- Sujet : `[<Company>] Invitation à corriger un test technique`
- Contenu : test, job role, périmètre (tous / N candidats), lien magique,
  date d'expiration, rappel anonymisation, interdiction de partage.
- Lien construit via :
  ```python
  link = f'{settings.FRONTEND_BASE_URL}{settings.CORRECTOR_LINK_PATH}?token={token}'
  ```
  - `FRONTEND_BASE_URL` : base de l'app frontend (vide en local).
  - `CORRECTOR_LINK_PATH` : défaut `/correct`.

Service `send_corrector_revocation(assignment)` envoyé en option à la révocation.

### Rotation du token à la réassignation

Si le recruteur "réassigne" la même adresse email (création POST avec un email
déjà présent pour ce test), `assign_corrector()` :

1. Réactive l'assignation (`is_revoked=False`).
2. **Régénère un nouveau token** (rotation de sécurité).
3. Met à jour `expires_at`, `all_candidates`, M2M.

L'ancien token est invalide immédiatement. C'est important si le précédent
lien a fuité ou été partagé.

### Audit log

Trois nouvelles actions dans `TestAuditLog.Action` :

- `CORRECTOR_ASSIGNED` : création d'une assignation (avec `actor=recruteur`).
- `CORRECTOR_REVOKED` : révocation (avec `actor=recruteur, corrector=…`).
- `CORRECTOR_REVIEW` : notation par le correcteur
  (`actor=None, corrector=assignment, old_value=…, new_value=…, reason=…`).

Permet de répondre à : « pourquoi le score est-il passé de 80 à 65 ? »
→ Audit log montre l'intervention du correcteur avec sa raison.

### Tests de non-régression

`apps/tests/tests_corrector.py` couvre :

- **Anonymisation** : aucun email/nom de candidat dans les payloads liste et
  détail correcteur.
- **Token** : missing / invalid / revoked / expired tous refusés ; query
  string OK ; `use_count` incrémenté.
- **Périmètre** : `all_candidates=True` voit tout, restreint voit les N
  attribués, détail/review d'une session hors périmètre → 404/403.
- **Override** : QCM auto-correcte peut être abaissée OU augmentée par le
  correcteur ; score clampé au max ; audit log créé avec `corrector` FK.
- **Recruteur** : CRUD complet, multi-tenant, rotation token à la réassignation,
  pas de fuite du token complet dans la réponse list.
- **Auth check** : retourne contexte test + scope.

### Frontend — points d'attention

L'interface correcteur doit :

1. Lire le `token` dans l'URL (`?token=…`).
2. L'envoyer en header `X-Corrector-Token` sur toutes les requêtes API
   (recommandé) — évite que le token apparaisse dans les logs serveur ou
   l'historique navigateur.
3. **Ne JAMAIS** afficher de nom/email candidat, même si pour une raison
   quelconque l'API en renvoyait (défense en profondeur).
4. Présenter `display_code` partout où on parlerait habituellement du candidat
   (« Candidat C-A3F9B2C1 — score 67/100 »).
5. Sur chaque réponse, afficher le score actuel + un bouton "Modifier le
   score" qui ouvre un dialog avec : nouveau score, is_correct (radio),
   raison (texte libre).

### Limites connues spécifiques au correcteur

- Pas d'envoi automatique d'invitation lors d'une réassignation par PATCH
  (volontairement — le recruteur peut envoyer manuellement via un endpoint à
  ajouter si besoin).
- Pas de notification automatique au recruteur quand le correcteur termine.
- Pas de protection anti-replay sur le token : si le correcteur reproduit la
  même requête de review avec les mêmes paramètres, elle s'applique
  idempotemment (overwrite). Idempotent par design.

## Limitations connues

- `Test.shuffle_options` est stocké côté serveur mais le shuffle effectif des
  options nécessite une adaptation frontend (renvoyer dans l'ordre stocké
  dans le pseudo-état `question_order` étendu, ou shuffler côté serveur dans
  `CandidateQuestionSerializer.get_options`). À implémenter dans une étape
  ultérieure si l'équipe RH demande cette protection en plus du shuffle de
  questions.
- L'envoi des emails d'invitation (`send_test_invitation`) n'est pas câblé
  automatiquement quand un candidat passe SHORTLISTED — il faudra brancher
  un signal `post_save` sur `Application` ou un appel explicite dans
  `apply_manual_override`/workflow.
