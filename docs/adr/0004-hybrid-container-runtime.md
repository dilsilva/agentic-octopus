# ADR-0004: Hybrid container runtime — compose-first, Cloud Run later, no Kubernetes

- **Status:** accepted
- **Date:** 2026-07-15
- **Deciders:** Diego
- **Related:** RFC-0001, ADR-0003

## Context

Agents should run on the owner's Mac today and survive a machine migration or move to
always-on cloud later, without redesign. Owner has GCP/K8s background but explicitly wants
solo-operator simplicity here.

## Decision

We will ship 12-factor containers (one image for api/worker/cli, all config via env) that run
identically under docker compose locally and on Cloud Run + Cloud SQL later. No Kubernetes.

## Options considered

### Option A — Hybrid, compose-first  ← chosen
- Pros: zero cloud cost until needed; identical artifact both places; machine migration =
  clone + `make dev`.
- Cons: hybrid discipline (nothing may depend on the Mac) costs a little design attention.

### Option B — Local-only (venv + launchd)
- Pros: simplest today. Cons: agents die when the laptop sleeps; cloud move becomes a rewrite.
  Rejected.

### Option C — Cloud-first from day one
- Pros: always-on immediately. Cons: IAM/secrets/deploy work before any agent is validated.
  Rejected as premature.

## Consequences

- Positive: the GCP phase (RFC-0001 P4) is a deployment exercise, not a redesign.
- Negative: some laptop-convenient shortcuts (host paths, keychain) are off-limits inside
  containers — config comes from env only.
- Follow-ups: P4 adds Cloud Run services, Cloud SQL, Secret Manager — behind the consent gate.
