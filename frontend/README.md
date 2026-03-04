# AfricaHire+ Frontend (ATS)

Interface React pour l'ATS AfricaHire+, connectée à l'API Django REST.

## Stack

- React 19 + TypeScript
- Vite 7
- Tailwind CSS 4
- Axios + React Query
- React Router v7
- i18next (FR/EN)
- @dnd-kit (Kanban pipeline)
- Lucide React (icônes)

## Prérequis

- Node.js 18+
- API Django démarrée (ex. `http://127.0.0.1:8000`)

## Installation

```bash
npm install
```

## Configuration

Copier `.env.example` en `.env` et adapter si besoin :

```bash
cp .env.example .env
```

- `VITE_API_URL` : URL de l'API (défaut : `http://127.0.0.1:8000/api/v1`)

## Logo

Placer le fichier **AfricaHire+.png** dans `public/logo/`.  
Si le fichier est absent, le nom "AfricaHire+" s'affiche à la place.

## Lancement

```bash
npm run dev
```

Ouvrir http://localhost:3000

## Build

```bash
npm run build
```

Les fichiers sont générés dans `dist/`.

## Fonctionnalités

1. **Authentification** : Connexion (JWT), inscription entreprise + premier recruteur
2. **Dashboard RH** : Statistiques et candidatures récentes
3. **Gestion offres** : Liste, création, édition, export CSV
4. **Pipeline candidats** : Vue Kanban par statut, glisser-déposer, export CSV / shortlist
5. **Profil candidat** : Fiche détaillée, candidatures, compétences
6. **Tests techniques** : Liste des tests, passage avec timer, soumission, export résultats CSV
7. **Templates emails** : CRUD templates (sujet, corps HTML, type)
8. **Multi-langue** : Français / Anglais (sélecteur dans la sidebar)

## CORS

En développement, le backend Django doit autoriser l’origine du frontend (ex. `http://localhost:3000`).  
Le projet utilise `django-cors-headers` ; en dev, `CORS_ALLOW_ALL_ORIGINS = True` est souvent utilisé.
