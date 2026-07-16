-- 0001_init: full spine schema (RFC-0001, ADR-0003, ADR-0005).
-- A run row IS the queue item — no separate jobs table.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE schedules (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    agent        text NOT NULL,
    cron_expr    text NOT NULL,
    timezone     text NOT NULL DEFAULT 'UTC',
    params       jsonb NOT NULL DEFAULT '{}',
    enabled      boolean NOT NULL DEFAULT true,
    next_run_at  timestamptz NOT NULL,
    last_run_at  timestamptz,
    last_run_id  uuid,
    created_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (agent, cron_expr)
);

CREATE TABLE runs (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    agent            text NOT NULL,
    status           text NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'running', 'awaiting_approval',
                          'completed', 'failed', 'rejected', 'cancelled')),
    trigger          text NOT NULL DEFAULT 'api'
        CHECK (trigger IN ('api', 'schedule', 'cli', 'webhook', 'chat')),
    params           jsonb NOT NULL DEFAULT '{}',
    schedule_id      uuid REFERENCES schedules(id),
    attempts         int NOT NULL DEFAULT 0,
    max_attempts     int NOT NULL DEFAULT 1,
    available_at     timestamptz NOT NULL DEFAULT now(),
    locked_by        text,
    lease_expires_at timestamptz,
    session_id       text,          -- Claude Agent SDK resume token (gates, retries)
    result           text,
    error            text,
    cost_usd         numeric(10, 4),
    created_at       timestamptz NOT NULL DEFAULT now(),
    started_at       timestamptz,
    finished_at      timestamptz
);

-- The queue poll path: claim the oldest available queued run.
CREATE INDEX runs_queue_idx ON runs (status, available_at);
CREATE INDEX runs_agent_idx ON runs (agent, created_at DESC);

-- Append-only transcript & audit trail: every status change, message, tool use.
CREATE TABLE run_events (
    id       bigserial PRIMARY KEY,
    run_id   uuid NOT NULL REFERENCES runs(id),
    ts       timestamptz NOT NULL DEFAULT now(),
    type     text NOT NULL,        -- status_change | message | tool_use | log
    payload  jsonb NOT NULL DEFAULT '{}'
);

CREATE INDEX run_events_run_idx ON run_events (run_id, id);

-- Consent gates: a pending row parks its run in awaiting_approval (ADR-0005).
CREATE TABLE approvals (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id        uuid NOT NULL REFERENCES runs(id),
    action        text NOT NULL,   -- what consent is being asked for
    payload       jsonb NOT NULL DEFAULT '{}',
    status        text NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'rejected', 'expired')),
    requested_at  timestamptz NOT NULL DEFAULT now(),
    decided_at    timestamptz,
    decided_via   text,            -- cli | api | chat
    note          text
);

CREATE INDEX approvals_pending_idx ON approvals (run_id) WHERE status = 'pending';

-- Agent memory; embeddings unused until the semantic-recall phase
-- (add an HNSW index when that lands, not before).
CREATE TABLE memories (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    agent       text NOT NULL,
    kind        text NOT NULL,
    content     text NOT NULL,
    metadata    jsonb NOT NULL DEFAULT '{}',
    embedding   vector(1536),
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX memories_agent_idx ON memories (agent, created_at DESC);
