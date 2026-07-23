# -*- coding: utf-8 -*-
"""Validación estricta de resultados Anguila."""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

import config
from services.prizes import normalize_number


def validate_result(
    primera,
    segunda,
    tercera,
    *,
    draw_date: str,
    sorteo_code: str,
    after_draw: bool = True,
    now: Optional[datetime] = None,
    reject_cuarteta: bool = True,
) -> tuple[bool, str]:
    src = config.SOURCES_BY_CODE.get(sorteo_code)
    if not src:
        return False, "sorteo_desconocido"
    if src.get("estado_fuente") == "FUENTE_NO_DISPONIBLE" and after_draw:
        # Auto-confirmación prohibida; entrada manual usa after_draw=False vía flag admin
        pass

    try:
        nums = [
            normalize_number(primera),
            normalize_number(segunda),
            normalize_number(tercera),
        ]
    except ValueError as e:
        return False, str(e)

    if len(nums) != 3:
        return False, "deben_ser_exactamente_tres"

    # Rechazo explícito de patrones Cuarteta (4 números)
    if reject_cuarteta:
        joined = f"{primera}-{segunda}-{tercera}"
        parts = [p for p in str(joined).replace(" ", "").split("-") if p != ""]
        if len(parts) > 3:
            return False, "parece_cuarteta"

    # Fecha YYYY-MM-DD
    try:
        d = date.fromisoformat(str(draw_date)[:10])
    except ValueError:
        return False, "fecha_invalida"

    if after_draw:
        import pytz

        tz = pytz.timezone(config.TIMEZONE)
        now = now or datetime.now(tz)
        if now.tzinfo is None:
            now = tz.localize(now)
        else:
            now = now.astimezone(tz)
        hh, mm = map(int, src["hora_oficial"].split(":"))
        draw_dt = tz.localize(datetime(d.year, d.month, d.day, hh, mm, 0))
        if now < draw_dt:
            return False, "resultado_antes_del_cierre"

    return True, "ok"


def is_cuarteta_score(score_row) -> bool:
    if not isinstance(score_row, (list, tuple)):
        return False
    filled = [x for x in score_row if str(x).strip() != ""]
    return len(filled) == 4
