"""Acceso a /ticket/<id> y enlace Revisar ticket en ganadores por rol."""
from __future__ import annotations

import time


def _session(client, *, uid, user, role):
    with client.session_transaction() as sess:
        sess["u"] = user
        sess["uid"] = uid
        sess["role"] = role
        sess["last_activity"] = time.time()
        sess["last_activity_touch"] = time.time()


def _seed_users_and_ticket(app, cur, *, admin_id=101, cajero_id=102, cajero_name="gris"):
    cur.execute(
        app._sql(
            """
            INSERT INTO users (id, username, password_hash, role, is_approved, is_blocked, pago_activo)
            VALUES (%s, 'admin_leda', 'x', 'admin', 1, 0, 1)
            """
        ),
        (admin_id,),
    )
    cur.execute(
        app._sql(
            """
            INSERT INTO users (id, username, password_hash, role, created_by, is_approved, is_blocked, pago_activo)
            VALUES (%s, %s, 'x', 'cajero', %s, 1, 0, 1)
            """
        ),
        (cajero_id, cajero_name, admin_id),
    )
    cur.execute(
        app._sql(
            """
            INSERT INTO tickets (cajero, cajero_id, created_at, pagado, monto, eliminado)
            VALUES (%s, %s, '2026-07-20 11:34:00', 0, 1800, 0)
            """
        ),
        (cajero_name, cajero_id),
    )
    return cur.lastrowid


def test_admin_ve_ticket_de_su_cajero(app_mod, client):
    app = app_mod
    c = app.db()
    cur = c.cursor()
    tid = _seed_users_and_ticket(app, cur)
    c.commit()
    c.close()

    _session(client, uid=101, user="admin_leda", role="admin")
    r = client.get(f"/ticket/{tid}")
    assert r.status_code == 200
    assert "JUGADA" in r.get_data(as_text=True) or "LA QUE NUNCA FALLA" in r.get_data(as_text=True)


def test_cajero_ve_su_propio_ticket_ganador(app_mod, client):
    app = app_mod
    c = app.db()
    cur = c.cursor()
    tid = _seed_users_and_ticket(app, cur)
    c.commit()
    c.close()

    _session(client, uid=102, user="gris", role="cajero")
    r = client.get(f"/ticket/{tid}")
    assert r.status_code == 200


def test_admin_otra_banca_no_ve_ticket(app_mod, client):
    app = app_mod
    c = app.db()
    cur = c.cursor()
    tid = _seed_users_and_ticket(app, cur)
    cur.execute(
        app._sql(
            """
            INSERT INTO users (id, username, password_hash, role, is_approved, is_blocked, pago_activo)
            VALUES (199, 'admin_otra', 'x', 'admin', 1, 0, 1)
            """
        )
    )
    c.commit()
    c.close()

    _session(client, uid=199, user="admin_otra", role="admin")
    r = client.get(f"/ticket/{tid}")
    assert r.status_code == 403


def test_ganadores_plantilla_incluye_revisar_ticket():
    from pathlib import Path

    tpl = Path(__file__).resolve().parents[1] / "templates" / "ganadores_dashboard_inner.html"
    body = tpl.read_text(encoding="utf-8")
    assert "Revisar ticket" in body
    assert 'href="/ticket/{{ t.ticket_id }}"' in body
