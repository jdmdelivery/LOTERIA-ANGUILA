# -*- coding: utf-8 -*-
"""Base de datos JDM Anguila (SQLite local / PostgreSQL en Render)."""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator, Optional
from urllib.parse import urlparse

from werkzeug.security import generate_password_hash

import config

_pg = None
if config.DATABASE_URL:
    try:
        import psycopg2
        import psycopg2.extras

        _pg = psycopg2
    except ImportError:
        _pg = None


def _is_postgres() -> bool:
    return bool(config.DATABASE_URL and _pg is not None)


def _pg_dsn() -> str:
    url = config.DATABASE_URL
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    return url


class _SQLiteRow(sqlite3.Row):
    pass


def _dict_factory(cursor, row):
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


@contextmanager
def get_conn() -> Iterator[Any]:
    if _is_postgres():
        conn = _pg.connect(_pg_dsn())
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    else:
        os.makedirs(os.path.dirname(config.SQLITE_PATH) or ".", exist_ok=True)
        conn = sqlite3.connect(config.SQLITE_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def _exec(conn, sql: str, params: tuple = ()):
    if _is_postgres():
        sql = sql.replace("?", "%s")
        cur = conn.cursor()
        cur.execute(sql, params)
        return cur
    return conn.execute(sql, params)


def _fetchone(conn, sql: str, params: tuple = ()) -> Optional[dict]:
    cur = _exec(conn, sql, params)
    row = cur.fetchone()
    if row is None:
        return None
    if _is_postgres():
        cols = [d[0] for d in cur.description]
        return dict(zip(cols, row))
    return dict(row)


def _fetchall(conn, sql: str, params: tuple = ()) -> list[dict]:
    cur = _exec(conn, sql, params)
    rows = cur.fetchall()
    if _is_postgres():
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in rows]
    return [dict(r) for r in rows]


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def init_db() -> None:
    ddl_sqlite = """
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT UNIQUE NOT NULL,
      password_hash TEXT NOT NULL,
      role TEXT NOT NULL,
      active INTEGER NOT NULL DEFAULT 1,
      created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS branches (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      address TEXT,
      phone TEXT
    );
    CREATE TABLE IF NOT EXISTS cash_registers (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      branch_id INTEGER NOT NULL,
      name TEXT NOT NULL,
      balance REAL NOT NULL DEFAULT 0,
      FOREIGN KEY(branch_id) REFERENCES branches(id)
    );
    CREATE TABLE IF NOT EXISTS tickets (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      public_number TEXT UNIQUE NOT NULL,
      security_code TEXT UNIQUE NOT NULL,
      branch_id INTEGER NOT NULL,
      cash_register_id INTEGER NOT NULL,
      cashier_id INTEGER NOT NULL,
      sold_at TEXT NOT NULL,
      draw_date TEXT NOT NULL,
      sorteo_code TEXT NOT NULL,
      status TEXT NOT NULL,
      total REAL NOT NULL,
      reprint_count INTEGER NOT NULL DEFAULT 0,
      ip TEXT,
      FOREIGN KEY(branch_id) REFERENCES branches(id),
      FOREIGN KEY(cash_register_id) REFERENCES cash_registers(id),
      FOREIGN KEY(cashier_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS ticket_lines (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      ticket_id INTEGER NOT NULL,
      modality TEXT NOT NULL,
      numbers TEXT NOT NULL,
      amount REAL NOT NULL,
      snapshot_json TEXT NOT NULL,
      prize_amount REAL NOT NULL DEFAULT 0,
      prize_status TEXT NOT NULL DEFAULT 'NONE',
      processed_winner INTEGER NOT NULL DEFAULT 0,
      prize_detail_json TEXT,
      FOREIGN KEY(ticket_id) REFERENCES tickets(id)
    );
    CREATE TABLE IF NOT EXISTS draw_results (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      sorteo_code TEXT NOT NULL,
      draw_date TEXT NOT NULL,
      primera TEXT,
      segunda TEXT,
      tercera TEXT,
      status TEXT NOT NULL,
      source TEXT,
      response_hash TEXT,
      first_read_json TEXT,
      second_read_json TEXT,
      confirmed_at TEXT,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      UNIQUE(sorteo_code, draw_date)
    );
    CREATE TABLE IF NOT EXISTS prize_payments (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      payment_uid TEXT UNIQUE NOT NULL,
      ticket_id INTEGER NOT NULL,
      user_id INTEGER NOT NULL,
      cash_register_id INTEGER NOT NULL,
      branch_id INTEGER NOT NULL,
      amount REAL NOT NULL,
      paid_at TEXT NOT NULL,
      observation TEXT,
      ip TEXT,
      result_snapshot_json TEXT,
      receipt_json TEXT,
      FOREIGN KEY(ticket_id) REFERENCES tickets(id)
    );
    CREATE TABLE IF NOT EXISTS reprint_audit (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      ticket_id INTEGER NOT NULL,
      user_id INTEGER NOT NULL,
      reason TEXT,
      created_at TEXT NOT NULL,
      ip TEXT,
      kind TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS collector_health (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      sorteo_code TEXT UNIQUE NOT NULL,
      last_run_at TEXT,
      status TEXT,
      last_error TEXT,
      response_hash TEXT
    );
    CREATE TABLE IF NOT EXISTS admin_notifications (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      level TEXT NOT NULL,
      message TEXT NOT NULL,
      created_at TEXT NOT NULL,
      read_flag INTEGER NOT NULL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS cash_movements (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      cash_register_id INTEGER NOT NULL,
      kind TEXT NOT NULL,
      amount REAL NOT NULL,
      ticket_id INTEGER,
      payment_id INTEGER,
      user_id INTEGER,
      created_at TEXT NOT NULL,
      note TEXT
    );
    CREATE TABLE IF NOT EXISTS collector_locks (
      sorteo_code TEXT NOT NULL,
      draw_date TEXT NOT NULL,
      locked_at TEXT NOT NULL,
      PRIMARY KEY (sorteo_code, draw_date)
    );
    """
    with get_conn() as conn:
        if _is_postgres():
            _init_postgres(conn)
        else:
            conn.executescript(ddl_sqlite)
        _seed(conn)


def _init_postgres(conn) -> None:
    stmts = [
        """CREATE TABLE IF NOT EXISTS users (
          id SERIAL PRIMARY KEY,
          username TEXT UNIQUE NOT NULL,
          password_hash TEXT NOT NULL,
          role TEXT NOT NULL,
          active INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS branches (
          id SERIAL PRIMARY KEY,
          name TEXT NOT NULL,
          address TEXT,
          phone TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS cash_registers (
          id SERIAL PRIMARY KEY,
          branch_id INTEGER NOT NULL REFERENCES branches(id),
          name TEXT NOT NULL,
          balance DOUBLE PRECISION NOT NULL DEFAULT 0
        )""",
        """CREATE TABLE IF NOT EXISTS tickets (
          id SERIAL PRIMARY KEY,
          public_number TEXT UNIQUE NOT NULL,
          security_code TEXT UNIQUE NOT NULL,
          branch_id INTEGER NOT NULL,
          cash_register_id INTEGER NOT NULL,
          cashier_id INTEGER NOT NULL,
          sold_at TEXT NOT NULL,
          draw_date TEXT NOT NULL,
          sorteo_code TEXT NOT NULL,
          status TEXT NOT NULL,
          total DOUBLE PRECISION NOT NULL,
          reprint_count INTEGER NOT NULL DEFAULT 0,
          ip TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS ticket_lines (
          id SERIAL PRIMARY KEY,
          ticket_id INTEGER NOT NULL REFERENCES tickets(id),
          modality TEXT NOT NULL,
          numbers TEXT NOT NULL,
          amount DOUBLE PRECISION NOT NULL,
          snapshot_json TEXT NOT NULL,
          prize_amount DOUBLE PRECISION NOT NULL DEFAULT 0,
          prize_status TEXT NOT NULL DEFAULT 'NONE',
          processed_winner INTEGER NOT NULL DEFAULT 0,
          prize_detail_json TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS draw_results (
          id SERIAL PRIMARY KEY,
          sorteo_code TEXT NOT NULL,
          draw_date TEXT NOT NULL,
          primera TEXT,
          segunda TEXT,
          tercera TEXT,
          status TEXT NOT NULL,
          source TEXT,
          response_hash TEXT,
          first_read_json TEXT,
          second_read_json TEXT,
          confirmed_at TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          UNIQUE(sorteo_code, draw_date)
        )""",
        """CREATE TABLE IF NOT EXISTS prize_payments (
          id SERIAL PRIMARY KEY,
          payment_uid TEXT UNIQUE NOT NULL,
          ticket_id INTEGER NOT NULL,
          user_id INTEGER NOT NULL,
          cash_register_id INTEGER NOT NULL,
          branch_id INTEGER NOT NULL,
          amount DOUBLE PRECISION NOT NULL,
          paid_at TEXT NOT NULL,
          observation TEXT,
          ip TEXT,
          result_snapshot_json TEXT,
          receipt_json TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS reprint_audit (
          id SERIAL PRIMARY KEY,
          ticket_id INTEGER NOT NULL,
          user_id INTEGER NOT NULL,
          reason TEXT,
          created_at TEXT NOT NULL,
          ip TEXT,
          kind TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS collector_health (
          id SERIAL PRIMARY KEY,
          sorteo_code TEXT UNIQUE NOT NULL,
          last_run_at TEXT,
          status TEXT,
          last_error TEXT,
          response_hash TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS admin_notifications (
          id SERIAL PRIMARY KEY,
          level TEXT NOT NULL,
          message TEXT NOT NULL,
          created_at TEXT NOT NULL,
          read_flag INTEGER NOT NULL DEFAULT 0
        )""",
        """CREATE TABLE IF NOT EXISTS cash_movements (
          id SERIAL PRIMARY KEY,
          cash_register_id INTEGER NOT NULL,
          kind TEXT NOT NULL,
          amount DOUBLE PRECISION NOT NULL,
          ticket_id INTEGER,
          payment_id INTEGER,
          user_id INTEGER,
          created_at TEXT NOT NULL,
          note TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS collector_locks (
          sorteo_code TEXT NOT NULL,
          draw_date TEXT NOT NULL,
          locked_at TEXT NOT NULL,
          PRIMARY KEY (sorteo_code, draw_date)
        )""",
    ]
    cur = conn.cursor()
    for s in stmts:
        cur.execute(s)


def _seed(conn) -> None:
    u = _fetchone(conn, "SELECT id FROM users WHERE username = ?", (config.ADMIN_USER,))
    if not u:
        _exec(
            conn,
            "INSERT INTO users (username, password_hash, role, active, created_at) VALUES (?,?,?,?,?)",
            (
                config.ADMIN_USER,
                generate_password_hash(config.ADMIN_PASSWORD),
                "admin",
                1,
                now_iso(),
            ),
        )
    c = _fetchone(conn, "SELECT id FROM users WHERE username = ?", (config.CAJERO_USER,))
    if not c:
        _exec(
            conn,
            "INSERT INTO users (username, password_hash, role, active, created_at) VALUES (?,?,?,?,?)",
            (
                config.CAJERO_USER,
                generate_password_hash(config.CAJERO_PASSWORD),
                "cajero",
                1,
                now_iso(),
            ),
        )
    b = _fetchone(conn, "SELECT id FROM branches LIMIT 1")
    if not b:
        _exec(
            conn,
            "INSERT INTO branches (name, address, phone) VALUES (?,?,?)",
            ("Principal", config.BANK_ADDRESS, config.BANK_PHONE),
        )
        b = _fetchone(conn, "SELECT id FROM branches LIMIT 1")
        _exec(
            conn,
            "INSERT INTO cash_registers (branch_id, name, balance) VALUES (?,?,?)",
            (b["id"], "Caja 1", 0),
        )


def notify_admin(level: str, message: str) -> None:
    with get_conn() as conn:
        _exec(
            conn,
            "INSERT INTO admin_notifications (level, message, created_at, read_flag) VALUES (?,?,?,0)",
            (level, message, now_iso()),
        )


def json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def json_loads(s: Optional[str], default=None):
    if not s:
        return default
    return json.loads(s)
