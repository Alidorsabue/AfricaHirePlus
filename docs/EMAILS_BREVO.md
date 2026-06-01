# Emails transactionnels — Brevo + pipeline durci (P9)

> Refactor du module `apps/emails/` : provider Brevo (API + SMTP), audit log
> de tous les envois, wrapper HTML brandé, templates par défaut étendus.

---

## 1. Architecture en un coup d'œil

```
   appel métier (apps/applications, apps/tests, ...)
            │
            ▼
   apps/emails/services.py     ← API publique (send_application_received, ...)
            │
            ▼
   apps/emails/dispatch.py     ← orchestration (audit + branding + envoi)
            │
            ▼
   apps/emails/branding.py     ← wrapper HTML email branded (header + CTA)
            │
            ▼
   Django EmailMultiAlternatives
            │
            ▼
   EMAIL_BACKEND configuré :
     ├── apps.emails.backends.BrevoApiBackend  (recommandé prod)
     ├── django.core.mail.backends.smtp.EmailBackend  (SMTP générique / Brevo SMTP)
     └── django.core.mail.backends.console.EmailBackend  (dev local)
```

Chaque envoi laisse une trace dans `EmailLog` (table `emails_emaillog`).

---

## 2. Configuration Brevo

### 2.a Option recommandée : API REST Brevo (HTTP)

Plus performant que SMTP, retourne un `message-id` pour le tracking et active
les statistiques Brevo (ouvertures, clics, bounces).

```bash
# .env (à la racine du projet)
BREVO_API_KEY=xkeysib-XXXXXXXXXXXXXXXXXX-YYYYYYYYYYYY
DEFAULT_FROM_EMAIL=noreply@votredomaine.com
EMAIL_FROM_DISPLAY_NAME=AfricaHire+
FRONTEND_BASE_URL=https://app.votredomaine.com  # pour les liens magiques
```

Aucune autre variable n'est nécessaire : si `BREVO_API_KEY` est défini,
le backend `BrevoApiBackend` est sélectionné automatiquement.

**Étapes côté Brevo :**

1. Créer un compte sur [brevo.com](https://www.brevo.com).
2. SMTP & API → Clés API → "Générer une nouvelle clé".
3. Configurer & valider l'expéditeur (`Sender, Domain & Dedicated IP`) avec
   les enregistrements DNS SPF + DKIM + DMARC.
4. Ajouter `BREVO_API_KEY` dans les variables d'environnement de production.

### 2.b Option alternative : Brevo SMTP

Drop-in remplacement d'un autre SMTP. Plus simple, pas de tracking message-id.

```bash
EMAIL_HOST=smtp-relay.brevo.com
EMAIL_PORT=587
EMAIL_USE_TLS=true
EMAIL_HOST_USER=votre-email@brevo.com   # login Brevo
EMAIL_HOST_PASSWORD=votre-smtp-key      # SMTP key (différent de l'API key !)
DEFAULT_FROM_EMAIL=noreply@votredomaine.com
EMAIL_FROM_DISPLAY_NAME=AfricaHire+
```

### 2.c Dev local

Aucune variable email → backend `console` (les emails apparaissent dans
le terminal `manage.py runserver`).

---

## 3. Auto-détection du backend

Le fichier `config/settings/base.py` choisit automatiquement :

| Variable env définie | Backend choisi |
|---|---|
| `BREVO_API_KEY` | `apps.emails.backends.BrevoApiBackend` |
| `EMAIL_HOST` (sans `BREVO_API_KEY`) | `django.core.mail.backends.smtp.EmailBackend` |
| aucune | `django.core.mail.backends.console.EmailBackend` |

Tu peux toujours forcer manuellement via `EMAIL_BACKEND=…` dans l'env.

---

## 4. Audit log (`EmailLog`)

Chaque envoi via `dispatch_email()` crée une entrée :

| Champ | Description |
|---|---|
| `recipient_email` | destinataire |
| `subject` | sujet rendu |
| `template_type` | type (`test_invitation`, `corrector_invitation`, etc.) |
| `status` | `pending` → `sent` / `failed` / `skipped` |
| `attempts` | nombre de tentatives |
| `provider` | backend utilisé (`brevo_api`, `smtp`, `console`) |
| `provider_message_id` | `messageId` Brevo (pour debug + webhooks) |
| `error_message` | détail de l'erreur si `failed` |
| `related_application_id` | FK lâche vers Application |
| `related_object_type/id` | objet déclencheur (CorrectorAssignment, TestAccessGrant…) |
| `sent_at` | timestamp d'envoi réussi |

**Désactiver l'audit (perf)** : `EMAIL_AUDIT_LOG_ENABLED=false`.

### Purge

```bash
python manage.py purge_old_email_logs              # respecte EMAIL_LOG_RETENTION_DAYS (défaut 90)
python manage.py purge_old_email_logs --days 30
python manage.py purge_old_email_logs --status failed   # garde les sent
python manage.py purge_old_email_logs --dry-run
```

Configurer un cron hebdomadaire en prod.

---

## 5. Pipeline d'envoi côté code

### 5.a Pour les emails métier "premier niveau"

L'API publique reste `apps.emails.services.*` (signatures identiques) :

```python
from apps.emails.services import (
    send_application_received,
    send_shortlist_notification,
    send_rejection_notification,
    send_test_invitation,
    send_test_submitted_notification,
    send_test_expired_notification,
    send_corrector_invitation,
    send_corrector_revocation,
)
```

Tous renvoient maintenant un `EmailLog | None` (utile pour debug, ignorable
sinon). Tous sont best-effort (n'élèvent jamais d'exception).

### 5.b Pour un email custom

Utiliser directement `dispatch_email()` :

```python
from apps.emails.dispatch import dispatch_email

log = dispatch_email(
    company=company,
    template_type='custom',
    recipient='john@ex.com',
    subject='Bonjour',
    body_html='<p>Contenu de l\'email</p>',
    cta_label='Voir mon profil',
    cta_url='https://app.ex.com/profile',
    preheader='Bienvenue chez nous',
    footer_note='Vous recevez cet email suite à votre inscription.',
    tags=['onboarding', 'welcome'],
)
```

Le wrapper s'occupe :
- du logo + couleur + footer entreprise,
- du bouton CTA cliquable + fallback URL en clair,
- du `text/plain` dérivé automatiquement,
- du logging,
- des retries (Brevo API : 3 tentatives sur 5xx/network).

---

## 6. Templates par défaut

À chaque création d'entreprise, le signal `company_post_save_create_default_email_templates`
crée automatiquement **8 templates** (par type) :

- `application_received`
- `shortlist_notification`
- `application_rejected`
- `test_invitation`
- `test_submitted` (notification recruteur)
- `test_expired` (candidat)
- `corrector_invitation`
- `corrector_revoked`

Le recruteur peut les éditer via l'admin Django ou le frontend (`/emails`).
Si un template est désactivé/supprimé, le code utilise un **fallback hardcodé**
de qualité équivalente (l'envoi ne tombe jamais).

### Variables disponibles

| Type | Variables |
|---|---|
| `application_*` | `candidate_name`, `candidate_email`, `job_title`, `company_name` |
| `test_invitation` | + `test_title`, `test_link` |
| `test_submitted` | + `test_title`, `score_str`, `verdict`, `pending_str`, `tab_switch_count`, `flagged_str` |
| `test_expired` | + `test_title`, `duration_minutes` |
| `corrector_invitation` | + `recipient_name`, `recruiter_name`, `test_title`, `job_title`, `scope_str`, `expires_str`, `corrector_link` |
| `corrector_revoked` | + `test_title` |

Syntaxe Django classique : `{{ candidate_name }}`.

---

## 7. Diagnostic en prod

### Tester l'envoi

```bash
python manage.py send_test_email moi@example.com
```

Affiche la configuration détectée + envoie un email de diagnostic. Le résultat
indique le `message_id` Brevo si succès :

```
Configuration e-mail actuelle :
  Provider détecté  = Brevo (API REST)
  EMAIL_BACKEND     = apps.emails.backends.BrevoApiBackend
  BREVO_API_KEY     = ***
  ...
E-mail de test envoyé à moi@example.com (id audit=42, message_id="<abc@brevo>").
```

### Consulter les logs

```python
from apps.emails.models import EmailLog

# Échecs récents par template
EmailLog.objects.filter(status='failed').values('template_type').annotate(n=Count('id'))

# Tous les envois pour un candidat
EmailLog.objects.filter(recipient_email='john@ex.com').order_by('-created_at')

# Retrouver un envoi via le messageId Brevo
EmailLog.objects.filter(provider_message_id='<abc@brevo>')
```

Ou via l'admin Django : `/admin/emails/emaillog/`.

---

## 8. Résilience & retries

- **Brevo API** : retry automatique sur erreurs réseau / 5xx / 429 (rate limit) —
  3 tentatives avec back-off exponentiel (0s, 0.8s, 2.0s).
- **Erreurs 4xx (sauf 429)** : pas de retry (cause fonctionnelle :
  domaine non vérifié, adresse invalide, etc.) — l'erreur est loguée dans
  `EmailLog.error_message`.
- **SMTP** : retry géré par Django (sortie standard de `EmailBackend`).
- **Validation destinataire** : si l'adresse est vide ou sans `@`, l'envoi est
  marqué `skipped` (pas de tentative réseau).

---

## 9. Sécurité

- La clé API Brevo n'est JAMAIS loguée (masquée par `***`).
- Les fichiers attachés > 10 Mo sont rejetés (limite Brevo).
- Le `From` est calculé par `apps.core.email_utils.get_from_email_for_company`
  (utilise `company.email` + nom si défini).
- Les liens magiques (correcteur, test) sont longs (32+ caractères hex) et
  uniques par destinataire.

---

## 10. Migration depuis l'ancien système

L'API publique `send_*` est **100 % compatible** : aucun appelant existant
n'a besoin d'être modifié. Les changements sont internes au module.

Pour bénéficier des nouveaux templates HTML brandés, les recruteurs n'ont rien
à faire — les fallbacks hardcodés sont déjà élégants. Pour personnaliser,
ils peuvent éditer les templates via `/emails` (frontend) ou l'admin Django.
