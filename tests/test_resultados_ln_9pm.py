"""Regresión: Lotería Nacional por día de semana RD (2:30 + 6PM domingo / 2:30 + 9PM lun–sáb)."""
from __future__ import annotations

import pytest


@pytest.mark.parametrize(
    "title,ref_fecha,expected",
    [
        ("Loteria Nacional Noche", "2026-06-29", "__ln_900"),
        ("Lotería Nacional Noche", "2026-06-28", "__ln_600"),
        ("Loteria Nacional 9:00 PM", "2026-06-29", "__ln_900"),
        ("Loteria Nacional 6:00 PM", "2026-06-28", "__ln_600"),
        ("Lotería Nacional", "2026-06-29", "__ln_900"),
        ("Lotería Nacional", "2026-06-28", "__ln_600"),
        ("Loteria Nacional Tarde (gana mas)", "2026-06-29", "__ln_230"),
    ],
)
def test_conectate_label_loteria_nacional_por_dia(app_mod, title, ref_fecha, expected):
    app = app_mod
    assert app._conectate_label_to_internal_key(title, ref_fecha_iso=ref_fecha) == expected


def test_espejo_ln_6pm_a_9pm_no_mezcla_horarios(app_mod):
    app = app_mod
    c = app.db()
    cur = c.cursor()
    fe = "2026-06-29"
    cur.execute(
        app._sql(
            """
            INSERT INTO resultados (lottery, draw, fecha, primero, segundo, tercero, confirmado)
            VALUES (%s, %s, %s, %s, %s, %s, 1)
            """
        ),
        ("Loteria Nacional", "6:00 PM", fe, "10", "20", "30"),
    )
    cur.execute(
        app._sql(
            """
            INSERT INTO resultados (lottery, draw, fecha, primero, segundo, tercero, confirmado)
            VALUES (%s, %s, %s, %s, %s, %s, 1)
            """
        ),
        ("Loteria Nacional", "9:00 PM", fe, "31", "07", "50"),
    )
    c.commit()
    app._resultado_espejo_ln_6pm_a_9pm_si_aplica(cur, fe)
    c.commit()
    cur.execute(
        app._sql(
            """
            SELECT primero, segundo, tercero FROM resultados
            WHERE lottery = %s AND draw = %s AND fecha = %s
            """
        ),
        ("Loteria Nacional", "9:00 PM", fe),
    )
    row = cur.fetchone()
    nums = (
        row["primero"] if hasattr(row, "get") else row[0],
        row["segundo"] if hasattr(row, "get") else row[1],
        row["tercero"] if hasattr(row, "get") else row[2],
    )
    assert nums == ("31", "07", "50")
    c.close()


def test_grilla_lunes_muestra_9pm_no_6pm_sin_espejo(app_mod):
    app = app_mod
    c = app.db()
    cur = c.cursor()
    hoy = "2026-06-29"
    viejo = "2026-06-27"
    cur.execute(
        app._sql(
            """
            INSERT INTO resultados (lottery, draw, fecha, primero, segundo, tercero)
            VALUES (%s, %s, %s, %s, %s, %s)
            """
        ),
        ("Loteria Nacional", "6:00 PM", hoy, "00", "97", "42"),
    )
    cur.execute(
        app._sql(
            """
            INSERT INTO resultados (lottery, draw, fecha, primero, segundo, tercero)
            VALUES (%s, %s, %s, %s, %s, %s)
            """
        ),
        ("Loteria Nacional", "9:00 PM", viejo, "31", "07", "50"),
    )
    c.commit()
    grid = app._ganadores_grilla_resultados_catalogo_fallback(cur, hoy)
    ln_rows = [r for r in grid if r.get("lottery") == "Loteria Nacional"]
    draws = {
        app.normalizar_sorteo(r.get("draw") or "") for r in ln_rows
    }
    d600 = app.normalizar_sorteo("6:00 PM")
    d900 = app.normalizar_sorteo("9:00 PM")
    assert d600 not in draws
    assert d900 in draws
    ln_9 = [r for r in ln_rows if app.normalizar_sorteo(r.get("draw") or "") == d900]
    assert len(ln_9) == 1
    assert ln_9[0]["primero"] == "31"
    assert str(ln_9[0].get("fecha") or "")[:10] == viejo
    c.close()


def test_filtrar_ln_oculta_6pm_entre_semana(app_mod):
    app = app_mod
    rows = [
        {"lottery": "Loteria Nacional", "draw": "6:00 PM", "primero": "1"},
        {"lottery": "Loteria Nacional", "draw": "9:00 PM", "primero": "2"},
    ]
    out = app._ganadores_resultados_filtrar_ln_por_dia_semana(
        rows, "2026-06-29", "2026-06-29"
    )
    draws = {app.normalizar_sorteo(r.get("draw") or "") for r in out}
    assert app.normalizar_sorteo("6:00 PM") not in draws
    assert app.normalizar_sorteo("9:00 PM") in draws


def test_filtrar_ln_oculta_9pm_domingo(app_mod):
    app = app_mod
    rows = [
        {"lottery": "Loteria Nacional", "draw": "6:00 PM", "primero": "1"},
        {"lottery": "Loteria Nacional", "draw": "9:00 PM", "primero": "2"},
    ]
    out = app._ganadores_resultados_filtrar_ln_por_dia_semana(
        rows, "2026-06-28", "2026-06-28"
    )
    draws = {app.normalizar_sorteo(r.get("draw") or "") for r in out}
    assert app.normalizar_sorteo("6:00 PM") in draws
    assert app.normalizar_sorteo("9:00 PM") not in draws
