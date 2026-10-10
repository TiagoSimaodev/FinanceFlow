CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    google_sub TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL,
    name TEXT NOT NULL,
    email_verified INTEGER NOT NULL DEFAULT 1 CHECK (email_verified = 1),
    session_version INTEGER NOT NULL DEFAULT 0 CHECK (session_version >= 0),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS password_credentials (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS password_recovery_codes (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    code_hash TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_normalized
    ON users (lower(email));

CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL COLLATE NOCASE CHECK (length(trim(name)) > 0),
    type TEXT NOT NULL CHECK (type IN ('receita', 'despesa')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE (name, type),
    UNIQUE (id, type)
);

CREATE TABLE IF NOT EXISTS import_batches (
    id INTEGER PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    file_name TEXT NOT NULL CHECK (length(trim(file_name)) > 0),
    file_sha256 TEXT NOT NULL CHECK (length(file_sha256) = 64),
    status TEXT NOT NULL DEFAULT 'processing'
        CHECK (status IN ('processing', 'succeeded', 'partial', 'failed')),
    started_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    finished_at TEXT,
    rows_processed INTEGER NOT NULL DEFAULT 0 CHECK (rows_processed >= 0),
    rows_accepted INTEGER NOT NULL DEFAULT 0 CHECK (rows_accepted >= 0),
    rows_rejected INTEGER NOT NULL DEFAULT 0 CHECK (rows_rejected >= 0),
    duration_ms INTEGER CHECK (duration_ms IS NULL OR duration_ms >= 0),
    error_message TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_import_batches_user_file_sha256
    ON import_batches (user_id, file_sha256);
CREATE INDEX IF NOT EXISTS idx_import_batches_user_id
    ON import_batches (user_id, id DESC);

CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    type TEXT NOT NULL CHECK (type IN ('receita', 'despesa')),
    amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
    transaction_date TEXT NOT NULL
        CHECK (
            length(transaction_date) = 10
            AND date(transaction_date) IS NOT NULL
            AND date(transaction_date, '+0 days') = transaction_date
        ),
    description TEXT NOT NULL DEFAULT '',
    category_id INTEGER NOT NULL,
    source TEXT NOT NULL DEFAULT 'manual' CHECK (source IN ('manual', 'import')),
    import_batch_id INTEGER,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    FOREIGN KEY (category_id, type) REFERENCES categories (id, type) ON DELETE RESTRICT,
    FOREIGN KEY (import_batch_id) REFERENCES import_batches (id) ON DELETE RESTRICT,
    CHECK (
        (source = 'manual' AND import_batch_id IS NULL)
        OR (source = 'import' AND import_batch_id IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_transactions_date
    ON transactions (transaction_date);
CREATE INDEX IF NOT EXISTS idx_transactions_user_date
    ON transactions (user_id, transaction_date);
CREATE INDEX IF NOT EXISTS idx_transactions_category
    ON transactions (category_id);
CREATE INDEX IF NOT EXISTS idx_transactions_type
    ON transactions (type);
CREATE INDEX IF NOT EXISTS idx_transactions_import_batch
    ON transactions (import_batch_id);

CREATE TABLE IF NOT EXISTS goals (
    id INTEGER PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL CHECK (length(trim(name)) > 0),
    target_cents INTEGER NOT NULL CHECK (target_cents > 0),
    start_date TEXT NOT NULL
        CHECK (
            length(start_date) = 10
            AND date(start_date) IS NOT NULL
            AND date(start_date, '+0 days') = start_date
        ),
    end_date TEXT NOT NULL
        CHECK (
            length(end_date) = 10
            AND date(end_date) IS NOT NULL
            AND date(end_date, '+0 days') = end_date
        ),
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'completed', 'paused', 'expired')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    CHECK (end_date >= start_date)
);

CREATE TABLE IF NOT EXISTS import_rejections (
    id INTEGER PRIMARY KEY,
    import_batch_id INTEGER NOT NULL,
    row_number INTEGER NOT NULL CHECK (row_number > 0),
    raw_data TEXT NOT NULL,
    reason TEXT NOT NULL CHECK (length(trim(reason)) > 0),
    rejected_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    FOREIGN KEY (import_batch_id) REFERENCES import_batches (id) ON DELETE CASCADE,
    UNIQUE (import_batch_id, row_number)
);

CREATE INDEX IF NOT EXISTS idx_import_rejections_batch
    ON import_rejections (import_batch_id);
