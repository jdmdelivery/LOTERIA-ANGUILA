#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Reporte de impacto: Quinielas afectadas cuando el mismo número del resultado
aparece en 2 o 3 posiciones (regla nueva: un premio_shard por posición).

Solo analiza / corrige jugadas afectadas; no recalcula todo el día.

Uso:
  set DATABASE_URL=postgresql://...   # producción Render
  python scripts/reporte_quiniela_repetidas_impacto.py --dry-run
  python scripts/reporte_quiniela_repetidas_impacto.py --dry-run --fecha-desde 2026-05-01
  python scripts/reporte_quiniela_repetidas_impacto.py --apply --fecha-desde 2026-05-01

Con --apply:
  - Inserta/actualiza premios PENDIENTES faltantes vía _premios_upsert_pendiente.
  - No borra premios pagados ni duplica premio_shard existente.
  - No modifica filas pagadas (solo las reporta para confirmación manual).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _row_dict(row):
    if row is None:
        return {}
    if hasattr(row, "keys"):
        return dict(row)
    return {}


def _resultado_tiene_repeticion(app, r1, r2, r3):
    a = app._norm_sorteo_dos_digitos(r1)
    b = app._norm_sorteo_dos_digitos(r2)
    c = app._norm_sorteo_dos_digitos(r3)
    if not a or not b or not c:
        return False
    return len({a, b, c}) < 3


def _jugados_quiniela(app, numero_campo):
    jugados = list(app._quiniela_jugados_desde_campo(numero_campo) or [])
    if jugados:
        return [str(j).strip().zfill(2) for j in jugados if str(j).strip()]
    n_one = app._jugada_simple_int(app.normalizar_numero(numero_campo))
    if n_one is not None:
        return [str(n_one).zfill(2)]
    return []


def _linea_afectada_por_repeticion(app, numero_campo, r1, r2, r3):
    """True si algún número jugado coincide en 2+ posiciones del resultado repetido."""
    if not _resultado_tiene_repeticion(app, r1, r2, r3):
        return False
    slots = [
        app._norm_sorteo_dos_digitos(r1),
        app._norm_sorteo_dos_digitos(r2),
        app._norm_sorteo_dos_digitos(r3),
    ]
    for j in _jugados_quiniela(app, numero_campo):
        hits = sum(1 for s in slots if s and j == s)
        if hits >= 2:
            return True
    return False


def _fetch_premios_linea(cur, app, line_id):
    cur.execute(
        app._sql(
            """
            SELECT id, premio_shard, premio, estado, numero, ticket_id
            FROM premios
            WHERE line_id = %s
            ORDER BY premio_shard ASC, id ASC
            """
        ),
        (int(line_id),),
    )
    out = []
    for row in cur.fetchall() or []:
        d = _row_dict(row)
        if not d and row is not None:
            d = {
                "id": row[0],
                "premio_shard": row[1],
                "premio": row[2],
                "estado": row[3],
                "numero": row[4],
                "ticket_id": row[5],
            }
        out.append(d)
    return out


def _analizar_linea(app, cur, ld, pagos, fecha_rd):
    play_eff = app._play_efectivo_cruce(ld.get("play"), ld.get("number"))
    if play_eff != "Quiniela":
        return None
    fe = str(ld.get("fecha_sorteo") or fecha_rd or "").strip()[:10]
    triple, err, _info = app._resultado_sorteo_resolver_estricto(
        cur, ld.get("lottery"), ld.get("draw"), fe
    )
    if not triple or err:
        return None
    r1, r2, r3 = triple[0], triple[1], triple[2]
    if not _linea_afectada_por_repeticion(app, ld.get("number"), r1, r2, r3):
        return None
    try:
        amt = float(ld.get("amount") or 0)
    except (TypeError, ValueError):
        return None
    if amt <= 0:
        return None
    Pm = app._merge_pagos_calc(pagos)
    frags = app._quiniela_premio_fragmentos(ld.get("number"), amt, r1, r2, r3, Pm)
    if not frags:
        return None
    esperado = {
        str(f["premio_shard"]): round(float(f.get("premio") or 0), 2) for f in frags
    }
    lid = int(ld.get("line_id") or 0)
    existentes = _fetch_premios_linea(cur, app, lid)
    por_shard = {}
    for p in existentes:
        sh = app._premio_shard_norm(p)
        por_shard.setdefault(sh, []).append(p)

    faltantes = []
    actualizar_pendiente = []
    pagados_ok = []
    pagados_diferencia = []
    for sh, premio_esperado in sorted(esperado.items()):
        filas = por_shard.get(sh) or []
        if not filas:
            faltantes.append({"premio_shard": sh, "premio": premio_esperado})
            continue
        f0 = filas[0]
        est = str(f0.get("estado") or "").strip().lower()
        prem_db = round(float(f0.get("premio") or 0), 2)
        if est == "pagado":
            if abs(prem_db - premio_esperado) > 0.02:
                pagados_diferencia.append(
                    {
                        "premio_id": f0.get("id"),
                        "premio_shard": sh,
                        "premio_db": prem_db,
                        "premio_esperado": premio_esperado,
                        "delta": round(premio_esperado - prem_db, 2),
                    }
                )
            else:
                pagados_ok.append(sh)
        elif est == "pendiente":
            if abs(prem_db - premio_esperado) > 0.02:
                actualizar_pendiente.append(
                    {
                        "premio_id": f0.get("id"),
                        "premio_shard": sh,
                        "premio_db": prem_db,
                        "premio_esperado": premio_esperado,
                    }
                )
        else:
            pagados_ok.append(sh)

    shards_extra = [
        sh for sh in por_shard.keys() if sh not in esperado and sh != "0"
    ]
    delta_pendiente = sum(x["premio"] for x in faltantes)
    delta_pendiente += sum(
        max(0.0, x["premio_esperado"] - x["premio_db"]) for x in actualizar_pendiente
    )
    necesita_accion = bool(faltantes or actualizar_pendiente)
    return {
        "ticket_id": ld.get("ticket_id"),
        "line_id": lid,
        "lottery": ld.get("lottery"),
        "draw": ld.get("draw"),
        "fecha_sorteo": fe,
        "numero": ld.get("number"),
        "monto": amt,
        "resultado": "%s-%s-%s" % (r1, r2, r3),
        "premio_esperado_total": round(sum(esperado.values()), 2),
        "premio_shards_esperados": esperado,
        "faltantes": faltantes,
        "actualizar_pendiente": actualizar_pendiente,
        "pagados_diferencia": pagados_diferencia,
        "shards_extra_pendientes": shards_extra,
        "delta_pendiente_rd": round(delta_pendiente, 2),
        "necesita_accion": necesita_accion,
    }


def _enumerar_lineas_quiniela(cur, app, fecha_desde=None, fecha_hasta=None):
    params = []
    where = [
        "COALESCE(tl.estado, 'activo') <> 'cancelado'",
        "lower(replace(trim(COALESCE(tl.play, '')), ' ', '')) LIKE 'quiniela%'",
    ]
    if fecha_desde:
        where.append("substr(trim(COALESCE(tl.fecha_sorteo, '')), 1, 10) >= %s")
        params.append(fecha_desde)
    if fecha_hasta:
        where.append("substr(trim(COALESCE(tl.fecha_sorteo, '')), 1, 10) <= %s")
        params.append(fecha_hasta)
    sql = (
        """
        SELECT tl.ticket_id, tl.id AS line_id, tl.lottery, tl.draw,
               tl.fecha_sorteo, tl.number, tl.amount, tl.play,
               tk.banca_id, tk.cajero
        FROM ticket_lines tl
        INNER JOIN tickets tk ON tk.id = tl.ticket_id
        WHERE """
        + " AND ".join(where)
        + app._sql_ticket_no_eliminado("tk")
        + """
        ORDER BY tl.fecha_sorteo DESC, tl.ticket_id DESC, tl.id DESC
        """
    )
    cur.execute(app._sql(sql), tuple(params))
    rows = []
    for row in cur.fetchall() or []:
        if hasattr(row, "keys"):
            rows.append(dict(row))
        else:
            rows.append(
                {
                    "ticket_id": row[0],
                    "line_id": row[1],
                    "lottery": row[2],
                    "draw": row[3],
                    "fecha_sorteo": row[4],
                    "number": row[5],
                    "amount": row[6],
                    "play": row[7],
                    "banca_id": row[8],
                    "cajero": row[9],
                }
            )
    return rows


def _aplicar_linea(app, cur, ld, pagos, fecha_rd):
    gan = app._recalc_linea_directa_a_ganador(cur, ld, pagos, fecha_rd)
    if not gan:
        return {"line_id": ld.get("line_id"), "ok": False, "motivo": "sin_ganador"}
    creados = 0
    actualizados = 0
    omitidos = 0
    for g in gan:
        if app._premios_linea_tiene_invalidacion_manual(cur, int(g.get("line_id") or 0)):
            omitidos += 1
            continue
        pid_antes = app._premios_id_linea_shard(cur, int(g["line_id"]), app._premio_shard_norm(g))
        if pid_antes:
            cur.execute(
                app._sql("SELECT lower(trim(COALESCE(estado,''))) AS e FROM premios WHERE id = %s"),
                (pid_antes,),
            )
            rr = cur.fetchone()
            est = (
                (rr.get("e") if hasattr(rr, "get") else (rr[0] if rr else "")) or ""
            ).strip().lower()
            if est == "pagado":
                omitidos += 1
                continue
        if app._premios_upsert_pendiente(cur, g):
            if pid_antes:
                actualizados += 1
            else:
                creados += 1
        else:
            omitidos += 1
    return {
        "line_id": ld.get("line_id"),
        "ticket_id": ld.get("ticket_id"),
        "ok": True,
        "creados": creados,
        "actualizados": actualizados,
        "omitidos": omitidos,
    }


def main():
    parser = argparse.ArgumentParser(description="Impacto Quiniela números repetidos en resultado.")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Solo reporte (default).")
    parser.add_argument("--apply", action="store_true", help="Aplicar upsert solo en líneas afectadas.")
    parser.add_argument("--fecha-desde", default="", help="YYYY-MM-DD inclusive.")
    parser.add_argument("--fecha-hasta", default="", help="YYYY-MM-DD inclusive.")
    parser.add_argument("--json", action="store_true", help="Salida JSON.")
    args = parser.parse_args()
    dry_run = not args.apply

    import app

    if not os.environ.get("DATABASE_URL"):
        print(
            "ERROR: define DATABASE_URL (PostgreSQL de Render) para analizar producción.",
            file=sys.stderr,
        )
        sys.exit(2)

    conn = app.db()
    if not conn:
        print("ERROR: no hay conexión a la base de datos.", file=sys.stderr)
        sys.exit(2)

    pagos = dict(app.PAGOS)
    try:
        cur = conn.cursor()
        cfg = app._ganadores_try_load_pagos_config(cur) or {}
        pagos.update(cfg)
    except Exception:
        cur = conn.cursor()

    afectadas = []
    tickets = set()
    total_delta = 0.0
    pagados_manual = []

    try:
        lineas = _enumerar_lineas_quiniela(
            cur, app, fecha_desde=(args.fecha_desde or None), fecha_hasta=(args.fecha_hasta or None)
        )
        for ld in lineas:
            item = _analizar_linea(app, cur, ld, pagos, ld.get("fecha_sorteo"))
            if not item:
                continue
            if not item.get("necesita_accion") and not item.get("pagados_diferencia"):
                continue
            afectadas.append(item)
            tickets.add(int(item.get("ticket_id") or 0))
            total_delta += float(item.get("delta_pendiente_rd") or 0)
            if item.get("pagados_diferencia"):
                pagados_manual.extend(item["pagados_diferencia"])

        aplicados = []
        if not dry_run and afectadas:
            for item in afectadas:
                if not item.get("necesita_accion"):
                    continue
                ld = {
                    "ticket_id": item["ticket_id"],
                    "line_id": item["line_id"],
                    "lottery": item["lottery"],
                    "draw": item["draw"],
                    "fecha_sorteo": item["fecha_sorteo"],
                    "number": item["numero"],
                    "amount": item["monto"],
                    "play": "Quiniela",
                }
                aplicados.append(_aplicar_linea(app, cur, ld, pagos, item["fecha_sorteo"]))
            conn.commit()

        resumen = {
            "ok": True,
            "dry_run": dry_run,
            "fecha_desde": args.fecha_desde or None,
            "fecha_hasta": args.fecha_hasta or None,
            "lineas_quiniela_revisadas": len(lineas),
            "jugadas_afectadas": len(afectadas),
            "tickets_afectados": len(tickets),
            "delta_pendiente_total_rd": round(total_delta, 2),
            "premios_pagados_con_diferencia": len(pagados_manual),
            "pagados_diferencia": pagados_manual,
            "detalle": afectadas,
            "aplicados": aplicados,
        }
    except Exception as ex:
        try:
            conn.rollback()
        except Exception:
            pass
        print("ERROR:", ex, file=sys.stderr)
        sys.exit(1)
    finally:
        try:
            conn.close()
        except Exception:
            pass

    if args.json:
        print(json.dumps(resumen, ensure_ascii=False, indent=2))
        return

    print("=== Reporte Quiniela — número repetido en resultado ===")
    print("Modo:", "DRY-RUN (sin cambios)" if dry_run else "APPLY (solo pendientes faltantes)")
    print("Líneas Quiniela revisadas:", resumen["lineas_quiniela_revisadas"])
    print("Jugadas afectadas (requieren acción o revisión):", resumen["jugadas_afectadas"])
    print("Tickets distintos:", resumen["tickets_afectados"])
    print("Delta pendiente estimado (RD$):", "%.2f" % resumen["delta_pendiente_total_rd"])
    print("Premios PAGADOS con monto distinto (confirmación manual):", resumen["premios_pagados_con_diferencia"])
    print("")
    for it in afectadas[:50]:
        print(
            "- ticket #%s line_id=%s %s %s %s jugada=%s resultado=%s"
            % (
                it["ticket_id"],
                it["line_id"],
                it["fecha_sorteo"],
                it["lottery"],
                it["draw"],
                it["numero"],
                it["resultado"],
            )
        )
        if it.get("faltantes"):
            print("    FALTAN shards:", it["faltantes"])
        if it.get("actualizar_pendiente"):
            print("    ACTUALIZAR pendiente:", it["actualizar_pendiente"])
        if it.get("pagados_diferencia"):
            print("    PAGADO con diferencia (no tocar):", it["pagados_diferencia"])
    if len(afectadas) > 50:
        print("... y %d más (usa --json para lista completa)" % (len(afectadas) - 50))
    if aplicados:
        print("")
        print("Aplicado:", aplicados)


if __name__ == "__main__":
    main()
