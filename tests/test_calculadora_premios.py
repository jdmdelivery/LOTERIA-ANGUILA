"""Calculadora de premios: usa _pagos_efectivos_para_vendedor (misma lógica que venta)."""
from __future__ import annotations

import time


def _session(client, role="cajero", uid=2, username="Gris"):
    with client.session_transaction() as sess:
        sess["u"] = username
        sess["uid"] = uid
        sess["role"] = role
        sess["last_activity"] = time.time()
        sess["last_activity_touch"] = time.time()


def test_calculadora_usa_pagos_efectivos_cajero(app_mod, client):
    app = app_mod
    c = app.db()
    cur = c.cursor()
    cur.execute(app._sql("INSERT INTO users (username, role) VALUES (%s,%s)"), ("AdminCalc", "admin"))
    admin_id = cur.lastrowid
    cur.execute(
        app._sql("INSERT INTO users (username, role, created_by) VALUES (%s,%s,%s)"),
        ("GrisCalc", "cajero", admin_id),
    )
    gris_id = cur.lastrowid
    app._upsert_pagos_config_banca(cur, admin_id, {"quiniela_1": 80})
    app._upsert_pagos_config_banca(cur, gris_id, {"quiniela_1": 70})
    c.commit()
    c.close()

    _session(client, "cajero", gris_id, "GrisCalc")
    r = client.post("/calculadora_premios", data={"play": "Quiniela 1er", "monto": "100"})
    assert r.status_code == 200, r.get_data(as_text=True)[:300]
    html = r.get_data(as_text=True)
    assert "7,000.00" in html or "7000.00" in html
    assert "GrisCalc" in html
    assert "(Tú)" in html
    assert "configuración efectiva" in html.lower() or "configuracion efectiva" in html.lower()

    r2 = client.get("/calculadora_premios?tabla=1", headers={"X-Requested-With": "calculadora-tabla"})
    assert r2.status_code == 200
    data = r2.get_json()
    assert data.get("ok") is True
    assert float(data.get("mi_mult")) == 70.0
    gris_row = next((f for f in data["filas"] if f["id"] == gris_id), None)
    assert gris_row is not None
    assert float(gris_row["mult"]) == 70.0
    assert float(gris_row["cols"][4]) == 7000.0  # RD$100


def test_calculadora_cajero_sin_config_hereda_admin(app_mod, client):
    app = app_mod
    c = app.db()
    cur = c.cursor()
    cur.execute(app._sql("INSERT INTO users (username, role) VALUES (%s,%s)"), ("AdminHer", "admin"))
    admin_id = cur.lastrowid
    cur.execute(
        app._sql("INSERT INTO users (username, role, created_by) VALUES (%s,%s,%s)"),
        ("CajHer", "cajero", admin_id),
    )
    caj_id = cur.lastrowid
    app._upsert_pagos_config_banca(cur, admin_id, {"quiniela_1": 75})
    c.commit()
    c.close()

    _session(client, "cajero", caj_id, "CajHer")
    r = client.post("/calculadora_premios", data={"play": "Quiniela 1er", "monto": "100"})
    html = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "7,500.00" in html or "7500.00" in html
