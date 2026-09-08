# Raased — Base de données (v3 — avec inscription manager + vérification email)

> Mise à jour intégrant le nouveau flux d'auto-inscription des managers
> (formulaire Company → Manager → Verification → Documents).
> Changements marqués 🆕 (nouvelle table) ou ✏️ (colonnes modifiées/ajoutées).

---

## 1. `organizations` ✏️

**Rôle :** représente une entreprise cliente de Raased. Étendue pour stocker toutes les informations collectées à l'étape "Company" du formulaire d'inscription, et pour suivre le statut d'approbation de la demande (une inscription libre doit être validée avant d'être active).

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| `id` | UUID | PK | Identifiant unique de l'organisation |
| `name` | VARCHAR(150) | NOT NULL | Nom de l'entreprise |
| `legal_id` | VARCHAR(50) | NOT NULL | Identifiant légal (ICE / RC) |
| `country` | VARCHAR(100) | NOT NULL | Pays |
| `city` | VARCHAR(100) | NOT NULL | Ville |
| `phone` | VARCHAR(30) | NOT NULL | Téléphone de l'entreprise |
| `address` | TEXT | NOT NULL | Adresse complète |
| `website` | VARCHAR(255) | NULL | Site web (optionnel) |
| `email` | VARCHAR(255) | NOT NULL | Email de contact de l'entreprise |
| `status` | VARCHAR(20) | NOT NULL, DEFAULT 'PENDING' | 🆕 Statut de la demande : PENDING, APPROVED, REJECTED |
| `reviewed_by` | UUID | FK → users.id, NULL | 🆕 Admin ayant traité la demande |
| `reviewed_at` | TIMESTAMP | NULL | 🆕 Date de traitement de la demande |
| `rejection_reason` | TEXT | NULL | 🆕 Motif en cas de rejet |
| `created_at` | TIMESTAMP | NOT NULL | Date de création |
| `updated_at` | TIMESTAMP | NOT NULL | Dernière modification |

---

## 2. `users` ✏️

**Rôle :** les personnes qui utilisent la plateforme (admin, manager, chauffeur). Étendue pour stocker les champs collectés à l'étape "Manager" du formulaire, et pour suivre la vérification de l'email.

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| `id` | UUID | PK | Identifiant utilisateur |
| `organization_id` | UUID | FK → organizations.id | Entreprise de l'utilisateur |
| `first_name` | VARCHAR(100) | NOT NULL | Prénom |
| `last_name` | VARCHAR(100) | NOT NULL | Nom |
| `job_title` | VARCHAR(100) | NULL | Fonction (PDG, Directeur...) |
| `phone` | VARCHAR(30) | NULL | Téléphone professionnel |
| `email` | VARCHAR(255) | UNIQUE, NOT NULL | Email |
| `password` | TEXT | NULL | ✏️ Nullable — un driver invité n'a pas encore défini de mot de passe |
| `role` | VARCHAR(30) | NOT NULL | ADMIN, MANAGER ou DRIVER |
| `email_verified` | BOOLEAN | DEFAULT FALSE | Email vérifié (managers) |
| `email_verified_at` | TIMESTAMP | NULL | Date de vérification |
| `account_status` | VARCHAR(20) | NOT NULL, DEFAULT 'ACTIVE' | 🆕 INVITED, ACTIVE, DISABLED |
| `is_active` | BOOLEAN | DEFAULT TRUE | Compte actif ou désactivé |
| `created_at` | TIMESTAMP | NOT NULL | Date de création |
| `updated_at` | TIMESTAMP | NOT NULL | Dernière modification |

---
## X. `account_invitations` — 🆕

**Pourquoi :** quand un manager crée un compte driver, celui-ci ne doit pas connaître son mot de passe — cette table gère le lien d'invitation sécurisé (à usage unique) que le driver reçoit par email pour définir lui-même son mot de passe.

**Rôle :** stocke chaque token d'invitation envoyé, sa date d'expiration, et s'il a déjà été utilisé.

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| `id` | UUID | PK | Identifiant de l'invitation |
| `user_id` | UUID | FK → users.id | Driver invité |
| `token` | VARCHAR(255) | UNIQUE, NOT NULL | Token sécurisé inclus dans le lien email |
| `expires_at` | TIMESTAMP | NOT NULL | Date limite de validité du lien |
| `used_at` | TIMESTAMP | NULL | Date d'utilisation (NULL = pas encore utilisé) |
| `created_at` | TIMESTAMP | NOT NULL | Date de création de l'invitation |
---

## 3. `email_verification_codes` — 🆕 

**Pourquoi :** l'étape "Verification" du formulaire envoie un code à 6 chiffres par email, avec possibilité de le renvoyer. Une table séparée (plutôt que des colonnes sur `users`) permet de gérer proprement l'expiration, l'historique des tentatives, et le renvoi de code sans écraser l'ancien.

**Rôle :** stocke chaque code envoyé à un utilisateur, sa date d'expiration, et s'il a été utilisé.

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| `id` | UUID | PK | Identifiant du code |
| `user_id` | UUID | FK → users.id | Utilisateur concerné |
| `code` | VARCHAR(10) | NOT NULL | Code à 6 chiffres envoyé par email |
| `expires_at` | TIMESTAMP | NOT NULL | Date limite de validité du code |
| `verified_at` | TIMESTAMP | NULL | Date d'utilisation réussie (NULL = pas encore vérifié) |
| `attempts` | INT | NOT NULL, DEFAULT 0 | Nombre de tentatives de saisie incorrectes |
| `created_at` | TIMESTAMP | NOT NULL | Date d'envoi du code |

---

## 4. `organization_documents` — 🆕 

**Pourquoi :** l'étape "Documents" du formulaire permet d'uploader (en option) un certificat d'entreprise et une pièce d'identité du responsable, utilisés uniquement pour la vérification manuelle de la demande d'inscription.

**Rôle :** stocke les fichiers liés à une demande d'organisation.

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| `id` | UUID | PK | Identifiant du document |
| `organization_id` | UUID | FK → organizations.id | Organisation concernée |
| `document_type` | VARCHAR(50) | NOT NULL | COMPANY_CERTIFICATE ou RESPONSIBLE_ID |
| `file_url` | TEXT | NOT NULL | Emplacement du fichier stocké |
| `uploaded_at` | TIMESTAMP | NOT NULL | Date d'upload |

---

## 5. `cargos`

**Rôle :** une cargaison (marchandise) en cours de transport, avec son niveau de priorité/criticité.

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| `id` | UUID | PK | Identifiant cargo |
| `organization_id` | UUID | FK → organizations.id | Entreprise propriétaire |
| `reference` | VARCHAR(100) | UNIQUE | Référence métier (ex: CARGO-2026-001) |
| `type` | VARCHAR(50) | NOT NULL | Type de marchandise (ex: PHARMACEUTICAL) |
| `criticality` | VARCHAR(20) | NOT NULL | LOW, MEDIUM, HIGH, CRITICAL |
| `status` | VARCHAR(30) | NOT NULL | Statut de transport (ex: IN_TRANSIT) |
| `origin` | VARCHAR(150) | NOT NULL | Ville/point de départ |
| `destination` | VARCHAR(150) | NOT NULL | Ville/point d'arrivée |
| `deadline` | TIMESTAMP | NULL | Date limite de livraison |
| `created_at` | TIMESTAMP | NOT NULL | Date de création |
| `updated_at` | TIMESTAMP | NOT NULL | Dernière modification |

---

## 6. `trackers`

**Rôle :** le dispositif physique (ligne mobile) attaché à une cargaison pour la suivre.

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| `id` | UUID | PK | Identifiant interne |
| `organization_id` | UUID | FK → organizations.id | Entreprise propriétaire du dispositif |
| `device_id` | VARCHAR(100) | UNIQUE | Identifiant du boîtier physique |
| `msisdn` | VARCHAR(30) | NULL | Numéro mobile (SIM) associé |
| `status` | VARCHAR(30) | NOT NULL | ACTIVE, INACTIVE, MAINTENANCE... |
| `last_seen_at` | TIMESTAMP | NULL | Dernière activité connue |
| `created_at` | TIMESTAMP | NOT NULL | Date de création |
| `updated_at` | TIMESTAMP | NOT NULL | Dernière modification |

---

## 7. `cargo_trackers`

**Pourquoi :** un tracker (objet physique) est réutilisé sur plusieurs livraisons dans le temps. Sans cette table, on perd la trace de "quel tracker suivait quelle cargaison, à quel moment" — information essentielle en cas d'audit après un incident.

**Rôle :** carnet qui note "ce tracker a été mis sur cette cargaison à telle date, puis retiré à telle autre date".

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| `id` | UUID | PK | Identifiant de l'association |
| `cargo_id` | UUID | FK → cargos.id | Cargaison suivie |
| `tracker_id` | UUID | FK → trackers.id | Tracker utilisé |
| `assigned_at` | TIMESTAMP | NOT NULL | Date de mise en service sur cette cargaison |
| `unassigned_at` | TIMESTAMP | NULL | Date de retrait (NULL si toujours actif) |

---

## 8. `corridors`

**Rôle :** un itinéraire logistique surveillé (une route/autoroute entre deux villes), représenté comme une ligne sur la carte.

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| `id` | UUID | PK | Identifiant du corridor |
| `name` | VARCHAR(150) | NOT NULL | Nom du corridor |
| `origin` | VARCHAR(150) | NOT NULL | Point de départ |
| `destination` | VARCHAR(150) | NOT NULL | Point d'arrivée |
| `geometry` | GEOGRAPHY(LINESTRING, 4326) | NOT NULL | Tracé géographique (ligne reliant les points du trajet) |
| `risk_level` | VARCHAR(20) | NOT NULL | Niveau de risque de base du corridor |
| `is_active` | BOOLEAN | DEFAULT TRUE | Corridor actuellement surveillé ou non |
| `created_at` | TIMESTAMP | NOT NULL | Date de création |
| `updated_at` | TIMESTAMP | NOT NULL | Dernière modification |

---

## 9. `risk_zones`

**Rôle :** une zone géographique sensible à l'intérieur d'un corridor (frontière, port, douane, zone d'incident connu), représentée comme une surface sur la carte.

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| `id` | UUID | PK | Identifiant de la zone |
| `corridor_id` | UUID | FK → corridors.id | Corridor auquel appartient la zone |
| `name` | VARCHAR(150) | NOT NULL | Nom de la zone |
| `type` | VARCHAR(50) | NOT NULL | BORDER, PORT, CUSTOMS, INCIDENT, SECURITY... |
| `risk_level` | VARCHAR(20) | NOT NULL | Niveau de risque de la zone |
| `geometry` | GEOGRAPHY(POLYGON, 4326) | NOT NULL | Contour géographique de la zone |
| `description` | TEXT | NULL | Description libre |
| `is_active` | BOOLEAN | DEFAULT TRUE | Zone actuellement surveillée ou non |
| `created_at` | TIMESTAMP | NOT NULL | Date de création |
| `updated_at` | TIMESTAMP | NOT NULL | Dernière modification |

---

## 10. `tracker_locations`

**Rôle :** l'historique de toutes les positions successives d'un tracker (on ne l'écrase jamais, chaque nouvelle position est une nouvelle ligne).

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| `id` | BIGSERIAL | PK | Identifiant de l'enregistrement |
| `tracker_id` | UUID | FK → trackers.id | Tracker concerné |
| `location` | GEOGRAPHY(POINT, 4326) | NOT NULL | Position (un point sur la carte) |
| `accuracy` | DOUBLE PRECISION | NULL | Précision estimée de la position |
| `source` | VARCHAR(30) | NOT NULL | Origine de la donnée : GPS ou NETWORK |
| `timestamp` | TIMESTAMP | NOT NULL | Moment de cette position |

---

## 11. `corridor_congestion_baselines`

**Pourquoi :** pour savoir si une congestion est "anormale", il faut d'abord savoir ce qui est "normal" à cet endroit et ce moment-là.

**Rôle :** une mémoire du niveau de congestion habituel pour chaque corridor, selon l'heure de la journée et le jour de la semaine.

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| `id` | UUID | PK | Identifiant de la baseline |
| `corridor_id` | UUID | FK → corridors.id | Corridor concerné |
| `hour_of_day` | SMALLINT | NOT NULL | Heure de la journée (0 à 23) |
| `day_of_week` | SMALLINT | NOT NULL | Jour de la semaine (0 à 6) |
| `typical_congestion_level` | VARCHAR(30) | NOT NULL | Niveau de congestion habituel à ce créneau |
| `sample_count` | INT | NOT NULL | Nombre de mesures utilisées pour ce calcul |
| `updated_at` | TIMESTAMP | NOT NULL | Date du dernier recalcul |

---

## 12. `known_context_events`

**Pourquoi :** distinguer une vraie perturbation d'une congestion normale due à un évènement connu (match de foot, festival, travaux).

**Rôle :** un calendrier des évènements connus qui peuvent expliquer une hausse de congestion sans qu'il s'agisse d'un incident.

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| `id` | UUID | PK | Identifiant de l'évènement |
| `zone_id` | UUID | FK → risk_zones.id | Zone concernée par l'évènement |
| `event_type` | VARCHAR(50) | NOT NULL | Type d'évènement (STADIUM_EVENT, FESTIVAL, ROADWORK...) |
| `starts_at` | TIMESTAMP | NOT NULL | Début de l'évènement |
| `ends_at` | TIMESTAMP | NOT NULL | Fin de l'évènement |
| `description` | TEXT | NULL | Description libre |

---

## 13. `congestion_events`

**Rôle :** chaque signal de congestion reçu depuis le réseau mobile (via CAMARA/Nokia) pour un tracker donné, à un instant donné.

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| `id` | BIGSERIAL | PK | Identifiant interne |
| `tracker_id` | UUID | FK → trackers.id | Tracker concerné |
| `corridor_id` | UUID | FK → corridors.id | Corridor concerné |
| `congestion_level` | VARCHAR(30) | NOT NULL | Niveau de congestion (Low, Medium, High) |
| `confidence_level` | DECIMAL(5,4) | NULL | Fiabilité du signal donnée par l'API |
| `location` | GEOGRAPHY(POINT, 4326) | NULL | Position associée au signal |
| `timestamp` | TIMESTAMP | NOT NULL | Moment du signal |
| `source` | VARCHAR(50) | NOT NULL | Origine du signal (ex: NOKIA_CAMARA) |
| `raw_event_id` | VARCHAR(150) | NULL | Identifiant de l'évènement côté API externe |

---

## 14. `risk_assessments`

**Rôle :** le résultat de l'analyse de risque faite par l'agent pour un signal de congestion donné.

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| `id` | UUID | PK | Identifiant de l'évaluation |
| `tracker_id` | UUID | FK → trackers.id | Tracker concerné |
| `cargo_id` | UUID | FK → cargos.id | Cargaison concernée |
| `corridor_id` | UUID | FK → corridors.id | Corridor concerné |
| `congestion_event_id` | BIGINT | FK → congestion_events.id | Signal ayant déclenché l'évaluation |
| `risk_level` | VARCHAR(20) | NOT NULL | NORMAL, EVENT, INCIDENT, CRISIS |
| `risk_score` | DECIMAL(5,4) | NOT NULL | Score de risque calculé (0 à 1) |
| `confidence_score` | DECIMAL(5,4) | NULL | Confiance dans cette évaluation |
| `reason` | TEXT | NULL | Explication en langage naturel (générée par le LLM) |
| `factors` | JSONB | NULL | Détail des facteurs pris en compte |
| `security_snapshot` | JSONB | NULL | Copie figée des résultats de sécurité au moment de la décision |
| `created_at` | TIMESTAMP | NOT NULL | Date de l'évaluation |

---

## 15. `agent_decisions`

**Rôle :** l'action que l'agent a décidé de prendre suite à une évaluation de risque, et si un humain doit valider cette action.

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| `id` | UUID | PK | Identifiant de la décision |
| `risk_assessment_id` | UUID | FK → risk_assessments.id | Évaluation à l'origine de la décision |
| `tracker_id` | UUID | FK → trackers.id | Tracker concerné |
| `cargo_id` | UUID | FK → cargos.id | Cargaison concernée |
| `decision` | VARCHAR(40) | NOT NULL | MONITOR, ALERT, REROUTE, REQUEST_QOD, REQUEST_SLICING, ESCALATE_HUMAN |
| `reasoning_summary` | TEXT | NULL | Résumé explicatif de la décision |
| `confidence` | DECIMAL(5,4) | NULL | Confiance dans la décision |
| `requires_human_approval` | BOOLEAN | DEFAULT FALSE | Si un humain doit valider avant exécution |
| `approved_by` | UUID | FK → users.id, NULL | Manager/Admin ayant validé |
| `approved_at` | TIMESTAMP | NULL | Date de validation |
| `created_at` | TIMESTAMP | NOT NULL | Date de la décision |

---

## 16. `route_suggestions`

**Rôle :** stocke l'itinéraire alternatif que l'agent propose quand un corridor devient risqué.

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| `id` | UUID | PK | Identifiant de la suggestion |
| `agent_decision_id` | UUID | FK → agent_decisions.id | Décision à l'origine de la suggestion |
| `original_corridor_id` | UUID | FK → corridors.id | Corridor initialement emprunté |
| `suggested_corridor_id` | UUID | FK → corridors.id | Corridor alternatif proposé |
| `reason` | TEXT | NULL | Pourquoi ce nouvel itinéraire est proposé |
| `accepted` | BOOLEAN | NULL | Si l'opérateur a accepté (NULL = pas encore répondu) |
| `created_at` | TIMESTAMP | NOT NULL | Date de la suggestion |

---

## 17. `security_checks`

**Rôle :** l'historique de toutes les vérifications de sécurité faites sur un tracker.

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| `id` | UUID | PK | Identifiant du contrôle |
| `tracker_id` | UUID | FK → trackers.id | Tracker vérifié |
| `check_type` | VARCHAR(30) | NOT NULL | NUMBER_VERIFICATION, SIM_SWAP, DEVICE_SWAP |
| `status` | VARCHAR(30) | NOT NULL | PASS, FAIL, DETECTED, UNKNOWN |
| `provider` | VARCHAR(100) | NULL | Fournisseur de la vérification |
| `request_id` | VARCHAR(150) | NULL | Identifiant de la requête externe |
| `details` | JSONB | NULL | Détails complémentaires renvoyés par l'API |
| `timestamp` | TIMESTAMP | NOT NULL | Date du contrôle |

---

## 18. `geofence_subscriptions`

**Rôle :** liste des "alertes automatiques" activées pour prévenir quand un tracker entre ou sort d'une zone surveillée.

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| `id` | UUID | PK | Identifiant de l'abonnement |
| `tracker_id` | UUID | FK → trackers.id | Tracker surveillé |
| `zone_id` | UUID | FK → risk_zones.id | Zone surveillée |
| `webhook_url` | TEXT | NOT NULL | Adresse où CAMARA envoie la notification |
| `status` | VARCHAR(30) | NOT NULL | ACTIVE, CANCELLED, EXPIRED |
| `external_subscription_id` | VARCHAR(150) | NULL | Identifiant de l'abonnement côté API CAMARA |
| `created_at` | TIMESTAMP | NOT NULL | Date de création de l'abonnement |
| `cancelled_at` | TIMESTAMP | NULL | Date d'annulation (si applicable) |

---

## 19. `alerts`

**Rôle :** les notifications envoyées quand un risque est détecté.

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| `id` | UUID | PK | Identifiant de l'alerte |
| `organization_id` | UUID | FK → organizations.id | Entreprise concernée |
| `cargo_id` | UUID | FK → cargos.id | Cargaison concernée |
| `tracker_id` | UUID | FK → trackers.id | Tracker concerné |
| `risk_assessment_id` | UUID | FK → risk_assessments.id | Évaluation à l'origine de l'alerte |
| `severity` | VARCHAR(20) | NOT NULL | LOW, MEDIUM, HIGH, CRITICAL |
| `title` | VARCHAR(200) | NOT NULL | Titre court de l'alerte |
| `message` | TEXT | NOT NULL | Message détaillé |
| `status` | VARCHAR(30) | NOT NULL | OPEN, ACKNOWLEDGED, CLOSED |
| `created_at` | TIMESTAMP | NOT NULL | Date de création |
| `acknowledged_at` | TIMESTAMP | NULL | Date de prise en compte |
| `acknowledged_by` | UUID | FK → users.id, NULL | Utilisateur ayant pris en compte l'alerte |

---

## 20. `network_actions`

**Rôle :** trace chaque action envoyée aux APIs réseau (QoD ou Network Slicing) et son résultat.

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| `id` | UUID | PK | Identifiant de l'action |
| `tracker_id` | UUID | FK → trackers.id | Tracker concerné |
| `risk_assessment_id` | UUID | FK → risk_assessments.id | Évaluation à l'origine de l'action |
| `action_type` | VARCHAR(40) | NOT NULL | QOD ou NETWORK_SLICING |
| `status` | VARCHAR(30) | NOT NULL | REQUESTED, APPROVED, EXECUTED, FAILED, REJECTED |
| `requested_at` | TIMESTAMP | NOT NULL | Date de la demande |
| `executed_at` | TIMESTAMP | NULL | Date d'exécution effective |
| `request_id` | VARCHAR(150) | NULL | Identifiant externe (côté API CAMARA) |
| `response` | JSONB | NULL | Réponse brute renvoyée par l'API |
| `error_message` | TEXT | NULL | Message d'erreur en cas d'échec |

---

## 21. `audit_logs`

**Rôle :** le journal immuable de tout ce qui s'est passé d'important.

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| `id` | BIGSERIAL | PK | Identifiant de l'entrée |
| `organization_id` | UUID | FK → organizations.id | Entreprise concernée |
| `user_id` | UUID | FK → users.id, NULL | Utilisateur impliqué (si applicable) |
| `actor_type` | VARCHAR(30) | NOT NULL | USER, AGENT, SYSTEM |
| `action` | VARCHAR(100) | NOT NULL | Action effectuée |
| `entity_type` | VARCHAR(50) | NOT NULL | Type d'objet concerné |
| `entity_id` | UUID | NULL | Identifiant de l'objet concerné |
| `result` | VARCHAR(30) | NOT NULL | Résultat de l'action |
| `correlation_id` | UUID | NULL | Identifiant reliant les étapes d'une même opération |
| `payload_hash` | VARCHAR(128) | NULL | Empreinte (hash) pour vérifier l'intégrité des données |
| `created_at` | TIMESTAMP | NOT NULL | Date de l'entrée |

---

## 22. Index recommandés

```sql
-- Index spatiaux (obligatoires pour des requêtes PostGIS rapides)
CREATE INDEX idx_corridors_geometry ON corridors USING GIST (geometry);
CREATE INDEX idx_risk_zones_geometry ON risk_zones USING GIST (geometry);
CREATE INDEX idx_tracker_locations_geometry ON tracker_locations USING GIST (location);
CREATE INDEX idx_congestion_events_geometry ON congestion_events USING GIST (location);

-- Index composites (pour les recherches "historique d'un tracker dans le temps")
CREATE INDEX idx_tracker_locations_tracker_time ON tracker_locations (tracker_id, timestamp DESC);
CREATE INDEX idx_congestion_events_tracker_time ON congestion_events (tracker_id, timestamp DESC);
CREATE INDEX idx_congestion_events_corridor_time ON congestion_events (corridor_id, timestamp DESC);

-- Index pour le flux d'inscription
CREATE INDEX idx_organizations_status ON organizations (status);
CREATE INDEX idx_email_verification_codes_user ON email_verification_codes (user_id, expires_at DESC);
```

---

## 23. Petit lexique

- **Cron / job planifié** : une tâche informatique programmée pour s'exécuter automatiquement à intervalles réguliers, sans intervention humaine.
- **JSONB** : un type de colonne PostgreSQL qui stocke des données flexibles en format JSON, optimisé pour la recherche.
- **GiST** : un type d'index PostgreSQL spécialement conçu pour accélérer les recherches géographiques.

---
