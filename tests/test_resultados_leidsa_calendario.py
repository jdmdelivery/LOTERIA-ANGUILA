"""Regresión: Leidsa en Resultados de Hoy por día de semana RD."""
from __future__ import annotations

import pytest


def test_filtrar_leidsa_oculta_855_domingo(app_mod):
    app = app_mod
    rows = [
        {"lottery": "Leidsa", "draw": "3:55 PM", "primero": "1"},
        {"lottery": "Leidsa", "draw": "8:55 PM", "primero": "2"},
    ]
    out = app._ganadores_resultados_filtrar_leidsa_por_dia_semana(
        rows, "2026-06-28", "2026-06-28"
    )
    draws = {app.normalizar_sorteo(r.get("draw") or "") for r in out}
    assert app.normalizar_sorteo("3:55 PM") in draws
    assert app.normalizar_sorteo("8:55 PM") not in draws


def test_filtrar_leidsa_oculta_355_lunes(app_mod):
    app = app_mod
    rows = [
        {"lottery": "Leidsa", "draw": "3:55 PM", "primero": "1"},
        {"lottery": "Leidsa", "draw": "8:55 PM", "primero": "2"},
    ]
    out = app._ganadores_resultados_filtrar_leidsa_por_dia_semana(
        rows, "2026-06-29", "2026-06-29"
    )
    draws = {app.normalizar_sorteo(r.get("draw") or "") for r in out}
    assert app.normalizar_sorteo("3:55 PM") not in draws
    assert app.normalizar_sorteo("8:55 PM") in draws


def test_grilla_leidsa_lunes_muestra_855_no_355(app_mod):
    app = app_mod
    c = app.db()
    cur = c.cursor()
    hoy = "2026-06-29"
    cur.execute(
        app._sql(
            """
            INSERT INTO resultados (lottery, draw, fecha, primero, segundo, tercero)
            VALUES (%s, %s, %s, %s, %s, %s)
            """
        ),
        ("Leidsa", "3:55 PM", hoy, "10", "20", "30"),
    )
    cur.execute(
        app._sql(
            """
            INSERT INTO resultados (lottery, draw, fecha, primero, segundo, tercero)
            VALUES (%s, %s, %s, %s, %s, %s)
            """
        ),
        ("Leidsa", "8:55 PM", hoy, "40", "50", "60"),
    )
    c.commit()
    grid = app._ganadores_grilla_resultados_catalogo_fallback(cur, hoy)
    le_rows = [r for r in grid if r.get("lottery") == "Leidsa"]
    draws = {app.normalizar_sorteo(r.get("draw") or "") for r in le_rows}
    assert app.normalizar_sorteo("3:55 PM") not in draws
    assert app.normalizar_sorteo("8:55 PM") in draws
    c.close()


@pytest.mark.parametrize(
    "fecha,expected",
    [
        ("2026-07-05", "__leidsa_355"),
        ("2026-07-06", "__leidsa_855"),
    ],
)
def test_conectate_quiniela_leidsa_por_dia(app_mod, fecha, expected):
    app = app_mod
    assert (
        app._conectate_label_to_internal_key("Quiniela Leidsa", ref_fecha_iso=fecha)
        == expected
    )


def test_grilla_leidsa_domingo_muestra_855_legacy_en_casillero_355(app_mod):
    """Conectate domingo guardó en 8:55 PM; la grilla debe mostrar esos números en 3:55 PM."""
    app = app_mod
    c = app.db()
    cur = c.cursor()
    domingo = "2026-07-05"
    viejo = "2026-07-03"
    cur.execute(
        app._sql(
            """
            INSERT INTO resultados (lottery, draw, fecha, primero, segundo, tercero)
            VALUES (%s, %s, %s, %s, %s, %s)
            """
        ),
        ("Leidsa", "3:55 PM", viejo, "13", "13", "02"),
    )
    cur.execute(
        app._sql(
            """
            INSERT INTO resultados (lottery, draw, fecha, primero, segundo, tercero)
            VALUES (%s, %s, %s, %s, %s, %s)
            """
        ),
        ("Leidsa", "8:55 PM", domingo, "82", "60", "16"),
    )
    c.commit()
    grid = app._ganadores_grilla_resultados_catalogo_fallback(cur, domingo)
    le_355 = [
        r
        for r in grid
        if r.get("lottery") == "Leidsa"
        and app.normalizar_sorteo(r.get("draw") or "") == app.normalizar_sorteo("3:55 PM")
    ]
    assert len(le_355) == 1
    assert le_355[0]["primero"] == "82"
    assert le_355[0]["segundo"] == "60"
    assert le_355[0]["tercero"] == "16"
    assert str(le_355[0].get("fecha") or "")[:10] == domingo
    c.close()


def test_conectate_pega3_ignorado_domingo(app_mod):
    app = app_mod
    assert app._conectate_label_to_internal_key("Pega 3 Más", ref_fecha_iso="2026-07-05") is None
    assert (
        app._conectate_label_to_internal_key("Pega 3 Más", ref_fecha_iso="2026-07-06")
        == "__leidsa_355"
    )


def test_scraper_merge_quiniela_leidsa_gana_sobre_pega3(app_mod):
    app = app_mod
    dest = {}
    app._resultados_scraper_merge_item(
        dest,
        "__leidsa_355",
        {"title": "Pega 3 Más", "n1": "13", "n2": "13", "n3": "02"},
    )
    app._resultados_scraper_merge_item(
        dest,
        "__leidsa_355",
        {"title": "Quiniela Leidsa", "n1": "82", "n2": "60", "n3": "16"},
    )
    assert dest["__leidsa_355"]["n1"] == "82"
    assert dest["__leidsa_355"]["title"] == "Quiniela Leidsa"


def test_grilla_leidsa_domingo_prefiere_855_hoy_sobre_355_hoy_erroneo(app_mod):
    """Si BD tiene Pega 3 mal en 3:55 PM hoy, mostrar Quiniela Leidsa de 8:55 PM hoy."""
    app = app_mod
    c = app.db()
    cur = c.cursor()
    domingo = "2026-07-05"
    cur.execute(
        app._sql(
            """
            INSERT INTO resultados (lottery, draw, fecha, primero, segundo, tercero)
            VALUES (%s, %s, %s, %s, %s, %s)
            """
        ),
        ("Leidsa", "3:55 PM", domingo, "13", "13", "02"),
    )
    cur.execute(
        app._sql(
            """
            INSERT INTO resultados (lottery, draw, fecha, primero, segundo, tercero)
            VALUES (%s, %s, %s, %s, %s, %s)
            """
        ),
        ("Leidsa", "8:55 PM", domingo, "82", "60", "16"),
    )
    c.commit()
    grid = app._ganadores_grilla_resultados_catalogo_fallback(cur, domingo)
    le_355 = [
        r
        for r in grid
        if r.get("lottery") == "Leidsa"
        and app.normalizar_sorteo(r.get("draw") or "") == app.normalizar_sorteo("3:55 PM")
    ]
    assert len(le_355) == 1
    assert le_355[0]["primero"] == "82"
    assert le_355[0]["segundo"] == "60"
    assert le_355[0]["tercero"] == "16"
    c.close()


def test_premios_sync_leidsa_domingo_355_con_resultado_855(app_mod):
    """Ticket Leidsa 3:55 PM + resultado legacy 8:55 PM domingo → detecta ganador quiniela 82."""
    app = app_mod
    c = app.db()
    cur = c.cursor()
    domingo = "2026-07-05"
    cur.execute(
        app._sql(
            """
            INSERT INTO tickets (cajero, created_at, pagado)
            VALUES (%s, %s, 0)
            """
        ),
        ("test_cajero", domingo + " 14:00:00"),
    )
    tid = cur.lastrowid
    cur.execute(
        app._sql(
            """
            INSERT INTO ticket_lines (ticket_id, lottery, draw, number, play, amount, fecha_sorteo, pagado, premio_linea_pagada)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 0, 0)
            """
        ),
        (tid, "Leidsa", "3:55 PM", "82", "Quiniela", 50.0, domingo),
    )
    cur.execute(
        app._sql(
            """
            INSERT INTO resultados (lottery, draw, fecha, primero, segundo, tercero, confirmado, publicado, estado)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
        ),
        ("Leidsa", "8:55 PM", domingo, "82", "60", "16", 1, 1, "cerrado"),
    )
    c.commit()
    sync = app._premios_sync_por_sorteo(cur, domingo, "Leidsa", "3:55 PM")
    c.commit()
    assert int(sync.get("insertados") or 0) >= 1
    cur.execute(
        app._sql("SELECT COUNT(*) AS c FROM premios WHERE line_id IN (SELECT id FROM ticket_lines WHERE ticket_id = %s)"),
        (tid,),
    )
    row = cur.fetchone()
    cnt = int(row["c"] if hasattr(row, "keys") else row[0])
    assert cnt >= 1
    c.close()


def test_grilla_leidsa_lunes_no_usa_domingo_855_en_casillero_855(app_mod):
    """Lunes: casillero 8:55 PM no debe mostrar quiniela domingo mal guardada en 8:55 PM."""
    app = app_mod
    c = app.db()
    cur = c.cursor()
    lunes = "2026-07-06"
    domingo = "2026-07-05"
    cur.execute(
        app._sql(
            """
            INSERT INTO resultados (lottery, draw, fecha, primero, segundo, tercero)
            VALUES (%s, %s, %s, %s, %s, %s)
            """
        ),
        ("Leidsa", "8:55 PM", domingo, "82", "60", "16"),
    )
    c.commit()
    grid = app._ganadores_grilla_resultados_catalogo_fallback(cur, lunes)
    le_855 = [
        r
        for r in grid
        if r.get("lottery") == "Leidsa"
        and app.normalizar_sorteo(r.get("draw") or "") == app.normalizar_sorteo("8:55 PM")
    ]
    assert len(le_855) == 1
    assert not app._ganadores_grilla_fila_tiene_numeros(le_855[0])
    c.close()


def test_scraper_storage_key_por_fecha(app_mod):
    app = app_mod
    dest = {}
    app._resultados_scraper_merge_item(
        dest,
        "LoteDom",
        {"fecha": "2026-07-05", "n1": "01", "n2": "02", "n3": "03", "title": "LoteDom"},
    )
    app._resultados_scraper_merge_item(
        dest,
        "LoteDom",
        {"fecha": "2026-07-06", "n1": "02", "n2": "51", "n3": "71", "title": "LoteDom"},
    )
    assert len(dest) == 2
    k1 = app._resultados_scraper_storage_key("LoteDom", "2026-07-05")
    k2 = app._resultados_scraper_storage_key("LoteDom", "2026-07-06")
    assert dest[k1]["n1"] == "01"
    assert dest[k2]["n1"] == "02"


def test_purge_leidsa_855_domingo_duplicado(app_mod):
    app = app_mod
    c = app.db()
    cur = c.cursor()
    domingo = "2026-07-05"
    cur.execute(
        app._sql(
            """
            INSERT INTO resultados (lottery, draw, fecha, primero, segundo, tercero)
            VALUES (%s, %s, %s, %s, %s, %s)
            """
        ),
        ("Leidsa", "3:55 PM", domingo, "82", "60", "16"),
    )
    cur.execute(
        app._sql(
            """
            INSERT INTO resultados (lottery, draw, fecha, primero, segundo, tercero)
            VALUES (%s, %s, %s, %s, %s, %s)
            """
        ),
        ("Leidsa", "8:55 PM", domingo, "82", "60", "16"),
    )
    c.commit()
    ok = app._resultado_purge_leidsa_855_domingo_duplicado(cur, domingo, "82", "60", "16")
    c.commit()
    assert ok
    cur.execute(
        app._sql(
            "SELECT COUNT(*) AS c FROM resultados WHERE lottery = %s AND fecha = %s AND draw LIKE %s"
        ),
        ("Leidsa", domingo, "%8:55%"),
    )
    row = cur.fetchone()
    cnt = int(row["c"] if hasattr(row, "keys") else row[0])
    assert cnt == 0
    c.close()
