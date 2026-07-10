# Guide complet — Oracle VM EU + site Vercel (live)

Objectif : lancer `compare_tennis_aces_vs_fanduel.py` en **live** depuis ton telephone, 24/7, sans PC allume.

```
Telephone → Site Vercel → VM Oracle (EU) → scrape live → resultats
```

Temps total : ~30-45 min la premiere fois.

---

## Partie A — Compte Oracle + VM

### A1. Creer le compte

1. https://www.oracle.com/cloud/free/ → **Start for free**
2. Remplis le formulaire (carte souvent demandee pour verification, pas de debit si tu restes en Always Free)
3. Choisis une **region EU** a la creation du tenancy si possible :
   - **Germany Central (Frankfurt)** ou
   - **Netherlands Northwest (Amsterdam)**

### A2. Cle SSH sur Windows (avant de creer la VM)

PowerShell :

```powershell
ssh-keygen -t ed25519 -C "oracle-aces" -f "$env:USERPROFILE\.ssh\oracle_aces"
```

Appuie Entree 3 fois (pas de passphrase obligatoire).

Affiche la cle publique (a coller dans Oracle) :

```powershell
Get-Content "$env:USERPROFILE\.ssh\oracle_aces.pub"
```

Copie toute la ligne (`ssh-ed25519 AAAA...`).

### A3. Creer l'instance

1. Console Oracle → menu ≡ → **Compute** → **Instances**
2. **Create instance**
3. **Name** : `aces-runner`
4. **Image** : Ubuntu 22.04 (Always Free eligible)
5. **Shape** :
   - Ideal : **Ampere A1** → 1 OCPU, 6 GB RAM (Always Free)
   - Sinon : **VM.Standard.E2.1.Micro** (Always Free)
   - Si "Out of capacity" sur Ampere : change de region EU ou reessaie plus tard
6. **Networking** : coche **Assign a public IPv4 address**
7. **Add SSH keys** : colle ta cle publique
8. **Create**

Note l'**IP publique** affichee (ex. `132.145.x.x`).

### A4. Ouvrir le port 8787 (2 endroits)

#### 4a. Security list Oracle

1. Sur la page de l'instance → lien **Subnet** → **Security List** (Default)
2. **Add Ingress Rules** :
   - Source CIDR : `0.0.0.0/0`
   - IP Protocol : TCP
   - Destination port : `8787`
   - Description : `aces runner`
3. **Add Ingress Rules**

#### 4b. Pare-feu Ubuntu (sur la VM)

On le fera a l'etape B3.

---

## Partie B — Installer le projet sur la VM

### B1. Connexion SSH

PowerShell :

```powershell
ssh -i "$env:USERPROFILE\.ssh\oracle_aces" ubuntu@IP_PUBLIQUE_VM
```

Remplace `IP_PUBLIQUE_VM` par ton IP.

### B2. Paquets + clone

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git ufw

sudo mkdir -p /opt/testacevalue
sudo chown $USER:$USER /opt/testacevalue
cd /opt/testacevalue

git clone https://github.com/Noe-InTech/testacevalue.git .
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Repo prive ? Utilise :

```bash
git clone https://TON_TOKEN@github.com/Noe-InTech/testacevalue.git .
```

### B3. Pare-feu VM

```bash
sudo ufw allow OpenSSH
sudo ufw allow 8787/tcp
sudo ufw enable
sudo ufw status
```

### B4. Choisir un PIN secret

Exemple : `AcesLive2026!Noe` (note-le, ne le commite jamais).

Test manuel du runner :

```bash
cd /opt/testacevalue
source .venv/bin/activate
export RUNNER_SECRET="TON_PIN_ICI"
export RUNNER_HOST="0.0.0.0"
export RUNNER_PORT="8787"
python runner/server.py
```

Laisse tourner. Depuis ton PC (autre fenetre PowerShell) :

```powershell
curl.exe -X POST "http://IP_VM:8787/api/trigger" -H "Content-Type: application/json" -H "X-Runner-Secret: TON_PIN_ICI" -d "{}"
```

Attends ~30 s puis :

```powershell
curl.exe "http://IP_VM:8787/api/results"
```

Si tu vois `"status":"success"` et des comparables → OK. Ctrl+C sur la VM pour arreter le test.

### B5. Service permanent (systemd)

Sur la VM :

```bash
sudo cp /opt/testacevalue/runner/aces-runner.service /etc/systemd/system/
sudo sed -i "s/CHANGE_ME/TON_PIN_ICI/" /etc/systemd/system/aces-runner.service
sudo systemctl daemon-reload
sudo systemctl enable --now aces-runner
sudo systemctl status aces-runner
```

Le runner redemarre tout seul si la VM reboot.

Logs :

```bash
journalctl -u aces-runner -f
```

---

## Partie C — Brancher Vercel

Tu as deja le site sur Vercel (root directory = `web`).

### C1. Variables d'environnement

Vercel → ton projet → **Settings** → **Environment Variables**

| Variable | Valeur | Notes |
|----------|--------|-------|
| `RUNNER_URL` | `http://IP_VM:8787` | IP Oracle, pas de slash final |
| `RUNNER_SECRET` | meme PIN que sur la VM | |
| `TRIGGER_SECRET` | PIN pour le telephone | peut etre le meme |

Coche **Production**, **Preview**, **Development**.

Les variables `GITHUB_*` ne sont plus necessaires pour le live (tu peux les laisser ou supprimer).

### C2. Redeploy

**Deployments** → dernier deploy → **⋯** → **Redeploy**.

---

## Partie D — Utilisation telephone

1. Ouvre ton URL Vercel
2. **Code secret** = `TRIGGER_SECRET`
3. Filtre optionnel : `sinner`, `fery`...
4. **Lancer comparaison live**
5. Attends ~25-30 s
6. Tableaux mis a jour (toutes les cotes + FR > FanDuel)

Astuce : **Ajouter a l'ecran d'accueil** pour un acces rapide.

---

## Depannage

| Symptome | Cause probable | Fix |
|----------|----------------|-----|
| Site : `RUNNER_URL manquant` | Variables Vercel | Ajoute + redeploy |
| Site : `Secret incorrect` | PIN different | Aligner TRIGGER_SECRET et RUNNER_SECRET |
| Timeout / pas de reponse | Port 8787 ferme | Security list + `ufw` |
| `curl` PC vers VM echoue | IP ou firewall | Verifie IP publique instance |
| Compare echoue dans logs | Books FR | Normalement OK en EU ; voir `journalctl` |
| Vercel n'atteint pas la VM | HTTP bloque | Verifie RUNNER_URL en `http://IP:8787` |

Test sante depuis la VM :

```bash
curl -s http://127.0.0.1:8787/api/results | head
```

Mise a jour du code sur la VM :

```bash
cd /opt/testacevalue
git pull
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart aces-runner
```

---

## Cout

- VM **Always Free** Oracle : 0 EUR/mois si tu restes dans les limites free tier
- Vercel Hobby : 0 EUR
- Carte : verification Oracle uniquement (selon region)
