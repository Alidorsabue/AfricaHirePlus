# Configuration SMTP – AfricaHirePlus

L’application envoie des e-mails automatiques (candidature reçue, shortlist, refus). Pour envoyer de vrais e-mails, configurez un serveur SMTP via les variables d’environnement.

## 1. Où configurer

- **Développement** : créez un fichier `.env` à la racine du projet (à côté de `manage.py`), ou définissez les variables dans votre environnement.
- **Production** : utilisez les variables d’environnement de votre hébergeur (Railway, Heroku, serveur, etc.).

Copiez les variables depuis `.env.example` et remplissez les valeurs selon votre fournisseur (voir exemples ci‑dessous).

## 2. Variables (référence)

| Variable | Description | Exemple |
|----------|-------------|---------|
| `EMAIL_BACKEND` | Backend Django (SMTP pour envoi réel) | `django.core.mail.backends.smtp.EmailBackend` |
| `EMAIL_HOST` | Serveur SMTP | `smtp.gmail.com`, `ssl0.ovh.net`, etc. |
| `EMAIL_PORT` | Port **SMTP** (souvent **587** ou **465**) | `587` |
| `EMAIL_USE_TLS` | STARTTLS (souvent avec port **587**) | `true` |
| `EMAIL_USE_SSL` | SSL implicite (souvent avec port **465**) | `false` sauf port 465 |
| `EMAIL_HOST_USER` | Identifiant SMTP | `noreply@votredomaine.com` |
| `EMAIL_HOST_PASSWORD` | Mot de passe ou clé API | (secret) |
| `DEFAULT_FROM_EMAIL` | Adresse expéditeur (en-tête From) | `noreply@votredomaine.com` |
| `SERVER_EMAIL` | Expéditeur des alertes / erreurs | souvent identique à `DEFAULT_FROM_EMAIL` |
| `EMAIL_FROM_DISPLAY_NAME` | Nom affiché à côté de l’adresse | `AfricaHirePlus` → *« AfricaHirePlus » \<noreply@…>* |
| `EMAIL_TIMEOUT` | Délai max. connexion/envoi (secondes) | `30` (défaut dans `config/settings/base.py`) |

### Expéditeur par entreprise (multi-tenant)

Les e-mails automatiques (candidature reçue, shortlist, refus) utilisent l’adresse **`email` de l’entreprise** (`Company.email`) comme en-tête **From**, avec le **nom de l’entreprise** comme nom d’affichage. Si ce champ est vide, l’expéditeur retombe sur `DEFAULT_FROM_EMAIL` / `EMAIL_FROM_DISPLAY_NAME`.

Renseignez donc pour chaque entreprise une adresse valide (ex. `rh@client.com`) dans les paramètres entreprise (API / interface).

**Côté SMTP** : l’authentification reste celle des variables globales (`EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD`). Votre fournisseur doit **autoriser l’envoi** avec l’adresse utilisée dans `From` (même domaine, alias, ou compte autorisé à « envoyer en tant que »). Sinon le serveur peut refuser ou les messages partiront en spam. Pour des domaines totalement distincts par client, il faudrait un relais transactionnel (SendGrid, Mailgun, etc.) avec domaines vérifiés ou des identifiants SMTP par entreprise (non géré par défaut dans ce projet).

**Ne pas confondre** : le port **993** sert à **IMAP** (lecture de boîte), pas à l’envoi SMTP. Si la configuration SMTP échoue, vérifiez port + combinaison TLS/SSL auprès de votre hébergeur.

En **production**, si `EMAIL_HOST` est défini, le backend SMTP est activé automatiquement (voir `config/settings/prod.py`).

### Voir la configuration effective (sans mot de passe en clair)

```bash
python manage.py send_test_email --show-config
```

Pour lister les entreprises (id, slug, e-mail) sans connaître l’id : `python manage.py send_test_email --list-companies`. Un test avec expéditeur « comme une entreprise » peut utiliser `--company-slug` ou `--company-email` au lieu de `--company-id`.

Utile après modification du `.env` ou des variables Railway pour confirmer ce que Django charge réellement.

## 3. Exemples par fournisseur

### Gmail

1. Activez l’accès « Applications moins sécurisées » ou, mieux, créez un **mot de passe d’application** (compte Google → Sécurité → Validation en 2 étapes → Mots de passe des applications).
2. Dans `.env` :

```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=true
EMAIL_USE_SSL=false
EMAIL_HOST_USER=votre.email@gmail.com
EMAIL_HOST_PASSWORD=votre_mot_de_passe_application
DEFAULT_FROM_EMAIL=votre.email@gmail.com
```

### Outlook / Microsoft 365

```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.office365.com
EMAIL_PORT=587
EMAIL_USE_TLS=true
EMAIL_USE_SSL=false
EMAIL_HOST_USER=votre.email@outlook.com
EMAIL_HOST_PASSWORD=votre_mot_de_passe
DEFAULT_FROM_EMAIL=votre.email@outlook.com
```

### OVH (Webmail / MX Plan / ancienne offre)

```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=ssl0.ovh.net
EMAIL_PORT=587
EMAIL_USE_TLS=true
EMAIL_USE_SSL=false
EMAIL_HOST_USER=noreply@votredomaine.com
EMAIL_HOST_PASSWORD=mot_de_passe_du_boite_mail
DEFAULT_FROM_EMAIL=noreply@votredomaine.com
```

Avec port **465** (SSL implicite) :

```env
EMAIL_HOST=ssl0.ovh.net
EMAIL_PORT=465
EMAIL_USE_TLS=false
EMAIL_USE_SSL=true
```

### OVH Zimbra (messagerie collaborative)

Pour une boîte **Zimbra** OVHcloud (ex. `contact@africaits.com`), l’authentification SMTP utilise en général **l’adresse e-mail complète** et le **mot de passe de la boîte** (ou un mot de passe d’application si votre organisation en impose un).

Le relais sortant le plus courant côté OVH reste **`ssl0.ovh.net`**. Si l’envoi échoue, vérifiez dans l’**espace client OVH** → E-mails → votre service Zimbra → aide « configuration d’un logiciel de messagerie » : un hôte du type `pro*.mail.ovh.net` peut être indiqué selon l’offre.

**Recommandé en premier (port 587 + STARTTLS)** :

```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=ssl0.ovh.net
EMAIL_PORT=587
EMAIL_USE_TLS=true
EMAIL_USE_SSL=false
EMAIL_HOST_USER=contact@africaits.com
EMAIL_HOST_PASSWORD=votre_mot_de_passe_boite_mail
DEFAULT_FROM_EMAIL=contact@africaits.com
SERVER_EMAIL=contact@africaits.com
EMAIL_FROM_DISPLAY_NAME=Africa ITS
EMAIL_TIMEOUT=30
```

**Alternative (port 465 + SSL)** si 587 est bloqué depuis votre hébergeur d’application :

```env
EMAIL_HOST=ssl0.ovh.net
EMAIL_PORT=465
EMAIL_USE_TLS=false
EMAIL_USE_SSL=true
EMAIL_HOST_USER=contact@africaits.com
EMAIL_HOST_PASSWORD=votre_mot_de_passe_boite_mail
DEFAULT_FROM_EMAIL=contact@africaits.com
SERVER_EMAIL=contact@africaits.com
```

### SendGrid

Après création d’une clé API SendGrid :

```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.sendgrid.net
EMAIL_PORT=587
EMAIL_USE_TLS=true
EMAIL_USE_SSL=false
EMAIL_HOST_USER=apikey
EMAIL_HOST_PASSWORD=votre_cle_api_sendgrid
DEFAULT_FROM_EMAIL=noreply@votredomaine.com
```

### Brevo (ex-Sendinblue)

```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp-relay.brevo.com
EMAIL_PORT=587
EMAIL_USE_TLS=true
EMAIL_USE_SSL=false
EMAIL_HOST_USER=votre_login_smtp_brevo
EMAIL_HOST_PASSWORD=votre_cle_smtp
DEFAULT_FROM_EMAIL=noreply@votredomaine.com
```

L’identifiant / mot de passe SMTP se créent dans l’espace Brevo (SMTP & API).

### Mailtrap (test uniquement)

Pour tester sans envoyer de vrais e-mails, utilisez Mailtrap : les messages sont capturés dans leur interface.

```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=sandbox.smtp.mailtrap.io
EMAIL_PORT=2525
EMAIL_USE_TLS=true
EMAIL_USE_SSL=false
EMAIL_HOST_USER=votre_user_mailtrap
EMAIL_HOST_PASSWORD=votre_password_mailtrap
DEFAULT_FROM_EMAIL=noreply@africahireplus.com
```

## 4. Tester l’envoi

1. Afficher la config chargée par Django :

```bash
python manage.py send_test_email --show-config
```

2. Envoyer un message de test :

```bash
python manage.py send_test_email votre@email.com
```

Si vous recevez le message, la configuration SMTP est correcte. En cas d’erreur, le terminal affiche l’exception SMTP (refus d’auth, mauvais port, etc.).

## 5. En développement sans SMTP

Sans aucune config SMTP, les messages sont affichés dans le **terminal** où tourne `runserver` (backend console). Aucune variable n’est obligatoire pour développer.

Pour forcer l’envoi SMTP en dev, définissez au minimum `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_HOST_USER` et `EMAIL_HOST_PASSWORD` dans votre `.env`.
