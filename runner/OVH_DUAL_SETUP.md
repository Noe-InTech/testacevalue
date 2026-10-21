# Guide — 2 VPS OVH (France + US) + site Vercel

Objectif : remplacer Oracle Always Free quand Paris est saturé, avec **deux petites VMs OVH** :

```
Telephone → Vercel
              ├─ RUNNER_URL     → VPS OVH France (Winamax, Betclic, Unibet, compares)
              └─ RUNNER_US_URL  → VPS OVH US (Bet365 US, Piwi247, sites US)

VPS France appelle aussi le runner US en interne :
  US_RUNNER_URL + US_RUNNER_SECRET sur le service aces-runner (EU)
```

Budget typique : **~10–13 €/mois** (2× VPS-1 OVH), ou **~4,6 €/mois** en phase 1 (France seule).

---

## Phase 1 — France seule (recommande pour demarrer)

Tu peux **ne creer que le VPS FR** : tennis / WNBA / NBA / baseball + books FR + FanDuel fonctionnent sans runner US.

- **Vercel** : seulement `RUNNER_URL` + `RUNNER_SECRET` + `TRIGGER_SECRET` (pas besoin de `RUNNER_US_URL`).
- **VM FR** : ne configure **pas** `US_RUNNER_URL` sur `aces-runner.service` (Bet365 US reste en soft-fail).
- **Bandeau site** : le runner US affichera « Non configure » — normal.

Quand tu ajoutes Piwi247 / un autre site US : phase 2 (VPS US + `RUNNER_US_URL` sur Vercel + `US_RUNNER_URL` sur la VM FR).

Checklist phase 1 :

1. VPS OVH **Gravelines** ou **Strasbourg**, Ubuntu 22.04, VPS-1
2. SSH + `git clone` + `sudo RUNNER_SECRET=TON_PIN bash runner/install_eu_runner.sh`
3. Recuperer l’URL tunnel Cloudflare → `RUNNER_URL` sur Vercel → redeploy
4. Tester : comparer tennis depuis le site

Recuperer ton Python Oracle (si boot volume conserve) : copie `.env`, venv optionnel, ou `git pull` sur le repo.

---

## 1. Commander les VPS

### France (Gravelines ou Strasbourg)

1. https://www.ovhcloud.com/fr/vps/ → **VPS-1** (~4,57 € TTC/mois)
2. Ubuntu **22.04**
3. Cle SSH

### US (Virginia)

1. https://us.ovhcloud.com/vps/ → **VPS-1** (~4,54 $/mois)
2. Ubuntu **22.04**
3. Meme cle SSH

Le prix affiché « ~1,85 € boot volume » dans l’estimation OCI/OVH est souvent **hors Always Free** ; sur VPS OVH le disque est inclus dans l’offre.

---

## 2. Installer le runner **France**

```bash
ssh ubuntu@IP_FR
sudo apt-get update -qq && sudo apt-get install -y -qq git
sudo git clone https://github.com/Noe-InTech/testacevalue.git /opt/testacevalue
cd /opt/testacevalue
sudo RUNNER_SECRET=TON_PIN bash runner/install_eu_runner.sh
```

Service : `aces-runner.service` avec `RUNNER_ROLE=eu`.

Tunnel Cloudflare (comme Oracle) → note l’URL `https://....trycloudflare.com`.

### Mise à jour manuelle (git)

Le clone initial se fait souvent en `sudo` → le repo appartient à **root**. En tant qu’`ubuntu`, `git pull` peut afficher *dubious ownership*.

**Recommandé (une fois)** — rendre le repo à ton user SSH :

```bash
sudo chown -R ubuntu:ubuntu /opt/testacevalue
git config --global --add safe.directory /opt/testacevalue
cd /opt/testacevalue && git pull origin main
sudo systemctl restart aces-runner
```

**Sans changer les droits** — pull en root :

```bash
sudo git -C /opt/testacevalue pull origin main
sudo systemctl restart aces-runner
```

Ou réutiliser le script d’install (pull + deps + restart) :

```bash
cd /opt/testacevalue && sudo RUNNER_SECRET=TON_PIN bash runner/install_eu_runner.sh
```

---

## 3. Installer le runner **US**

```bash
ssh ubuntu@IP_US
sudo apt-get update -qq && sudo apt-get install -y -qq git
sudo git clone https://github.com/Noe-InTech/testacevalue.git /opt/testacevalue
cd /opt/testacevalue
sudo RUNNER_SECRET=TON_PIN bash runner/install_us_runner.sh
```

Service : `aces-runner-us.service` avec `RUNNER_ROLE=us`.

Tunnel Cloudflare US → note l’URL US.

---

## 4. Relier FR → US

Sur la **VM France**, edite `/etc/systemd/system/aces-runner.service` :

```ini
Environment=US_RUNNER_URL=https://URL_TUNNEL_US.trycloudflare.com
Environment=US_RUNNER_SECRET=TON_PIN
```

Puis :

```bash
sudo systemctl daemon-reload
sudo systemctl restart aces-runner
```

Le compare EU merge Bet365 US via `us_runner_client.py` (soft-fail si US down).

---

## 5. Variables **Vercel**

| Variable | Valeur |
|----------|--------|
| `RUNNER_URL` | Tunnel **France** |
| `RUNNER_SECRET` | Meme PIN que sur les 2 VPS |
| `RUNNER_US_URL` | Tunnel **US** (optionnel mais recommande pour le bandeau « Runners cloud ») |
| `TRIGGER_SECRET` | PIN affiche sur le site |

Redeploie le site après changement.

---

## 6. Verifier depuis le site

1. Onglet principal → bloc **Runners cloud** : FR et US en vert « Pret »
2. Page **/runnerlink** : health detaille du runner FR + bouton mise a jour
3. Lance une comparaison tennis → logs FR ; Bet365 passe par le runner US si configure

---

## 7. Migrer depuis l’ancien disque Oracle

Si tu as **termine** l’instance Oracle sans supprimer le boot volume :

1. Attache le volume ou monte-le depuis une VM temporaire
2. Copie `/opt/testacevalue`, `.env`, configs cloudflared
3. Ou `git clone` + recopie `.env` / secrets a la main

---

## Piwi247 / autres sites US

Branche les scrapers sur la **VM US** (meme repo Python). Le site Vercel pourra les exposer plus tard via de nouvelles routes ; pour l’instant le runner US expose deja `POST /api/us/bet365`.

Voir aussi : `runner/ORACLE_US_SETUP.md` (meme logique, autre hebergeur).
