"""SQLite operations for engagements and their parcel links."""

from contextlib import closing, contextmanager
import sqlite3

ENGAGEMENTS_TABLE_NAME = "engagements_fiscaux"
PARCA_ENGAGEMENTS_TABLE_NAME = "parca_engagements"


@contextmanager
def connection(path):
    with closing(sqlite3.connect(path.as_uri() + "?mode=rw", uri=True)) as db, db:
        db.execute("PRAGMA foreign_keys = ON")
        yield db

def tables_exist(db):
    return db.execute("""
    SELECT count(*)
    FROM sqlite_master
    WHERE type='table' AND name IN (?, ?)
    """, (ENGAGEMENTS_TABLE_NAME, PARCA_ENGAGEMENTS_TABLE_NAME)).fetchone()[0] == 2

def create_tables(path, parcel_table):
    quoted_table = parcel_table.replace('"', '""')
    with connection(path) as db:
        db.execute("BEGIN IMMEDIATE")
        existed = tables_exist(db)
        db.execute(f'CREATE UNIQUE INDEX IF NOT EXISTS "uq_idu_{quoted_table}" ON "{quoted_table}" (IDU)')
        db.execute(f"""
        CREATE TABLE IF NOT EXISTS "{ENGAGEMENTS_TABLE_NAME}" (
            fid INTEGER PRIMARY KEY,
            NAME TEXT NOT NULL UNIQUE,
            TYPE TEXT NOT NULL,
            START_DATE DATE,
            END_DATE DATE
        )""")
        db.execute(f"""
        CREATE TABLE IF NOT EXISTS "{PARCA_ENGAGEMENTS_TABLE_NAME}" (
            fid INTEGER PRIMARY KEY,
            IDU TEXT NOT NULL REFERENCES "{quoted_table}"(IDU),
            ENGAGEMENT_FID INTEGER NOT NULL REFERENCES "{ENGAGEMENTS_TABLE_NAME}"(fid) ON DELETE CASCADE,
            UNIQUE (IDU, ENGAGEMENT_FID)
        )""")
        db.executemany("""
            INSERT INTO gpkg_contents (table_name, data_type) VALUES (?, 'attributes')
            ON CONFLICT(table_name) DO NOTHING
        """,
            [(ENGAGEMENTS_TABLE_NAME,), (PARCA_ENGAGEMENTS_TABLE_NAME,)]
        )
        return not existed


def engagements(path):
    """Return None until the tables are ready, or (fid, name, type) rows."""
    with connection(path) as db:
        if not tables_exist(db):
            return None
        return db.execute(f'SELECT fid, NAME, TYPE FROM "{ENGAGEMENTS_TABLE_NAME}" ORDER BY NAME').fetchall()


def parcel_ids(path, engagement_fid):
    with connection(path) as db:
        rows = db.execute(f'SELECT IDU FROM "{PARCA_ENGAGEMENTS_TABLE_NAME}" WHERE ENGAGEMENT_FID=?', (engagement_fid,))
        return [idu for idu, in rows]


def link_parcels(path, engagement_fid, idus):
    with connection(path) as db:
        return db.executemany(f"""
            INSERT INTO "{PARCA_ENGAGEMENTS_TABLE_NAME}" (IDU, ENGAGEMENT_FID) VALUES (?, ?)
            ON CONFLICT(IDU, ENGAGEMENT_FID) DO NOTHING
        """,
        [(idu, engagement_fid) for idu in idus]
        ).rowcount


def unlink_parcels(path, engagement_fid, idus):
    with connection(path) as db:
        return db.executemany(f"""
            DELETE FROM "{PARCA_ENGAGEMENTS_TABLE_NAME}" WHERE IDU=? AND ENGAGEMENT_FID=?
        """,
        [(idu, engagement_fid) for idu in idus]
        ).rowcount


def delete_engagement(path, engagement_fid):
    with connection(path) as db:
        db.execute(f'DELETE FROM "{ENGAGEMENTS_TABLE_NAME}" WHERE fid=?', (engagement_fid,))
