# Runner EU live (gratuit, sans PC a la maison)

Le mode **live** a besoin d'une IP europeenne. GitHub Actions (US) bloque souvent Betclic/Unibet/Winamax.

Solution : petite VM **Oracle Cloud Always Free** (Frankfurt/Amsterdam) qui execute le script en live 24/7.

## 1. Creer la VM Oracle (gratuit)

1. https://cloud.oracle.com → compte gratuit
2. **Compute → Instances → Create instance**
3. Image : **Ubuntu 22.04**
4. Shape : **Ampere A1** (Always Free) si dispo, sinon E2.1.Micro
5. Region : **Germany Central (Frankfurt)** ou **Netherlands (Amsterdam)**
6. Coche une cle SSH publique
7. Create

## 2. Ouvrir le port 8787

Networking → Security List → Ingress rule :

- Source : `0.0.0.0/0`
- Port : `8787`
- Protocol : TCP

## 3. Installer sur la VM

```bash
ssh ubuntu@IP_PUBLIQUE_VM

sudo apt update
sudo apt install -y python3 python3-venv python3-pip git

sudo mkdir -p /opt/testacevalue
sudo chown $USER:$USER /opt/testacevalue
cd /opt/testacevalue

git clone https://github.com/Noe-InTech/testacevalue.git .
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export RUNNER_SECRET="ton-pin-secret"
export RUNNER_HOST="0.0.0.0"
export RUNNER_PORT="8787"
python runner/server.py
```

Test depuis ton PC :

```bash
curl -X POST http://IP_VM:8787/api/trigger \
  -H "Content-Type: application/json" \
  -H "X-Runner-Secret: ton-pin-secret" \
  -d "{\"match\":\"\"}"
```

## 4. Service permanent (systemd)

```bash
sudo cp runner/aces-runner.service /etc/systemd/system/
sudo sed -i "s/CHANGE_ME/ton-pin-secret/" /etc/systemd/system/aces-runner.service
sudo systemctl daemon-reload
sudo systemctl enable --now aces-runner
sudo systemctl status aces-runner
```

## 5. Brancher Vercel (live uniquement)

Dans Vercel → Environment Variables :

| Variable | Valeur |
|----------|--------|
| `RUNNER_URL` | `http://IP_VM:8787` |
| `RUNNER_SECRET` | meme PIN que la VM |
| `TRIGGER_SECRET` | PIN saisi sur le telephone |

Redeploy Vercel.

Le site appellera directement le runner EU en **live** (~25 s).

## Securite

- Choisis un PIN fort
- Optionnel : limiter l'IP source du port 8787 a Vercel (plus complexe)
- Ne publie jamais `RUNNER_SECRET` dans le repo
