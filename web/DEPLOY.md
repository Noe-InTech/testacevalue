# Deploiement mobile (Vercel + GitHub Actions)

Site pour lancer `compare_tennis_aces_vs_fanduel.py` depuis ton telephone, sans PC allume.

## Fonctionnement

1. Tu ouvres le site Vercel sur ton telephone.
2. Tu saisis ton code secret + filtre match optionnel.
3. Le site declenche GitHub Actions.
4. Le workflow execute le script Python (~25 s) et pousse `web/public/latest_aces.json`.
5. Le site affiche les 2 sections (toutes les cotes + FR > FanDuel).

## Setup unique (~10 min)

### 1. GitHub

```bash
git init
git add .
git commit -m "Add aces compare web dashboard"
git branch -M main
git remote add origin https://github.com/TON_USER/TON_REPO.git
git push -u origin main
```

### 2. Vercel

1. Va sur [vercel.com](https://vercel.com) → **Add New Project**
2. Importe ton repo GitHub
3. **Root Directory** : `web`
4. Deploy

### 3. Variables d'environnement Vercel

Dans **Project Settings → Environment Variables** :

| Variable | Exemple | Role |
|----------|---------|------|
| `GITHUB_TOKEN` | `ghp_...` | PAT GitHub avec scope `repo` + `workflow` |
| `GITHUB_OWNER` | `ton-user` | Proprietaire du repo |
| `GITHUB_REPO` | `values` | Nom du repo |
| `GITHUB_BRANCH` | `main` | Branche (optionnel) |
| `TRIGGER_SECRET` | `mon-pin-123` | Code saisi sur le telephone |

### 4. Creer le token GitHub

GitHub → **Settings → Developer settings → Personal access tokens → Fine-grained token**

- Acces au repo concerne
- Permissions : **Contents** (read/write), **Actions** (read/write), **Workflows** (write)

## Utilisation quotidienne

1. Ouvre ton URL Vercel sur le telephone
2. Entre le code secret (memorise dans le navigateur)
3. Optionnel : `sinner`, `fery`, etc.
4. Appuie sur **Lancer comparaison live**
5. Attends ~30 s

## Limite importante

GitHub Actions tourne souvent hors France. Si Betclic/Unibet/Winamax bloquent l'IP, le workflow echouera. Dans ce cas, il faudra un petit serveur EU gratuit (Oracle Cloud) a la place de GitHub pour le scrape FR.

## Test local du site

```bash
cd web
npm install
npm run dev
```

Le site lira les fichiers locaux `web/public/*.json` tant que `GITHUB_OWNER` / `GITHUB_REPO` ne sont pas configures.
