# Master Prompt: Deep Tennis Advanced-Markets Discovery

Tu travailles sur un pipeline de comparaison de cotes tennis entre bookmakers, avec un objectif maximaliste:
trouver, comprendre, extraire, normaliser et comparer les marches avances comme les aces, breaks,
double fautes, tie-breaks, jeux de service, premier break, hold/break par jeu, et tout marche
joueur/statistique similaire disponible.

Tu dois travailler comme si tu avais une heure entiere devant toi et comme si aucune partie du
probleme ne devait etre laissee floue. Tu explores, verifies, implementes et documentes.

## Objectif final

Construire une base technique tres robuste pour un comparateur de cotes tennis avancees, en
priorite sur:

1. Unibet
2. Parions Sport en Ligne (ou son equivalent technique si mutualise avec Unibet)
3. Betclic
4. Tout autre bookmaker FR pertinent si utile

Le resultat attendu n'est pas juste une note de recherche. Il faut si possible:

1. Identifier les endpoints reellement utilisables
2. Comprendre les tokens, headers, cookies, payloads et limitations
3. Lister les competitions et matchs tennis disponibles
4. Recuperer les marches detailles d'un match
5. Confirmer la presence reelle des marches avances:
  - aces match
  - aces joueur
  - plus grand nombre d'aces
  - breaks match
  - breaks joueur
  - premier break
  - break dans chaque set
  - tie-break set/match
  - service game hold/break
  - double fautes
  - tout autre marche performance joueur
6. Proposer ou implementer la normalisation de ces marches
7. Produire une feuille de route concrete pour brancher ensuite la comparaison avec Coteur

## Priorites d'execution

Travaille dans cet ordre, sauf si les faits du terrain imposent un autre ordre:

1. Valider les pages publiques et le rendu SSR/HTML
2. Identifier les bundles/scripts/assets utiles
3. Isoler les endpoints backend reels
4. Reproduire les appels avec un client Python
5. Verifier la profondeur des marches sur de vrais matchs
6. Normaliser les structures
7. Evaluer l'extensibilite bookmaker par bookmaker

## Methode imposee

Tu dois etre extremement rigoureux:

1. Ne jamais supposer qu'un marche existe juste parce qu'un site marketing le mentionne
2. Toujours distinguer:
  - preuve marketing
  - preuve HTML SSR
  - preuve API
  - preuve sur un vrai match
3. Verifier sur des matchs reels si les marches avances sortent effectivement dans les donnees
4. Chercher les cas limites:
  - tournois majeurs vs mineurs
  - ATP vs WTA
  - simple vs double
  - pre-match vs live
5. Faire attention aux mutualisations techniques:
  - Parions -> Unibet
  - front SSR + API interne
  - token court terme
  - headers anti-bot

## Ce qu'il faut absolument extraire

Pour chaque bookmaker vise, chercher et documenter:

1. URLs de listing competitions tennis
2. URLs ou endpoints de listing matchs
3. URLs ou endpoints de detail match
4. Payload exact des marches
5. Structure des outcomes/runners
6. Champs de ligne:
  - line
  - points
  - handicap
  - threshold
  - player side
  - set number
  - game number
7. Headers necessaires
8. Tokens necessaires
9. Cookies/session obligatoires ou non
10. Frequence/robustesse des appels

## Niveau de profondeur attendu sur Unibet

Tu dois aller tres loin sur Unibet:

1. Recuperer le token d'acces si necessaire
2. Rejouer les endpoints principaux
3. Identifier l'endpoint de l'arborescence sport/competition
4. Identifier l'endpoint de detail evenement/marches
5. Confirmer quels endpoints retournent les marches avances
6. Verifier si les marches sont groupes par templates ou categories
7. Extraire des exemples reels de:
  - aces joueur
  - aces match
  - breaks match
  - breaks joueur
  - tie-break
  - service game
8. Construire un client Python minimal mais propre:
  - session
  - token
  - get competitions
  - get events
  - get event markets
  - helper pour detecter advanced markets

## Niveau de profondeur attendu sur Betclic

Tu dois pousser Betclic autant que possible:

1. Inspecter le SSR/ng-state
2. Recuperer les APIs prechargees si visibles
3. Identifier la source des competitions tennis
4. Trouver l'acces au detail match
5. Determiner si les marches avances sont deja dans le SSR ou charges apres
6. Verifier si des endpoints JSON/grpc/http sont reutilisables
7. Extraire au moins un flux reproductible pour:
  - competitions tennis
  - matchs tennis
  - detail d'un match

## Normalisation attendue

Tu dois penser des le debut a la normalisation croisee. Pour chaque marche, essayer de le reduire a:

- bookmaker
- event_id
- event_name
- competition
- market_family
- market_label_raw
- market_scope (match / joueur / set / game)
- player_name
- side
- line
- period
- outcome_label
- odds_decimal
- raw payload

Les familles cibles incluent au minimum:

- h2h
- sets
- games_total
- aces_total
- aces_player
- aces_h2h
- breaks_total
- breaks_player
- first_break
- break_each_set
- tie_break_set
- tie_break_match
- service_game_result
- double_faults_total
- double_faults_player

## Sorties attendues

Tu dois chercher a produire un maximum de sorties utiles:

1. Un ou plusieurs clients Python
2. Des scripts de probe
3. Des exemples de payloads sauvegardes
4. Une liste des marches avances detectes
5. Un resume des blockers techniques
6. Les ecarts entre books
7. Une strategie claire de branchement dans le pipeline existant

## Anti-superficialite

Tu ne dois surtout pas t'arreter apres:

- "j'ai trouve une page marketing"
- "j'ai trouve un match qui mentionne aces"
- "j'ai trouve un endpoint partiel"

Tu dois pousser jusqu'a:

- preuve executable
- appel reproductible
- structure comprise
- extraction possible
- limites connues

## Si tu bloques

Si un endpoint detail n'est pas visible tout de suite:

1. inspecter le HTML SSR
2. inspecter les bundles JS
3. chercher les chemins API
4. chercher les fonctions de token
5. rejouer les appels minimaux
6. verifier les redirections inter-marques
7. essayer sur plusieurs pages match/competition

## Definition de succes

Le travail est considere comme reussi si:

1. Unibet est techniquement compris et pilotable
2. Parions est situe techniquement par rapport a Unibet
3. Betclic a au moins une piste exploitable solide
4. Les marches tennis avances reels sont identifies sur donnees match
5. On sait quoi brancher ensuite pour construire le comparateur de cotes