-- 0003_tags: request tagging for data analysis (ADR-0008).
-- Tags are dual-written: here (SQL analysis with zero infra) and as OTEL span
-- attributes (when an OTLP endpoint is configured).

ALTER TABLE messages ADD COLUMN tags jsonb NOT NULL DEFAULT '{}';
ALTER TABLE chat_completions ADD COLUMN tags jsonb NOT NULL DEFAULT '{}';
ALTER TABLE runs ADD COLUMN tags jsonb NOT NULL DEFAULT '{}';

CREATE INDEX messages_tags_idx ON messages USING gin (tags);
CREATE INDEX chat_completions_tags_idx ON chat_completions USING gin (tags);
CREATE INDEX runs_tags_idx ON runs USING gin (tags);
