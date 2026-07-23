"""Eliminación forzada de ticket solo por super_admin."""
from __future__ import annotations

import time

FECHA = "2026-07-06"


def _session_super(client):
    with client.session_transaction() as sess:
        sess["u"] = "super_test"
        sess["uid"] = 99
        sess["role"] = "super_admin"
        sess["last_activity"] = time.time()
        sess["last_activity_touch"] = time.time()


def _session_admin(client):
    with client.session_transaction() as sess:
        sess["u"] = "admin_test"
        sess["uid"] = 1
        sess["role"] = "admin"
        sess["last_activity"] = time.time()
        sess["last_activity_touch"] = time.time()


def _seed_ticket(app, cur, *, monto=80.0):
    cur.execute(
        app._sql(
            """
            INSERT INTO tickets (cajero, created_at, pagado, monto, ticket_group, eliminado)
            VALUES ('cajero_test', %s, 0, %s, %s, 0)
            """
        ),
        (f"{FECHA} 10:00:00", monto, 900001),
    )
    tid = cur.lastrowid
    cur.execute(
        app._sql(
            """
            INSERT INTO ticket_lines (ticket_id, lottery, draw, number, play, amount, fecha_sorteo, estado)
            VALUES (%s, 'La Primera', '12:00 PM', '22', 'Quiniela', %s, %s, 'activo')
            """
        ),
        (tid, monto, FECHA),
    )
    return tid


def test_api_eliminar_ticket_super_admin_403_admin(app_mod, client):
    app = app_mod
    c = app.db()
    cur = c.cursor()
    tid = _seed_ticket(app, cur)
    c.commit()
    c.close()

    _session_admin(client)
    r = client.post(
        "/api/super_admin/eliminar_ticket",
        json={"ticket_id": tid, "motivo": "prueba"},
    )
    assert r.status_code == 403
    assert r.get_json().get("ok") is False


def test_api_eliminar_ticket_super_admin_ok(app_mod, client):
    app = app_mod
    c = app.db()
    cur = c.cursor()
    tid = _seed_ticket(app, cur)
    c.commit()
    c.close()

    _session_super(client)
    r = client.post(
        "/api/super_admin/eliminar_ticket",
        json={"ticket_id": tid, "motivo": "reversión completa"},
    )
    assert r.status_code == 200
    data = r.get_json()
    assert data.get("ok") is True
    assert "Caja y Banco Global actualizados" in (data.get("message") or "")

    c2 = app.db()
    cur2 = c2.cursor()
    cur2.execute(app._sql("SELECT eliminado, monto FROM tickets WHERE id = %s"), (tid,))
    row = cur2.fetchone()
    assert int((row["eliminado"] if hasattr(row, "keys") else row[0]) or 0) == 1
    cur2.execute(
        app._sql("SELECT estado FROM ticket_lines WHERE ticket_id = %s"),
        (tid,),
    )
    line = cur2.fetchone()
    estado = line["estado"] if hasattr(line, "keys") else line[0]
    assert str(estado) == "cancelado"
    cur2.execute(
        app._sql("SELECT COUNT(*) AS n FROM tickets_eliminados WHERE ticket_id = %s"),
        (tid,),
    )
    n = cur2.fetchone()
    assert int((n["n"] if hasattr(n, "keys") else n[0]) or 0) >= 1
    c2.close()
