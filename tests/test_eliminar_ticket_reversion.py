"""Reversión financiera y exclusión de tickets eliminados por super_admin."""
from __future__ import annotations

import time


def _session_super(client):
    with client.session_transaction() as sess:
        sess["u"] = "super_test"
        sess["uid"] = 99
        sess["role"] = "super_admin"
        sess["last_activity"] = time.time()
        sess["last_activity_touch"] = time.time()


def test_eliminar_ticket_revierte_y_excluye_de_ventas(app_mod, client):
    app = app_mod
    c = app.db()
    cur = c.cursor()
    # cajero user
    try:
        cur.execute(
            app._sql(
                "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)"
            ),
            ("awilda_test", "x", "cajero"),
        )
    except Exception:
        pass
    cur.execute(app._sql("SELECT id FROM users WHERE username = %s"), ("awilda_test",))
    urow = cur.fetchone()
    cid = int(urow["id"] if hasattr(urow, "keys") else urow[0])

    cur.execute(
        app._sql(
            """
            INSERT INTO tickets (cajero, cajero_id, created_at, pagado, monto, eliminado)
            VALUES ('awilda_test', %s, '2026-07-12 15:00:00', 0, 2725, 0)
            """
        ),
        (cid,),
    )
    tid = cur.lastrowid
    cur.execute(
        app._sql(
            """
            INSERT INTO ticket_lines (ticket_id, lottery, draw, number, play, amount, fecha_sorteo, estado)
            VALUES (%s, 'La Primera', '12:00 PM', '11', 'Quiniela', 2725, '2026-07-12', 'activo')
            """
        ),
        (tid,),
    )
    # movimiento de venta en banco
    app.banco_registrar_venta(cur, tid, cid, 2725.0, descripcion="venta test")
    bal_antes = app.banco_get_balance_general(cur)
    c.commit()
    c.close()

    _session_super(client)
    r = client.post(
        "/api/super_admin/eliminar_ticket",
        json={"ticket_id": tid, "motivo": "test reversion"},
    )
    assert r.status_code == 200
    assert r.get_json().get("ok") is True

    c2 = app.db()
    cur2 = c2.cursor()
    cur2.execute(app._sql("SELECT eliminado, monto FROM tickets WHERE id = %s"), (tid,))
    row = cur2.fetchone()
    elim = int((row["eliminado"] if hasattr(row, "keys") else row[0]) or 0)
    monto = float((row["monto"] if hasattr(row, "keys") else row[1]) or 0)
    assert elim == 1
    assert monto == 0

    cur2.execute(
        app._sql(
            """
            SELECT COALESCE(SUM(t.monto), 0) AS s
            FROM tickets t
            WHERE lower(trim(t.cajero)) = 'awilda_test'
              AND COALESCE(t.monto, 0) > 0
            """
            + app._sql_ticket_no_eliminado("t")
        )
    )
    srow = cur2.fetchone()
    s = float((srow["s"] if hasattr(srow, "keys") else srow[0]) or 0)
    assert s == 0.0

    bal_despues = app.banco_get_balance_general(cur2)
    assert round(bal_antes - bal_despues, 2) == 2725.0

    # Idempotente: segunda llamada no vuelve a restar
    c2.close()
    r2 = client.post(
        "/api/super_admin/eliminar_ticket",
        json={"ticket_id": tid, "motivo": "repair"},
    )
    assert r2.status_code == 200
    c3 = app.db()
    bal_final = app.banco_get_balance_general(c3.cursor())
    c3.close()
    assert round(bal_despues, 2) == round(bal_final, 2)


def test_repair_soft_delete_sin_reversion_previa(app_mod, client):
    """Ticket ya eliminado=1 con monto>0 y sin anulación bancaria: completa reversión."""
    app = app_mod
    c = app.db()
    cur = c.cursor()
    try:
        cur.execute(
            app._sql(
                "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)"
            ),
            ("awilda2", "x", "cajero"),
        )
    except Exception:
        pass
    cur.execute(app._sql("SELECT id FROM users WHERE username = %s"), ("awilda2",))
    urow = cur.fetchone()
    cid = int(urow["id"] if hasattr(urow, "keys") else urow[0])

    cur.execute(
        app._sql(
            """
            INSERT INTO tickets (cajero, cajero_id, created_at, pagado, monto, eliminado)
            VALUES ('awilda2', %s, '2026-07-12 16:00:00', 0, 2725, 1)
            """
        ),
        (cid,),
    )
    tid = cur.lastrowid
    cur.execute(
        app._sql(
            """
            INSERT INTO tickets_eliminados
                (ticket_id, eliminado_por, motivo, fecha_eliminacion, monto_ticket, serial_ticket)
            VALUES (%s, 'super_test', 'parcial', '2026-07-12 16:01:00', 2725, %s)
            """
        ),
        (tid, str(tid)),
    )
    app.banco_registrar_venta(cur, tid, cid, 2725.0, descripcion="venta orphan")
    bal_antes = app.banco_get_balance_general(cur)
    c.commit()
    c.close()

    _session_super(client)
    r = client.post(
        "/api/super_admin/eliminar_ticket",
        json={"ticket_id": tid, "motivo": "completar"},
    )
    assert r.status_code == 200
    assert r.get_json().get("ok") is True

    c2 = app.db()
    cur2 = c2.cursor()
    cur2.execute(app._sql("SELECT monto FROM tickets WHERE id = %s"), (tid,))
    m = cur2.fetchone()
    assert float((m["monto"] if hasattr(m, "keys") else m[0]) or 0) == 0
    bal_despues = app.banco_get_balance_general(cur2)
    c2.close()
    assert round(bal_antes - bal_despues, 2) == 2725.0
