"""SQLite persistence for the local single-workspace application."""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


DEFAULT_ASSUMPTIONS = {
    "starting_units": ("0", "volume", "units", "Starting monthly unit volume"),
    "monthly_unit_growth": ("0", "revenue", "fraction", "Monthly volume growth"),
    "unit_price": ("0", "revenue", "currency/unit", "Average selling price"),
    "variable_cost_per_unit": ("0", "costs", "currency/unit", "Variable cost per unit"),
    "fixed_opex": ("0", "costs", "currency/month", "Monthly fixed operating expenses"),
    "payroll": ("0", "people", "currency/month", "Monthly payroll and benefits"),
    "depreciation": ("0", "costs", "currency/month", "Monthly depreciation and amortization"),
    "interest_expense": ("0", "financing", "currency/month", "Monthly interest expense"),
    "tax_rate": ("0.25", "tax", "fraction", "Effective tax rate on positive pre-tax income"),
    "opening_cash": ("0", "cash", "currency", "Opening cash balance"),
    "minimum_cash": ("0", "cash", "currency", "Minimum cash reserve"),
    "collection_rate": ("1", "cash", "fraction", "Same-period cash collection proportion"),
    "payment_rate": ("1", "cash", "fraction", "Same-period operating payment proportion"),
    "monthly_capex": ("0", "cash", "currency/month", "Monthly capital expenditure"),
    "monthly_debt_proceeds": ("0", "cash", "currency/month", "Monthly debt proceeds"),
    "monthly_debt_repayment": ("0", "cash", "currency/month", "Monthly debt principal repayments"),
    "monthly_equity_contribution": ("0", "cash", "currency/month", "Monthly equity contributions"),
}

ASSUMPTION_LABELS = {
    key: definition[3] for key, definition in DEFAULT_ASSUMPTIONS.items()
}


class WorkspaceConflict(Exception):
    """Raised when a workspace already exists or a record conflicts."""


class Store:
    def __init__(self, path: Optional[str] = None) -> None:
        configured = path or os.environ.get(
            "ABHIVESTRA_DB",
            str(Path(__file__).resolve().parent.parent / "data" / "abhivestra.sqlite3"),
        )
        self.path = Path(configured)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.path), timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    @contextmanager
    def connection(self):
        connection = self.connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS workspace (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    company_name TEXT NOT NULL,
                    currency TEXT NOT NULL,
                    start_period TEXT NOT NULL,
                    horizon INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS assumption (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    category TEXT NOT NULL,
                    unit TEXT NOT NULL,
                    label TEXT NOT NULL,
                    source TEXT NOT NULL,
                    rationale TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS scenario (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS scenario_override (
                    scenario_id INTEGER NOT NULL REFERENCES scenario(id) ON DELETE CASCADE,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (scenario_id, key)
                );
                CREATE TABLE IF NOT EXISTS investment (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    initial_investment TEXT NOT NULL,
                    annual_cash_flow TEXT NOT NULL,
                    years INTEGER NOT NULL,
                    discount_rate TEXT NOT NULL,
                    residual_value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit_event (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entity TEXT NOT NULL,
                    entity_key TEXT NOT NULL,
                    old_value TEXT,
                    new_value TEXT,
                    reason TEXT NOT NULL,
                    occurred_at TEXT NOT NULL
                );
                """
            )

    @staticmethod
    def timestamp() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def get_workspace(self) -> Optional[Dict[str, Any]]:
        with self.connection() as connection:
            workspace = connection.execute("SELECT * FROM workspace WHERE id = 1").fetchone()
            if workspace is None:
                return None
            assumptions = connection.execute(
                "SELECT * FROM assumption ORDER BY category, key"
            ).fetchall()
            scenarios = connection.execute(
                "SELECT id, name, created_at FROM scenario ORDER BY id"
            ).fetchall()
            result = dict(workspace)
            result["assumptions"] = {row["key"]: dict(row) for row in assumptions}
            result["scenarios"] = []
            for scenario in scenarios:
                item = dict(scenario)
                overrides = connection.execute(
                    "SELECT key, value FROM scenario_override WHERE scenario_id = ?",
                    (scenario["id"],),
                ).fetchall()
                item["overrides"] = {row["key"]: row["value"] for row in overrides}
                result["scenarios"].append(item)
            investment = connection.execute(
                "SELECT * FROM investment WHERE id = 1"
            ).fetchone()
            result["investment"] = dict(investment) if investment else None
            return result

    def create_workspace(
        self,
        company_name: str,
        currency: str,
        start_period: str,
        horizon: int,
        assumptions: Dict[str, Any],
        base_scenario_name: str = "Base Case",
    ) -> None:
        now = self.timestamp()
        try:
            with self.connection() as connection:
                if connection.execute("SELECT id FROM workspace WHERE id = 1").fetchone():
                    raise WorkspaceConflict("A workspace already exists in this local database.")
                connection.execute(
                    "INSERT INTO workspace VALUES (1, ?, ?, ?, ?, ?)",
                    (company_name, currency, start_period, horizon, now),
                )
                for key, definition in DEFAULT_ASSUMPTIONS.items():
                    value = str(assumptions.get(key, definition[0]))
                    source = str(assumptions.get(key + "_source", "user input"))
                    rationale = str(assumptions.get(key + "_rationale", ""))
                    connection.execute(
                        """INSERT INTO assumption
                        (key, value, category, unit, label, source, rationale, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (key, value, definition[1], definition[2], definition[3], source, rationale, now),
                    )
                connection.execute(
                    "INSERT INTO scenario(name, created_at) VALUES (?, ?)",
                    (base_scenario_name, now),
                )
        except sqlite3.IntegrityError as error:
            if "UNIQUE" in str(error).upper():
                raise WorkspaceConflict("A workspace or scenario with that name already exists.")
            raise

    def update_assumption(self, key: str, value: str, reason: str) -> None:
        now = self.timestamp()
        with self.connection() as connection:
            row = connection.execute(
                "SELECT value FROM assumption WHERE key = ?", (key,)
            ).fetchone()
            if row is None:
                raise KeyError("Unknown assumption.")
            connection.execute(
                "UPDATE assumption SET value = ?, rationale = ?, updated_at = ? WHERE key = ?",
                (value, reason, now, key),
            )
            connection.execute(
                """INSERT INTO audit_event(entity, entity_key, old_value, new_value, reason, occurred_at)
                VALUES ('assumption', ?, ?, ?, ?, ?)""",
                (key, row["value"], value, reason, now),
            )

    def create_scenario(self, name: str) -> int:
        try:
            with self.connection() as connection:
                cursor = connection.execute(
                    "INSERT INTO scenario(name, created_at) VALUES (?, ?)",
                    (name, self.timestamp()),
                )
                return int(cursor.lastrowid)
        except sqlite3.IntegrityError as error:
            if "UNIQUE" in str(error).upper():
                raise WorkspaceConflict("A scenario with that name already exists.")
            raise

    def update_scenario_override(
        self, scenario_id: int, key: str, value: str, reason: str
    ) -> None:
        now = self.timestamp()
        with self.connection() as connection:
            scenario = connection.execute(
                "SELECT id FROM scenario WHERE id = ?", (scenario_id,)
            ).fetchone()
            if scenario is None:
                raise KeyError("Scenario not found.")
            existing = connection.execute(
                "SELECT value FROM scenario_override WHERE scenario_id = ? AND key = ?",
                (scenario_id, key),
            ).fetchone()
            connection.execute(
                """INSERT INTO scenario_override(scenario_id, key, value, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(scenario_id, key) DO UPDATE SET
                value = excluded.value, updated_at = excluded.updated_at""",
                (scenario_id, key, value, now),
            )
            connection.execute(
                """INSERT INTO audit_event(entity, entity_key, old_value, new_value, reason, occurred_at)
                VALUES ('scenario_override', ?, ?, ?, ?, ?)""",
                (
                    "%d:%s" % (scenario_id, key),
                    existing["value"] if existing else None,
                    value,
                    reason,
                    now,
                ),
            )

    def save_investment(
        self,
        initial_investment: str,
        annual_cash_flow: str,
        years: int,
        discount_rate: str,
        residual_value: str,
    ) -> None:
        now = self.timestamp()
        with self.connection() as connection:
            previous = connection.execute("SELECT * FROM investment WHERE id = 1").fetchone()
            new_data = {
                "initial_investment": initial_investment,
                "annual_cash_flow": annual_cash_flow,
                "years": years,
                "discount_rate": discount_rate,
                "residual_value": residual_value,
            }
            connection.execute(
                """INSERT INTO investment VALUES (1, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                initial_investment = excluded.initial_investment,
                annual_cash_flow = excluded.annual_cash_flow,
                years = excluded.years,
                discount_rate = excluded.discount_rate,
                residual_value = excluded.residual_value,
                updated_at = excluded.updated_at""",
                (
                    initial_investment,
                    annual_cash_flow,
                    years,
                    discount_rate,
                    residual_value,
                    now,
                ),
            )
            connection.execute(
                """INSERT INTO audit_event(entity, entity_key, old_value, new_value, reason, occurred_at)
                VALUES ('investment', 'project', ?, ?, 'Investment assumptions updated', ?)""",
                (
                    json.dumps(dict(previous)) if previous else None,
                    json.dumps(new_data, sort_keys=True),
                    now,
                ),
            )

    def list_audit_events(self, limit: int = 100) -> list:
        with self.connection() as connection:
            rows = connection.execute(
                """SELECT entity, entity_key, old_value, new_value, reason, occurred_at
                FROM audit_event ORDER BY id DESC LIMIT ?""",
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]
