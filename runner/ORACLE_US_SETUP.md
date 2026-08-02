# Guide — 2e VM Oracle US (Bet365) + multi-runner

Objectif : scraper **Bet365 US** depuis un egress américain, puis merger les cotes
dans le compare EU (Winamax / Unibet / Betclic ↔ FanDuel / RotoWire / Bet365).

```
Telephone → Vercel → Runner EU (Oracle EU)
                         ├─ FR books + FanDuel (+ RotoWire)
                         └─ HTTP → Runner US (Oracle US) → Bet365 US
```

**Ne jamais scraper Bet365 depuis l’EU** : `va.bet365.com` redirige vers `.fr` + Cloudflare.

---

## Partie A — Creer la VM Oracle US

### A1. Region

Cree une **2e instance** Always Free dans une region **US** :
- **US East (Ashburn)**
- **US West (Phoenix)**
- **US West (San Jose)**

Nom suggere : `aces-runner-us`.

Meme shape que l’EU si possible (Ampere A1 1 OCPU / 6 GB, ou E2.1.Micro).

### A2. SSH

Reutilise ta cle `~/.ssh/oracle_aces` (ou une cle dediee `oracle_aces_us`).

### A3. Ports

Comme l’EU :
- Security list : TCP **22** + **8787**
- ufw ouvert par le script d’install

Note l’**IP publique US**.

---

## Partie B — Installer le runner US

Sur la VM US :

```bash
sudo apt-get update -qq
sudo apt-get install -y -qq git
sudo git clone https://github.com/Noe-InTech/testacevalue.git /opt/testacevalue
cd /opt/testacevalue
sudo RUNNER_SECRET=TON_SECRET bash runner/install_us_runner.sh
```

Le service systemd part avec `RUNNER_ROLE=us` (`aces-runner-us.service`).

Endpoints utiles :
- `GET  /api/health` → `"role": "us"`
- `POST /api/us/bet365` → map normalisee Bet365 (auth `X-Runner-Secret`)

Exemple :

```bash
curl -sS -X POST "$US_RUNNER_URL/api/us/bet365" \
  -H "Content-Type: application/json" \
  -H "X-Runner-Secret: TON_SECRET" \
  -d '{"sport":"tennis","home":"Jannik Sinner","away":"Carlos Alcaraz","families":["aces","breaks"]}'
```

---

## Partie C — Brancher le runner EU

Sur la **VM EU** (`/etc/systemd/system/aces-runner.service`), ajoute :

```ini
Environment=US_RUNNER_URL=https://xxxxx.trycloudflare.com
Environment=US_RUNNER_SECRET=TON_SECRET
```

Puis :

```bash
sudo systemctl daemon-reload
sudo systemctl restart aces-runner
```

Le compare EU :
1. scrape FR + FanDuel (et RotoWire si applicable)
2. appelle le runner US pour Bet365
3. merge **meilleure cote US gagne** (par issue)
4. **soft-fail** si US down / non configure (compare FR↔FD continue)

Vercel garde `RUNNER_URL` = tunnel **EU** uniquement (triggers compares).  
`US_RUNNER_URL` n’est pas requis sur Vercel.

---

## Partie D — Tunnel Cloudflare US

Meme mecanisme que l’EU (`cloudflared-aces.service`).  
L’URL change a chaque restart cloudflared → mets a jour `US_RUNNER_URL` sur l’EU.

Astuce : apres reboot US,

```bash
sudo truncate -s 0 /var/log/cloudflared-aces.log
sudo systemctl restart cloudflared-aces
sudo journalctl -u cloudflared-aces -n 40 --no-pager | grep trycloudflare
```

---

## Partie E — Scrape Bet365 live

Etat actuel du client (`bet365_us_client.py`) :
- **Probe geo** : refuse si redirection `.fr` / Cloudflare challenge
- **Fixture** : `BET365_FIXTURE_JSON=/path/to.json` pour tests / dry-run
- **Live** : `BET365_LIVE_SCRAPE=1` reserve au parseur (Playwright / blobs) a activer sur la VM US

Tant que le parseur live n’est pas branche, le runner US repond `soft_fail` + `map: {}` si joignable, ce qui n’empeche pas le compare EU.

---

## Checklist

- [ ] VM Oracle region US creee + SSH
- [ ] `install_us_runner.sh` OK, health `role=us`
- [ ] Probe Bet365 ne redirige pas vers `.fr`
- [ ] `US_RUNNER_URL` + `US_RUNNER_SECRET` sur le runner EU
- [ ] Compare tennis/baseball/WNBA : colonne Book US peut afficher Bet365 US
- [ ] Couper le runner US → compare EU continue (soft-fail)
