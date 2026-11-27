from pathlib import Path
import sqlite3

from qsequoia2.modules.utils.seq_config import seq_layer_path
from qsequoia2.modules.utils.plugin_vars import PLUGIN_DIR
from qsequoia2.modules.utils.variable import get_global_variable

DEFAULT_SQL_DLL_CONFIG_DIR = PLUGIN_DIR / "config" / "sql_data_definition_language"

class Qsequoia2DbManager():

    def __init__(self, gpkg_key: str, build: bool = False, sql_ddl_script: str | None = None, sch_scripts: list[str] | None = None):

        self.db_path = seq_layer_path(gpkg_key)
        self.db: sqlite3.Connection | None = None
        self.cursor: sqlite3.Cursor | None = None
        self.sql_ddl_script = sql_ddl_script
        self.sch_scripts = sch_scripts
        self.initialize(build=build)

    def connect(self):
        self.db = sqlite3.connect(f"file:{self.db_path}?mode=rw", uri=True)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        self.cursor = self.db.cursor()

    def commit(self):
        self.db.commit()

    def close(self):
        if self.db is not None:
            self.db.close()
            self.db = None
            self.cursor = None

    def build_db(self) -> bool:
        if not self.sql_ddl_script:
            raise ValueError("Aucun script DDL fourni pour construire la base")
        return self.ddl_execute(self.sql_ddl_script, self.sch_scripts)

    def ddl_execute(self, sql_ddl_script: str, sch_scripts: list[str] | None = None) -> bool:
        scripts = [sql_ddl_script, *(sch_scripts or [])]
        try:
            for name in scripts:
                sql = self._sql_reader(self._resolve_sql_script_path(name))
                self.cursor.executescript(sql)
            self.commit()
            return True
        except (sqlite3.Error, OSError) as e:
            self.db.rollback()
            print(f"Échec du script DDL '{name}' : {e}")  # ou QgsMessageLog
            return False

    def _resolve_sql_script_path(self, script_name: str) -> Path:
        return Path(DEFAULT_SQL_DLL_CONFIG_DIR) / f"{script_name}.sql"

    def initialize(self, build: bool = False):
        self.connect()
        if build:
            self.build_db()

    @staticmethod
    def _sql_reader(file_path: Path) -> str:
        return file_path.read_text(encoding="utf-8")













