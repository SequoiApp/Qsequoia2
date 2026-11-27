
import sqlite3

from qsequoia2.modules.database.database_manager import Qsequoia2DbManager

class Qsequoia2DbEntities():

    def __init__(self, dbm: Qsequoia2DbManager):
        self.dbm = dbm

    def request(self, table: str, columns=None, values=None, fetchone=True) -> sqlite3.Row | list[sqlite3.Row] | None:

        if self.dbm.db is None:
            return None

        existing = self.get_columns(table)
        if not existing:
            return None

        query = f'SELECT * FROM "{table}"'
        params = ()

        if columns:
            if isinstance(columns, str):
                columns, values = (columns,), (values,)

            if len(columns) != len(values or ()) or not set(columns) <= set(existing):
                return None

            query += " WHERE " + " OR ".join(f'"{c}" IS ?' for c in columns)
            params = tuple(values)

        try:
            cur = self.dbm.db.execute(query, params)
        except sqlite3.Error:
            return None

        if fetchone:
            return cur.fetchone()
        return cur.fetchall() or None


    def insert(self, table: str, columns: tuple, values: tuple) -> sqlite3.Row:
        placeholders = ", ".join("?" for _ in values)
        columns_sql = ", ".join(columns)

        self.dbm.cursor.execute(
            f'INSERT INTO "{table}" ({columns_sql}) VALUES ({placeholders})', values
        )
        rowid = self.dbm.cursor.lastrowid
        self.dbm.commit()

        self.dbm.cursor.execute(f'SELECT * FROM "{table}" WHERE rowid = ?', (rowid,))
        return self.dbm.cursor.fetchone()

    def delete(self, table: str, columns: tuple, values: tuple) -> int:
        if len(columns) != len(values):
            raise ValueError(
                "Le nombre de colonnes doit correspondre au nombre de valeurs."
            )

        conditions = " AND ".join(f"{column} = ?" for column in columns)

        query = f"DELETE FROM {table} WHERE {conditions}"

        self.dbm.cursor.execute(query, values)
        deleted_rows = self.dbm.cursor.rowcount
        self.dbm.commit()

        return deleted_rows

    def update(self, table: str, columns: tuple, values: tuple, id_column: str, id_value):

        if len(columns) != len(values):
            raise ValueError("Le nombre de colonnes doit correspondre au nombre de valeurs.")

        assignments = ", ".join(f"{column} = ?" for column in columns)
        query = f"UPDATE {table} SET {assignments} WHERE {id_column} = ?"

        self.dbm.cursor.execute(query, values + (id_value,))
        self.dbm.commit()

        return self.dbm.cursor.rowcount


    def get_primary_key(self, table: str) -> str | None:
        self.dbm.cursor.execute(f'PRAGMA table_info("{table}")')
        columns = self.dbm.cursor.fetchall()

        primary_keys = [
            column["name"]
            for column in columns
            if column["pk"] > 0
        ]

        if len(primary_keys) == 1:
            return primary_keys[0]

        return None

    def get_columns(self, table: str) -> list[str]:
        self.dbm.cursor.execute(f'PRAGMA table_info("{table}")')
        return [c["name"] for c in self.dbm.cursor.fetchall()]

    def delete_cascade(self, table: str, column: str, values: list) -> None:
        """Supprime les lignes ciblées et toutes leurs données dépendantes (transaction unique)."""
        try:
            self._cascade(table, column, list(values))
            self.dbm.commit()
        except Exception:
            self.dbm.cursor.connection.rollback()
            raise

    def _cascade(self, table: str, column: str, values: list) -> None:
        if not values:
            return
        cur = self.dbm.cursor
        ph = ",".join("?" for _ in values)

        cur.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )
        tables = [r["name"] for r in cur.fetchall()]

        for child in tables:
            if child == table:
                continue
            cur.execute(f'PRAGMA foreign_key_list("{child}")')
            fks = [fk for fk in cur.fetchall() if fk["table"] == table]

            for fk in fks:
                to_col = fk["to"] or self.get_primary_key(table)
                cur.execute(
                    f'SELECT "{to_col}" FROM "{table}" WHERE "{column}" IN ({ph})',
                    values,
                )
                parent_values = [r[0] for r in cur.fetchall() if r[0] is not None]
                self._cascade(child, fk["from"], parent_values)

        cur.execute(f'DELETE FROM "{table}" WHERE "{column}" IN ({ph})', values)