# Configuration SMTP – AfricaHirePlus

L’application envoie des e-mails automatiques (candidature reçue, shortlist, refus). Pour envoyer de vrais e-mails, configurez un serveur SMTP via les variables d’environnement.

## 1. Où configurer

- **Développement** : créez un fichier `.env` à la racine du projet (à côté de `manage.py`), ou définissez les variables dans votre environnement.
- **Production** : utilisez les variables d’environnement de votre hébergeur (Railway, Heroku, serveur, etc.).

Copiez les variables depuis `.env.example` et remplissez les valeurs selon votre fournisseur (voir exemples ci‑dessous).

## 2. Variables requises

| Variable | Description | Exemple |
|----------|-------------|---------|
| `EMAIL_BACKEND` | Backend Django (SMTP pour envoi réel) | `django.core.mail.backends.smtp.EmailBackend` |
| `EMAIL_HOST` | Serveur SMTP | `smtp.gmail.com`, `ssl0.ovh.net`, etc. |
| `EMAIL_PORT` | Port (souvent 587 ou 465) | `587` |
| `EMAIL_USE_TLS` | Activer TLS (port 587) | `true` |
| `EMAIL_USE_SSL` | Activer SSL (port 465) | `false` (sauf si port 465) |
| `EMAIL_HOST_USER` | Votre adresse ou identifiant SMTP | `noreply@votredomaine.com` |
| `EMAIL_HOST_PASSWORD` | Mot de passe ou mot de passe d’application | (secret) |
| `DEFAULT_FROM_EMAIL` | Adresse expéditeur affichée | `noreply@votredomaine.com` ou `"Nom" <noreply@...>` |

En **production**, si `EMAIL_HOST` est défini, le backend SMTP est activé automatiquement (voir `config/settings/prod.py`).

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

### OVH

Pour un e-mail OVH (ex. `noreply@votredomaine.com`) :

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

Avec port 465 (SSL) :

```env
EMAIL_HOST=ssl0.ovh.net
EMAIL_PORT=465
EMAIL_USE_TLS=false
EMAIL_USE_SSL=true
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

Après avoir configuré les variables et redémarré l’application :

```bash
python manage.py send_test_email alidorsabue1@outlook.com
```

Un e-mail de test est envoyé à l’adresse indiquée. Si vous le recevez, la configuration SMTP est correcte.

## 5. En développement sans SMTP

Sans aucune config SMTP, les messages sont affichés dans le **terminal** où tourne `runserver` (backend console). Aucune variable n’est obligatoire pour développer.

Pour forcer l’envoi SMTP en dev, définissez au minimum `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_HOST_USER` et `EMAIL_HOST_PASSWORD` dans votre `.env`.
