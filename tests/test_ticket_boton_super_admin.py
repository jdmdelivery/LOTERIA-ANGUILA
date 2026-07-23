"""Botón Eliminar (Super Admin) visible en /ticket/<id>."""
from __future__ import annotations

import time


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
        sess["uid"] = 201
        sess["role"] = "admin"
        sess["last_activity"] = time.time()
        sess["last_activity_touch"] = time.time()


def _seed(app, cur):
    cur.execute(
        app._sql(
            """
            INSERT INTO users (id, username, password_hash, role, is_approved, is_blocked, pago_activo)
            VALUES (201, 'admin_test', 'x', 'admin', 1, 0, 1)
            """
        )
    )
    cur.execute(
        app._sql(
            """
            INSERT INTO users (id, username, password_hash, role, created_by, is_approved, is_blocked, pago_activo)
            VALUES (202, 'cajero_a', 'x', 'cajero', 201, 1, 0, 1)
            """
        )
    )
    cur.execute(
        app._sql(
            """
            INSERT INTO tickets (cajero, cajero_id, created_at, pagado, monto, eliminado)
            VALUES ('cajero_a', 202, '2026-07-12 11:00:00', 0, 25, 0)
            """
        )
    )
    return cur.lastrowid


def test_ticket_muestra_boton_eliminar_solo_super_admin(app_mod, client):
    app = app_mod
    c = app.db()
    cur = c.cursor()
    tid = _seed(app, cur)
    c.commit()
    c.close()

    _session_super(client)
    r = client.get(f"/ticket/{tid}")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "Eliminar (Super Admin)" in body
    assert "btnEliminarSuperAdmin" in body
    assert "/api/super_admin/eliminar_ticket" in body
    # Modal HTML (WebView a menudo no muestra diálogos JS nativos)
    assert "ticketElimOverlay" in body
    assert "ticketElimOk" in body
    assert "btn.addEventListener(\"click\", function(){ openModal(); });" in body
    assert "window.prompt(" not in body

    _session_admin(client)
    r2 = client.get(f"/ticket/{tid}")
    assert r2.status_code == 200
    body2 = r2.get_data(as_text=True)
    assert "Eliminar (Super Admin)" not in body2
    assert "ticketElimOverlay" not in body2
