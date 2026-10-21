# Reprise Cursor — testacevalue (Values)

Document de reprise après changement de PC. Coller ce fichier (ou `@REPRISE_CURSOR.md`) dans un **nouveau chat** Cursor.

## Repo

- GitHub: [Noe-InTech/testacevalue](https://github.com/Noe-InTech/testacevalue), branche `main`
- Commits repère NBA runner :
  - `d927843` — scrape books séquentiel (PR #23)
  - `3bb88aa` — flush partiel différé + timeout runner 45 min + `scripts/profile_nba_fr_map.py`
  - `88db605` — filtre marchés Winamax props joueur (PR #24)

## Infra EU (OVH)

- VPS: `51.77.156.182`, user `ubuntu`
- SSH: `Host oracle-eu` → `IdentityFile ~/.ssh/runner_ovh` (sans passphrase pour scripts)
- Services: `aces-runner`, `cloudflared-aces`
- Secret runner: variable `RUNNER_SECRET` dans `/etc/systemd/system/aces-runner.service` (ne pas committer)
- Vercel: `RUNNER_URL` = URL trycloudflare → `cat /opt/testacevalue/runner/data/public_url.txt` sur le VPS
- Docs: `runner/OVH_SETUP.md`, `runner/OVH_DUAL_SETUP.md`

## Problème NBA

- **Cause** : run multi-matchs bloqué sur le 1er match ; Winamax ~825 marchés bruts → `build_best_fr_player_props_map` très lent
- **Correctifs sur `main`** :
  - scrape séquentiel, pas de flush UI lourd à chaque book, timeout 2700s
  - filtre marchés Winamax **props joueur** dans `winamax_basketball_client.py` (`is_basketball_player_prop_label`)
- **À faire maintenant** : déployer sur le VPS (voir ci-dessous), puis vérifier un run NBA + logs

## Debug VPS

```bash
cd /opt/testacevalue
PYTHONPATH=. .venv/bin/python scripts/profile_nba_fr_map.py
PYTHONPATH=. .venv/bin/python scripts/probe_unibet_nba_event.py wizards
tail -f runner/data/compare_nba.log
```

Attendu après filtre Winamax : log du type
`Winamax …: N marches props (filtre depuis ~825 bruts)` et `profile_nba_fr_map` rapide (ordre secondes, pas minutes).

## Déploiement

```bash
cd /opt/testacevalue && git pull origin main
sudo git config --global --add safe.directory /opt/testacevalue
sudo systemctl restart aces-runner
```

## Suite (plus tard)

- 2e VPS US : Pinnacle / Bet365 → `US_RUNNER_URL` sur le runner EU
- Si Unibet reste lent : profiler avec `scripts/profile_nba_fr_map.py` (`SLOW unibet market …`)

## Retrouver un ancien chat Cursor

1. Même **compte** Cursor sur [cursor.com/agents](https://cursor.com/agents) (agents cloud)
2. Chat **Desktop** « de projet » : surtout sur le PC où il a été créé → historique (icône horloge)
3. Ancien PC : `%USERPROFILE%\.cursor\projects\...\agent-transcripts\` (fichiers `.jsonl`, non sync auto)
