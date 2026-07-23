"""Regresión: helpers de pagos no deben borrar un ticket a mitad de la venta."""
from __future__ import annotations


def test_ensure_pagos_schema_no_borra_ticket_insertado(app_mod):
    app = app_mod
    c = app.db()
    cur = c.cursor()
    cur.execute(
        app._sql(
            "INSERT INTO tickets (cajero, cajero_id, banca_id, monto) VALUES (%s,%s,%s,%s)"
        ),
        ("vendedor", 1, 1, 100),
    )
    tid = cur.lastrowid
    # Columna ya existe tras init_db; ensure no debe hacer rollback de la venta.
    app._ensure_pagos_banquera_schema(cur)
    app._ensure_pagos_banquera_schema(cur)
    cur.execute(app._sql("SELECT id, monto FROM tickets WHERE id=%s"), (tid,))
    row = cur.fetchone()
    c.commit()
    c.close()
    assert row is not None
    mid = row["id"] if hasattr(row, "keys") else row[0]
    assert int(mid) == int(tid)


def test_ticket_lines_tiene_pagos_json(app_mod):
    app = app_mod
    c = app.db()
    cur = c.cursor()
    assert app._ticket_lines_tiene_columna(cur, "pagos_json") is True
    assert app._ticket_lines_tiene_columna(cur, "no_existe_xyz") is False
    c.close()


def test_pagos_helpers_despues_insert_no_borran_ticket(app_mod):
    """
    El bug de producción: INSERT ticket → helpers de pagos con ROLLBACK total →
    redirect a /ticket/<id> → «Ticket no encontrado».
    """
    app = app_mod
    c = app.db()
    cur = c.cursor()
    cur.execute(
        app._sql(
            "INSERT INTO tickets (cajero, cajero_id, banca_id, monto) VALUES (%s,%s,%s,%s)"
        ),
        ("vendedor", 1, 1, 50),
    )
    tid = cur.lastrowid
    # Simula el orden antiguo (después del INSERT) y el nuevo (helpers con SAVEPOINT).
    app._ensure_pagos_banquera_schema(cur)
    snap = app._pagos_snapshot_json(app._pagos_efectivos_para_vendedor(cur, 1))
    assert snap and "quiniela_1" in snap
    _ = app._load_pagos_config_banca(cur, 1)
    _ = app._admin_dueno_id_para_pagos(cur, 1)
    _ = app._ganadores_try_load_pagos_config(cur)
    cur.execute(app._sql("SELECT id FROM tickets WHERE id=%s"), (tid,))
    row = cur.fetchone()
    c.commit()
    c.close()
    assert row is not None
    mid = row["id"] if hasattr(row, "keys") else row[0]
    assert int(mid) == int(tid)
