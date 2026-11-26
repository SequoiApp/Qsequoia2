"""SQLite operations for certifications and their parcel links."""

from contextlib import closing, contextmanager
import sqlite3


@contextmanager
def connection(path):
    with closing(sqlite3.connect(path.as_uri() + "?mode=rw", uri=True)) as db, db:
        db.execute("PRAGMA foreign_keys = ON")
        yield db


def tables_exist(db):
    return db.execute("""SELECT count(*) FROM sqlite_master WHERE type='table'
                         AND name IN ('engagements_fiscaux', 'parca_engagements')""").fetchone()[0] == 2


def create_tables(path, parcel_table):
    quoted_table = parcel_table.replace('"', '""')
    with connection(path) as db:
        db.execute("BEGIN IMMEDIATE")
        existed = tables_exist(db)
        db.execute(f'CREATE UNIQUE INDEX IF NOT EXISTS "uq_idu_{quoted_table}" ON "{quoted_table}" (IDU)')
        db.execute("""CREATE TABLE IF NOT EXISTS engagements_fiscaux (
            fid INTEGER PRIMARY KEY, engagement_id TEXT NOT NULL UNIQUE,
            type TEXT NOT NULL CHECK (type IN ('IFI', 'MONICHON')), start_date DATE, end_date DATE
        )""")
        db.execute(f"""CREATE TABLE IF NOT EXISTS parca_engagements (
            fid INTEGER PRIMARY KEY, IDU TEXT NOT NULL REFERENCES "{quoted_table}"(IDU),
            engagement_id TEXT NOT NULL REFERENCES engagements_fiscaux(engagement_id),
            UNIQUE (IDU, engagement_id)
        )""")
        db.executemany("""INSERT INTO gpkg_contents (table_name, data_type) VALUES (?, 'attributes')
                          ON CONFLICT(table_name) DO NOTHING""", [("engagements_fiscaux",), ("parca_engagements",)])
        return not existed


def certifications(path):
    """Return None before initialization, or a list of (code, type) pairs."""
    with connection(path) as db:
        if not tables_exist(db):
            return None
        return db.execute("SELECT engagement_id, type FROM engagements_fiscaux ORDER BY engagement_id").fetchall()


def parcel_ids(path, code):
    with connection(path) as db:
        rows = db.execute("SELECT IDU FROM parca_engagements WHERE engagement_id=?", (code,))
        return [idu for idu, in rows]


def link_parcels(path, code, idus):
    with connection(path) as db:
        return db.executemany("""INSERT INTO parca_engagements (IDU, engagement_id) VALUES (?, ?)
                                 ON CONFLICT(IDU, engagement_id) DO NOTHING""",
                              [(idu, code) for idu in idus]).rowcount


def unlink_parcels(path, code, idus):
    with connection(path) as db:
        return db.executemany("DELETE FROM parca_engagements WHERE IDU=? AND engagement_id=?",
                              [(idu, code) for idu in idus]).rowcount


def delete_certification(path, code):
    with connection(path) as db:
        db.execute("DELETE FROM parca_engagements WHERE engagement_id=?", (code,))
        db.execute("DELETE FROM engagements_fiscaux WHERE engagement_id=?", (code,))
