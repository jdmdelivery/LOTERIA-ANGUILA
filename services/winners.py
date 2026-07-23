# -*- coding: utf-8 -*-
"""Detección automática de ganadores (solo tras CONFIRMADO)."""
from __future__ import annotations

import database as db
from services.prizes import calc_pale, calc_quiniela, normalize_pale


def detect_winners(sorteo_code: str, draw_date: str) -> dict:
    with db.get_conn() as conn:
        result = db._fetchone(
            conn,
            "SELECT * FROM draw_results WHERE sorteo_code=? AND draw_date=?",
            (sorteo_code, draw_date),
        )
        if not result or result.get("status") not in ("CONFIRMADO", "CORREGIDO"):
            return {"ok": False, "error": "resultado_no_confirmado"}

        p1, p2, p3 = result["primera"], result["segunda"], result["tercera"]
        tickets = db._fetchall(
            conn,
            "SELECT * FROM tickets WHERE sorteo_code=? AND draw_date=? AND status != 'ANULADO'",
            (sorteo_code, draw_date),
        )
        winners = 0
        processed_lines = 0
        for t in tickets:
            if t["status"] == "PAGADO":
                continue
            lines = db._fetchall(conn, "SELECT * FROM ticket_lines WHERE ticket_id=?", (t["id"],))
            ticket_prize = 0.0
            for line in lines:
                if line.get("processed_winner"):
                    ticket_prize += float(line.get("prize_amount") or 0)
                    continue
                snap = db.json_loads(line.get("snapshot_json"), {})
                prize = 0.0
                detail = []
                if line["modality"] == "QUINIELA":
                    prize, detail = calc_quiniela(line["numbers"], line["amount"], p1, p2, p3, snap)
                elif line["modality"] == "PALE":
                    try:
                        # normalize stored combo
                        parts = str(line["numbers"]).replace(" ", "").split("-")
                        if len(parts) == 2:
                            combo = normalize_pale(parts[0], parts[1])
                        else:
                            combo = line["numbers"]
                        prize, detail = calc_pale(combo, line["amount"], p1, p2, p3, snap)
                    except ValueError:
                        prize, detail = 0.0, []
                status = "PENDIENTE" if prize > 0 else "NONE"
                db._exec(
                    conn,
                    """UPDATE ticket_lines SET prize_amount=?, prize_status=?, processed_winner=1,
                       prize_detail_json=? WHERE id=?""",
                    (prize, status, db.json_dumps(detail), line["id"]),
                )
                ticket_prize += prize
                processed_lines += 1
            new_status = "GANADOR_PENDIENTE" if ticket_prize > 0 else "NO_GANADOR"
            db._exec(conn, "UPDATE tickets SET status=? WHERE id=? AND status != 'PAGADO'", (new_status, t["id"]))
            if ticket_prize > 0:
                winners += 1

    db.notify_admin(
        "INFO",
        f"Detección ganadores {sorteo_code} {draw_date}: {winners} tickets ganadores, {processed_lines} líneas.",
    )
    return {"ok": True, "winners": winners, "processed_lines": processed_lines}
