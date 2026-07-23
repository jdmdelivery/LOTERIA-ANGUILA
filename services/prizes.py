# -*- coding: utf-8 -*-
"""Cálculo de Quiniela y Palé usando snapshot de pagos."""
from __future__ import annotations

from typing import Any


def pay_snapshot(src: dict | None = None) -> dict:
    import config

    base = dict(config.DEFAULT_PAY_SNAPSHOT)
    if src:
        for k in ("quiniela_primera", "quiniela_segunda", "quiniela_tercera", "pale"):
            if k in src and src[k] is not None:
                base[k] = float(src[k])
    return base


def normalize_number(value: Any) -> str:
    s = str(value or "").strip()
    if s.startswith("+"):
        s = s[1:]
    if not s.isdigit():
        raise ValueError("numero_invalido")
    n = int(s)
    if n < 0 or n > 99:
        raise ValueError("numero_fuera_rango")
    return f"{n:02d}"


def normalize_pale(a: Any, b: Any) -> str:
    x = normalize_number(a)
    y = normalize_number(b)
    return "-".join(sorted([x, y]))


def calc_quiniela(
    number: Any,
    amount: float,
    primera: str,
    segunda: str,
    tercera: str,
    snapshot: dict | None = None,
) -> tuple[float, list[dict]]:
    """Suma todas las posiciones donde aparece el número."""
    snap = pay_snapshot(snapshot)
    num = normalize_number(number)
    p1, p2, p3 = normalize_number(primera), normalize_number(segunda), normalize_number(tercera)
    amt = float(amount)
    detail = []
    total = 0.0
    positions = [
        ("primera", p1, float(snap["quiniela_primera"])),
        ("segunda", p2, float(snap["quiniela_segunda"])),
        ("tercera", p3, float(snap["quiniela_tercera"])),
    ]
    for name, val, mult in positions:
        if num == val:
            prize = amt * mult
            total += prize
            detail.append(
                {
                    "posicion": name,
                    "numero": num,
                    "monto": amt,
                    "multiplicador": mult,
                    "premio": prize,
                }
            )
    return total, detail


def calc_pale(
    numbers: Any,
    amount: float,
    primera: str,
    segunda: str,
    tercera: str,
    snapshot: dict | None = None,
) -> tuple[float, list[dict]]:
    """Gana si ambos números aparecen en las 3 posiciones (sin importar orden)."""
    snap = pay_snapshot(snapshot)
    raw = str(numbers or "").replace(" ", "")
    parts = [p for p in raw.replace("/", "-").split("-") if p]
    if len(parts) != 2:
        raise ValueError("pale_invalido")
    combo = normalize_pale(parts[0], parts[1])
    a, b = combo.split("-")
    pool = {
        normalize_number(primera),
        normalize_number(segunda),
        normalize_number(tercera),
    }
    amt = float(amount)
    if a in pool and b in pool:
        mult = float(snap["pale"])
        prize = amt * mult
        return prize, [
            {
                "modalidad": "PALE",
                "combinacion": combo,
                "monto": amt,
                "multiplicador": mult,
                "premio": prize,
            }
        ]
    return 0.0, []
