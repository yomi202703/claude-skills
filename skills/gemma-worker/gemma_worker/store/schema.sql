CREATE TABLE IF NOT EXISTS trace_log (
  trace_id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  playbook TEXT NOT NULL,
  started_at REAL NOT NULL,
  finished_at REAL,
  verdict TEXT,
  payload_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_trace_task ON trace_log(task_id);
CREATE INDEX IF NOT EXISTS idx_trace_playbook ON trace_log(playbook, started_at);

CREATE TABLE IF NOT EXISTS retry_state (
  task_id TEXT PRIMARY KEY,
  attempts INTEGER NOT NULL DEFAULT 0,
  last_error TEXT,
  next_retry_at REAL
);

CREATE TABLE IF NOT EXISTS spans (
  span_id TEXT PRIMARY KEY,
  trace_id TEXT NOT NULL,
  parent_span_id TEXT,
  name TEXT NOT NULL,
  started_at REAL NOT NULL,
  ended_at REAL,
  attributes_json TEXT NOT NULL DEFAULT '{}',
  status TEXT
);

CREATE INDEX IF NOT EXISTS idx_spans_trace ON spans(trace_id, started_at);

CREATE TABLE IF NOT EXISTS audit_disagreements (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  trace_id TEXT NOT NULL,
  axis INTEGER NOT NULL,
  cheap_verdict TEXT,
  expensive_verdict TEXT,
  tiebreaker_verdict TEXT,
  final TEXT,
  finding_json TEXT NOT NULL,
  created_at REAL NOT NULL
);
