# Lancer les aces depuis ton telephone

Guide pas a pas. Temps total : ~10 minutes.

---

## Etape 1 — GitHub : creer le repo

1. Va sur https://github.com/new
2. **Repository name** : `values` (ou un autre nom — note-le)
3. Laisse **Public** ou **Private** (les deux marchent)
4. **Ne coche pas** "Add a README"
5. Clique **Create repository**

GitHub affiche des commandes — on les fait juste apres.

---

## Etape 2 — Pousser le code (sur ton PC)

Ouvre PowerShell dans `C:\Users\Noe\Desktop\Values` et execute :

```powershell
git init
git branch -M main
git add .
git commit -m "Add aces compare pipeline and mobile dashboard"
```

Remplace `TON_USER` et `values` par ton compte / nom de repo :

```powershell
git remote add origin https://github.com/TON_USER/values.git
git push -u origin main
```

GitHub te demandera de te connecter (navigateur ou token).

---

## Etape 3 — Token GitHub (pour Vercel)

1. https://github.com/settings/tokens?type=beta → **Generate new token**
2. Nom : `vercel-aces-trigger`
3. **Repository access** : Only select repositories → ton repo `values`
4. Permissions :
   - **Contents** : Read and write
   - **Actions** : Read and write
   - **Workflows** : Read and write
5. **Generate token** → **copie le token** (`github_pat_...`) — tu ne le reverras plus

---

## Etape 4 — Vercel : deployer le site

1. Va sur https://vercel.com/signup (compte gratuit avec GitHub)
2. **Add New… → Project**
3. Importe ton repo `values`
4. **Root Directory** : clique *Edit* → choisis **`web`**
5. **Deploy** (attends la fin du build)

---

## Etape 5 — Variables Vercel

Dans le projet Vercel : **Settings → Environment Variables**

Ajoute ces 5 variables (Production + Preview + Development) :

| Nom | Valeur | Exemple |
|-----|--------|---------|
| `GITHUB_TOKEN` | Token etape 3 | `github_pat_xxxx` |
| `GITHUB_OWNER` | Ton pseudo GitHub | `noe123` |
| `GITHUB_REPO` | Nom du repo | `values` |
| `GITHUB_BRANCH` | Branche | `main` |
| `TRIGGER_SECRET` | PIN de ton choix | `monpin2026` |

Puis **Redeploy** : Deployments → … → Redeploy.

---

## Etape 6 — Activer GitHub Actions

1. Sur GitHub : repo → onglet **Actions**
2. Si demande : **I understand my workflows, go ahead and enable them**
3. Tu dois voir le workflow **Aces compare**

Test manuel (optionnel) : Actions → Aces compare → **Run workflow** → Run.

Si ca echoue sur Betclic/Unibet → IP GitHub bloquee (voir fin du guide).

---

## Etape 7 — Utiliser depuis le telephone

1. Ouvre l’URL Vercel (ex. `https://values-xxx.vercel.app`)
2. **Code secret** : le `TRIGGER_SECRET` choisi a l’etape 5
3. Filtre optionnel : `sinner`, `fery`…
4. **Lancer comparaison live**
5. Attends ~30 secondes

---

## Depannage

| Probleme | Solution |
|----------|----------|
| `Code secret incorrect` | Verifie `TRIGGER_SECRET` sur Vercel + redeploy |
| `Configuration GitHub manquante` | Les 5 variables Vercel sont bien definies ? |
| `Echec du declenchement` | Token sans permission **Workflows** |
| Workflow rouge sur GitHub | Ouvre le log ; souvent blocage books FR |
| Resultats ne se mettent pas a jour | Attends 30 s ; recharge la page |

### Si les books FR bloquent GitHub

Les runners GitHub sont souvent hors France. Symptome : erreur HTTP Betclic/Unibet dans les logs Actions.

Solutions :
- Tester quand meme (parfois ca passe)
- Passer le scrape sur une VM EU gratuite (Oracle) — me demander si besoin

---

## Raccourci telephone

Sur iPhone/Android : navigateur → URL Vercel → **Ajouter a l’ecran d’accueil** = icone app.
