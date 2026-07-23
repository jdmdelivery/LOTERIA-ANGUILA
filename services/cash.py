# -*- coding: utf-8 -*-
"""Movimientos de caja: venta suma; pago de premio descuenta solo al confirmar."""
from __future__ import annotations

import database as db


def add_sale(cash_register_id: int, amount: float, ticket_id: int, user_id: int) -> None:
    with db.get_conn() as conn:
        db._exec(
            conn,
            "UPDATE cash_registers SET balance = balance + ? WHERE id=?",
            (float(amount), cash_register_id),
        )
        db._exec(
            conn,
            """INSERT INTO cash_movements
            (cash_register_id, kind, amount, ticket_id, payment_id, user_id, created_at, note)
            VALUES (?,?,?,?,NULL,?,?,?)""",
            (cash_register_id, "VENTA", float(amount), ticket_id, user_id, db.now_iso(), "venta ticket"),
        )


def pay_prize(
    cash_register_id: int,
    amount: float,
    ticket_id: int,
    payment_id: int,
    user_id: int,
) -> None:
    """Descuenta caja únicamente cuando el premio se paga físicamente."""
    with db.get_conn() as conn:
        db._exec(
            conn,
            "UPDATE cash_registers SET balance = balance - ? WHERE id=?",
            (float(amount), cash_register_id),
        )
        db._exec(
            conn,
            """INSERT INTO cash_movements
            (cash_register_id, kind, amount, ticket_id, payment_id, user_id, created_at, note)
            VALUES (?,?,?,?,?,?,?,?)""",
            (
                cash_register_id,
                "PAGO_PREMIO",
                -float(amount),
                ticket_id,
                payment_id,
                user_id,
                db.now_iso(),
                "pago premio",
            ),
        )


def get_balance(cash_register_id: int) -> float:
    with db.get_conn() as conn:
        row = db._fetchone(conn, "SELECT balance FROM cash_registers WHERE id=?", (cash_register_id,))
        return float(row["balance"]) if row else 0.0
