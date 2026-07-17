-- 0002_chat: chat as a spine capability (ADR-0007).
-- Conversations are spine-owned; every UI is a thin client of the same tables.

CREATE TABLE conversations (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    title       text,
    persona     text,             -- agents/<persona>/ dir supplying the system prompt
    model       text,             -- 'default' -> provider default at send time
    summary     text,             -- reserved for rolling summarization (fast-follow)
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE messages (
    id                bigserial PRIMARY KEY,
    conversation_id   uuid NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role              text NOT NULL
        CHECK (role IN ('system', 'user', 'assistant', 'tool')),
    content           text NOT NULL,
    model             text,
    metadata          jsonb NOT NULL DEFAULT '{}',   -- tool calls, citations, truncated flag
    prompt_tokens     int,
    completion_tokens int,
    duration_ms       int,
    created_at        timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX messages_conv_idx ON messages (conversation_id, id);

-- Metadata-only log for the stateless /v1 OpenAI-compat shim (never message content).
CREATE TABLE chat_completions (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ts                timestamptz NOT NULL DEFAULT now(),
    model             text,
    prompt_tokens     int,
    completion_tokens int,
    total_tokens      int,
    duration_ms       int,
    stream            boolean NOT NULL DEFAULT false,
    client            text NOT NULL DEFAULT 'openai-compat'
);

CREATE INDEX chat_completions_ts_idx ON chat_completions (ts);
