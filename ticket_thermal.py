# -*- coding: utf-8 -*-
"""
Ticket térmico 58mm — banca dominicana: centrado, grande, profesional.
HTML + CSS impresión, texto plano y ESC/POS (RawBT / Sunmi / Bluetooth / Android).
"""
from __future__ import annotations

import base64
import html
import os
import re
from collections import defaultdict
from enum import Enum
from typing import Dict, List, Optional, Tuple

TICKET_WIDTH_MM = 58
CHARS = 32


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


def _cp437(text: str) -> bytes:
    return str(text or "").encode("cp437", "replace")


def _money(value) -> str:
    try:
        return "{:.2f}".format(float(value or 0))
    except (TypeError, ValueError):
        return "0.00"


def _clip(text: str, width: int = CHARS) -> str:
    return str(text or "")[:width]


def _center(text: str, width: int = CHARS) -> str:
    return _clip(text, width).center(width)


def _sep(width: int = CHARS) -> str:
    return "-" * width


def _hora_display(raw: str) -> str:
    s = str(raw or "").strip()
    if not s:
        return ""
    if re.search(r"(AM|PM)", s, re.I):
        m = re.search(r"(\d{1,2}:\d{2}\s*(?:AM|PM))", s, re.I)
        if m:
            parts = re.match(r"(\d{1,2}):(\d{2})\s*(AM|PM)", m.group(1), re.I)
            if parts:
                h12 = int(parts.group(1)) % 12 or 12
                return "%d:%02d %s" % (h12, int(parts.group(2)), parts.group(3).upper())
            return m.group(1).upper()
        return s.upper()
    m = re.match(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?", s)
    if m:
        h, mi = int(m.group(1)), int(m.group(2))
        ap = "AM" if h < 12 else "PM"
        h12 = h % 12 or 12
        return "%d:%02d %s" % (h12, mi, ap)
    return s


def _draw_display(hora: str) -> str:
    s = str(hora or "").strip()
    if s.lower().startswith("domingos "):
        s = s[9:].strip()
    return _hora_display(s) or s


def _lot_sorteo_line(loteria: str, hora: str) -> str:
    lot = str(loteria or "").strip()
    draw = _draw_display(hora)
    if lot and draw:
        return "%s %s" % (lot, draw)
    return lot or draw


def _numero_sort_key(numero: str):
    partes = re.split(r"[-\s]+", str(numero or "").strip())
    out = []
    for p in partes:
        try:
            out.append((0, int(p)))
        except ValueError:
            out.append((1, p))
    return tuple(out)


def _jugada_linea(numero: str, monto) -> str:
    """58  -  RD$25.00 centrado en 58mm."""
    n = str(numero or "").strip()
    amt = "RD$%s" % _money(monto)
    return _center("%s  -  %s" % (n, amt))


def _agrupar_por_loteria(jugadas: List[dict]) -> Tuple[List[dict], float]:
    tree: Dict[Tuple[str, str], List[dict]] = defaultdict(list)
    total = 0.0
    for j in jugadas or []:
        lot = str(j.get("loteria") or j.get("lottery") or "").strip()
        hora = str(j.get("hora") or j.get("draw") or "").strip()
        num = str(j.get("numeros") or j.get("numero") or j.get("number") or "").strip()
        try:
            monto = float(j.get("monto") or j.get("amount") or 0)
        except (TypeError, ValueError):
            monto = 0.0
        total += monto
        tree[(lot, hora)].append({"numero": num, "monto": monto})

    bloques: List[dict] = []
    for key in sorted(tree.keys(), key=lambda k: (k[0].lower(), k[1])):
        filas = sorted(tree[key], key=lambda x: _numero_sort_key(x.get("numero")))
        bloques.append({"encabezado": _lot_sorteo_line(key[0], key[1]), "filas": filas})
    return bloques, total


def _lineas_ticket_estructurado(data: dict) -> Tuple[List[Tuple[str, _LineKind]], float]:
    bloques, total = _agrupar_por_loteria(data.get("jugadas") or [])
    out: List[Tuple[str, _LineKind]] = []

    out.append((_center("LA QUE NUNCA FALLA ANGUILA"), _LineKind.HEADER))
    out.append((_center("NO PAGAMOS SIN TICKET"), _LineKind.HEADER))
    out.append((_center(_sep()), _LineKind.SEP))

    fecha = str(data.get("fecha") or "").strip()
    hora = _hora_display(data.get("hora") or data.get("hora_venta") or "")
    if fecha and hora:
        out.append((_center("Fecha: %s Hora: %s" % (fecha, hora)), _LineKind.META))
    elif fecha:
        out.append((_center("Fecha: %s" % fecha), _LineKind.META))
    elif hora:
        out.append((_center("Hora: %s" % hora), _LineKind.META))

    out.append(
        (
            _center(
                "Ticket: %s ID: %s"
                % (data.get("ticket") or "", data.get("id") or data.get("ticket") or "")
            ),
            _LineKind.META,
        )
    )
    cajero = str(data.get("cajero") or "").strip()
    if cajero:
        out.append((_center("Cajero: %s" % cajero), _LineKind.META))

    out.append((_center(_sep()), _LineKind.SEP))
    out.append((_center("JUGADA:"), _LineKind.JUGADA))
    out.append((_center(_sep()), _LineKind.SEP))

    for bloque in bloques:
        out.append((_center(bloque["encabezado"]), _LineKind.LOTERIA))
        for fila in bloque["filas"]:
            out.append((_jugada_linea(fila["numero"], fila["monto"]), _LineKind.PLAY))
        out.append((_center(_sep()), _LineKind.SEP))

    out.append((_center("TOTAL RD$%s" % _money(total)), _LineKind.TOTAL))
    out.append((_center(_sep()), _LineKind.SEP))
    out.append((_center("REVISA SU TICKET"), _LineKind.FOOTER))
    out.append((_center("BUENA SUERTE"), _LineKind.FOOTER))

    return out, total


def generar_ticket(data: dict) -> str:
    estructurado, _ = _lineas_ticket_estructurado(data)
    parts: List[str] = []
    for txt, kind in estructurado:
        if kind == _LineKind.BLANK:
            parts.append("")
        else:
            parts.append(txt if txt is not None else "")
    return "\n".join(parts) + "\n"


def render_ticket_html(data: dict, qr_url: Optional[str] = None) -> str:
    """HTML semántico 58mm para navegador / impresión (sin QR)."""
    _ = qr_url  # obsoleto; se ignora
    bloques, total = _agrupar_por_loteria(data.get("jugadas") or [])
    fecha = str(data.get("fecha") or "").strip()
    hora = _hora_display(data.get("hora") or data.get("hora_venta") or "")
    cajero = str(data.get("cajero") or "").strip()
    ticket_pub = str(data.get("ticket") or "")
    ticket_id = str(data.get("id") or ticket_pub)

    parts: List[str] = []
    parts.append('<div class="header">LA QUE NUNCA FALLA ANGUILA</div>')
    parts.append('<div class="header">NO PAGAMOS SIN TICKET</div>')
    parts.append('<div class="line">%s</div>' % html.escape(_sep()))

    if fecha and hora:
        parts.append(
            '<div class="info">Fecha: %s Hora: %s</div>'
            % (html.escape(fecha), html.escape(hora))
        )
    elif fecha:
        parts.append('<div class="info">Fecha: %s</div>' % html.escape(fecha))
    elif hora:
        parts.append('<div class="info">Hora: %s</div>' % html.escape(hora))

    parts.append(
        '<div class="info">Ticket: %s ID: %s</div>'
        % (html.escape(ticket_pub), html.escape(ticket_id))
    )
    if cajero:
        parts.append('<div class="info">Cajero: %s</div>' % html.escape(cajero))

    parts.append('<div class="line">%s</div>' % html.escape(_sep()))
    parts.append('<div class="jugada-title">JUGADA:</div>')
    parts.append('<div class="line">%s</div>' % html.escape(_sep()))

    for bloque in bloques:
        parts.append(
            '<div class="loteria-title">%s</div>' % html.escape(bloque["encabezado"])
        )
        for fila in bloque["filas"]:
            n = html.escape(str(fila["numero"] or "").strip())
            amt = html.escape("RD$%s" % _money(fila["monto"]))
            parts.append(
                '<div class="play-row">'
                '<span class="play-number">%s  -</span>'
                '<span class="play-amount">%s</span>'
                "</div>" % (n, amt)
            )
        parts.append('<div class="line">%s</div>' % html.escape(_sep()))

    parts.append('<div class="total">TOTAL RD$%s</div>' % html.escape(_money(total)))
    parts.append('<div class="line">%s</div>' % html.escape(_sep()))
    parts.append('<div class="footer">REVISA SU TICKET</div>')
    parts.append('<div class="footer">BUENA SUERTE</div>')

    return "\n".join(parts)


# --- ESC/POS ---

def esc_init() -> bytes:
    return b"\x1b\x40"


def esc_align(mode: int = 0) -> bytes:
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
    if kind == _LineKind.BLANK:
        return esc_text_line("")

    if kind == _LineKind.HEADER:
        buf += esc_size(2, 2)
        buf += esc_bold(True)
    elif kind == _LineKind.TOTAL:
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


def qr_code_escpos(data: str, module_size: int = 10) -> bytes:
    payload = _cp437(str(data or ""))
    ms = max(4, min(16, int(module_size)))
    length = len(payload) + 3
    return (
        b"\x1d\x28\x6b\x04\x00\x31\x41\x32\x00"
        + b"\x1d\x28\x6b\x03\x00\x31\x43" + bytes([ms])
        + b"\x1d\x28\x6b"
        + bytes([length & 0xFF, (length >> 8) & 0xFF])
        + b"\x31\x50\x30"
        + payload
        + b"\x1d\x28\x6b\x03\x00\x31\x51\x30"
    )


def generar_ticket_escpos(data: dict, qr_url: Optional[str] = None) -> bytes:
    _ = qr_url  # obsoleto; sin QR en ticket de venta
    estructurado, _ = _lineas_ticket_estructurado(data)
    buf = bytearray()
    buf += esc_init()
    buf += esc_align(1)
    for txt, kind in estructurado:
        buf += _esc_linea(txt, kind)
    buf += esc_feed(4)
    return bytes(buf)


def ticket_escpos_b64(data: dict, qr_url: Optional[str] = None) -> str:
    return base64.b64encode(generar_ticket_escpos(data, qr_url)).decode("ascii")


def generar_recibo_pago_escpos(
    ticket_id,
    premio,
    cajero,
    fecha,
    lottery="",
    play="",
    numero_ganador="",
) -> bytes:
    buf = bytearray()
    buf += esc_init()
    buf += esc_align(1)
    buf += _esc_linea("LA QUE NUNCA FALLA ANGUILA", _LineKind.HEADER)
    buf += _esc_linea("PAGO DE PREMIO", _LineKind.JUGADA)
    buf += _esc_linea(_sep(), _LineKind.SEP)
    buf += _esc_linea("Ticket: %s" % ticket_id, _LineKind.META)
    buf += _esc_linea("Cajero: %s" % cajero, _LineKind.META)
    buf += _esc_linea("Fecha: %s" % fecha, _LineKind.META)
    if lottery:
        buf += _esc_linea(str(lottery).strip(), _LineKind.LOTERIA)
    if play:
        buf += _esc_linea("Jugada: %s" % play, _LineKind.META)
    if numero_ganador:
        buf += _esc_linea(str(numero_ganador), _LineKind.PLAY)
    buf += _esc_linea(_sep(), _LineKind.SEP)
    buf += _esc_linea("TOTAL RD$%s" % _money(premio), _LineKind.TOTAL)
    buf += _esc_linea(_sep(), _LineKind.SEP)
    buf += _esc_linea("PREMIO PAGADO", _LineKind.FOOTER)
    buf += esc_feed(4)
    return bytes(buf)


def recibo_pago_escpos_b64(**kwargs) -> str:
    return base64.b64encode(generar_recibo_pago_escpos(**kwargs)).decode("ascii")


TICKET_THERMAL_CSS = open(
    os.path.join(os.path.dirname(__file__), "static", "ticket_thermal.css"),
    encoding="utf-8",
).read() if os.path.isfile(os.path.join(os.path.dirname(__file__), "static", "ticket_thermal.css")) else ""
