"""Regresión: venta rápida en lote y orden de parámetros SQL en ranking pendientes."""
from __future__ import annotations

import pytest


def test_venta_insertar_jugadas_batch(app_mod):
    app = app_mod
    c = app.db()
    cur = c.cursor()
    cur.execute(
        app._sql("INSERT INTO tickets (cajero, monto) VALUES (%s, 0)"),
        ("cajero_batch",),
    )
    tid = cur.lastrowid
    jugadas = [
        {
            "lottery": "Loteka",
            "lottery2": None,
            "draw": "7:55 PM",
            "play": "Quiniela",
            "number": "12",
            "amount": 10.0,
        },
        {
            "lottery": "Loteka",
            "lottery2": None,
            "draw": "7:55 PM",
            "play": "Quiniela",
            "number": "34",
            "amount": 25.0,
        },
    ]
    app._venta_upsert_lotteries_para_jugadas(cur, jugadas)
    cache = app._venta_loteria_id_cache(cur, jugadas)
    total = app._venta_insertar_jugadas_batch(cur, tid, jugadas, loteria_id_cache=cache)
    c.commit()
    assert total == pytest.approx(35.0)
    cur.execute(app._sql("SELECT COUNT(*) AS n FROM ticket_lines WHERE ticket_id = %s"), (tid,))
    row = cur.fetchone()
    n = row["n"] if hasattr(row, "get") else row[0]
    assert int(n) == 2
    cur.execute(
        app._sql("SELECT COUNT(*) AS n FROM historial_jugadas WHERE ticket_id = %s"),
        (tid,),
    )
    row2 = cur.fetchone()
    n2 = row2["n"] if hasattr(row2, "get") else row2[0]
    assert int(n2) == 2
    c.close()


def test_premios_ranking_params_order_con_filtro_banca(app_mod):
    """Con filtro banca (entero), no debe fallar text=integer por orden de params."""
    app = app_mod
    c = app.db()
    cur = c.cursor()
    fe = app.fecha_hoy_rd_iso()
    filt_banca, filt_params = app._filtro_sql_ticket_banca_admin_scope("tk", 1)
    rows = app._premios_pendientes_ranking_por_cajero_rows(
        cur,
        fe,
        filtro_cajero="",
        filt_banca=filt_banca,
        filt_extra_params=list(filt_params),
    )
    assert isinstance(rows, list)
    c.close()


def test_venta_post_no_sync_balance_inline(app_mod, client, monkeypatch):
    """POST /venta no debe llamar _sync_balance_cajero en la petición (va en background)."""
    app = app_mod
    monkeypatch.setattr(app, "caja_cerrada_hoy", lambda: False)
    monkeypatch.setattr(app, "is_admin_or_super", lambda: True)
    monkeypatch.setattr(app, "loteria_cerrada_para_venta", lambda *a, **k: False)
    monkeypatch.setattr(app, "ventas_loterias_permiso_horario_global", lambda: True)
    monkeypatch.setattr(app, "_validar_limites_banca_venta", lambda *a, **k: (True, ""))
    monkeypatch.setattr(app, "_reservar_sale_key", lambda *a, **k: (True, None))
    monkeypatch.setattr(app, "_marcar_sale_key_ticket", lambda *a, **k: None)
    monkeypatch.setattr(app, "banco_registrar_venta", lambda *a, **k: {"ok": True})
    sync_calls = []
    bg_calls = []

    def _no_sync(*a, **k):
        sync_calls.append(1)
        return None

    def _bg(*a, **k):
        bg_calls.append(1)

    monkeypatch.setattr(app, "_sync_balance_cajero", _no_sync)
    monkeypatch.setattr(app, "_venta_sync_balance_cajero_background", _bg)

    with client.session_transaction() as sess:
        sess["u"] = "admin"
        sess["uid"] = 1
        sess["last_activity"] = __import__("time").time()

    resp = client.post(
        "/venta",
        data={
            "sale_key": "test-sale-key-unique-001",
            "loteria[]": ["Loteka"],
            "sorteo[]": ["7:55 PM"],
            "numero[]": ["11"],
            "jugada[]": ["Quiniela"],
            "monto[]": ["50"],
        },
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)
    assert sync_calls == []
    assert bg_calls == [1]
