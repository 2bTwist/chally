# Chally — MVP vs "Pragmatic Production" Decisions

**Goal:** capture choices we made for the MVP and how we'll evolve them to handle "a lot of users" (reliable, cost-aware production — not hyperscale).

> Glossary is at the bottom for any terms that might be unfamiliar.

---

## 1) Core Stack & Runtime

| Area                    | MVP Decision                                 | Pragmatic Production (next)                                                                                                           |
| ----------------------- | -------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| API framework           | FastAPI + Uvicorn (single process in Docker) | Uvicorn workers behind Gunicorn (`uvicorn.workers.UvicornWorker`), 2–4 workers per CPU; health/ready probes split (`/live`, `/ready`) |
| Language/runtime        | Python 3.13 slim                             | Multi-stage Dockerfile, non-root user, pinned base image; keep 3.13                                                                   |
| Data store              | Postgres (single instance)                   | Managed Postgres (e.g., RDS/Cloud SQL/Aiven), daily snapshots, **pgBouncer** for connection pooling, `max_connections` sane           |
| Cache/queue             | Redis + RQ                                   | Managed Redis; RQ ok, or switch to Celery later. Add a **scheduler** for periodic jobs                                                |
| Object storage          | MinIO (local dev)                            | AWS S3 (or similar). Use **pre-signed URLs**; bucket lifecycle policy & server-side encryption                                        |
| Container orchestration | Docker Compose                               | ECS/Fargate or Kubernetes (one service + one worker). Blue/green deploys                                                              |

---

## 2) Auth & Accounts

| Area               | MVP Decision                                             | Pragmatic Production (next)                                                                                              |
| ------------------ | -------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| Passwords          | `bcrypt` via passlib                                     | Keep bcrypt, tune rounds; consider **argon2id** later                                                                    |
| Tokens             | JWT **HS256** with static secret; access 15m, refresh 7d | **RS256** (public/private key), rotation every 90d. Shorter refresh (7–30d). Consider storing refresh in HttpOnly cookie |
| Login limits       | None                                                     | Rate limit by IP + account (e.g., 5/min), exponential backoff, lockout window                                            |
| Email verification | Not required                                             | Add email verification + password reset. (Out of scope for M0 code; plan endpoints)                                      |
| Admin docs         | Swagger open                                             | Swagger behind auth in prod or limited to internal VPN; publish static OpenAPI                                           |

**Why RS256?** Public key can be shared with other services without exposing signing keys; enables key rotation cleanly.

---

## 3) API Design & Contracts

| Area        | MVP Decision               | Pragmatic Production (next)                                                      |
| ----------- | -------------------------- | -------------------------------------------------------------------------------- |
| Versioning  | Single version             | Prefix with `/v1`. Avoid breaking changes; deprecate with headers                |
| Idempotency | Most writes not idempotent | Add **Idempotency-Key** header for `join`, uploads, payments                     |
| CORS        | `*` in dev                 | Restrict to known web origins; set `Access-Control-Max-Age`                      |
| Pagination  | Roster & lists unpaginated | Add `limit`, `offset` (defaults: 25/0). Return `total` if cheap; else `has_more` |
| Validation  | Pydantic models            | Add request size limits (e.g., 2–5MB), body timeouts, stricter field length caps |

---

## 4) Challenges, Participants & Status

| Area              | MVP Decision                                           | Pragmatic Production (next)                                                                            |
| ----------------- | ------------------------------------------------------ | ------------------------------------------------------------------------------------------------------ |
| Owner membership  | Owner auto-joins on create                             | Keep                                                                                                   |
| Join gating       | Only when `status="active"` and **before** `starts_at` | Flag for **late join** (owner toggle), optional **max_participants**; enforce at DB with check + error |
| Status field      | `draft | active | canceled | deleted`                | Add `paused | archived` if needed; state machine enforced in service layer                            |
| Runtime state     | Computed: `upcoming | started | ended` (+ pass-through canceled/deleted) | Keep; compute db-side later if needed (view/materialized view)                                         |
| Roster visibility | Anyone can view (MVP)                                  | Restrict to participants & owner; add privacy mode for "code" challenges                               |
| Counts            | `COUNT(*)` on demand                                   | Optional cached counter column with transactional updates to avoid hot COUNTs                          |

**Concurrency:** `participants` has unique `(challenge_id,user_id)` — prevents double joins. For high join bursts, wrap joins in a single transaction; consider a **distributed lock** (Redis) if you add max participants.

---

## 5) Timezones & Windows

| Area          | MVP Decision                                                                      | Pragmatic Production (next)                                                                               |
| ------------- | --------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| Storage       | All instants in **UTC**; users supply IANA timezone (e.g., `America/Los_Angeles`) | Keep; validate tz names strictly; reject invalid strings                                                  |
| Rule scope    | `participant_local` (default) or `challenge_tz`                                   | Keep both. Make UI explicit.                                                                              |
| DST handling  | `zoneinfo` conversion; supports gaps & overlaps; tests added                      | Keep; add monitoring for DST days (extra scrutiny)                                                        |
| Daily windows | Compute on the fly with helper                                                    | Precompute **today/tomorrow windows** per participant at midnight UTC via a scheduled job to speed checks |

> **IANA timezone:** the standardized database of world time zones (names like `America/New_York`). Using these prevents "PST vs PDT" confusion.

---

## 6) Uploads & Anti-Cheat

| Area       | MVP Decision                                             | Pragmatic Production (next)                                                                               |
| ---------- | -------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| Storage    | MinIO dev bucket                                         | S3 bucket per env with lifecycle (e.g., temp uploads 7–30 days), server-side encryption                   |
| Access     | Direct upload via API (TBD)                              | **Pre-signed S3 PUT** for clients; size/type validation on callback; virus scan queue (ClamAV)            |
| Metadata   | Basic fields                                             | Strip EXIF if privacy mode; keep minimal metadata necessary for verification                              |
| Anti-cheat | Flags in DSL (`overlay`, `exif_required`, `phash_check`) | Enforce in worker jobs (phash duplicates, EXIF presence). Rate limit attempts. Keep toggles per challenge |

---

## 7) Background Jobs

| Area        | MVP Decision | Pragmatic Production (next)                                                                         |
| ----------- | ------------ | --------------------------------------------------------------------------------------------------- |
| Queue       | RQ + Redis   | Keep RQ initially; add worker autoscaling (K8s HPA or ECS autoscaling). Later: Celery+SQS if needed |
| Scheduling  | None         | RQ-Scheduler / APScheduler sidecar for nightly tasks: window precompute, reminders, cleanup         |
| Idempotency | Best-effort  | Add **task keys** for de-dup; store job results for 24h; dead-letter queue (DLQ) for failures       |

---

## 8) Observability & Ops

| Area            | MVP Decision                              | Pragmatic Production (next)                                                                |
| --------------- | ----------------------------------------- | ------------------------------------------------------------------------------------------ |
| Logs            | JSON via structlog; request_id middleware | Ship to a central sink (CloudWatch/Datadog/ELK). Add **PII redaction**.                    |
| Metrics         | None                                      | **OpenTelemetry** or Prometheus metrics: request latency, error rate, DB time, queue depth |
| Tracing         | None                                      | W3C trace headers through API & workers; sample 1–5%                                       |
| Health          | `/health`                                 | Add `/live` (process up) and `/ready` (DB/Redis checks) for orchestrator probes            |
| Error reporting | None                                      | Sentry/Rollbar capture exceptions with request_id correlation                              |

---

## 9) Database & Migrations

| Area       | MVP Decision                   | Pragmatic Production (next)                                                                              |
| ---------- | ------------------------------ | -------------------------------------------------------------------------------------------------------- |
| Migrations | Alembic                        | Keep; **additive first** strategy; use `CREATE INDEX CONCURRENTLY`; run migrations in a maintenance step |
| Indices    | PKs + invite_code/user indices | Add indices for frequent filters (e.g., `(challenge_id, user_id)`, `created_at` on lists)                |
| Pooling    | SQLAlchemy async engine        | **pgBouncer** transaction pooling in front of DB                                                         |
| Backups    | None                           | Managed daily snapshots + PITR (where supported)                                                         |

---

## 10) Security

| Area         | MVP Decision                  | Pragmatic Production (next)                                                                                                 |
| ------------ | ----------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| Secrets      | `.env.dev` checked in example | Real secrets in a **secrets manager** (AWS SM/GCP SM). Rotate periodically                                                  |
| Transport    | Assume HTTPS locally          | Enforce HTTPS (HSTS). Proxy terminates TLS; service only accepts internal traffic                                           |
| Headers      | None                          | Security headers: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Content-Security-Policy` (tight for app) |
| Abuse        | None                          | **Rate limiting** (per IP & token), **WAF** (Cloudflare/ALB), request body size limits                                      |
| Data privacy | N/A                           | Delete/Export account data endpoints; **soft-delete** users; audit log for sensitive actions                                |

---

## 11) Testing & CI/CD

| Area      | MVP Decision                                                     | Pragmatic Production (next)                                                          |
| --------- | ---------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| Tests     | Unit/integration tests via pytest; dockerized test runner script | CI pipeline (GitHub Actions): run tests, build images, push; smoke tests post-deploy |
| Load test | None                                                             | Quick k6/Gatling script: create/join/list flows at target RPS; watch p99 latency     |
| Staging   | None                                                             | Staging env mirrors prod infra; gated deploys; feature flags                         |

---

## 12) Product Guardrails

| Area       | MVP Decision | Pragmatic Production (next)                                                                           |
| ---------- | ------------ | ----------------------------------------------------------------------------------------------------- |
| Visibility | `public | private | code`(MVP uses`code`) | Clarify what roster is visible in each; mask emails; display **username** only |
| Limits     | None         | Per-challenge limits (max participants, daily proof cap), per-user quotas (storage, challenges owned) |
| Moderation | None         | Report/ban endpoints; admin dashboard lite                                                            |

---

## 13) Current Endpoints Snapshot (what changed in MVP)

* **Auth:** `/auth/register`, `/auth/login`, `/auth/refresh`, `/auth/me`
* **System:** `/health`, `/version`
* **Challenges:**

  * `POST /challenges` → owner auto-joins; returns `participant_count`, `is_owner`, `is_participant`, `runtime_state`
  * `GET  /challenges/mine` → hydrated fields above
  * `GET  /challenges/joined` → challenges where requester is a participant (includes ones they own)
  * `GET  /challenges/{id}` → hydrated single challenge
  * `GET  /challenges/{id}/participants` → roster (participant_id, user_id, username, joined_at) *(MVP visible to anyone; will tighten)*
  * `POST /challenges/{invite_code}/join` → **blocked** for owner; allowed only if `status="active"` **and** now < `starts_at`; idempotent for re-join with timezone update

**Near-term prod tweaks:** pagination on list endpoints; roster visibility restriction; idempotency key for `join`.

---

## 14) Go-Live (Pragmatic) Checklist

* [ ] Move to managed Postgres + pgBouncer; set correct `DATABASE_URL`
* [ ] Managed Redis; deploy a worker service for RQ
* [ ] S3 buckets + pre-signed uploads (and callbacks)
* [ ] Gunicorn with 2–4 Uvicorn workers; readiness & liveness endpoints
* [ ] RS256 JWT keys in secrets manager; rotate
* [ ] CORS restricted; Swagger gated
* [ ] Basic rate limits; body size limit; request timeouts
* [ ] Centralized logs + Sentry; minimal metrics (RPS, p95, error rate)
* [ ] CI builds & pushes images; staged deploy
* [ ] Alembic migration step in pipeline; `CREATE INDEX CONCURRENTLY` where needed

---

## 15) Open Questions (to decide before heavier traffic)

1. Do we allow **late join** after `starts_at`? With/without handicap?
2. Who can view rosters on `code` vs `private` challenges?
3. Maximum participants per challenge (default 100? 500?)
4. Upload size cap (e.g., 10–25MB) and allowed MIME types?
5. Do we require **email verification** before joining public/code challenges?

---

## 16) Glossary (plain-English)

* **IANA timezone**: the canonical list of timezone names like `America/New_York`. Safer than "EST/PST" because it handles daylight saving changes.
* **JWT**: a signed token the server creates and the client sends with requests to prove identity.
* **HS256 vs RS256**: HS256 uses a shared secret (simpler). RS256 uses a private/public key pair (safer key rotation and sharing).
* **pgBouncer**: a lightweight Postgres connection pooler that reduces database connection overhead.
* **Pre-signed URL**: a temporary URL that lets clients upload directly to object storage (like S3) without sending the file through our API servers.
* **OpenTelemetry/Prometheus**: tools to collect metrics (like request latency) so we can see health/perf.
* **RQ**: a simple job queue backed by Redis, used to run background work (like scanning uploads).

---

*Last updated: September 29, 2025*