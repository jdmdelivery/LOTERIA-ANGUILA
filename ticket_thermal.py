# -*- coding: utf-8 -*-
"""
Ticket térmico 58/80mm — adaptado para JDM ANGUILA.
Misma estructura visual de banca térmica dominicana (centrado, monoespaciado).
"""
from __future__ import annotations

import base64
import html
import os
from enum import Enum
from typing import List, Optional, Tuple

import config

CHARS_58 = 32
CHARS_80 = 42


class _LineKind(str, Enum):
    HEADER = "header"
    META = "meta"
    SEP = "sep"
    JUGADA = "jugada"
    LOTERIA = "loteria"
    PLAY = "play"
    TOTAL = "total"
    FOOTER = "footer"
    BLANK = "blank"
    WARN = "warn"


def _chars(width_mm: int = 58) -> int:
    return CHARS_80 if int(width_mm) >= 80 else CHARS_58


def _cp437(text: str) -> bytes:
    return str(text or "").encode("cp437", "replace")


def _money(value) -> str:
    try:
        return "{:.2f}".format(float(value or 0))
    except (TypeError, ValueError):
        return "0.00"


def _clip(text: str, width: int) -> str:
    return str(text or "")[:width]


def _center(text: str, width: int) -> str:
    return _clip(text, width).center(width)


def _sep(width: int) -> str:
    return "-" * width


def _lineas_venta(data: dict, width_mm: int = 58) -> Tuple[List[Tuple[str, _LineKind]], float]:
    w = _chars(width_mm)
    out: List[Tuple[str, _LineKind]] = []
    if data.get("reimpresion"):
        out.append((_center("*** REIMPRESIÓN ***", w), _LineKind.WARN))
    out.append((_center(str(data.get("banca") or config.BANK_NAME), w), _LineKind.HEADER))
    addr = str(data.get("direccion") or config.BANK_ADDRESS or "").strip()
    phone = str(data.get("telefono") or config.BANK_PHONE or "").strip()
    if addr:
        out.append((_center(addr, w), _LineKind.META))
    if phone:
        out.append((_center(phone, w), _LineKind.META))
    out.append((_center(_sep(w), w), _LineKind.SEP))
    out.append((_center("Ticket #%s" % (data.get("ticket") or ""), w), _LineKind.META))
    out.append((_center("Fecha: %s" % (data.get("fecha") or ""), w), _LineKind.META))
    if data.get("cajero"):
        out.append((_center("Cajero: %s" % data.get("cajero"), w), _LineKind.META))
    if data.get("sucursal"):
        out.append((_center("Sucursal: %s" % data.get("sucursal"), w), _LineKind.META))
    out.append((_center(_sep(w), w), _LineKind.SEP))
    out.append((_center(str(data.get("sorteo") or ""), w), _LineKind.LOTERIA))
    out.append((_center(_sep(w), w), _LineKind.SEP))

    total = 0.0
    quiniela = [j for j in (data.get("jugadas") or []) if str(j.get("modality") or j.get("tipo") or "").upper() == "QUINIELA"]
    pale = [j for j in (data.get("jugadas") or []) if str(j.get("modality") or j.get("tipo") or "").upper() == "PALE"]
    if quiniela:
        out.append((_center("QUINIELA", w), _LineKind.JUGADA))
        for j in quiniela:
            monto = float(j.get("monto") or j.get("amount") or 0)
            total += monto
            left = str(j.get("numeros") or j.get("numero") or "")
            right = "RD$%s" % _money(monto)
            pad = max(1, w - len(left) - len(right))
            out.append((_clip(left + (" " * pad) + right, w), _LineKind.PLAY))
    if pale:
        out.append((_center("PALÉ", w), _LineKind.JUGADA))
        for j in pale:
            monto = float(j.get("monto") or j.get("amount") or 0)
            total += monto
            left = str(j.get("numeros") or j.get("numero") or "")
            right = "RD$%s" % _money(monto)
            pad = max(1, w - len(left) - len(right))
            out.append((_clip(left + (" " * pad) + right, w), _LineKind.PLAY))

    if data.get("total") is not None:
        total = float(data.get("total"))
    out.append((_center(_sep(w), w), _LineKind.SEP))
    out.append((_center("TOTAL              RD$%s" % _money(total), w), _LineKind.TOTAL))
    out.append((_center("Estado: %s" % (data.get("estado") or "ACTIVO"), w), _LineKind.META))
    out.append((_center("Código: %s" % (data.get("codigo") or data.get("security_code") or ""), w), _LineKind.META))
    msg = str(data.get("mensaje") or config.TICKET_MESSAGE or "Conserve este ticket")
    out.append((_center(msg, w), _LineKind.FOOTER))
    return out, total


def _lineas_premio(data: dict, width_mm: int = 58) -> List[Tuple[str, _LineKind]]:
    w = _chars(width_mm)
    out: List[Tuple[str, _LineKind]] = []
    if data.get("reimpresion"):
        out.append((_center("*** PREMIO YA PAGADO ***", w), _LineKind.WARN))
    out.append((_center(str(data.get("banca") or config.BANK_NAME), w), _LineKind.HEADER))
    out.append((_center("PREMIO PAGADO", w), _LineKind.HEADER))
    out.append((_center(_sep(w), w), _LineKind.SEP))
    out.append((_center("Ticket ganador: #%s" % (data.get("ticket") or ""), w), _LineKind.META))
    if data.get("codigo"):
        out.append((_center("Código: %s" % data.get("codigo"), w), _LineKind.META))
    out.append((_center("Sorteo: %s" % (data.get("sorteo") or ""), w), _LineKind.META))
    if data.get("fecha_sorteo"):
        out.append((_center("Fecha sorteo: %s" % data.get("fecha_sorteo"), w), _LineKind.META))
    out.append((_center("Resultado: %s" % (data.get("resultado") or ""), w), _LineKind.LOTERIA))
    out.append((_center(_sep(w), w), _LineKind.SEP))
    for line in data.get("lineas") or []:
        out.append((_center(str(line.get("titulo") or ""), w), _LineKind.JUGADA))
        out.append((_center(str(line.get("detalle") or ""), w), _LineKind.PLAY))
    out.append((_center(_sep(w), w), _LineKind.SEP))
    out.append((_center("TOTAL PAGADO: RD$%s" % _money(data.get("total")), w), _LineKind.TOTAL))
    out.append((_center("Pagado por: %s" % (data.get("cajero") or ""), w), _LineKind.META))
    out.append((_center("Fecha: %s" % (data.get("fecha_pago") or ""), w), _LineKind.META))
    if data.get("caja"):
        out.append((_center("Caja: %s" % data.get("caja"), w), _LineKind.META))
    out.append((_center("Pago: %s" % (data.get("pago_uid") or ""), w), _LineKind.META))
    out.append((_center("Firma: ______________________", w), _LineKind.FOOTER))
    return out


def generar_ticket(data: dict, width_mm: int = 58) -> str:
    lines, _ = _lineas_venta(data, width_mm)
    return "\n".join(t for t, _k in lines) + "\n"


def generar_recibo_premio(data: dict, width_mm: int = 58) -> str:
    lines = _lineas_premio(data, width_mm)
    return "\n".join(t for t, _k in lines) + "\n"


def render_ticket_html(data: dict, width_mm: int = 58) -> str:
    lines, total = _lineas_venta(data, width_mm)
    parts = []
    for txt, kind in lines:
        cls = {
            _LineKind.HEADER: "header",
            _LineKind.TOTAL: "total",
            _LineKind.FOOTER: "footer",
            _LineKind.LOTERIA: "loteria-title",
            _LineKind.JUGADA: "jugada-title",
            _LineKind.WARN: "header",
            _LineKind.PLAY: "play-row",
            _LineKind.META: "info",
            _LineKind.SEP: "line",
        }.get(kind, "line")
        parts.append('<div class="%s">%s</div>' % (cls, html.escape(txt)))
    _ = total
    return "\n".join(parts)


def render_premio_html(data: dict, width_mm: int = 58) -> str:
    lines = _lineas_premio(data, width_mm)
    parts = []
    for txt, kind in lines:
        cls = {
            _LineKind.HEADER: "header",
            _LineKind.TOTAL: "total",
            _LineKind.FOOTER: "footer",
            _LineKind.LOTERIA: "loteria-title",
            _LineKind.JUGADA: "jugada-title",
            _LineKind.WARN: "header",
            _LineKind.PLAY: "line",
            _LineKind.META: "info",
            _LineKind.SEP: "line",
        }.get(kind, "line")
        parts.append('<div class="%s">%s</div>' % (cls, html.escape(txt)))
    return "\n".join(parts)


def esc_init() -> bytes:
    return b"\x1b\x40"


def esc_align(mode: int = 1) -> bytes:
    return bytes([0x1B, 0x61, max(0, min(2, mode))])


def esc_feed(n: int = 1) -> bytes:
    return bytes([0x1B, 0x64, max(0, min(255, int(n)))])


def esc_bold(on: bool = True) -> bytes:
    return bytes([0x1B, 0x45, 1 if on else 0])


def esc_size(width: int = 1, height: int = 1) -> bytes:
    w = max(1, min(8, int(width))) - 1
    h = max(1, min(8, int(height))) - 1
    return bytes([0x1D, 0x21, (h << 4) | w])


def esc_reset_style() -> bytes:
    return esc_size(1, 1) + esc_bold(False)


def esc_text_line(text: str) -> bytes:
    return _cp437(text) + b"\n"


def _esc_linea(text: str, kind: _LineKind) -> bytes:
    buf = bytearray()
    if kind == _LineKind.HEADER or kind == _LineKind.TOTAL or kind == _LineKind.WARN:
        buf += esc_size(2, 2)
        buf += esc_bold(True)
    elif kind in (_LineKind.JUGADA, _LineKind.LOTERIA):
        buf += esc_size(1, 2)
        buf += esc_bold(True)
    else:
        buf += esc_size(1, 1)
        buf += esc_bold(True)
    buf += esc_text_line(text)
    buf += esc_reset_style()
    return bytes(buf)


def generar_ticket_escpos(data: dict, width_mm: int = 58) -> bytes:
    lines, _ = _lineas_venta(data, width_mm)
    buf = bytearray()
    buf += esc_init()
    buf += esc_align(1)
    for txt, kind in lines:
        buf += _esc_linea(txt, kind)
    # QR con código de seguridad
    code = str(data.get("codigo") or data.get("security_code") or "")
    if code:
        payload = _cp437(code)
        ms = 6
        length = len(payload) + 3
        buf += (
            b"\x1d\x28\x6b\x04\x00\x31\x41\x32\x00"
            + b"\x1d\x28\x6b\x03\x00\x31\x43"
            + bytes([ms])
            + b"\x1d\x28\x6b"
            + bytes([length & 0xFF, (length >> 8) & 0xFF])
            + b"\x31\x50\x30"
            + payload
            + b"\x1d\x28\x6b\x03\x00\x31\x51\x30"
        )
    buf += esc_feed(4)
    return bytes(buf)


def generar_premio_escpos(data: dict, width_mm: int = 58) -> bytes:
    lines = _lineas_premio(data, width_mm)
    buf = bytearray()
    buf += esc_init()
    buf += esc_align(1)
    for txt, kind in lines:
        buf += _esc_linea(txt, kind)
    buf += esc_feed(4)
    return bytes(buf)


def ticket_escpos_b64(data: dict, width_mm: int = 58) -> str:
    return base64.b64encode(generar_ticket_escpos(data, width_mm)).decode("ascii")


def premio_escpos_b64(data: dict, width_mm: int = 58) -> str:
    return base64.b64encode(generar_premio_escpos(data, width_mm)).decode("ascii")


def render_ticket_page_html(data: dict, width_mm: int = 58, kind: str = "venta") -> str:
    body = render_premio_html(data, width_mm) if kind == "premio" else render_ticket_html(data, width_mm)
    b64 = premio_escpos_b64(data, width_mm) if kind == "premio" else ticket_escpos_b64(data, width_mm)
    plain = generar_recibo_premio(data, width_mm) if kind == "premio" else generar_ticket(data, width_mm)
    mm = 80 if int(width_mm) >= 80 else 58
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{html.escape(config.BANK_NAME)} Ticket</title>
<link rel="stylesheet" href="/static/ticket_thermal.css"/>
<style>@page {{ size: {mm}mm auto; margin: 0; }} .ticket-thermal {{ width: {mm}mm; }}</style>
</head>
<body class="ticket-body">
<button class="btn-print-top no-print" id="printBtn" type="button">Imprimir</button>
<div class="ticket-container">
<div class="ticket ticket-thermal" data-ticket-id="{html.escape(str(data.get('ticket') or ''))}" data-escpos-b64="{b64}">
{body}
</div>
<pre class="no-print" style="display:none" id="ticketPlain">{html.escape(plain)}</pre>
</div>
<script src="/static/print_ticket_app.js"></script>
<script>document.getElementById('printBtn').addEventListener('click', function(){{ window.print(); }});</script>
</body></html>"""


TICKET_THERMAL_CSS_PATH = os.path.join(os.path.dirname(__file__), "static", "ticket_thermal.css")
