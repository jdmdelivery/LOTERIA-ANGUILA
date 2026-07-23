"""Regresión: premios visibles en ranking vs lista de pendientes (/ganadores)."""
from __future__ import annotations

import logging

import pytest

LOTERY = "Loteria Nacional"
DRAW = "2:30 PM"
RESULTADO = "87-30-86"


def _seed_resultado_nacional(app, cur, fecha, p1="87", p2="30", p3="86"):
    nl, nd, frd = app._resultados_norm_tuple_for_unique(LOTERY, DRAW, fecha)
    cur.execute(
        app._sql(
            """
            INSERT INTO resultados (lottery, draw, primero, segundo, tercero, fecha, confirmado, publicado, estado,
                normalized_lottery, normalized_draw, fecha_rd)
            VALUES (%s, %s, %s, %s, %s, %s, 1, 1, 'cerrado', %s, %s, %s)
            """
        ),
        (LOTERY, DRAW, p1, p2, p3, fecha, nl, nd, frd),
    )


def _insert_premio_pendiente(
    app,
    cur,
    tid,
    lid,
    *,
    premio=2200.0,
    fecha,
    cajero="anabel",
    lottery=LOTERY,
    draw=DRAW,
):
    cur.execute(
        app._sql(
            """
            INSERT INTO premios (
                ticket_id, line_id, numero, monto, premio, lottery, draw, play, resultado,
                fecha_sorteo, fecha_resultado, fecha_dia, cajero, premio_shard, estado
            )
            VALUES (%s, %s, '87', 10, %s, %s, %s, 'quiniela', %s,
                    %s, %s, %s, %s, '0', 'pendiente')
            """
        ),
        (tid, lid, premio, lottery, draw, RESULTADO, fecha, fecha, fecha, cajero),
    )
    return cur.lastrowid


def test_premio_pendiente_visible_aunque_ticket_pagado_cabecera(app_mod, monkeypatch):
    """Premio pendiente válido se muestra aunque tickets.pagado=1 (ticket multi-línea / cabecera desfasada)."""
    app = app_mod
    from datetime import datetime

    try:
        import pytz
    except ImportError:
        pytest.skip("pytz requerido")

    fe = "2026-05-26"
    tz = pytz.timezone("America/Santo_Domingo")
    monkeypatch.setattr(
        app,
        "ahora_rd",
        lambda: tz.localize(datetime(2026, 5, 26, 14, 0, 0)),
    )
    c = app.db()
    cur = c.cursor()
    cur.execute(
        app._sql(
            """
            INSERT INTO tickets (id, cajero, created_at, pagado)
            VALUES (720, 'anabel', %s, 1)
            """
        ),
        (f"{fe} 10:00:00",),
    )
    cur.execute(
        app._sql(
            """
            INSERT INTO ticket_lines (ticket_id, lottery, draw, number, play, amount, fecha_sorteo, pagado, premio_linea_pagada)
            VALUES (720, %s, %s, '87', 'Quiniela', 10, %s, 0, 0)
            """
        ),
        (LOTERY, DRAW, fe),
    )
    lid = cur.lastrowid
    pid = _insert_premio_pendiente(
        app, cur, 720, lid, premio=2200.0, fecha=fe, cajero="anabel"
    )
    c.commit()

    visibles = app._premios_ids_visibles_lista_pendientes(
        cur, fe, cajero_filtro=None, hoy_rd=fe, extend_pendiente_ventana=True
    )
    assert pid in visibles

    rows = app._premios_pendientes_ranking_por_cajero_rows(cur, fe)
    by_caj = {
        str(r.get("cajero_norm") or "").lower(): float(r.get("pendiente_premios") or 0)
        for r in rows
    }
    assert by_caj.get("anabel", 0) == pytest.approx(2200.0)


def test_premio_ayer_visible_en_lista_hoy_con_ventana(app_mod, monkeypatch):
    """Premio Loteria Nacional 2:30 PM del día anterior aparece en lista de hoy."""
    app = app_mod
    from datetime import datetime

    try:
        import pytz
    except ImportError:
        pytest.skip("pytz requerido")

    ayer = "2026-05-25"
    hoy = "2026-05-26"
    tz = pytz.timezone("America/Santo_Domingo")
    monkeypatch.setattr(
        app,
        "ahora_rd",
        lambda: tz.localize(datetime(2026, 5, 26, 14, 0, 0)),
    )
    c = app.db()
    cur = c.cursor()
    cur.execute(
        app._sql(
            """
            INSERT INTO tickets (cajero, created_at, pagado)
            VALUES ('anabel', %s, 0)
            """
        ),
        (f"{ayer} 10:00:00",),
    )
    tid = cur.lastrowid
    cur.execute(
        app._sql(
            """
            INSERT INTO ticket_lines (ticket_id, lottery, draw, number, play, amount, fecha_sorteo, pagado, premio_linea_pagada)
            VALUES (%s, %s, %s, '87', 'Quiniela', 10, %s, 0, 0)
            """
        ),
        (tid, LOTERY, DRAW, ayer),
    )
    lid = cur.lastrowid
    pid = _insert_premio_pendiente(
        app, cur, tid, lid, premio=2200.0, fecha=ayer, cajero="anabel"
    )
    c.commit()

    lista = app.premios_pendientes_fetch(
        cur, hoy, cajero_username=None, extend_pendiente_ventana=True
    )
    ids = {int(x.get("premio_id") or 0) for x in lista}
    assert pid in ids

    rows = app._premios_pendientes_ranking_por_cajero_rows(cur, hoy)
    by_caj = {
        str(r.get("cajero_norm") or "").lower(): float(r.get("pendiente_premios") or 0)
        for r in rows
    }
    assert by_caj.get("anabel", 0) == pytest.approx(2200.0)


def test_premio_oculto_loteria_desface_nacional_vs_new_york(app_mod, caplog):
    """Línea Nacional 2:30 PM pero premio guardado como New York → sanear + recalcular Nacional."""
    app = app_mod
    fe = "2026-05-26"
    c = app.db()
    cur = c.cursor()
    _seed_resultado_nacional(app, cur, fe)
    cur.execute(
        app._sql(
            """
            INSERT INTO tickets (id, cajero, created_at, pagado)
            VALUES (720, 'anabel', %s, 0)
            """
        ),
        (f"{fe} 10:00:00",),
    )
    cur.execute(
        app._sql(
            """
            INSERT INTO ticket_lines (ticket_id, lottery, draw, number, play, amount, fecha_sorteo, pagado, premio_linea_pagada)
            VALUES (720, %s, %s, '87', 'Quiniela', 10, %s, 0, 0)
            """
        ),
        (LOTERY, DRAW, fe),
    )
    lid = cur.lastrowid
    pid_malo = _insert_premio_pendiente(
        app,
        cur,
        720,
        lid,
        premio=2200.0,
        fecha=fe,
        cajero="anabel",
        lottery="New York",
        draw=DRAW,
    )
    c.commit()

    motivo = app._premios_motivo_no_visible_lista(cur, pid_malo, fe)
    assert motivo == "loteria_desface_premio_vs_linea"

    caplog.set_level(logging.WARNING, logger="app")
    n = app._premios_sanear_desface_pendientes(
        cur, fecha_rd=fe, ticket_id=720, lottery=LOTERY, draw=DRAW
    )
    c.commit()
    assert n >= 1
    assert any("[PREMIO_SANEAR]" in r.message and "ticket_id=720" in r.message for r in caplog.records)

    cur.execute(app._sql("SELECT id, lottery, draw, premio FROM premios WHERE line_id = %s"), (lid,))
    rows = cur.fetchall()
    assert rows
    row = dict(rows[0]) if hasattr(rows[0], "keys") else {}
    lot = row.get("lottery") if hasattr(row, "get") else rows[0][1]
    assert "Nacional" in str(lot or "")
    assert int(row.get("id") if hasattr(row, "get") else rows[0][0]) != pid_malo


def test_ticket_multi_loteria_muestra_solo_linea_ganadora(app_mod, monkeypatch):
    """Ticket con Nacional ganadora + New York perdedora: lista y ranking suman solo la válida."""
    app = app_mod
    from datetime import datetime

    try:
        import pytz
    except ImportError:
        pytest.skip("pytz requerido")

    fe = "2026-05-26"
    tz = pytz.timezone("America/Santo_Domingo")
    monkeypatch.setattr(
        app,
        "ahora_rd",
        lambda: tz.localize(datetime(2026, 5, 26, 14, 0, 0)),
    )
    c = app.db()
    cur = c.cursor()
    _seed_resultado_nacional(app, cur, fe)
    app._premios_migrate_unique_constraints(cur)
    cur.execute(
        app._sql(
            """
            INSERT INTO tickets (cajero, created_at, pagado)
            VALUES ('anabel', %s, 0)
            """
        ),
        (f"{fe} 10:00:00",),
    )
    tid = cur.lastrowid
    cur.execute(
        app._sql(
            """
            INSERT INTO ticket_lines (ticket_id, lottery, draw, number, play, amount, fecha_sorteo, pagado, premio_linea_pagada)
            VALUES (%s, %s, %s, '87', 'Quiniela', 10, %s, 0, 0)
            """
        ),
        (tid, LOTERY, DRAW, fe),
    )
    lid_ok = cur.lastrowid
    cur.execute(
        app._sql(
            """
            INSERT INTO ticket_lines (ticket_id, lottery, draw, number, play, amount, fecha_sorteo, pagado, premio_linea_pagada)
            VALUES (%s, 'New York', %s, '99', 'Quiniela', 5, %s, 0, 0)
            """
        ),
        (tid, DRAW, fe),
    )
    c.commit()

    sync = app._recalcular_ganadores_fecha_completo(
        cur, fe, lottery=LOTERY, draw=DRAW, recalc_ctx={"usuario": "test", "rol": "admin", "usuario_id": 1}
    )
    assert sync.get("ok") is True
    c.commit()

    lista = app.premios_pendientes_fetch(cur, fe, extend_pendiente_ventana=True)
    tids = {int(x.get("ticket_id") or 0) for x in lista}
    assert tid in tids
    lineas_ticket = [x for x in lista if int(x.get("ticket_id") or 0) == tid]
    assert len(lineas_ticket) >= 1
    assert all("Nacional" in str(x.get("lottery") or "") for x in lineas_ticket)

    grouped = app._ganadores_agrupar_por_ticket(lista)
    gt = [g for g in grouped if int(g.get("ticket_id") or 0) == tid]
    assert gt and float(gt[0].get("total_pendiente") or 0) > 0

    rows = app._premios_pendientes_ranking_por_cajero_rows(cur, fe)
    by_caj = {
        str(r.get("cajero_norm") or "").lower(): float(r.get("pendiente_premios") or 0)
        for r in rows
    }
    assert by_caj.get("anabel", 0) == pytest.approx(float(gt[0].get("total_pendiente") or 0))
