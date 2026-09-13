# Raased — Database (v3 — with manager sign-up + email verification)

> Update integrating the new manager self-registration flow
> (Company → Manager → Verification → Documents form).
> Changes marked 🆕 (new table) or ✏️ (modified/added columns).

---

## 1. `organizations` ✏️

**Role:** represents a client company of Raased. Extended to store all the information collected at the "Company" step of the sign-up form, and to track the approval status of the request (a free sign-up must be validated before becoming active).

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK | Unique organization identifier |
| `name` | VARCHAR(150) | NOT NULL | Company name |
| `legal_id` | VARCHAR(50) | NOT NULL | Legal identifier (ICE / RC) |
| `country` | VARCHAR(100) | NOT NULL | Country |
| `city` | VARCHAR(100) | NOT NULL | City |
| `phone` | VARCHAR(30) | NOT NULL | Company phone number |
| `address` | TEXT | NOT NULL | Full address |
| `website` | VARCHAR(255) | NULL | Website (optional) |
| `email` | VARCHAR(255) | NOT NULL | Company contact email |
| `status` | VARCHAR(20) | NOT NULL, DEFAULT 'PENDING' | 🆕 Request status: PENDING, APPROVED, REJECTED |
| `reviewed_by` | UUID | FK → users.id, NULL | 🆕 Admin who processed the request |
| `reviewed_at` | TIMESTAMP | NULL | 🆕 Date the request was processed |
| `rejection_reason` | TEXT | NULL | 🆕 Reason in case of rejection |
| `created_at` | TIMESTAMP | NOT NULL | Creation date |
| `updated_at` | TIMESTAMP | NOT NULL | Last modification |

---

## 2. `users` ✏️

**Role:** the people who use the platform (admin, manager, driver). Extended to store the fields collected at the "Manager" step of the form, and to track email verification.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK | User identifier |
| `organization_id` | UUID | FK → organizations.id | User's company |
| `first_name` | VARCHAR(100) | NOT NULL | First name |
| `last_name` | VARCHAR(100) | NOT NULL | Last name |
| `job_title` | VARCHAR(100) | NULL | Job title (CEO, Director...) |
| `phone` | VARCHAR(30) | NULL | Professional phone number |
| `email` | VARCHAR(255) | UNIQUE, NOT NULL | Email |
| `password` | TEXT | NULL | ✏️ Nullable — an invited driver hasn't set a password yet |
| `role` | VARCHAR(30) | NOT NULL | ADMIN, MANAGER, or DRIVER |
| `email_verified` | BOOLEAN | DEFAULT FALSE | Email verified (managers) |
| `email_verified_at` | TIMESTAMP | NULL | Verification date |
| `account_status` | VARCHAR(20) | NOT NULL, DEFAULT 'ACTIVE' | 🆕 INVITED, ACTIVE, DISABLED |
| `is_active` | BOOLEAN | DEFAULT TRUE | Whether the account is active or disabled |
| `created_at` | TIMESTAMP | NOT NULL | Creation date |
| `updated_at` | TIMESTAMP | NOT NULL | Last modification |

---
## X. `account_invitations` — 🆕

**Why:** when a manager creates a driver account, the driver shouldn't know their password — this table manages the secure (single-use) invitation link the driver receives by email to set their own password.

**Role:** stores each invitation token sent, its expiration date, and whether it has already been used.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK | Invitation identifier |
| `user_id` | UUID | FK → users.id | Invited driver |
| `token` | VARCHAR(255) | UNIQUE, NOT NULL | Secure token included in the email link |
| `expires_at` | TIMESTAMP | NOT NULL | Expiration date of the link |
| `used_at` | TIMESTAMP | NULL | Date of use (NULL = not yet used) |
| `created_at` | TIMESTAMP | NOT NULL | Date the invitation was created |
---

## 3. `email_verification_codes` — 🆕

**Why:** the "Verification" step of the form sends a 6-digit code by email, with the option to resend it. A separate table (rather than columns on `users`) allows clean handling of expiration, attempt history, and code resending without overwriting the old one.

**Role:** stores each code sent to a user, its expiration date, and whether it has been used.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK | Code identifier |
| `user_id` | UUID | FK → users.id | Related user |
| `code` | VARCHAR(10) | NOT NULL | 6-digit code sent by email |
| `expires_at` | TIMESTAMP | NOT NULL | Expiration date of the code |
| `verified_at` | TIMESTAMP | NULL | Date of successful use (NULL = not yet verified) |
| `attempts` | INT | NOT NULL, DEFAULT 0 | Number of incorrect entry attempts |
| `created_at` | TIMESTAMP | NOT NULL | Date the code was sent |

---

## 4. `organization_documents` — 🆕

**Why:** the "Documents" step of the form allows (optionally) uploading a company certificate and an ID document for the responsible person, used only for manual verification of the sign-up request.

**Role:** stores the files linked to an organization's request.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK | Document identifier |
| `organization_id` | UUID | FK → organizations.id | Related organization |
| `document_type` | VARCHAR(50) | NOT NULL | COMPANY_CERTIFICATE or RESPONSIBLE_ID |
| `file_url` | TEXT | NOT NULL | Location of the stored file |
| `uploaded_at` | TIMESTAMP | NOT NULL | Upload date |

---

## 5. `cargos`

**Role:** a cargo (goods) currently being transported, with its priority/criticality level.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK | Cargo identifier |
| `organization_id` | UUID | FK → organizations.id | Owning company |
| `reference` | VARCHAR(100) | UNIQUE | Business reference (e.g. CARGO-2026-001) |
| `type` | VARCHAR(50) | NOT NULL | Type of goods (e.g. PHARMACEUTICAL) |
| `criticality` | VARCHAR(20) | NOT NULL | LOW, MEDIUM, HIGH, CRITICAL |
| `status` | VARCHAR(30) | NOT NULL | Transport status (e.g. IN_TRANSIT) |
| `origin` | VARCHAR(150) | NOT NULL | Departure city/point |
| `destination` | VARCHAR(150) | NOT NULL | Arrival city/point |
| `deadline` | TIMESTAMP | NULL | Delivery deadline |
| `created_at` | TIMESTAMP | NOT NULL | Creation date |
| `updated_at` | TIMESTAMP | NOT NULL | Last modification |

---

## 6. `trackers`

**Role:** the physical device (mobile line) attached to a cargo to track it.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK | Internal identifier |
| `organization_id` | UUID | FK → organizations.id | Company that owns the device |
| `device_id` | VARCHAR(100) | UNIQUE | Physical device identifier |
| `msisdn` | VARCHAR(30) | NULL | Associated mobile (SIM) number |
| `status` | VARCHAR(30) | NOT NULL | ACTIVE, INACTIVE, MAINTENANCE... |
| `last_seen_at` | TIMESTAMP | NULL | Last known activity |
| `created_at` | TIMESTAMP | NOT NULL | Creation date |
| `updated_at` | TIMESTAMP | NOT NULL | Last modification |

---

## 7. `cargo_trackers`

**Why:** a tracker (physical object) is reused across multiple deliveries over time. Without this table, we'd lose track of "which tracker was following which cargo, at what time" — information essential for auditing after an incident.

**Role:** a log noting "this tracker was put on this cargo on this date, then removed on this other date".

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK | Association identifier |
| `cargo_id` | UUID | FK → cargos.id | Tracked cargo |
| `tracker_id` | UUID | FK → trackers.id | Tracker used |
| `assigned_at` | TIMESTAMP | NOT NULL | Date the tracker was put into service on this cargo |
| `unassigned_at` | TIMESTAMP | NULL | Removal date (NULL if still active) |

---

## 8. `corridors`

**Role:** a monitored logistics route (a road/highway between two cities), represented as a line on the map.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK | Corridor identifier |
| `name` | VARCHAR(150) | NOT NULL | Corridor name |
| `origin` | VARCHAR(150) | NOT NULL | Starting point |
| `destination` | VARCHAR(150) | NOT NULL | Ending point |
| `geometry` | GEOGRAPHY(LINESTRING, 4326) | NOT NULL | Geographic path (line connecting the route's points) |
| `risk_level` | VARCHAR(20) | NOT NULL | Corridor's baseline risk level |
| `is_active` | BOOLEAN | DEFAULT TRUE | Whether the corridor is currently monitored |
| `created_at` | TIMESTAMP | NOT NULL | Creation date |
| `updated_at` | TIMESTAMP | NOT NULL | Last modification |

---

## 9. `risk_zones`

**Role:** a sensitive geographic area within a corridor (border, port, customs, known incident zone), represented as a surface on the map.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK | Zone identifier |
| `corridor_id` | UUID | FK → corridors.id | Corridor the zone belongs to |
| `name` | VARCHAR(150) | NOT NULL | Zone name |
| `type` | VARCHAR(50) | NOT NULL | BORDER, PORT, CUSTOMS, INCIDENT, SECURITY... |
| `risk_level` | VARCHAR(20) | NOT NULL | Zone's risk level |
| `geometry` | GEOGRAPHY(POLYGON, 4326) | NOT NULL | Geographic boundary of the zone |
| `description` | TEXT | NULL | Free-text description |
| `is_active` | BOOLEAN | DEFAULT TRUE | Whether the zone is currently monitored |
| `created_at` | TIMESTAMP | NOT NULL | Creation date |
| `updated_at` | TIMESTAMP | NOT NULL | Last modification |

---

## 10. `tracker_locations`

**Role:** the history of all successive positions of a tracker (never overwritten — each new position is a new row).

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | BIGSERIAL | PK | Record identifier |
| `tracker_id` | UUID | FK → trackers.id | Related tracker |
| `location` | GEOGRAPHY(POINT, 4326) | NOT NULL | Position (a point on the map) |
| `accuracy` | DOUBLE PRECISION | NULL | Estimated accuracy of the position |
| `source` | VARCHAR(30) | NOT NULL | Data origin: GPS or NETWORK |
| `timestamp` | TIMESTAMP | NOT NULL | Moment of this position |

---

## 11. `corridor_congestion_baselines`

**Why:** to know if congestion is "abnormal", you first need to know what is "normal" at that place and time.

**Role:** a record of the usual congestion level for each corridor, based on time of day and day of the week.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK | Baseline identifier |
| `corridor_id` | UUID | FK → corridors.id | Related corridor |
| `hour_of_day` | SMALLINT | NOT NULL | Hour of the day (0 to 23) |
| `day_of_week` | SMALLINT | NOT NULL | Day of the week (0 to 6) |
| `typical_congestion_level` | VARCHAR(30) | NOT NULL | Usual congestion level for this time slot |
| `sample_count` | INT | NOT NULL | Number of measurements used for this calculation |
| `updated_at` | TIMESTAMP | NOT NULL | Date of the last recalculation |

---

## 12. `known_context_events`

**Why:** to distinguish real disruption from normal congestion caused by a known event (football match, festival, roadworks).

**Role:** a calendar of known events that can explain a rise in congestion without it being an incident.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK | Event identifier |
| `zone_id` | UUID | FK → risk_zones.id | Zone affected by the event |
| `event_type` | VARCHAR(50) | NOT NULL | Event type (STADIUM_EVENT, FESTIVAL, ROADWORK...) |
| `starts_at` | TIMESTAMP | NOT NULL | Event start |
| `ends_at` | TIMESTAMP | NOT NULL | Event end |
| `description` | TEXT | NULL | Free-text description |

---

## 13. `congestion_events`

**Role:** each congestion signal received from the mobile network (via CAMARA/Nokia) for a given tracker, at a given moment.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | BIGSERIAL | PK | Internal identifier |
| `tracker_id` | UUID | FK → trackers.id | Related tracker |
| `corridor_id` | UUID | FK → corridors.id | Related corridor |
| `congestion_level` | VARCHAR(30) | NOT NULL | Congestion level (Low, Medium, High) |
| `confidence_level` | DECIMAL(5,4) | NULL | Reliability of the signal as given by the API |
| `location` | GEOGRAPHY(POINT, 4326) | NULL | Position associated with the signal |
| `timestamp` | TIMESTAMP | NOT NULL | Moment of the signal |
| `source` | VARCHAR(50) | NOT NULL | Origin of the signal (e.g. NOKIA_CAMARA) |
| `raw_event_id` | VARCHAR(150) | NULL | Identifier of the event on the external API side |

---

## 14. `risk_assessments`

**Role:** the result of the risk analysis performed by the agent for a given congestion signal.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK | Assessment identifier |
| `tracker_id` | UUID | FK → trackers.id | Related tracker |
| `cargo_id` | UUID | FK → cargos.id | Related cargo |
| `corridor_id` | UUID | FK → corridors.id | Related corridor |
| `congestion_event_id` | BIGINT | FK → congestion_events.id | Signal that triggered the assessment |
| `risk_level` | VARCHAR(20) | NOT NULL | NORMAL, EVENT, INCIDENT, CRISIS |
| `risk_score` | DECIMAL(5,4) | NOT NULL | Calculated risk score (0 to 1) |
| `confidence_score` | DECIMAL(5,4) | NULL | Confidence in this assessment |
| `reason` | TEXT | NULL | Natural-language explanation (generated by the LLM) |
| `factors` | JSONB | NULL | Details of the factors taken into account |
| `security_snapshot` | JSONB | NULL | Frozen copy of security results at the time of the decision |
| `created_at` | TIMESTAMP | NOT NULL | Assessment date |

---

## 15. `agent_decisions`

**Role:** the action the agent decided to take following a risk assessment, and whether a human must validate this action.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK | Decision identifier |
| `risk_assessment_id` | UUID | FK → risk_assessments.id | Assessment that triggered the decision |
| `tracker_id` | UUID | FK → trackers.id | Related tracker |
| `cargo_id` | UUID | FK → cargos.id | Related cargo |
| `decision` | VARCHAR(40) | NOT NULL | MONITOR, ALERT, REROUTE, REQUEST_QOD, REQUEST_SLICING, ESCALATE_HUMAN |
| `reasoning_summary` | TEXT | NULL | Explanatory summary of the decision |
| `confidence` | DECIMAL(5,4) | NULL | Confidence in the decision |
| `requires_human_approval` | BOOLEAN | DEFAULT FALSE | Whether a human must validate before execution |
| `approved_by` | UUID | FK → users.id, NULL | Manager/Admin who validated it |
| `approved_at` | TIMESTAMP | NULL | Validation date |
| `created_at` | TIMESTAMP | NOT NULL | Decision date |

---

## 16. `route_suggestions`

**Role:** stores the alternative route the agent suggests when a corridor becomes risky.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK | Suggestion identifier |
| `agent_decision_id` | UUID | FK → agent_decisions.id | Decision that triggered the suggestion |
| `original_corridor_id` | UUID | FK → corridors.id | Originally used corridor |
| `suggested_corridor_id` | UUID | FK → corridors.id | Proposed alternative corridor |
| `reason` | TEXT | NULL | Why this new route is being suggested |
| `accepted` | BOOLEAN | NULL | Whether the operator accepted it (NULL = not yet answered) |
| `created_at` | TIMESTAMP | NOT NULL | Suggestion date |

---

## 17. `security_checks`

**Role:** the history of all security checks performed on a tracker.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK | Check identifier |
| `tracker_id` | UUID | FK → trackers.id | Checked tracker |
| `check_type` | VARCHAR(30) | NOT NULL | NUMBER_VERIFICATION, SIM_SWAP, DEVICE_SWAP |
| `status` | VARCHAR(30) | NOT NULL | PASS, FAIL, DETECTED, UNKNOWN |
| `provider` | VARCHAR(100) | NULL | Verification provider |
| `request_id` | VARCHAR(150) | NULL | External request identifier |
| `details` | JSONB | NULL | Additional details returned by the API |
| `timestamp` | TIMESTAMP | NOT NULL | Date of the check |

---

## 18. `geofence_subscriptions`

**Role:** list of "automatic alerts" enabled to notify when a tracker enters or exits a monitored zone.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK | Subscription identifier |
| `tracker_id` | UUID | FK → trackers.id | Monitored tracker |
| `zone_id` | UUID | FK → risk_zones.id | Monitored zone |
| `webhook_url` | TEXT | NOT NULL | Address where CAMARA sends the notification |
| `status` | VARCHAR(30) | NOT NULL | ACTIVE, CANCELLED, EXPIRED |
| `external_subscription_id` | VARCHAR(150) | NULL | Subscription identifier on the CAMARA API side |
| `created_at` | TIMESTAMP | NOT NULL | Subscription creation date |
| `cancelled_at` | TIMESTAMP | NULL | Cancellation date (if applicable) |

---

## 19. `alerts`

**Role:** the notifications sent when a risk is detected.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK | Alert identifier |
| `organization_id` | UUID | FK → organizations.id | Related company |
| `cargo_id` | UUID | FK → cargos.id | Related cargo |
| `tracker_id` | UUID | FK → trackers.id | Related tracker |
| `risk_assessment_id` | UUID | FK → risk_assessments.id | Assessment that triggered the alert |
| `severity` | VARCHAR(20) | NOT NULL | LOW, MEDIUM, HIGH, CRITICAL |
| `title` | VARCHAR(200) | NOT NULL | Short alert title |
| `message` | TEXT | NOT NULL | Detailed message |
| `status` | VARCHAR(30) | NOT NULL | OPEN, ACKNOWLEDGED, CLOSED |
| `created_at` | TIMESTAMP | NOT NULL | Creation date |
| `acknowledged_at` | TIMESTAMP | NULL | Date it was acknowledged |
| `acknowledged_by` | UUID | FK → users.id, NULL | User who acknowledged the alert |

---

## 20. `network_actions`

**Role:** logs every action sent to the network APIs (QoD or Network Slicing) and its result.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK | Action identifier |
| `tracker_id` | UUID | FK → trackers.id | Related tracker |
| `risk_assessment_id` | UUID | FK → risk_assessments.id | Assessment that triggered the action |
| `action_type` | VARCHAR(40) | NOT NULL | QOD or NETWORK_SLICING |
| `status` | VARCHAR(30) | NOT NULL | REQUESTED, APPROVED, EXECUTED, FAILED, REJECTED |
| `requested_at` | TIMESTAMP | NOT NULL | Request date |
| `executed_at` | TIMESTAMP | NULL | Actual execution date |
| `request_id` | VARCHAR(150) | NULL | External identifier (CAMARA API side) |
| `response` | JSONB | NULL | Raw response returned by the API |
| `error_message` | TEXT | NULL | Error message in case of failure |

---

## 21. `audit_logs`

**Role:** the immutable log of everything important that happened.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | BIGSERIAL | PK | Entry identifier |
| `organization_id` | UUID | FK → organizations.id | Related company |
| `user_id` | UUID | FK → users.id, NULL | Involved user (if applicable) |
| `actor_type` | VARCHAR(30) | NOT NULL | USER, AGENT, SYSTEM |
| `action` | VARCHAR(100) | NOT NULL | Action performed |
| `entity_type` | VARCHAR(50) | NOT NULL | Type of object involved |
| `entity_id` | UUID | NULL | Identifier of the object involved |
| `result` | VARCHAR(30) | NOT NULL | Result of the action |
| `correlation_id` | UUID | NULL | Identifier linking the steps of the same operation |
| `payload_hash` | VARCHAR(128) | NULL | Hash used to verify data integrity |
| `created_at` | TIMESTAMP | NOT NULL | Entry date |

---

## 22. Recommended indexes

```sql
-- Spatial indexes (required for fast PostGIS queries)
CREATE INDEX idx_corridors_geometry ON corridors USING GIST (geometry);
CREATE INDEX idx_risk_zones_geometry ON risk_zones USING GIST (geometry);
CREATE INDEX idx_tracker_locations_geometry ON tracker_locations USING GIST (location);
CREATE INDEX idx_congestion_events_geometry ON congestion_events USING GIST (location);

-- Composite indexes (for "history of a tracker over time" lookups)
CREATE INDEX idx_tracker_locations_tracker_time ON tracker_locations (tracker_id, timestamp DESC);
CREATE INDEX idx_congestion_events_tracker_time ON congestion_events (tracker_id, timestamp DESC);
CREATE INDEX idx_congestion_events_corridor_time ON congestion_events (corridor_id, timestamp DESC);

-- Indexes for the sign-up flow
CREATE INDEX idx_organizations_status ON organizations (status);
CREATE INDEX idx_email_verification_codes_user ON email_verification_codes (user_id, expires_at DESC);
```

---

## 23. Quick glossary

- **Cron / scheduled job**: a computing task programmed to run automatically at regular intervals, without human intervention.
- **JSONB**: a PostgreSQL column type that stores flexible data in JSON format, optimized for searching.
- **GiST**: a PostgreSQL index type specifically designed to speed up geographic searches.

---
