# Agent SENTRY — cœur de raisonnement

Module de l'agent IA de **Raased**, plateforme de résilience logistique pour les
corridors de fret critiques de la région MENA.
*Projet MENA IGNITE HACKATHON / GSMA Open Gateway Innovation Challenge — équipe NovaTech.*

L'agent porte le nom de code **SENTRY**. Son rôle : détecter une dégradation sur un
trajet de fret, en évaluer le risque réel, et déclencher la réponse proportionnée —
depuis la simple surveillance jusqu'à la réservation d'une tranche réseau dédiée via
les APIs CAMARA.

---

## Principe directeur : la décision n'est pas confiée au LLM

C'est le choix d'architecture central de ce module, et il conditionne tout le reste.

| | Rôle | Nature |
|---|---|---|
| **`rules.py`** | **décide** | déterministe, auditable, testable sans réseau |
| **`reasoning.py`** | **explique** | probabiliste (Gemini), remplaçable, non bloquant |

Une décision qui déclenche une action réseau facturée ne peut pas dépendre d'un modèle
probabiliste. Le LLM produit donc uniquement du **texte destiné aux humains** ; la
décision, le score et le niveau de risque viennent des règles. Un garde-fou réaligne
systématiquement toute sortie LLM divergente, et l'agent continue de fonctionner
normalement si Gemini est indisponible.

Conséquence directe : on peut répondre *« pourquoi cette décision ? »* en lisant
`rule_trace`, **sans interroger le LLM**.

---

## Contenu du dossier

| Fichier | Lignes | État | Rôle |
|---|---|---|---|
| [`state.py`](state.py) | 572 | ✅ écrit | Contrat de données partagé entre les nœuds |
| [`rules.py`](rules.py) | 1101 | ✅ écrit | Moteur de décision déterministe |
| [`reasoning.py`](reasoning.py) | 820 | ✅ écrit | Couche d'explication (Gemini) |
| [`nodes.py`](nodes.py) | — | ✅ écrit | Nœuds LangGraph : contexte PostgreSQL, appels CAMARA conditionnels, persistance et mémoire |
| [`graph.py`](graph.py) | — | ✅ écrit | Assemblage et compilation du graphe avec branches CAMARA et validation humaine |
| `__init__.py` | 0 | — | Marqueur de package |
| `.env` | — | 🔒 non versionné | `GEMINI_API_KEY` locale |

Les trois fichiers écrits n'effectuent **aucune requête SQL, aucun appel réseau,
aucun accès CAMARA**. Ils sont donc importables et testables alors que la base est
encore vide.

---

## `state.py` — le contrat de données

Définit la structure qui circule entre les nœuds du graphe LangGraph. **Zéro logique
métier.**

### La convention fondamentale

```
None  ==  « l'information n'est PAS disponible dans PostgreSQL »
None  !=  « non »
None  !=  0
None  !=  "aucun"
```

Un champ à `None` signifie *« je ne sais pas »*, jamais *« il n'y a rien »*. En
logistique, confondre « aucun incident détecté » et « je n'ai pas pu vérifier s'il y a
un incident » produit exactement le faux négatif que le projet cherche à éviter.

Pour exprimer un « non » **vérifié**, on utilise un booléen à trois états :

| Valeur | Signification |
|---|---|
| `True` | la base a été interrogée, le fait est confirmé |
| `False` | la base a été interrogée, le fait est infirmé |
| `None` | la base n'a pas pu répondre |

### Contenu

**`AgentState`** (`TypedDict, total=False`) — une quarantaine de champs regroupés en
8 sections : identification, cargaison, position/géographie, incident, réseau/sécurité,
évaluation, décision, traçabilité. **Chaque champ documente la colonne PostgreSQL dont
il provient** — aucun champ n'est inventé.

`total=False` permet à chaque nœud de ne renvoyer que les clés qu'il a réellement pu
renseigner (mise à jour partielle, comportement natif LangGraph).

**Six sous-structures** calquées sur les tables réelles :

| Structure | Table source | Point notable |
|---|---|---|
| `LocationSnapshot` | `tracker_locations` | coordonnées extraites de `ST_Y`/`ST_X`, jamais interpolées ; `age_seconds` mesure la fraîcheur |
| `CorridorSnapshot` | `corridors` | la géométrie `LINESTRING` reste en base |
| `RiskZoneSnapshot` | `risk_zones` | `contains_current_position` = résultat de `ST_Contains` ; `None` si non évaluable — on ne suppose jamais qu'un véhicule est hors zone |
| `IncidentSnapshot` | `congestion_events` | `raw_event_id` conserve la corrélation avec l'événement CAMARA |
| `NetworkCondition` | `congestion_events` + `network_actions` | `deviates_from_baseline` compare au trafic habituel ; `active_qod_status` évite de redemander un QoD déjà actif |
| `KnownContextSnapshot` | `known_context_events` | **principal réducteur de faux positifs** : une congestion expliquée par des travaux planifiés ne déclenche pas la même escalade |

**Deux réducteurs LangGraph.** Sans réducteur, deux nœuds renvoyant la même clé
provoquent un **écrasement** — inacceptable pour une liste de lacunes.

- `merge_missing` — accumule en dédoublonnant (chaque nœud découvre ses propres lacunes)
- `merge_trace` — accumule sans dédoublonner (une règle peut s'appliquer plusieurs fois ; on garde la chronologie complète pour l'audit)

Branchés via `Annotated[list[str], merge_missing]`.

**Utilitaires.**

| Fonction | Rôle |
|---|---|
| `create_initial_state()` | état de départ avec les **seuls identifiants du déclencheur** |
| `is_available()` | une liste ou un dict **vide** compte comme indisponible (résultat typique d'un `SELECT` sans ligne) |
| `record_missing()` | liste les champs absents, à renvoyer sous `missing_information` |
| `compute_remaining_time()` | `None` si l'échéance est absente — **jamais de valeur par défaut** ; garde les valeurs négatives (retard constaté) |
| `state_summary()` | vue API ne renvoyant **que les clés présentes**, pour que le front affiche fidèlement « information indisponible » |
| `utc_now_iso()` | horodatage UTC centralisé, testable |

---

## `rules.py` — le moteur de décision

**Seule autorité de décision.** Fonctions pures : même entrée ⇒ même sortie, toujours.
Aucun SQL, aucun réseau, aucun LLM.

### Vocabulaires canoniques

Le schéma PostgreSQL stocke ces valeurs en `VARCHAR` **sans contrainte `CHECK`** : il
n'existe donc pas d'énumération en base, et ce fichier en est la source de vérité
applicative.

`RiskLevel` · `Criticality` · `CongestionLevel` · `Decision` · `SecurityStatus` ·
`SecurityCheckType` · `IncidentType` · `Severity` · `TerminalCargoStatus`

**Les 7 décisions possibles :**

| Décision | Signification |
|---|---|
| `MONITOR` | surveillance passive, aucune action |
| `NOTIFY_MANAGER` | informer le responsable, sans agir sur le terrain |
| `RECOMMEND_ALTERNATIVE_ROUTE` | proposer un itinéraire de contournement |
| `REQUEST_QOD` | sécuriser temporairement le lien réseau d'un tracker |
| `REQUEST_NETWORK_SLICE` | réserver une tranche réseau dédiée (opération critique) |
| `HUMAN_APPROVAL` | ne pas trancher, remonter le cas au manager |
| `REQUEST_MORE_INFORMATION` | données insuffisantes pour conclure |

### Le score de risque et la couverture

Six facteurs pondérés :

| Facteur | Poids |
|---|---|
| congestion réseau | 0.25 |
| criticité de la cargaison | 0.25 |
| pression de l'échéance | 0.20 |
| zone à risque | 0.15 |
| sécurité (SIM swap, etc.) | 0.10 |
| risque structurel du corridor | 0.05 |

**`compute_risk_score()` renormalise sur les seuls facteurs disponibles** :

```
score = somme_pondérée(facteurs disponibles) / somme(poids de CES facteurs)
coverage = somme(poids disponibles) / somme(poids totaux)
```

C'est le garde-fou anti-invention le plus important du projet. Traiter un facteur absent
comme `0` abaisserait mécaniquement le score et **fabriquerait un faux sentiment de
sécurité**. Ici une donnée absente n'influence pas le score : elle réduit `coverage`,
information rendue explicite. Sous `MIN_RISK_DATA_COVERAGE` (0.50), l'agent **refuse de
conclure**.

Le score est dans **[0.0, 1.0] arrondi à 4 décimales**, aligné sur
`risk_assessments.risk_score` qui est un `DECIMAL(5,4)` — l'échelle n'est pas 0-100.

`CONGESTION_SCALE` traduit le niveau catégoriel CAMARA (`none|low|medium|high`) en
scalaire, pour que le seuil flottant `CONGESTION_ALERT_THRESHOLD` reste comparable à une
colonne textuelle.

### La cascade de décision

`evaluate(state)` est le point d'entrée unique. Priorité **stricte, de haut en bas** :

| Règle | Condition | Décision |
|---|---|---|
| `R-00` | cargaison livrée ou annulée | `MONITOR` |
| `R-01` | identifiant bloquant absent | `REQUEST_MORE_INFORMATION` |
| `R-02` | contrôle de sécurité en échec | `HUMAN_APPROVAL` |
| `R-03` | couverture < 0.50 | `REQUEST_MORE_INFORMATION` |
| `R-03b` | idem **et** cargaison HIGH/CRITICAL | `HUMAN_APPROVAL` |
| `R-04` | score non calculable | `REQUEST_MORE_INFORMATION` |
| `R-05` | tranche réseau justifiée | `REQUEST_NETWORK_SLICE` |
| `R-06` | QoD justifié | `REQUEST_QOD` |
| `R-07` | reroutage pertinent | `RECOMMEND_ALTERNATIVE_ROUTE` |
| `R-08` | notification justifiée | `NOTIFY_MANAGER` |
| `R-09` | nominal | `MONITOR` |

Chaque règle appliquée est journalisée dans `rule_trace`.

### QoD ou tranche réseau — deux réponses distinctes

| | `REQUEST_QOD` | `REQUEST_NETWORK_SLICE` |
|---|---|---|
| Nature | ponctuel, réversible | structurel, durable |
| Portée | un tracker | une opération entière |
| Coût | faible | élevé |
| Déclencheur | le **lien** est dégradé : congestion ≥ seuil avec confiance suffisante, ou signal perdu | cargaison HIGH/CRITICAL **et** risque CRITICAL |
| Validation humaine | selon le contexte | **toujours** |

Les deux ne sont jamais demandés ensemble : une tranche réseau couvre déjà le besoin QoD.

### Validation humaine (Human-in-the-Loop)

`requires_human_approval()` — 5 cas nommés :

| Cas | Condition |
|---|---|
| `H1` | action coûteuse sur cargaison HIGH/CRITICAL |
| `H2` | toute demande de tranche réseau |
| `H3` | risque CRITICAL + action coûteuse |
| `H4` | contrôle de sécurité en échec — ne jamais laisser l'agent agir seul sur un tracker possiblement détourné |
| `H5` | couverture de données insuffisante + action coûteuse |

`MONITOR`, `NOTIFY_MANAGER` et `REQUEST_MORE_INFORMATION` ne requièrent jamais de
validation : notifier est gratuit et sans effet de bord.

### Sortie

`RuleEvaluation` (dataclass) expose `as_state_update()`, qui retourne un dictionnaire
dont les clés sont exactement des champs d'`AgentState`.

---

## `reasoning.py` — la couche d'explication

Appelle **Gemini**, mais **ne décide rien**. Reçoit la décision déjà prise et produit
uniquement du texte destiné aux humains.

### Ce que le LLM produit

| Champ | Destination |
|---|---|
| `reasoning` | analyse contextuelle, 3-6 phrases — audit, dashboard admin |
| `justification` | 1-3 phrases → `agent_decisions.reasoning_summary`, `alerts.message` |
| `missing_information` | lacunes éventuellement oubliées par les règles |
| `requires_human_approval` | **escalade uniquement** (voir garde-fou) |

Rédaction en **français** : ces textes sont lus par des managers et des chauffeurs
francophones dans le dashboard.

### Le prompt système

Trois sections contraignantes :

1. **Interdiction absolue d'inventer** — position, latitude/longitude, ville, criticité,
   incident, horaire, échéance, identité de chauffeur/véhicule/tracker, nom de corridor
   ou d'organisation.
2. **Autorité des règles** — la décision, le score et le niveau de risque sont *fournis*,
   doivent être reproduits à l'identique, et ne se recalculent pas.
3. **Vocabulaires fermés** — 7 décisions, 4 niveaux de risque, sortie **JSON strict**.

Le prompt utilisateur ne transmet que les champs réellement disponibles ; tous les autres
sont marqués **`NON DISPONIBLE`**, avec une section explicite *« facteurs indisponibles —
ne pas les estimer »*.

### Le garde-fou — `_enforce_rule_authority()`

Applique quatre corrections systématiques :

1. La **décision** est toujours remplacée par celle des règles ; l'écart est journalisé
   (`R-GUARD:decision_llm=…:remplacee_par=…`).
2. Le **niveau de risque** est toujours celui des règles.
3. **Asymétrie d'escalade** — le LLM peut *ajouter* une validation humaine, **jamais la
   retirer**. Il peut rendre l'agent plus prudent, jamais moins.
4. `missing_information` est l'**union** des lacunes des règles et de celles du LLM.

Le `risk_factors` textuel du LLM va dans `risk_factors_narrative` et **n'écrase pas** le
détail numérique pondéré produit par les règles, destiné à `risk_assessments.factors`.

### Le mode dégradé

Si Gemini est injoignable — clé absente, quota épuisé, réseau, JSON invalide —
`analyze()` **ne lève jamais d'exception**. La décision des règles est conservée, et la
justification est reconstruite depuis la seule trace des règles :

> « Les informations nécessaires ne sont pas disponibles dans la base : aucune conclusion
> ne peut être formulée. Aucun score de risque n'a pu être calculé. […] Analyse
> contextuelle non disponible. »

`llm_available` passe à `False`. **L'agent reste pleinement fonctionnel sans LLM.**

### Fournisseur

**Gemini uniquement**, via le SDK natif `google-generativeai 0.8.2`
(`langchain-google-genai` n'est pas installé — aucune dépendance ajoutée).
Utilise `system_instruction` et le mode JSON natif
(`response_mime_type="application/json"`).

`LLMProvider` (Protocol) est conservé, mais **pas** pour brancher un autre fournisseur :
il permet d'injecter un double en test, sans clé API ni réseau.

### Points d'entrée

| Fonction | Usage |
|---|---|
| `analyze(state, evaluation, *, provider=None)` | synchrone ; ne lève jamais |
| `aanalyze(...)` | asynchrone — le SDK Gemini est bloquant et la couche DB est `async`, donc `asyncio.to_thread` |
| `is_llm_configured()` | diagnostic booléen, **aucun appel facturé** |
| `llm_status()` | `{provider, configured, model, reason}` — **n'expose jamais la clé** |

---

## Communication entre les fichiers

```
state.py ──── AgentState ────► rules.py ──── RuleEvaluation ────► reasoning.py
   ▲                                                                    │
   └──────── as_state_update() ◄───── ReasoningResult ◄─────────────────┘
```

Le couplage est **unidirectionnel** : `state.py` n'importe ni `rules` ni `reasoning`.
Les deux autres produisent des dataclasses exposant `as_state_update()`, dont les clés
sont exactement des champs d'`AgentState`.

L'ordre est **imposé par les signatures** : `analyze()` exige un `RuleEvaluation` en
paramètre. Le raisonnement vient donc toujours après les règles — impossible de se
tromper.

Un nœud LangGraph tient en trois lignes :

```python
async def reasoning_node(state: AgentState) -> dict:
    evaluation = rules.evaluate(state)                       # décision déterministe
    result = await reasoning.aanalyze(state, evaluation)     # explication
    return {**evaluation.as_state_update(), **result.as_state_update()}
```

---

## Injection des données PostgreSQL

À la charge du futur nœud d'enrichissement dans `nodes.py`. Les trois fichiers écrits
sont déjà alignés sur les colonnes réelles :

| Champ `AgentState` | Origine |
|---|---|
| `cargo_*`, `criticality`, `origin`, `destination`, `deadline` | `cargos` |
| `trip_id` | `cargo_trackers.id` |
| `current_location` | `tracker_locations` — `ST_Y`/`ST_X`, `ORDER BY timestamp DESC LIMIT 1` |
| `corridor` | `corridors` |
| `risk_zone.contains_current_position` | `ST_Contains(risk_zones.geometry, point)` |
| `incident`, `network_condition` | `congestion_events` |
| `network_condition.baseline_level` | `corridor_congestion_baselines` (jointure heure/jour) |
| `known_context.is_active_now` | `known_context_events` (`starts_at <= now <= ends_at`) |
| `security_checks` | `security_checks`, agrégé par `aggregate_security_status()` |
| `remaining_time_hours` | dérivé par `compute_remaining_time()` |

**Deux règles impératives pour ce nœud :**

1. `scalar_one_or_none()`, **jamais** `scalar_one()`.
2. Sur un `None`, ajouter une entrée dans `missing_information` — **jamais** une valeur
   de repli.

La session est asynchrone (`AsyncSessionLocal`), d'où `aanalyze()`.

---

## Branchement CAMARA (à venir)

**Aucun appel CAMARA n'est effectué aujourd'hui** — `app/camara/` est vide et n'est pas
importé.

Les règles positionnent deux drapeaux **indépendamment** de la décision
(`qod_required`, `network_slice_required`) : l'agent peut décider
`RECOMMEND_ALTERNATIVE_ROUTE` tout en signalant qu'un QoD serait utile. Un futur nœud
d'exécution les lira :

```python
if state["requires_human_approval"] and state.get("human_approved") is not True:
    return {}                                    # rien ne partira sans feu vert
if state.get("network_slice_required"):
    await app.camara.slicing.request(...)
elif state.get("qod_required"):
    await app.camara.qod.request(...)
```

Chaque appel s'écrira dans `network_actions` (`action_type`, `status`, `request_id`,
`response`) — la table existe déjà.

---

## Branchement du dashboard manager

Le modèle repose sur **deux colonnes distinctes** de `agent_decisions` :

| Cas | `decision` | `requires_human_approval` | Sens |
|---|---|---|---|
| L'agent ne tranche pas | `HUMAN_APPROVAL` | `True` | « arbitrez, je n'ai pas les éléments » |
| L'agent sait quoi faire mais l'action coûte | `REQUEST_NETWORK_SLICE` | `True` | « feu vert ? » |
| Action sans effet de bord | `NOTIFY_MANAGER` | `False` | exécution directe |

`human_approved` porte le troisième état : `None` = **en attente**. Le nœud d'exécution
ne fait rien tant que `requires_human_approval=True` et `human_approved is None`.

Côté web, un endpoint `POST /api/v1/agent/decisions/{id}/approve` protégé par
`Depends(require_role("MANAGER"))` remplira `approved_by` / `approved_at`, puis relancera
le graphe avec `human_approved=True`.

**Ce que chaque acteur voit :**

| Acteur | Champs exposés |
|---|---|
| `ADMIN` | tout, y compris `reasoning`, `rule_trace`, `llm_status()` |
| `MANAGER` | `justification`, `risk_factors`, `risk_level`, `rule_trace`, file d'approbation |
| `DRIVER` | `justification`, `incident_severity` |

Le manager voit **pourquoi** sans dépendre du LLM : `rule_trace` et `risk_factors`
suffisent.

---

## Configuration

Une seule clé est nécessaire : **`GEMINI_API_KEY`**. Elle n'apparaît jamais dans le code
et n'est jamais journalisée.

Résolution à l'exécution, dans cet ordre :

1. `Settings.GEMINI_API_KEY` ← `backend/.env`
2. `os.environ`
3. `app/agent/.env` ← chargé à l'import par `load_dotenv(..., override=False)`

Le troisième niveau existe parce que `Settings` lit `env_file=".env"` **relativement au
répertoire courant** : une clé placée dans `app/agent/.env` serait autrement ignorée.

Variables reconnues :

| Variable | Défaut | Effet |
|---|---|---|
| `GEMINI_API_KEY` | — | absente ⇒ mode dégradé, pas de crash |
| `LLM_MODEL` | `gemini-1.5-pro` | `gemini-1.5-flash` est plus rapide et moins coûteux |
| `LLM_TEMPERATURE` | `0.2` | basse volontairement : deux analyses du même incident doivent se ressembler |
| `CONGESTION_ALERT_THRESHOLD` | `0.7` | lu depuis `app/core/config.py` |
| `CONGESTION_CONFIDENCE_MIN` | `0.6` | idem |

`LLM_PROVIDER` est **ignoré** pour le choix du fournisseur : Gemini est le seul moteur
supporté. Si la variable désigne autre chose, un avertissement est journalisé une fois —
aucun basculement silencieux.

> ⚠️ Les fichiers `.env` sont ignorés par git (`backend/.gitignore`). Ne jamais versionner
> une clé.

---

## Comportement actuel — base vide

La base PostgreSQL existe mais **ne contient encore aucune donnée métier**. Aucune donnée
simulée n'a été créée : ce n'est pas un manque, c'est une contrainte de conception.

Comportement réellement observé :

```
create_initial_state()            → tracker_id=None, cargo_id=None
  ↓  nœud d'enrichissement : 0 ligne
  ↓  rules.evaluate()
     rule_trace   = ['R-01:informations_bloquantes_absentes:2']
     decision     = REQUEST_MORE_INFORMATION
     risk_score   = None          ← pas 0.0
     risk_level   = None          ← pas "LOW"
     coverage     = 0.0
     missing      = cargo_id, tracker_id, criticality, current_location,
                    corridor, network_condition, deadline, security_check_status
  ↓  reasoning.analyze()
     justification factuelle, aucun fait de terrain affirmé
```

Aucune position, criticité, localisation ni incident n'est inventé. Le jour où les tables
sont peuplées, le même flux traverse `R-SCORE` → `R-05…R-09` et produit une décision
réelle — **sans qu'une ligne de ces trois fichiers ne change**.

---

## Contraintes de conception respectées

- ❌ aucune donnée simulée, fictive ou générée
- ❌ aucun appel CAMARA (`app/camara/` vide, non importé)
- ❌ aucun usage de ChromaDB
- ❌ aucune clé API dans le code
- ✅ absence de donnée traitée explicitement, jamais convertie en valeur arbitraire
- ✅ `nodes.py` et `graph.py` laissés intacts

---

## Reste à faire

1. **Appliquer les migrations** — depuis `backend/` : `alembic upgrade head`.
   Sans cela, `\dt` ne montre que `spatial_ref_sys`.
2. **Écrire `nodes.py`** — nœud d'enrichissement PostgreSQL, nœud de raisonnement, nœud
   de persistance (`risk_assessments`, `agent_decisions`, `alerts`).
3. **Écrire `graph.py`** — `StateGraph(AgentState)`, arêtes, `compile()`.
4. **Exposer les endpoints** dans `app/api/v1/agent.py` (le router existe, sans route).
5. **Brancher CAMARA** dans `app/camara/` une fois les identifiants sandbox disponibles.

### Lacune de schéma connue — affectation d'un chauffeur

Aucune colonne du schéma actuel ne relie un utilisateur `DRIVER` à un cargo ou à un
tracker. `AgentState` ne contient donc pas de `driver_id` : cette information ne sera
ajoutée qu'avec une clé étrangère (`cargos.driver_id`) ou une table d'affectation. L'acteur
« chauffeur » existe dans le produit, mais sa relation avec un transport n'est pas encore
représentée en base.

---

## Environnement vérifié

| Paquet | Version |
|---|---|
| langgraph | 0.2.38 |
| langchain-core | 0.3.9 |
| google-generativeai | 0.8.2 |
| sqlalchemy | 2.0.52 |
| fastapi | 0.115.0 |
| geoalchemy2 | 0.15.2 |
| alembic | 1.13.3 |
| python-dotenv | 1.0.1 |

Interpréteur : `backend/.venv/Scripts/python.exe`.

Compatibilité LangGraph confirmée : `StateGraph(AgentState).compile().invoke()` fonctionne,
et les deux réducteurs accumulent correctement entre nœuds successifs.
