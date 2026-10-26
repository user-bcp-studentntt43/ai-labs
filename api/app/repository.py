import sqlite3
from pathlib import Path


class TaskRepository:
    def __init__(self, database_path: str) -> None:
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(database_path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self._initialize_database()

    def _initialize_database(self) -> None:
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, description TEXT NOT NULL, status TEXT NOT NULL, owner TEXT NOT NULL, priority TEXT NOT NULL, created_at TEXT NOT NULL)"
        )
        task_count = self.connection.execute(
            "SELECT COUNT(*) AS total FROM tasks"
        ).fetchone()["total"]
        if task_count == 0:
            self._seed_initial_tasks()

    def _seed_initial_tasks(self) -> None:
        self.connection.execute(
            "INSERT INTO tasks(title,description,status,owner,priority,created_at) VALUES ('Refactor login','Separar responsabilidades en frontend','TODO','student','HIGH',datetime('now'))"
        )
        self.connection.execute(
            "INSERT INTO tasks(title,description,status,owner,priority,created_at) VALUES ('Review API','Revisar seguridad de endpoints','IN_PROGRESS','student','MEDIUM',datetime('now'))"
        )
        self.connection.execute(
            "INSERT INTO tasks(title,description,status,owner,priority,created_at) VALUES ('Trainer notes','Preparar retrospectiva','TODO','trainer','LOW',datetime('now'))"
        )
        self.connection.commit()

    def list_by_owner(self, owner: str) -> list[sqlite3.Row]:
        sql = "SELECT id,title,description,status,owner,priority,created_at FROM tasks WHERE owner=? ORDER BY id"
        return self.connection.execute(sql, (owner,)).fetchall()

    def create_task(
        self, title: str, description: str, status: str, owner: str, priority: str
    ) -> sqlite3.Row:
        sql = "INSERT INTO tasks(title,description,status,owner,priority,created_at) VALUES (?,?,?,?,?,datetime('now'))"
        cursor = self.connection.execute(
            sql, (title, description, status, owner, priority)
        )
        self.connection.commit()
        return self.connection.execute(
            "SELECT id,title,description,status,owner,priority,created_at FROM tasks WHERE id=?",
            (cursor.lastrowid,),
        ).fetchone()

    def summary_by_owner(self, owner: str) -> list[sqlite3.Row]:
        return self.connection.execute(
            "SELECT status,priority FROM tasks WHERE owner=?", (owner,)
        ).fetchall()

    def close(self) -> None:
        self.connection.close()
