"""Regresión: New York Noche (10:30 PM) vs filas legacy 7:30 PM."""
from __future__ import annotations


def test_grilla_ny_1030_muestra_legacy_730_hoy(app_mod):
    """Si Conectate guardó en 7:30 PM legacy, el casillero 10:30 PM debe mostrar esos números de hoy."""
    app = app_mod
    c = app.db()
    cur = c.cursor()
    hoy = "2026-07-05"
    viejo = "2026-07-04"
    cur.execute(
        app._sql(
            """
            INSERT INTO resultados (lottery, draw, fecha, primero, segundo, tercero)
            VALUES (%s, %s, %s, %s, %s, %s)
            """
        ),
        ("New York", "10:30 PM", viejo, "89", "25", "36"),
    )
    cur.execute(
        app._sql(
            """
            INSERT INTO resultados (lottery, draw, fecha, primero, segundo, tercero)
            VALUES (%s, %s, %s, %s, %s, %s)
            """
        ),
        ("New York", "7:30 PM", hoy, "71", "48", "56"),
    )
    c.commit()
    grid = app._ganadores_grilla_resultados_catalogo_fallback(cur, hoy)
    ny_1030 = [
        r
        for r in grid
        if r.get("lottery") == "New York"
        and app.normalizar_sorteo(r.get("draw") or "") == app.normalizar_sorteo("10:30 PM")
    ]
    assert len(ny_1030) == 1
    assert ny_1030[0]["primero"] == "71"
    assert ny_1030[0]["segundo"] == "48"
    assert ny_1030[0]["tercero"] == "56"
    assert str(ny_1030[0].get("fecha") or "")[:10] == hoy
    c.close()


def test_conectate_new_york_noche_mapea_1030(app_mod):
    app = app_mod
    assert app._conectate_label_to_internal_key("New York Noche") == "New York 11:30"
    lot, dr = app.RESULT_LOTTERY_TO_TICKET["New York 11:30"]
    assert lot == "New York"
    assert app.normalizar_sorteo(dr) == app.normalizar_sorteo("10:30 PM")
