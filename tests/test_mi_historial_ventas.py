"""Mi historial de ventas: solo el cajero ve y reimprime sus propios tickets."""
from __future__ import annotations

import time

FECHA = "2026-07-12"


def _session_cajero(client, *, uid=2, user="cajero_a"):
    with client.session_transaction() as sess:
        sess["u"] = user
        sess["uid"] = uid
        sess["role"] = "cajero"
        sess["last_activity"] = time.time()
        sess["last_activity_touch"] = time.time()


def _session_admin(client):
    with client.session_transaction() as sess:
        sess["u"] = "admin_test"
        sess["uid"] = 1
        sess["role"] = "admin"
        sess["last_activity"] = time.time()
        sess["last_activity_touch"] = time.time()


def _seed(app, cur, *, cajero, cajero_id, monto=25.0):
    cur.execute(
        app._sql(
            """
            INSERT INTO tickets (cajero, cajero_id, created_at, pagado, monto, eliminado)
            VALUES (%s, %s, %s, 0, %s, 0)
            """
        ),
        (cajero, cajero_id, f"{FECHA} 11:00:00", monto),
    )
    return cur.lastrowid


def test_mi_historial_ventas_solo_cajero_propio(app_mod, client):
    app = app_mod
    c = app.db()
    cur = c.cursor()
    tid_a = _seed(app, cur, cajero="cajero_a", cajero_id=2, monto=40)
    tid_b = _seed(app, cur, cajero="cajero_b", cajero_id=3, monto=55)
    c.commit()
    c.close()

    _session_cajero(client, uid=2, user="cajero_a")
    r = client.get(f"/mi_historial_ventas?desde={FECHA}&hasta={FECHA}")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "Mi historial de ventas" in body
    assert f"/ticket/{tid_a}" in body
    assert f"/ticket/{tid_b}" not in body
    assert 'name="cajero"' not in body
    assert f">#{tid_a}<" in body or f"#{tid_a}</td>" in body


def test_mi_historial_ventas_admin_redirige_ventas_cajeros(client):
    _session_admin(client)
    r = client.get("/mi_historial_ventas", follow_redirects=False)
    assert r.status_code in (301, 302)
    assert "/ventas_cajeros" in (r.headers.get("Location") or "")


def test_ticket_ajeno_403_para_cajero(app_mod, client):
    app = app_mod
    c = app.db()
    cur = c.cursor()
    tid_b = _seed(app, cur, cajero="cajero_b", cajero_id=3, monto=30)
    c.commit()
    c.close()

    _session_cajero(client, uid=2, user="cajero_a")
    r = client.get(f"/ticket/{tid_b}")
    assert r.status_code == 403
    assert "denegado" in r.get_data(as_text=True).lower()


def test_ticket_propio_ok_para_cajero(app_mod, client):
    app = app_mod
    c = app.db()
    cur = c.cursor()
    tid_a = _seed(app, cur, cajero="cajero_a", cajero_id=2, monto=30)
    c.commit()
    c.close()

    _session_cajero(client, uid=2, user="cajero_a")
    r = client.get(f"/ticket/{tid_a}")
    assert r.status_code == 200
