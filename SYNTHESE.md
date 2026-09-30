# Race Strategist Agent — synthèse technique

Document de reprise : ce qui existe, comment les pièces s'emboîtent, pourquoi les choix ont
été faits, et ce qui reste à construire. Pour le cadrage fonctionnel complet, voir
`cahier-des-charges-race-strategist-agent-v1.1.md` ; pour les idées écartées, `BACKLOG.md`.

---

## 1. En une phrase

Un agent LLM qui transforme la trace GPX d'un trail, un profil d'athlète déclaré et la météo
attendue en un **plan de course chiffré** : allure cible et temps de passage par segment, plus
un plan nutrition/hydratation — le tout produit par des outils déterministes testés, le LLM ne
servant qu'à orchestrer et rédiger.

**Principe directeur, valable partout dans le code : le LLM ne calcule rien.** Tous les nombres
du rapport final proviennent de fonctions Python testées unitairement. C'est l'argument
anti-hallucination du projet, et il est vérifiable : couper l'accès au LLM produit toujours un
rapport complet avec les vrais chiffres, seulement privé de sa mise en forme rédigée.

---

## 2. État d'avancement

| Jalon | Contenu | Statut |
|---|---|---|
| J1 | Socle FastAPI + Docker Compose + Postgres, healthcheck | ✅ |
| J2 | Parsing GPX, lissage, segmentation, modèle GAP théorique | ✅ |
| J3 | Profil athlète, météo, ingestion d'activités, calibrage GAP | ✅ |
| J4 | Agent LangGraph 4 nœuds, 7 outils branchés | ✅ |
| F5/F6 | Plan d'allure et plan nutrition | ✅ |
| J5 | API `/plan`, UI Streamlit, export PDF, graphique | ⚠️ partiel |
| J6 | Dockerfile multi-stage, CI, README, démo | ❌ |
| Bonus | Kubernetes (kind) | ❌ |

**Chiffres :** 24 modules Python dans `app/`, 19 fichiers de tests, ~3 060 lignes,
**79 tests au vert**, 0 appel réseau dans la suite de tests.

---

## 3. Architecture

```
  UI Streamlit (:8501)
        │ HTTP multipart (GPX + date + objectif)
        ▼
  API FastAPI (:8000)  ──  POST /plan
        │
        ▼
  Graphe LangGraph
        planner ──────► tool_executor ──────► critic ──────► writer
           ▲                  │                  │              │
           └──────────────────┘                  └──── boucle ──┘
                                                  (si données manquantes)
        │
        ▼ 7 outils déterministes
  gpx · segmentation · athlete · gap_calibration · weather · pacing · fueling
        │
        ├──► config/athlete.json   (volume, jamais commité)
        ├──► data/activities/*.gpx (volume, jamais commité)
        └──► Open-Meteo API        (libre d'usage)
```

Aucune flèche sortante vers une API soumise à restriction d'usage IA — voir §6.

### Les quatre nœuds

| Nœud | Rôle | Appelle le LLM ? |
|---|---|---|
| `planner` | Décide quels outils appeler ensuite | Oui |
| `tool_executor` | Exécute les outils, journalise, range les résultats | Non — 100 % déterministe |
| `critic` | Vérifie la cohérence du plan | Seulement si les contrôles Python passent |
| `writer` | Rédige le rapport Markdown | Oui |

Le routage entre nœuds est **déterministe** (`graph.py`) : on ne paie jamais un appel LLM pour
trancher une question que Python peut trancher, comme « reste-t-il des données à collecter ? ».

---

## 4. Les modules

### `app/core/` — le calcul, sans aucune dépendance au LLM

| Module | Rôle |
|---|---|
| `models.py` | `TrackPoint`, `RouteProfile`, `Segment` (Pydantic) |
| `gpx.py` | Parsing GPX, distance haversine, lissage Savitzky-Golay, D+/D− avec seuil |
| `segmentation.py` | Découpe en segments homogènes, classés montée/descente/plat |
| `gap.py` | Coût énergétique de la pente (Minetti 2002), facteur GAP théorique |
| `activity.py` | Lecture d'un `.gpx` d'activité **horodaté**, extraction des couples (pente, vitesse) |
| `gap_calibration.py` | Agrégation par classes de pente, courbe GAP empirique, RMSE vs Minetti, ingestion du dossier avec déduplication par hash |
| `athlete.py` | `AthleteInput` (déclaré) → `AthleteProfile` (déduit) : régression de Riegel, avertissements |
| `weather.py` | Open-Meteo : prévision si < 14 j, sinon climatologie sur 5 ans |
| `pacing.py` | **F5** — allure, vitesse ascensionnelle, temps et cumul par segment |
| `fueling.py` | **F6** — glucides, liquide, sodium par heure |
| `chart.py` | Profil altimétrique annoté (matplotlib, backend `Agg`) |
| `export.py` | Markdown → HTML → PDF (`markdown` + `xhtml2pdf`) |

### `app/agent/` — l'orchestration

| Module | Rôle |
|---|---|
| `state.py` | `AgentState` (TypedDict), `ToolCall`, `TOOL_OUTPUT_FIELD`, `MAX_ITERATIONS` |
| `tools.py` | Registre des 7 outils : nom, fonction, description exploitée par le function calling |
| `executor.py` | Résolution des arguments depuis l'état, exécution, journalisation, isolation des échecs |
| `planner.py` | Décision LLM en sortie structurée + plan de secours déterministe |
| `critic.py` | Contrôles arithmétiques puis jugement qualitatif LLM |
| `writer.py` | Prompt de rédaction + rapport de secours sans LLM |
| `graph.py` | Assemblage LangGraph, routage conditionnel, garde `MAX_ITERATIONS` |

### Le reste

- `app/main.py` — `GET /health`, `POST /plan` (upload GPX → graphe → rapport + journal d'outils)
- `app/ui/streamlit_app.py` — formulaire, rapport, journal des appels d'outils (✅/❌)
- `app/api/` — paquet vide, jamais utilisé (l'API tient dans `main.py`)

---

## 5. Le contrat d'outils

```python
load_route(source, smooth_window=5, threshold_m=0.5)        -> RouteProfile
segment_route(route, target_segments=15)                    -> list[Segment]
load_athlete_profile(reference_distance_m, path)            -> AthleteProfile
calibrate_gap_curve(activities_dir="data/activities")       -> GapModel
get_weather_forecast(lat, lon, race_date)                   -> WeatherForecast
compute_pacing_plan(segments, athlete, gap_model, weather, target_time_s) -> PacingPlan
compute_fueling_plan(duration_h, temp_c, intensity)         -> FuelingPlan
```

Chaque outil a des entrées/sorties Pydantic, une docstring servant de description au LLM, et
des tests unitaires. L'`executor` connaît les dépendances entre eux (`load_route` doit précéder
ceux qui consomment son résultat) et résout les arguments contre `{**state, **updates}` — ce qui
permet d'exécuter **les 7 outils en une seule vague**, un outil voyant les résultats des
précédents.

---

## 6. Les décisions de conception qui se défendent en entretien

### Conformité : le connecteur Strava retiré

La politique d'API Strava de juin 2026 interdit l'usage de ses données dans l'opération d'une
application d'IA. Le connecteur a été **retiré du périmètre avant d'être codé**. Le profil
athlète est désormais saisi, et le calibrage s'appuie sur des fichiers d'activité exportés
localement, hors du champ de cette politique. Les seules sources externes sont Open-Meteo
(libre) et les fichiers de l'utilisateur.

### Saisie et déduction sont deux modèles distincts

`AthleteInput` = ce que l'humain déclare. `AthleteProfile` = ce que le système en déduit.
Cette séparation permet au `critic` de comparer les deux et de détecter les objectifs
irréalistes. Mélanger les deux dans une seule classe aurait supprimé cette possibilité.

### Régression de Riegel : bornage et ré-ancrage

`T = a·D^k` est ajusté par régression linéaire **sur les logarithmes** (une loi de puissance
devient une droite). `k` est borné à `[1.00, 1.30]` ; **quand le bornage s'applique, le
coefficient `a` est recalculé pour que la courbe passe exactement par le record le plus long** —
celui qui compte pour extrapoler vers une distance supérieure. Sans ce ré-ancrage, le couple
`(a, k)` issu des moindres carrés perd sa cohérence.

### Calibrage GAP : médiane, seuil d'échantillons, centre réel

- **Médiane** et non moyenne par classe de pente : les données de terrain contiennent toujours
  des arrêts (ravitaillement, photo) que la moyenne absorbe et que la médiane ignore.
- **20 échantillons minimum par classe** : mieux vaut une classe manquante (qui retombe sur
  Minetti) qu'une statistique mensongère tirée de 3 points.
- Le centre d'une classe est la **moyenne des pentes réellement observées**, pas le milieu
  géométrique de l'intervalle — sinon des données alignées sur les bornes décalent le centre
  d'une demi-classe.

### Les replis sont des chemins de première classe, pas des gestions d'erreur

| Situation | Repli |
|---|---|
| Aucune activité locale | Courbe théorique de Minetti, mention explicite dans le rapport |
| Course à plus de 14 jours | Climatologie sur 5 ans, source tracée |
| LLM planificateur indisponible | Séquence d'outils déterministe (`DEFAULT_TOOL_ORDER`) |
| LLM rédacteur indisponible | Rapport complet en mode dégradé, avec tous les vrais chiffres |
| Un outil échoue | Journalisé en ❌, les autres continuent |

Une course préparée six mois à l'avance est le cas **normal**, pas l'exception : le repli
climatologique devait donc être aussi soigné que le chemin nominal.

### Testabilité : injecter plutôt que lire

Le LLM (`llm=None`), l'horloge (`today=None`) et l'accès réseau (`_fetch_day`) sont tous
injectables. Conséquence : **les 79 tests ne font aucun appel réseau** et sont déterministes.
C'est aussi ce qui a permis de changer de modèle Gemini en une ligne quand le quota a explosé.

### Le contrôle qualité avant le LLM

Le `critic` vérifie d'abord en pur Python ce qui est vérifiable arithmétiquement (somme des
segments = distance totale, contiguïté, présence d'avertissements de profil). Il n'appelle le
LLM que si ces contrôles passent. Un test vérifie explicitement ce court-circuit : le faux LLM
répond « ok » alors que le test attend « needs_revision ».

---

## 7. Performance : mesures réelles

Sur la trace du Chianti CUT 73 (13 196 points, 3,8 Mo) :

| Étape | Durée |
|---|---|
| Les 7 outils réunis | **1,3 s** |
| Un seul appel LLM (même trivial) | **7 à 127 s** |

La latence est **intégralement imputable au palier gratuit de l'API Gemini**, qui met les
requêtes en file d'attente. Ni le transport (gRPC et REST sont équivalents), ni la taille des
prompts, ni le code n'y changent quoi que ce soit.

**Conséquence honnête : NF2 (« plan complet en moins de 60 s ») n'est pas tenable sur le palier
gratuit.** Le calcul tient en 1,3 s ; c'est l'accès au LLM qui ne suit pas.

**Quotas Gemini, à savoir :** le palier gratuit impose une limite **par jour et par modèle**
(20 requêtes/jour sur les modèles récents), en plus d'une limite par minute. Comme le quota est
**par modèle**, changer de modèle donne un quota neuf immédiatement. Le modèle se configure via
`GEMINI_MODEL` dans `.env`, sans toucher au code.

---

## 8. Lancer le projet

```bash
cp .env.example .env            # puis renseigner GOOGLE_API_KEY
cp config/athlete.example.json config/athlete.json   # puis ajuster ses mesures
pip install -r requirements.txt

pytest -v                       # 79 tests, aucun appel réseau

uvicorn app.main:app --reload --reload-dir app   # terminal 1
streamlit run app/ui/streamlit_app.py            # terminal 2
```

`--reload-dir app` n'est pas cosmétique : sans lui, le watcher surveille aussi `.venv/` et
meurt pendant un `pip install`, après quoi le serveur continue de servir **l'ancien code** sans
rien signaler.

**Fichiers jamais commités** (`.gitignore`) : `.env`, `config/athlete.json`, `data/activities/`.

---

## 9. Ce qui reste à faire

### Câblage laissé en suspens

1. **`chart.py` et `export.py` ne sont appelés nulle part.** Les deux modules existent et sont
   testés, mais ni le rapport ni l'UI ne les utilisent. Le graphique altimétrique et l'export
   PDF exigés par F8 sont donc écrits mais inactifs.
2. **`API_URL` est codé en dur** sur `http://localhost:8000` dans l'UI. Sous `docker compose`,
   `localhost` désigne le conteneur lui-même : il faut passer par une variable d'environnement
   valant `http://api:8000`.

### PostgreSQL : présent mais inutilisé

Le conteneur tourne et son healthcheck est vert, mais **aucune table n'est créée et rien n'y
écrit**. Tout le schéma du §6.3 du cahier des charges (`athletes`, `activities`, `routes`,
`gap_models`, `plans`, `agent_runs`) reste à implémenter. C'est le manque le plus visible :
`agent_runs` est le support du message d'entretien « j'ai instrumenté mes agents » (itérations,
latence, tokens, taux d'échec). Les données existent déjà en mémoire dans `tool_call_log`, il
manque la persistance.

### J6 — industrialisation

- Dockerfile multi-stage (< 500 Mo)
- GitHub Actions : ruff + mypy + pytest + build et push vers GHCR
- README avec schéma d'architecture, commande de lancement, GIF de démo, section
  « choix techniques et limites » (y compris l'arbitrage Strava et la mesure de latence du §7)
- Un exemple de rapport généré, commité dans `examples/`

### Dette technique connue

- `requirements.txt` est encodé en UTF-16 depuis J1 — fonctionne, mais à réenregistrer en UTF-8
- Quelques imports morts (`PLANNER_MODEL` dans `critic.py`, `date` dans `test_executor.py`),
  que ruff signalera en J6
- Aucune vérification de type n'a encore été passée (mypy prévu en J6)
- La vitesse ascensionnelle est affichée sur tous les segments, y compris les descentes :
  exact mais peu actionnable (noté au `BACKLOG.md`)
