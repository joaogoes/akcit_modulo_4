"""Esquema e dados de um banco criado pela primeira versão da aplicação."""

V0_WITH_ONE_REPOSITORY = """
    CREATE TABLE repositories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL UNIQUE COLLATE NOCASE,
        branch TEXT, created_at TEXT NOT NULL,
        last_collected_at TEXT, last_collection_status TEXT);
    CREATE TABLE reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        repository_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
        phase TEXT NOT NULL, feature TEXT NOT NULL, path TEXT NOT NULL,
        generated TEXT, verdict TEXT);
    INSERT INTO repositories (full_name, created_at) VALUES ('acme/app', '2026-10-01T00:00:00+00:00');
"""
