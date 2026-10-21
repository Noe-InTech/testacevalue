# Runner EU sur VPS OVH

Même stack que Oracle : repo dans `/opt/testacevalue`, systemd `aces-runner` + tunnel Cloudflare → `RUNNER_URL` sur Vercel.

## 1. Accès SSH (pour toi + Cursor)

Sur le VPS OVH, ajoute ta clé publique :

```powershell
Get-Content "$env:USERPROFILE\.ssh\oracle_aces.pub"
```

Colle-la dans le manager OVH (clé SSH à la création) ou dans `~/.ssh/authorized_keys` sur le serveur.

Sur **Windows**, crée ou complète `C:\Users\Noe\.ssh\config` :

```
Host aces-eu
  HostName REMPLACE_PAR_IP_OU_HOSTNAME
  User debian
  IdentityFile ~/.ssh/oracle_aces
  IdentitiesOnly yes
```

OVH Debian → user **`debian`**. Ubuntu → **`ubuntu`**.

Test :

```cmd
ssh -o ConnectTimeout=15 aces-eu "echo ok"
```

## 2. Fichier local pour l’agent (ne pas committer)

Copie `runner/ovh.local.env.example` → `runner/ovh.local.env` et remplis :

```env
RUNNER_SSH_HOST=aces-eu
RUNNER_SSH_USER=debian
```

`RUNNER_SSH_HOST` peut être l’alias `aces-eu` ou l’IP brute.

## 3. Installation runner (une fois sur le VPS)

```bash
sudo apt update && sudo apt install -y git python3 python3-venv
sudo mkdir -p /opt/testacevalue && sudo chown $USER:$USER /opt/testacevalue
git clone https://github.com/Noe-InTech/testacevalue.git /opt/testacevalue
cd /opt/testacevalue
sudo RUNNER_SECRET=TON_PIN bash runner/install_eu_runner.sh
```

Note l’URL `https://….trycloudflare.com` → **RUNNER_URL** sur Vercel (+ **RUNNER_SECRET** / **TRIGGER_SECRET**).

## 4. GitHub Actions « Repair runner »

Dans **Settings → Secrets** :

| Secret | Valeur |
|--------|--------|
| `RUNNER_SSH_HOST` | IP ou hostname OVH |
| `RUNNER_SSH_USER` | `debian` ou `ubuntu` |
| `ORACLE_SSH_KEY` | clé privée `oracle_aces` (inchangé) |

(`ORACLE_HOST` peut rester pour compat ; le workflow préfère `RUNNER_SSH_HOST`.)

## 5. Pare-feu OVH

Autorise **22** (SSH). Le runner écoute en **8787** en local ; Vercel passe par le **tunnel HTTPS**, pas besoin d’ouvrir 8787 sur Internet si tu utilises cloudflared.
