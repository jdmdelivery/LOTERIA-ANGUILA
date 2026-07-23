# -*- coding: utf-8 -*-
"""Colector de resultados Conectate Anguila (fuera de la ruta de venta)."""
from __future__ import annotations

import hashlib
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from typing import Any, Optional

import pytz

import config
import database as db
from services.prizes import normalize_number
from services.validation import is_cuarteta_score, validate_result

_LOCK = threading.Lock()


class ConectateAnguillaResultCollector:
    """Servicio separado: consulta API pública /sessions y confirma con doble lectura."""

    def __init__(self):
        self.tz = pytz.timezone(config.TIMEZONE)

    def _now(self) -> datetime:
        return datetime.now(self.tz)

    def _today(self) -> str:
        return self._now().date().isoformat()

    def notify(self, level: str, message: str) -> None:
        db.notify_admin(level, message)

    def fetch_sessions(self, when: Optional[datetime] = None) -> tuple[list, bytes, str]:
        when = when or datetime.now(pytz.UTC)
        q = urllib.parse.urlencode({"date": when.strftime("%Y-%m-%dT%H:%M:%S.000Z")})
        url = f"{config.API_SESSIONS_URL}?{q}"
        last_err = None
        delay = 1.0
        for attempt in range(1, config.COLLECTOR_MAX_RETRIES + 1):
            try:
                req = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": config.USER_AGENT,
                        "Accept": "application/json",
                    },
                )
                with urllib.request.urlopen(req, timeout=config.COLLECTOR_TIMEOUT_SEC) as resp:
                    raw = resp.read()
                digest = hashlib.sha256(raw).hexdigest()
                data = json.loads(raw.decode("utf-8"))
                if not isinstance(data, list):
                    raise ValueError("respuesta_no_lista")
                return data, raw, digest
            except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as e:
                last_err = e
                time.sleep(delay)
                delay = min(delay * 2, 8)
        raise RuntimeError(f"fetch_sessions_fallo: {last_err}")

    def extract_by_game_id(self, blocks: list, game_id: str) -> Optional[dict]:
        if game_id in config.CUARTETA_GAME_IDS:
            return None
        for b in blocks:
            if b.get("game_id") == game_id:
                last = b.get("lastSession") or (b.get("sessions") or [None])[0]
                if not last:
                    return None
                score = last.get("score")
                if not score or not isinstance(score, list) or not score:
                    return None
                row = score[0]
                if is_cuarteta_score(row):
                    return None
                if not isinstance(row, list) or len(row) != 3:
                    return None
                if any(str(x).strip() == "" for x in row):
                    return None
                try:
                    nums = [normalize_number(x) for x in row]
                except ValueError:
                    return None
                # date from API is midnight AST as UTC
                api_date = str(last.get("date") or "")[:10]
                if api_date and "T" in str(last.get("date")):
                    # Convert UTC instant to AST calendar date
                    try:
                        dt = datetime.fromisoformat(str(last["date"]).replace("Z", "+00:00"))
                        api_date = dt.astimezone(self.tz).date().isoformat()
                    except Exception:
                        api_date = str(last.get("date"))[:10]
                return {
                    "primera": nums[0],
                    "segunda": nums[1],
                    "tercera": nums[2],
                    "date": api_date,
                    "updatedAt": last.get("updatedAt"),
                    "session_id": last.get("_id"),
                    "score_raw": score,
                }
        return None

    def _set_health(self, code: str, status: str, err: str = "", resp_hash: str = "") -> None:
        with db.get_conn() as conn:
            row = db._fetchone(conn, "SELECT id FROM collector_health WHERE sorteo_code=?", (code,))
            if row:
                db._exec(
                    conn,
                    "UPDATE collector_health SET last_run_at=?, status=?, last_error=?, response_hash=? WHERE sorteo_code=?",
                    (db.now_iso(), status, err, resp_hash, code),
                )
            else:
                db._exec(
                    conn,
                    "INSERT INTO collector_health (sorteo_code, last_run_at, status, last_error, response_hash) VALUES (?,?,?,?,?)",
                    (code, db.now_iso(), status, err, resp_hash),
                )

    def _acquire_lock(self, code: str, draw_date: str) -> bool:
        with db.get_conn() as conn:
            row = db._fetchone(
                conn,
                "SELECT locked_at FROM collector_locks WHERE sorteo_code=? AND draw_date=?",
                (code, draw_date),
            )
            if row:
                try:
                    locked = datetime.fromisoformat(row["locked_at"].replace("Z", "+00:00"))
                    if (datetime.now(pytz.UTC) - locked).total_seconds() < 90:
                        return False
                except Exception:
                    return False
                db._exec(
                    conn,
                    "UPDATE collector_locks SET locked_at=? WHERE sorteo_code=? AND draw_date=?",
                    (db.now_iso(), code, draw_date),
                )
                return True
            db._exec(
                conn,
                "INSERT INTO collector_locks (sorteo_code, draw_date, locked_at) VALUES (?,?,?)",
                (code, draw_date, db.now_iso()),
            )
            return True

    def _release_lock(self, code: str, draw_date: str) -> None:
        with db.get_conn() as conn:
            db._exec(
                conn,
                "DELETE FROM collector_locks WHERE sorteo_code=? AND draw_date=?",
                (code, draw_date),
            )

    def _get_result_row(self, code: str, draw_date: str) -> Optional[dict]:
        with db.get_conn() as conn:
            return db._fetchone(
                conn,
                "SELECT * FROM draw_results WHERE sorteo_code=? AND draw_date=?",
                (code, draw_date),
            )

    def _upsert_result(self, **fields) -> None:
        code = fields["sorteo_code"]
        draw_date = fields["draw_date"]
        now = db.now_iso()
        with db.get_conn() as conn:
            existing = db._fetchone(
                conn,
                "SELECT id, status FROM draw_results WHERE sorteo_code=? AND draw_date=?",
                (code, draw_date),
            )
            if existing and existing["status"] in ("CONFIRMADO", "CORREGIDO"):
                return
            if existing:
                db._exec(
                    conn,
                    """UPDATE draw_results SET primera=?, segunda=?, tercera=?, status=?, source=?,
                       response_hash=?, first_read_json=?, second_read_json=?, confirmed_at=?, updated_at=?
                       WHERE sorteo_code=? AND draw_date=?""",
                    (
                        fields.get("primera"),
                        fields.get("segunda"),
                        fields.get("tercera"),
                        fields["status"],
                        fields.get("source"),
                        fields.get("response_hash"),
                        fields.get("first_read_json"),
                        fields.get("second_read_json"),
                        fields.get("confirmed_at"),
                        now,
                        code,
                        draw_date,
                    ),
                )
            else:
                db._exec(
                    conn,
                    """INSERT INTO draw_results
                    (sorteo_code, draw_date, primera, segunda, tercera, status, source, response_hash,
                     first_read_json, second_read_json, confirmed_at, created_at, updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        code,
                        draw_date,
                        fields.get("primera"),
                        fields.get("segunda"),
                        fields.get("tercera"),
                        fields["status"],
                        fields.get("source"),
                        fields.get("response_hash"),
                        fields.get("first_read_json"),
                        fields.get("second_read_json"),
                        fields.get("confirmed_at"),
                        now,
                        now,
                    ),
                )

    def minutes_since_draw(self, src: dict, draw_date: str) -> float:
        hh, mm = map(int, src["hora_oficial"].split(":"))
        d = date.fromisoformat(draw_date)
        draw_dt = self.tz.localize(datetime(d.year, d.month, d.day, hh, mm))
        return (self._now() - draw_dt).total_seconds() / 60.0

    def should_poll(self, src: dict, draw_date: str, row: Optional[dict]) -> bool:
        if row and row.get("status") in ("CONFIRMADO", "CORREGIDO", "RECHAZADO"):
            return False
        mins = self.minutes_since_draw(src, draw_date)
        if mins < 1:
            return False
        if mins > 45:
            return False
        # Simplified: caller runs frequently; collector itself decides confirm waits
        return True

    def run_once(self, sorteo_code: str, draw_date: Optional[str] = None, confirm_wait: bool = True) -> dict:
        src = config.SOURCES_BY_CODE.get(sorteo_code)
        if not src:
            return {"ok": False, "error": "sorteo_desconocido"}
        draw_date = draw_date or self._today()

        if src.get("estado_fuente") == "FUENTE_NO_DISPONIBLE":
            self.notify(
                "WARNING",
                f"{sorteo_code}: FUENTE_NO_DISPONIBLE. Entrada manual requerida. Sin auto-pago.",
            )
            self._upsert_result(
                sorteo_code=sorteo_code,
                draw_date=draw_date,
                status="REQUIERE_REVISION",
                source="FUENTE_NO_DISPONIBLE",
            )
            self._set_health(sorteo_code, "FUENTE_NO_DISPONIBLE", "sin pagina verificable")
            return {"ok": False, "error": "FUENTE_NO_DISPONIBLE", "manual": True}

        if not self._acquire_lock(sorteo_code, draw_date):
            return {"ok": False, "error": "proceso_simultaneo"}

        try:
            existing = self._get_result_row(sorteo_code, draw_date)
            if existing and existing.get("status") in ("CONFIRMADO", "CORREGIDO"):
                return {"ok": True, "status": existing["status"], "idempotent": True}

            mins = self.minutes_since_draw(src, draw_date)
            if mins < 1:
                return {"ok": False, "error": "aún_no_toca"}
            if mins > 45 and (not existing or existing.get("status") not in ("CONFIRMADO", "CORREGIDO")):
                self._upsert_result(
                    sorteo_code=sorteo_code,
                    draw_date=draw_date,
                    status="REQUIERE_REVISION",
                    source="timeout_45m",
                    primera=(existing or {}).get("primera"),
                    segunda=(existing or {}).get("segunda"),
                    tercera=(existing or {}).get("tercera"),
                )
                self.notify("WARNING", f"{sorteo_code} {draw_date}: REQUIERE_REVISION (>45 min)")
                self._set_health(sorteo_code, "REQUIERE_REVISION", ">45min")
                return {"ok": False, "status": "REQUIERE_REVISION"}

            blocks, _raw, digest = self.fetch_sessions()
            extracted = self.extract_by_game_id(blocks, src["game_id"])
            if not extracted:
                self._set_health(sorteo_code, "SIN_RESULTADO", "", digest)
                return {"ok": False, "error": "sin_resultado"}

            if extracted.get("date") and extracted["date"] != draw_date:
                self._set_health(sorteo_code, "FECHA_DISTINTA", f"api={extracted['date']}", digest)
                return {"ok": False, "error": "fecha_distinta", "api_date": extracted["date"]}

            ok, reason = validate_result(
                extracted["primera"],
                extracted["segunda"],
                extracted["tercera"],
                draw_date=draw_date,
                sorteo_code=sorteo_code,
                after_draw=True,
                now=self._now(),
            )
            if not ok:
                self._set_health(sorteo_code, "RECHAZADO", reason, digest)
                return {"ok": False, "error": reason}

            reading = {
                "primera": extracted["primera"],
                "segunda": extracted["segunda"],
                "tercera": extracted["tercera"],
                "date": draw_date,
                "hash": digest,
            }

            # Primera lectura -> CANDIDATO
            if not existing or existing.get("status") in ("PENDIENTE", "REQUIERE_REVISION"):
                self._upsert_result(
                    sorteo_code=sorteo_code,
                    draw_date=draw_date,
                    primera=reading["primera"],
                    segunda=reading["segunda"],
                    tercera=reading["tercera"],
                    status="CANDIDATO",
                    source="conectate_sessions",
                    response_hash=digest,
                    first_read_json=db.json_dumps(reading),
                )
                self._set_health(sorteo_code, "CANDIDATO", "", digest)
                if not confirm_wait:
                    return {"ok": True, "status": "CANDIDATO", "reading": reading}

                time.sleep(60)
                blocks2, _r2, digest2 = self.fetch_sessions()
                extracted2 = self.extract_by_game_id(blocks2, src["game_id"])
                if not extracted2:
                    return {"ok": False, "error": "segunda_lectura_vacia", "status": "CANDIDATO"}
                reading2 = {
                    "primera": extracted2["primera"],
                    "segunda": extracted2["segunda"],
                    "tercera": extracted2["tercera"],
                    "date": draw_date,
                    "hash": digest2,
                }
                same = (
                    reading["primera"] == reading2["primera"]
                    and reading["segunda"] == reading2["segunda"]
                    and reading["tercera"] == reading2["tercera"]
                )
                if not same:
                    self._upsert_result(
                        sorteo_code=sorteo_code,
                        draw_date=draw_date,
                        primera=reading2["primera"],
                        segunda=reading2["segunda"],
                        tercera=reading2["tercera"],
                        status="CANDIDATO",
                        source="conectate_sessions",
                        response_hash=digest2,
                        first_read_json=db.json_dumps(reading),
                        second_read_json=db.json_dumps(reading2),
                    )
                    self._set_health(sorteo_code, "CANDIDATO_DIVERGENTE", "", digest2)
                    return {"ok": False, "error": "lecturas_distintas", "status": "CANDIDATO"}

                self._upsert_result(
                    sorteo_code=sorteo_code,
                    draw_date=draw_date,
                    primera=reading["primera"],
                    segunda=reading["segunda"],
                    tercera=reading["tercera"],
                    status="CONFIRMADO",
                    source="conectate_sessions",
                    response_hash=digest2,
                    first_read_json=db.json_dumps(reading),
                    second_read_json=db.json_dumps(reading2),
                    confirmed_at=db.now_iso(),
                )
                self._set_health(sorteo_code, "CONFIRMADO", "", digest2)
                from services.winners import detect_winners

                detect_winners(sorteo_code, draw_date)
                self.notify(
                    "INFO",
                    f"Resultado CONFIRMADO {sorteo_code} {draw_date}: "
                    f"{reading['primera']}-{reading['segunda']}-{reading['tercera']}",
                )
                return {"ok": True, "status": "CONFIRMADO", "reading": reading}

            if existing.get("status") == "CANDIDATO":
                # Segunda lectura inmediata
                first = db.json_loads(existing.get("first_read_json"), {})
                same = (
                    first.get("primera") == reading["primera"]
                    and first.get("segunda") == reading["segunda"]
                    and first.get("tercera") == reading["tercera"]
                )
                if same:
                    self._upsert_result(
                        sorteo_code=sorteo_code,
                        draw_date=draw_date,
                        primera=reading["primera"],
                        segunda=reading["segunda"],
                        tercera=reading["tercera"],
                        status="CONFIRMADO",
                        source="conectate_sessions",
                        response_hash=digest,
                        first_read_json=existing.get("first_read_json"),
                        second_read_json=db.json_dumps(reading),
                        confirmed_at=db.now_iso(),
                    )
                    self._set_health(sorteo_code, "CONFIRMADO", "", digest)
                    from services.winners import detect_winners

                    detect_winners(sorteo_code, draw_date)
                    return {"ok": True, "status": "CONFIRMADO", "reading": reading}
                self._upsert_result(
                    sorteo_code=sorteo_code,
                    draw_date=draw_date,
                    primera=reading["primera"],
                    segunda=reading["segunda"],
                    tercera=reading["tercera"],
                    status="CANDIDATO",
                    source="conectate_sessions",
                    response_hash=digest,
                    first_read_json=db.json_dumps(reading),
                    second_read_json=None,
                )
                return {"ok": False, "status": "CANDIDATO", "error": "reinicio_candidato"}

            return {"ok": True, "status": existing.get("status")}
        except Exception as e:
            self._set_health(sorteo_code, "ERROR", str(e))
            self.notify("ERROR", f"Collector {sorteo_code}: {e}")
            return {"ok": False, "error": str(e)}
        finally:
            self._release_lock(sorteo_code, draw_date)

    def manual_enter_result(
        self,
        sorteo_code: str,
        draw_date: str,
        primera: str,
        segunda: str,
        tercera: str,
        admin_user: str,
    ) -> dict:
        src = config.SOURCES_BY_CODE.get(sorteo_code)
        if not src:
            return {"ok": False, "error": "sorteo_desconocido"}
        ok, reason = validate_result(
            primera,
            segunda,
            tercera,
            draw_date=draw_date,
            sorteo_code=sorteo_code,
            after_draw=False,
        )
        if not ok:
            return {"ok": False, "error": reason}
        p1, p2, p3 = normalize_number(primera), normalize_number(segunda), normalize_number(tercera)
        reading = {"primera": p1, "segunda": p2, "tercera": p3, "date": draw_date, "by": admin_user}
        self._upsert_result(
            sorteo_code=sorteo_code,
            draw_date=draw_date,
            primera=p1,
            segunda=p2,
            tercera=p3,
            status="CONFIRMADO",
            source="manual",
            first_read_json=db.json_dumps(reading),
            second_read_json=db.json_dumps(reading),
            confirmed_at=db.now_iso(),
        )
        from services.winners import detect_winners

        detect_winners(sorteo_code, draw_date)
        self.notify("INFO", f"Resultado manual CONFIRMADO {sorteo_code} {draw_date} por {admin_user}")
        return {"ok": True, "status": "CONFIRMADO"}

    def run_due(self) -> list:
        """Ejecuta sorteos que ya pasaron su hora oficial (hoy)."""
        results = []
        today = self._today()
        with _LOCK:
            for src in config.ANGUILLA_RESULT_SOURCES:
                mins = self.minutes_since_draw(src, today)
                if mins < 1:
                    continue
                row = self._get_result_row(src["code"], today)
                if row and row.get("status") in ("CONFIRMADO", "CORREGIDO"):
                    continue
                # Frecuencia: primeros 10 min cada ~60s (scheduler externo), luego 3 min
                if mins > 45:
                    if not row or row.get("status") != "REQUIERE_REVISION":
                        results.append(self.run_once(src["code"], today, confirm_wait=False))
                    continue
                results.append(self.run_once(src["code"], today, confirm_wait=True))
        return results


collector = ConectateAnguillaResultCollector()
