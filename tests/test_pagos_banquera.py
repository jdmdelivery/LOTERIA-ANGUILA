"""Pagos personalizados por banquera/cajero: snapshot + resolución al vender."""
from __future__ import annotations

import json
import time


def _session_role(client, role, uid=1, username="u_test"):
    with client.session_transaction() as sess:
        sess["u"] = username
        sess["uid"] = uid
        sess["role"] = role
        sess["last_activity"] = time.time()
        sess["last_activity_touch"] = time.time()


def _seed_banquera_y_cajero(app, cur, admin_name, cajero_name):
    cur.execute(
        app._sql("INSERT INTO users (username, role) VALUES (%s, %s)"),
        (admin_name, "admin"),
    )
    admin_id = cur.lastrowid
    cur.execute(
        app._sql(
            "INSERT INTO users (username, role, created_by) VALUES (%s, %s, %s)"
        ),
        (cajero_name, "cajero", admin_id),
    )
    cajero_id = cur.lastrowid
    return admin_id, cajero_id


def _premio_quiniela(app, pagos, monto=100):
    return float(
        app.calcular_premio("Quiniela", "10", monto, "10", "20", "30", pagos=pagos) or 0
    )


def _sell_snapshot(app, cur, cajero_id, cajero_name, amount=100, number="10"):
    """Reproduce la resolución de venta + snapshot en ticket_lines."""
    bid = app._banquera_id_para_pagos(cur, cajero_id)
    pagos = app._pagos_efectivos_para_vendedor(cur, cajero_id)
    snap = app._pagos_snapshot_json(pagos)
    cur.execute(
        app._sql(
            "INSERT INTO tickets (cajero, cajero_id, banca_id, monto) VALUES (%s,%s,%s,%s)"
        ),
        (cajero_name, cajero_id, cajero_id, amount),
    )
    tid = cur.lastrowid
    cur.execute(
        app._sql(
            """
            INSERT INTO ticket_lines
            (ticket_id, lottery, draw, play, number, amount, fecha_sorteo, pagos_json)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """
        ),
        (tid, "Loteka", "7:55 PM", "Quiniela", number, amount, "2026-07-15", snap),
    )
    lid = cur.lastrowid
    return tid, lid, bid, pagos, snap


def test_dos_banqueras_premios_diferentes(app_mod):
    app = app_mod
    c = app.db()
    cur = c.cursor()
    a1, _ = _seed_banquera_y_cajero(app, cur, "banq_a80", "caj_a80")
    a2, _ = _seed_banquera_y_cajero(app, cur, "banq_a70", "caj_a70")
    app._upsert_pagos_config_banca(cur, a1, {"quiniela_1": 80})
    app._upsert_pagos_config_banca(cur, a2, {"quiniela_1": 70})
    c.commit()

    p1 = app._pagos_efectivos_banquera(cur, a1)
    p2 = app._pagos_efectivos_banquera(cur, a2)
    c.close()

    assert _premio_quiniela(app, p1) == 8000.0
    assert _premio_quiniela(app, p2) == 7000.0


def test_sin_config_usa_global(app_mod):
    app = app_mod
    c = app.db()
    cur = c.cursor()
    a1, _ = _seed_banquera_y_cajero(app, cur, "banq_global", "caj_global")
    c.commit()
    efectivo = app._pagos_efectivos_banquera(cur, a1)
    globales = app._pagos_globales_efectivos(cur)
    c.close()
    assert float(efectivo["quiniela_1"]) == float(globales["quiniela_1"])
    assert _premio_quiniela(app, efectivo) == float(globales["quiniela_1"]) * 100


def test_gris_70_no_lo_sobrescribe_admin_80(app_mod):
    """Gris (cajero) en 70 paga 7000 aunque el admin dueño esté en 80."""
    app = app_mod
    c = app.db()
    cur = c.cursor()
    # Forzar IDs cercanos a producción: admin=1 no siempre libre; usamos seed normal
    # y etiquetamos mentalmente cajero como Gris.
    admin_id, gris_id = _seed_banquera_y_cajero(app, cur, "AdminDueño", "Gris")
    app._upsert_pagos_config_banca(cur, admin_id, {"quiniela_1": 80})
    app._upsert_pagos_config_banca(cur, gris_id, {"quiniela_1": 70})
    c.commit()

    assert app._banquera_id_para_pagos(cur, gris_id) == gris_id
    pagos = app._pagos_efectivos_para_vendedor(cur, gris_id)
    assert float(pagos["quiniela_1"]) == 70.0
    assert _premio_quiniela(app, pagos) == 7000.0
    c.close()


def test_cajero_sin_config_hereda_admin(app_mod):
    app = app_mod
    c = app.db()
    cur = c.cursor()
    admin_id, cajero_id = _seed_banquera_y_cajero(app, cur, "banq_hered", "caj_hered")
    app._upsert_pagos_config_banca(cur, admin_id, {"quiniela_1": 65})
    c.commit()

    assert app._banquera_id_para_pagos(cur, cajero_id) == admin_id
    pagos = app._pagos_efectivos_para_vendedor(cur, cajero_id)
    assert float(pagos["quiniela_1"]) == 65.0
    assert _premio_quiniela(app, pagos) == 6500.0
    c.close()


def test_sin_cajero_ni_admin_usa_global(app_mod):
    app = app_mod
    c = app.db()
    cur = c.cursor()
    admin_id, cajero_id = _seed_banquera_y_cajero(app, cur, "banq_gl2", "caj_gl2")
    c.commit()
    globales = app._pagos_globales_efectivos(cur)
    pagos = app._pagos_efectivos_para_vendedor(cur, cajero_id)
    assert float(pagos["quiniela_1"]) == float(globales["quiniela_1"])
    assert _premio_quiniela(app, pagos) == float(globales["quiniela_1"]) * 100
    c.close()


def test_snapshot_gris_conserva_70_tras_cambiar_a_80(app_mod):
    app = app_mod
    c = app.db()
    cur = c.cursor()
    admin_id, gris_id = _seed_banquera_y_cajero(app, cur, "AdminSnap", "GrisSnap")
    app._upsert_pagos_config_banca(cur, admin_id, {"quiniela_1": 80})
    app._upsert_pagos_config_banca(cur, gris_id, {"quiniela_1": 70})
    tid, lid, bid, pagos, snap = _sell_snapshot(app, cur, gris_id, "GrisSnap")
    c.commit()
    assert bid == gris_id
    assert float(json.loads(snap)["quiniela_1"]) == 70.0
    assert _premio_quiniela(app, pagos) == 7000.0

    app._upsert_pagos_config_banca(cur, gris_id, {"quiniela_1": 80})
    c.commit()

    cur.execute(app._sql("SELECT pagos_json FROM ticket_lines WHERE id=%s"), (lid,))
    row = cur.fetchone()
    pj = row["pagos_json"] if hasattr(row, "keys") else row[0]
    pagos_old = app._pagos_para_calculo_linea({"pagos_json": pj})
    assert _premio_quiniela(app, pagos_old) == 7000.0

    pagos_new = app._pagos_efectivos_para_vendedor(cur, gris_id)
    c.close()
    assert _premio_quiniela(app, pagos_new) == 8000.0


def test_ticket_nuevo_despues_cambio_paga_80(app_mod):
    app = app_mod
    c = app.db()
    cur = c.cursor()
    admin_id, gris_id = _seed_banquera_y_cajero(app, cur, "AdminNew", "GrisNew")
    app._upsert_pagos_config_banca(cur, gris_id, {"quiniela_1": 70})
    _sell_snapshot(app, cur, gris_id, "GrisNew")
    app._upsert_pagos_config_banca(cur, gris_id, {"quiniela_1": 80})
    c.commit()
    tid2, lid2, bid2, pagos2, snap2 = _sell_snapshot(app, cur, gris_id, "GrisNew")
    c.commit()
    c.close()
    assert bid2 == gris_id
    assert float(json.loads(snap2)["quiniela_1"]) == 80.0
    assert _premio_quiniela(app, pagos2) == 8000.0


def test_snapshot_linea_no_cambia_al_actualizar_config(app_mod):
    app = app_mod
    c = app.db()
    cur = c.cursor()
    admin_id, cajero_id = _seed_banquera_y_cajero(app, cur, "banq_snap", "caj_snap")
    app._upsert_pagos_config_banca(cur, admin_id, {"quiniela_1": 80})
    pagos_venta = app._pagos_efectivos_banquera(cur, admin_id)
    snap = app._pagos_snapshot_json(pagos_venta)

    cur.execute(
        app._sql(
            "INSERT INTO tickets (cajero, cajero_id, banca_id, monto) VALUES (%s,%s,%s,%s)"
        ),
        ("caj_snap", cajero_id, cajero_id, 100),
    )
    tid = cur.lastrowid
    cur.execute(
        app._sql(
            """
            INSERT INTO ticket_lines
            (ticket_id, lottery, draw, play, number, amount, fecha_sorteo, pagos_json)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """
        ),
        (tid, "Loteka", "7:55 PM", "Quiniela", "10", 100, "2026-07-15", snap),
    )
    lid = cur.lastrowid
    c.commit()

    app._upsert_pagos_config_banca(cur, admin_id, {"quiniela_1": 70})
    c.commit()

    cur.execute(app._sql("SELECT pagos_json FROM ticket_lines WHERE id=%s"), (lid,))
    row = cur.fetchone()
    pj = row["pagos_json"] if hasattr(row, "keys") else row[0]

    pagos_line = app._pagos_para_calculo_linea({"pagos_json": pj, "line_id": lid})
    assert _premio_quiniela(app, pagos_line) == 8000.0

    pagos_new = app._pagos_efectivos_banquera(cur, admin_id)
    c.close()
    assert _premio_quiniela(app, pagos_new) == 7000.0


def test_ticket_legacy_sin_pagos_json_usa_global(app_mod):
    app = app_mod
    c = app.db()
    cur = c.cursor()
    admin_id, cajero_id = _seed_banquera_y_cajero(app, cur, "banq_leg", "caj_leg")
    app._upsert_pagos_config_banca(cur, admin_id, {"quiniela_1": 55})
    cur.execute(
        app._sql(
            "INSERT INTO tickets (cajero, cajero_id, banca_id, monto) VALUES (%s,%s,%s,%s)"
        ),
        ("caj_leg", cajero_id, cajero_id, 100),
    )
    tid = cur.lastrowid
    cur.execute(
        app._sql(
            """
            INSERT INTO ticket_lines
            (ticket_id, lottery, draw, play, number, amount, fecha_sorteo)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
            """
        ),
        (tid, "Loteka", "7:55 PM", "Quiniela", "10", 100, "2026-07-15"),
    )
    c.commit()
    globales = app._pagos_globales_efectivos(cur)
    c.close()

    pagos_line = app._pagos_para_calculo_linea(
        {"pagos_json": None, "line_id": None},
        pagos_fallback={**app.PAGOS, **globales},
    )
    premio = _premio_quiniela(app, pagos_line)
    assert premio == float(globales["quiniela_1"]) * 100
    assert premio != 5500.0


def test_banquera_id_prioridad_cajero_luego_admin(app_mod):
    app = app_mod
    c = app.db()
    cur = c.cursor()
    admin_id, cajero_id = _seed_banquera_y_cajero(app, cur, "banq_own", "caj_own")
    c.commit()
    # Sin config en cajero → admin dueño
    assert app._banquera_id_para_pagos(cur, cajero_id) == admin_id
    assert app._banquera_id_para_pagos(cur, admin_id) == admin_id
    # Con config en cajero → el propio cajero
    app._upsert_pagos_config_banca(cur, cajero_id, {"quiniela_1": 70})
    c.commit()
    assert app._banquera_id_para_pagos(cur, cajero_id) == cajero_id
    c.close()


def test_api_solo_super_admin(app_mod, client):
    app = app_mod
    c = app.db()
    cur = c.cursor()
    admin_id, _ = _seed_banquera_y_cajero(app, cur, "banq_api", "caj_api")
    c.commit()
    c.close()

    _session_role(client, "admin", uid=admin_id, username="banq_api")
    r = client.post(
        "/api/superadmin/pagos_banquera/%s" % admin_id,
        json={"quiniela_1": 99},
    )
    assert r.status_code == 403

    _session_role(client, "cajero", uid=999, username="caj_api")
    r2 = client.post(
        "/api/superadmin/pagos_banquera/%s" % admin_id,
        json={"quiniela_1": 99},
    )
    assert r2.status_code == 403

    _session_role(client, "super_admin", uid=1, username="super_x")
    r3 = client.post(
        "/api/superadmin/pagos_banquera/%s" % admin_id,
        json={"quiniela_1": 99},
    )
    assert r3.status_code == 200, r3.get_data(as_text=True)
    data = r3.get_json()
    assert data.get("ok") is True
    assert float(data["efectivo"]["quiniela_1"]) == 99.0

    r4 = client.get("/superadmin/configuracion-pagos")
    assert r4.status_code == 200
    assert "Configuración de pagos" in r4.get_data(as_text=True)

    _session_role(client, "admin", uid=admin_id, username="banq_api")
    r5 = client.get("/superadmin/configuracion-pagos")
    assert r5.status_code == 403


def test_venta_batch_guarda_pagos_json(app_mod):
    app = app_mod
    c = app.db()
    cur = c.cursor()
    admin_id, cajero_id = _seed_banquera_y_cajero(app, cur, "banq_ins", "caj_ins")
    app._upsert_pagos_config_banca(cur, admin_id, {"quiniela_1": 77})
    cur.execute(
        app._sql(
            "INSERT INTO tickets (cajero, cajero_id, banca_id, monto) VALUES (%s,%s,%s,%s)"
        ),
        ("caj_ins", cajero_id, cajero_id, 0),
    )
    tid = cur.lastrowid
    pagos = app._pagos_efectivos_para_vendedor(cur, cajero_id)
    snap = app._pagos_snapshot_json(pagos)
    total = app._venta_insertar_jugadas_batch(
        cur,
        tid,
        [
            {
                "lottery": "Loteka",
                "draw": "7:55 PM",
                "play": "Quiniela",
                "number": "12",
                "amount": 50,
            }
        ],
        pagos_json=snap,
    )
    c.commit()
    assert total == 50.0
    cur.execute(
        app._sql("SELECT pagos_json, amount FROM ticket_lines WHERE ticket_id=%s"),
        (tid,),
    )
    row = cur.fetchone()
    c.close()
    pj = row["pagos_json"] if hasattr(row, "keys") else row[0]
    parsed = json.loads(pj)
    assert float(parsed["quiniela_1"]) == 77.0


def test_mismo_importe_calculo_y_snapshot(app_mod):
    """El premio desde snapshot coincide con calcular_premio (única lógica)."""
    app = app_mod
    snap = app._pagos_snapshot_json({"quiniela_1": 80, **{k: v for k, v in app.PAGOS.items()}})
    pagos = app._pagos_para_calculo_linea({"pagos_json": snap})
    p = float(app.calcular_premio("Quiniela", "10", 100, "10", "00", "00", pagos=pagos) or 0)
    assert p == 8000.0


def test_gris_id_25_escenario_completo(app_mod):
    """Escenario Gris ID 25: 70 al vender; admin 80 no pisa; cambio a 80 solo tickets nuevos."""
    app = app_mod
    c = app.db()
    cur = c.cursor()
    cur.execute(app._sql("DELETE FROM users"))
    cur.execute(
        app._sql(
            "INSERT INTO users (id, username, role, is_approved, approved) VALUES (%s,%s,%s,%s,%s)"
        ),
        (1, "Administrador", "admin", 1, 1),
    )
    cur.execute(
        app._sql(
            """
            INSERT INTO users (id, username, role, created_by, is_approved, approved)
            VALUES (%s,%s,%s,%s,%s,%s)
            """
        ),
        (25, "Gris", "cajero", 1, 1, 1),
    )
    app._upsert_pagos_config_banca(cur, 1, {"quiniela_1": 80})
    app._upsert_pagos_config_banca(cur, 25, {"quiniela_1": 70})
    c.commit()

    assert app._banquera_id_para_pagos(cur, 25) == 25
    pagos1 = app._pagos_efectivos_para_vendedor(cur, 25)
    assert _premio_quiniela(app, pagos1) == 7000.0

    tid, lid, bid, _, snap = _sell_snapshot(app, cur, 25, "Gris")
    c.commit()
    assert tid >= 1 and bid == 25
    assert float(json.loads(snap)["quiniela_1"]) == 70.0

    app._upsert_pagos_config_banca(cur, 25, {"quiniela_1": 80})
    c.commit()
    cur.execute(app._sql("SELECT pagos_json FROM ticket_lines WHERE id=%s"), (lid,))
    row = cur.fetchone()
    pj = row["pagos_json"] if hasattr(row, "keys") else row[0]
    assert _premio_quiniela(app, app._pagos_para_calculo_linea({"pagos_json": pj})) == 7000.0

    pagos2 = app._pagos_efectivos_para_vendedor(cur, 25)
    c.close()
    assert _premio_quiniela(app, pagos2) == 8000.0


def test_ganadores_respeta_snapshot_gris_70_no_global_80(app_mod):
    """Integridad de ganadores debe usar snapshot; no rechazar 7000 por global 80."""
    app = app_mod
    c = app.db()
    cur = c.cursor()
    admin_id, gris_id = _seed_banquera_y_cajero(app, cur, "AdminGan", "GrisGan")
    app._upsert_pagos_config_banca(cur, admin_id, {"quiniela_1": 80})
    app._upsert_pagos_config_banca(cur, gris_id, {"quiniela_1": 70})
    tid, lid, bid, pagos, snap = _sell_snapshot(app, cur, gris_id, "GrisGan")
    c.commit()
    fecha = app.ahora_rd().strftime("%Y-%m-%d")
    cur.execute(
        app._sql("UPDATE ticket_lines SET fecha_sorteo=%s WHERE id=%s"),
        (fecha, lid),
    )
    c.commit()
    lista = app._ganadores_procesar_filas(
        [
            {
                "line_id": lid,
                "ticket_id": tid,
                "number": "10",
                "play": "Quiniela",
                "amount": 100,
                "pagos_json": snap,
                "lottery": "Loteka",
                "draw": "7:55 PM",
                "fecha_sorteo": fecha,
                "resultado_fecha": fecha,
                "primero": "10",
                "segundo": "20",
                "tercero": "30",
                "banca_id": gris_id,
                "cajero": "GrisGan",
            }
        ],
        pagos=app._pagos_globales_efectivos(cur),
        hoy_rd_str=fecha,
        cur=None,
        recalc_log=True,
    )
    c.close()
    total = sum(float(x.get("premio") or 0) for x in (lista or []))
    assert total == 7000.0, (total, lista)
