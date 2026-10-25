"""
SQLite Database Layer for Maintainer Shield.
Persists ingested PRs, Stage 1 quick check flags, visualization metadata,
AI verdicts, and maintainer audit logs.
"""

import sqlite3
import json
from typing import List, Dict, Optional, Any
from core.schemas import PRShieldContext


class ShieldDatabase:
    """Manages SQLite storage for PR analysis, verdicts, and actions."""

    def __init__(self, db_path: str = "shield_data.sqlite3"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Initializes tables for PR records and maintainer actions."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pr_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pr_id INTEGER NOT NULL,
                    repo_name TEXT NOT NULL,
                    pr_url TEXT NOT NULL UNIQUE,
                    author TEXT NOT NULL,
                    title TEXT NOT NULL,
                    raw_description TEXT,
                    quick_check_score INTEGER,
                    quick_check_flags TEXT,
                    ci_status TEXT,
                    ai_verdict TEXT,
                    ai_reason TEXT,
                    ai_suspicious_injection INTEGER DEFAULT 0,
                    maintainer_decision TEXT,
                    raw_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS triage_actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pr_id INTEGER NOT NULL,
                    repo_name TEXT NOT NULL,
                    action_type TEXT NOT NULL,  -- comment, label, review
                    comment_body TEXT,
                    labels TEXT,
                    dispatched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    success INTEGER NOT NULL
                );
            """)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_repo_pr ON pr_records (repo_name, pr_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_verdict ON pr_records (ai_verdict);")
            conn.commit()

    def save_pr(self, context: PRShieldContext) -> int:
        """Saves or updates a PR context record in SQLite."""
        raw_json_str = context.model_dump_json()
        quick_score = context.quick_checks.score if context.quick_checks else None
        quick_flags = json.dumps(context.quick_checks.flags) if context.quick_checks else "[]"
        ci_status = context.quick_checks.ci_status if context.quick_checks else "none"

        ai_verdict = context.ai_review.verdict if context.ai_review else None
        ai_reason = context.ai_review.short_reason if context.ai_review else None
        ai_injection = 1 if (context.ai_review and context.ai_review.is_suspicious_injection) else 0

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO pr_records (
                    pr_id, repo_name, pr_url, author, title, raw_description,
                    quick_check_score, quick_check_flags, ci_status,
                    ai_verdict, ai_reason, ai_suspicious_injection,
                    maintainer_decision, raw_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(pr_url) DO UPDATE SET
                    title = excluded.title,
                    raw_description = excluded.raw_description,
                    quick_check_score = excluded.quick_check_score,
                    quick_check_flags = excluded.quick_check_flags,
                    ci_status = excluded.ci_status,
                    ai_verdict = excluded.ai_verdict,
                    ai_reason = excluded.ai_reason,
                    ai_suspicious_injection = excluded.ai_suspicious_injection,
                    maintainer_decision = excluded.maintainer_decision,
                    raw_json = excluded.raw_json,
                    updated_at = CURRENT_TIMESTAMP;
            """, (
                context.pr_id,
                context.repo_name,
                context.pr_url,
                context.author,
                context.title,
                context.raw_description,
                quick_score,
                quick_flags,
                ci_status,
                ai_verdict,
                ai_reason,
                ai_injection,
                context.maintainer_decision,
                raw_json_str,
            ))
            conn.commit()
            return cursor.lastrowid or 0

    def get_pr(self, pr_id: int, repo_name: Optional[str] = None) -> Optional[PRShieldContext]:
        """Retrieves a PR by ID and optional repo_name."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if repo_name:
                cursor.execute("SELECT raw_json FROM pr_records WHERE pr_id = ? AND repo_name = ?", (pr_id, repo_name))
            else:
                cursor.execute("SELECT raw_json FROM pr_records WHERE pr_id = ? ORDER BY id DESC LIMIT 1", (pr_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return PRShieldContext.model_validate_json(row["raw_json"])

    def get_pr_by_url(self, pr_url: str) -> Optional[PRShieldContext]:
        """Retrieves a PR by URL."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT raw_json FROM pr_records WHERE pr_url = ?", (pr_url,))
            row = cursor.fetchone()
            if not row:
                return None
            return PRShieldContext.model_validate_json(row["raw_json"])

    def list_prs(self, limit: int = 50, verdict_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lists PR records with metadata summaries for inbox view."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT pr_id, repo_name, pr_url, author, title, quick_check_score,
                       quick_check_flags, ci_status, ai_verdict, ai_reason,
                       ai_suspicious_injection, maintainer_decision, created_at, updated_at
                FROM pr_records
            """
            params: List[Any] = []
            if verdict_filter:
                query += " WHERE ai_verdict = ?"
                params.append(verdict_filter)

            query += " ORDER BY id DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()

            result = []
            for r in rows:
                item = dict(r)
                item["quick_check_flags"] = json.loads(item.get("quick_check_flags") or "[]")
                result.append(item)
            return result

    def record_action(
        self,
        pr_id: int,
        repo_name: str,
        action_type: str,
        comment_body: Optional[str] = None,
        labels: Optional[List[str]] = None,
        success: bool = True,
    ) -> int:
        """Logs an action dispatched to GitHub by the maintainer."""
        labels_str = json.dumps(labels or [])
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO triage_actions (pr_id, repo_name, action_type, comment_body, labels, success)
                VALUES (?, ?, ?, ?, ?, ?);
            """, (pr_id, repo_name, action_type, comment_body, labels_str, 1 if success else 0))
            conn.commit()
            return cursor.lastrowid or 0

    def get_action_history(self, pr_id: int, repo_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieves action history for a PR."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if repo_name:
                cursor.execute(
                    "SELECT * FROM triage_actions WHERE pr_id = ? AND repo_name = ? ORDER BY dispatched_at DESC",
                    (pr_id, repo_name)
                )
            else:
                cursor.execute(
                    "SELECT * FROM triage_actions WHERE pr_id = ? ORDER BY dispatched_at DESC",
                    (pr_id,)
                )
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
