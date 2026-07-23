# -*- coding: utf-8 -*-
"""JDM Anguila — aplicación Flask lista para vender (Render/GitHub)."""
from __future__ import annotations

import secrets
import string
from datetime import datetime, timedelta
from functools import wraps

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash

import config
import database as db
import ticket_thermal
from services.cash import add_sale, get_balance, pay_prize
from services.collector import collector
from services.prizes import normalize_number, normalize_pale, pay_snapshot
from services.validation import validate_result
from services.winners import detect_winners

app = Flask(__name__)
app.secret_key = config.SECRET_KEY
TZ = pytz.timezone(config.TIMEZONE)
scheduler = BackgroundScheduler(timezone=config.TIMEZONE)


def now_local() -> datetime:
    return datetime.now(TZ)


def today_str() -> str:
    return now_local().date().isoformat()


def client_ip() -> str:
    return request.headers.get("X-Forwarded-For", request.remote_addr or "")


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        return fn(*args, **kwargs)

    return wrapper


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        if session.get("role") != "admin":
            flash("Permiso de administrador requerido.", "error")
            return redirect(url_for("venta"))
        return fn(*args, **kwargs)

    return wrapper


def _user():
    with db.get_conn() as conn:
        return db._fetchone(conn, "SELECT * FROM users WHERE id=?", (session["user_id"],))


def _branch_caja():
    with db.get_conn() as conn:
        branch = db._fetchone(conn, "SELECT * FROM branches ORDER BY id LIMIT 1")
        caja = db._fetchone(conn, "SELECT * FROM cash_registers ORDER BY id LIMIT 1")
        return branch, caja


def _sorteo_open(code: str) -> tuple[bool, str]:
    src = config.SOURCES_BY_CODE.get(code)
    if not src:
        return False, "Sorteo desconocido"
    hh, mm = map(int, src["hora_oficial"].split(":"))
    n = now_local()
    close_at = n.replace(hour=hh, minute=mm, second=0, microsecond=0) - timedelta(
        minutes=config.CLOSE_BEFORE_DRAW_MINUTES
    )
    if n >= close_at:
        return False, "Sorteo cerrado"
    return True, "ok"


def _gen_public_number(conn) -> str:
    row = db._fetchone(conn, "SELECT COUNT(*) AS c FROM tickets")
    n = int(row["c"] if row else 0) + 1
    return f"{n:08d}"


def _gen_security_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(8))


def _ticket_print_data(ticket: dict, lines: list, reimpresion: bool = False) -> dict:
    src = config.SOURCES_BY_CODE.get(ticket["sorteo_code"], {})
    sold = ticket["sold_at"]
    try:
        dt = datetime.fromisoformat(sold.replace("Z", "+00:00")).astimezone(TZ)
        fecha = dt.strftime("%d/%m/%Y %I:%M %p")
    except Exception:
        fecha = sold
    with db.get_conn() as conn:
        cajero = db._fetchone(conn, "SELECT username FROM users WHERE id=?", (ticket["cashier_id"],))
        branch = db._fetchone(conn, "SELECT name FROM branches WHERE id=?", (ticket["branch_id"],))
    jugadas = []
    for ln in lines:
        jugadas.append(
            {
                "modality": ln["modality"],
                "tipo": ln["modality"],
                "numeros": ln["numbers"],
                "monto": ln["amount"],
            }
        )
    return {
        "banca": config.BANK_NAME,
        "direccion": config.BANK_ADDRESS,
        "telefono": config.BANK_PHONE,
        "ticket": ticket["public_number"],
        "fecha": fecha,
        "cajero": (cajero or {}).get("username", ""),
        "sucursal": (branch or {}).get("name", "Principal"),
        "sorteo": src.get("nombre", ticket["sorteo_code"]),
        "jugadas": jugadas,
        "total": ticket["total"],
        "estado": ticket["status"] if ticket["status"] != "ACTIVO" else "ACTIVO",
        "codigo": ticket["security_code"],
        "security_code": ticket["security_code"],
        "mensaje": config.TICKET_MESSAGE,
        "reimpresion": reimpresion,
    }


@app.route("/health")
def health():
    return {"ok": True, "service": "jdm-anguila", "time": now_local().isoformat()}


@app.route("/")
def index():
    if session.get("user_id"):
        return redirect(url_for("venta"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        with db.get_conn() as conn:
            user = db._fetchone(conn, "SELECT * FROM users WHERE username=? AND active=1", (username,))
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            return redirect(url_for("venta"))
        flash("Usuario o clave incorrectos", "error")
    return render_template("login.html", bank=config.BANK_NAME)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/venta", methods=["GET", "POST"])
@login_required
def venta():
    branch, caja = _branch_caja()
    sorteos = [
        s
        for s in config.ANGUILLA_RESULT_SOURCES
        if s.get("estado_fuente") != "FUENTE_NO_DISPONIBLE" or True
    ]
    # Mostrar todos; bloquear venta en cerrado / FUENTE_NO_DISPONIBLE solo se permite vender
    # (resultado manual luego). Cierre por hora aplica a todos.
    if request.method == "POST":
        sorteo_code = request.form.get("sorteo_code")
        open_ok, why = _sorteo_open(sorteo_code)
        if not open_ok:
            flash(why, "error")
            return redirect(url_for("venta"))
        src = config.SOURCES_BY_CODE.get(sorteo_code)
        if not src:
            flash("Sorteo inválido", "error")
            return redirect(url_for("venta"))

        lines = []
        # Quinielas: numbers[] amounts[]
        q_nums = request.form.getlist("q_number")
        q_amts = request.form.getlist("q_amount")
        for n, a in zip(q_nums, q_amts):
            n = (n or "").strip()
            a = (a or "").strip()
            if not n and not a:
                continue
            try:
                num = normalize_number(n)
                amt = float(a)
                if amt <= 0:
                    raise ValueError("monto")
                lines.append({"modality": "QUINIELA", "numbers": num, "amount": amt})
            except Exception:
                flash(f"Quiniela inválida: {n} / {a}", "error")
                return redirect(url_for("venta"))

        p_a = request.form.getlist("p_a")
        p_b = request.form.getlist("p_b")
        p_amts = request.form.getlist("p_amount")
        for a, b, amt in zip(p_a, p_b, p_amts):
            if not str(a).strip() and not str(b).strip() and not str(amt).strip():
                continue
            try:
                combo = normalize_pale(a, b)
                amount = float(amt)
                if amount <= 0:
                    raise ValueError("monto")
                lines.append({"modality": "PALE", "numbers": combo, "amount": amount})
            except Exception:
                flash(f"Palé inválido: {a}-{b}", "error")
                return redirect(url_for("venta"))

        if not lines:
            flash("Agrega al menos una jugada", "error")
            return redirect(url_for("venta"))

        snap = pay_snapshot()
        total = sum(x["amount"] for x in lines)
        with db.get_conn() as conn:
            public_number = _gen_public_number(conn)
            security = _gen_security_code()
            db._exec(
                conn,
                """INSERT INTO tickets
                (public_number, security_code, branch_id, cash_register_id, cashier_id,
                 sold_at, draw_date, sorteo_code, status, total, reprint_count, ip)
                VALUES (?,?,?,?,?,?,?,?,?,?,0,?)""",
                (
                    public_number,
                    security,
                    branch["id"],
                    caja["id"],
                    session["user_id"],
                    db.now_iso(),
                    today_str(),
                    sorteo_code,
                    "ACTIVO",
                    total,
                    client_ip(),
                ),
            )
            ticket = db._fetchone(conn, "SELECT * FROM tickets WHERE public_number=?", (public_number,))
            for ln in lines:
                db._exec(
                    conn,
                    """INSERT INTO ticket_lines
                    (ticket_id, modality, numbers, amount, snapshot_json, prize_amount, prize_status, processed_winner)
                    VALUES (?,?,?,?,?,0,'NONE',0)""",
                    (
                        ticket["id"],
                        ln["modality"],
                        ln["numbers"],
                        ln["amount"],
                        db.json_dumps(snap),
                    ),
                )
        add_sale(caja["id"], total, ticket["id"], session["user_id"])
        return redirect(url_for("ticket_view", ticket_id=ticket["id"]))

    abiertos = []
    for s in config.ANGUILLA_RESULT_SOURCES:
        ok, _ = _sorteo_open(s["code"])
        abiertos.append({**s, "abierto": ok})
    balance = get_balance(caja["id"]) if caja else 0
    return render_template(
        "venta.html",
        bank=config.BANK_NAME,
        user=session.get("username"),
        role=session.get("role"),
        sorteos=abiertos,
        balance=balance,
        snap=pay_snapshot(),
    )


@app.route("/ticket/<int:ticket_id>")
@login_required
def ticket_view(ticket_id):
    width = int(request.args.get("mm", 58))
    with db.get_conn() as conn:
        ticket = db._fetchone(conn, "SELECT * FROM tickets WHERE id=?", (ticket_id,))
        lines = db._fetchall(conn, "SELECT * FROM ticket_lines WHERE ticket_id=?", (ticket_id,))
    if not ticket:
        flash("Ticket no encontrado", "error")
        return redirect(url_for("venta"))
    data = _ticket_print_data(ticket, lines, reimpresion=False)
    return ticket_thermal.render_ticket_page_html(data, width_mm=width, kind="venta")


@app.route("/ticket/<int:ticket_id>/reimprimir", methods=["POST"])
@login_required
def ticket_reprint(ticket_id):
    if session.get("role") != "admin" and not request.form.get("autorizado"):
        # cajero needs admin permission flag in form for reprint — require admin
        if session.get("role") != "admin":
            flash("Reimpresión requiere permiso de administrador.", "error")
            return redirect(url_for("premios"))
    reason = (request.form.get("reason") or "reimpresion").strip()
    width = int(request.form.get("mm") or 58)
    with db.get_conn() as conn:
        ticket = db._fetchone(conn, "SELECT * FROM tickets WHERE id=?", (ticket_id,))
        if not ticket:
            flash("Ticket no encontrado", "error")
            return redirect(url_for("venta"))
        db._exec(conn, "UPDATE tickets SET reprint_count = reprint_count + 1 WHERE id=?", (ticket_id,))
        db._exec(
            conn,
            """INSERT INTO reprint_audit (ticket_id, user_id, reason, created_at, ip, kind)
               VALUES (?,?,?,?,?,?)""",
            (ticket_id, session["user_id"], reason, db.now_iso(), client_ip(), "VENTA"),
        )
        ticket = db._fetchone(conn, "SELECT * FROM tickets WHERE id=?", (ticket_id,))
        lines = db._fetchall(conn, "SELECT * FROM ticket_lines WHERE ticket_id=?", (ticket_id,))
    data = _ticket_print_data(ticket, lines, reimpresion=True)
    return ticket_thermal.render_ticket_page_html(data, width_mm=width, kind="venta")


@app.route("/premios", methods=["GET", "POST"])
@login_required
def premios():
    ticket = None
    lines = []
    result = None
    total_pagar = 0.0
    estado_ui = "SORTEO PENDIENTE"
    detail_rows = []
    q = ""
    if request.method == "POST" or request.args.get("q"):
        q = (request.form.get("q") or request.args.get("q") or "").strip()
        with db.get_conn() as conn:
            ticket = db._fetchone(
                conn,
                "SELECT * FROM tickets WHERE public_number=? OR security_code=? OR CAST(id AS TEXT)=?",
                (q.lstrip("#"), q, q),
            )
            if ticket:
                lines = db._fetchall(conn, "SELECT * FROM ticket_lines WHERE ticket_id=?", (ticket["id"],))
                result = db._fetchone(
                    conn,
                    "SELECT * FROM draw_results WHERE sorteo_code=? AND draw_date=?",
                    (ticket["sorteo_code"], ticket["draw_date"]),
                )
        if not ticket:
            flash("Ticket no encontrado", "error")
        else:
            if ticket["status"] == "ANULADO":
                estado_ui = "ANULADO"
            elif ticket["status"] == "PAGADO":
                estado_ui = "PAGADO"
                total_pagar = sum(float(l.get("prize_amount") or 0) for l in lines)
            elif not result or result.get("status") not in ("CONFIRMADO", "CORREGIDO"):
                if result and result.get("status") == "CANDIDATO":
                    estado_ui = "RESULTADO NO CONFIRMADO"
                elif result and result.get("status") == "REQUIERE_REVISION":
                    estado_ui = "EN REVISIÓN"
                else:
                    estado_ui = "SORTEO PENDIENTE"
            elif ticket["status"] == "NO_GANADOR":
                estado_ui = "NO GANADOR"
            elif ticket["status"] == "GANADOR_PENDIENTE":
                estado_ui = "GANADOR PENDIENTE"
                total_pagar = sum(float(l.get("prize_amount") or 0) for l in lines if l.get("prize_status") == "PENDIENTE")
            for l in lines:
                for d in db.json_loads(l.get("prize_detail_json"), []) or []:
                    detail_rows.append(d)

    return render_template(
        "premios.html",
        bank=config.BANK_NAME,
        user=session.get("username"),
        role=session.get("role"),
        q=q,
        ticket=ticket,
        lines=lines,
        result=result,
        total_pagar=total_pagar,
        estado_ui=estado_ui,
        detail_rows=detail_rows,
        sources=config.SOURCES_BY_CODE,
    )


@app.route("/premios/pagar/<int:ticket_id>", methods=["POST"])
@login_required
def premios_pagar(ticket_id):
    confirm = request.form.get("confirm")
    if confirm != "PAGAR PREMIO":
        flash("Debes confirmar escribiendo: PAGAR PREMIO", "error")
        return redirect(url_for("premios", q=str(ticket_id)))
    branch, caja = _branch_caja()
    with db.get_conn() as conn:
        ticket = db._fetchone(conn, "SELECT * FROM tickets WHERE id=?", (ticket_id,))
        if not ticket:
            flash("Ticket no encontrado", "error")
            return redirect(url_for("premios"))
        if ticket["status"] == "PAGADO":
            flash("Este ticket ya fue pagado.", "error")
            return redirect(url_for("premios", q=ticket["public_number"]))
        if ticket["status"] == "ANULADO":
            flash("Ticket anulado.", "error")
            return redirect(url_for("premios"))
        result = db._fetchone(
            conn,
            "SELECT * FROM draw_results WHERE sorteo_code=? AND draw_date=?",
            (ticket["sorteo_code"], ticket["draw_date"]),
        )
        if not result or result.get("status") not in ("CONFIRMADO", "CORREGIDO"):
            flash("Resultado no confirmado. No se puede pagar.", "error")
            return redirect(url_for("premios", q=ticket["public_number"]))
        # evitar doble pago
        existing = db._fetchone(conn, "SELECT id FROM prize_payments WHERE ticket_id=?", (ticket_id,))
        if existing:
            flash("Pago ya registrado.", "error")
            return redirect(url_for("premios", q=ticket["public_number"]))
        lines = db._fetchall(
            conn,
            "SELECT * FROM ticket_lines WHERE ticket_id=? AND prize_status='PENDIENTE'",
            (ticket_id,),
        )
        amount = sum(float(l["prize_amount"] or 0) for l in lines)
        if amount <= 0:
            flash("No hay premio pendiente.", "error")
            return redirect(url_for("premios", q=ticket["public_number"]))
        # payment uid
        cnt = db._fetchone(conn, "SELECT COUNT(*) AS c FROM prize_payments")
        payment_uid = f"PG-{int(cnt['c']) + 1:08d}"
        receipt_lines = []
        for l in lines:
            for d in db.json_loads(l.get("prize_detail_json"), []) or []:
                if l["modality"] == "QUINIELA":
                    receipt_lines.append(
                        {
                            "titulo": f"QUINIELA {d.get('numero')} ({d.get('posicion')})",
                            "detalle": f"RD${d.get('monto')} × {d.get('multiplicador')} = RD${d.get('premio')}",
                        }
                    )
                else:
                    receipt_lines.append(
                        {
                            "titulo": f"PALÉ {d.get('combinacion')}",
                            "detalle": f"RD${d.get('monto')} × {d.get('multiplicador')} = RD${d.get('premio')}",
                        }
                    )
        obs = request.form.get("observation") or ""
        db._exec(
            conn,
            """INSERT INTO prize_payments
            (payment_uid, ticket_id, user_id, cash_register_id, branch_id, amount, paid_at,
             observation, ip, result_snapshot_json, receipt_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                payment_uid,
                ticket_id,
                session["user_id"],
                caja["id"],
                branch["id"],
                amount,
                db.now_iso(),
                obs,
                client_ip(),
                db.json_dumps(
                    {
                        "primera": result["primera"],
                        "segunda": result["segunda"],
                        "tercera": result["tercera"],
                    }
                ),
                db.json_dumps(receipt_lines),
            ),
        )
        payment = db._fetchone(conn, "SELECT * FROM prize_payments WHERE payment_uid=?", (payment_uid,))
        db._exec(conn, "UPDATE ticket_lines SET prize_status='PAGADO' WHERE ticket_id=? AND prize_status='PENDIENTE'", (ticket_id,))
        db._exec(conn, "UPDATE tickets SET status='PAGADO' WHERE id=?", (ticket_id,))
    pay_prize(caja["id"], amount, ticket_id, payment["id"], session["user_id"])
    return redirect(url_for("premio_recibo", payment_id=payment["id"]))


@app.route("/premios/recibo/<int:payment_id>")
@login_required
def premio_recibo(payment_id):
    width = int(request.args.get("mm", 58))
    reprint = request.args.get("reprint") == "1"
    with db.get_conn() as conn:
        payment = db._fetchone(conn, "SELECT * FROM prize_payments WHERE id=?", (payment_id,))
        if not payment:
            flash("Pago no encontrado", "error")
            return redirect(url_for("premios"))
        ticket = db._fetchone(conn, "SELECT * FROM tickets WHERE id=?", (payment["ticket_id"],))
        user = db._fetchone(conn, "SELECT username FROM users WHERE id=?", (payment["user_id"],))
        caja = db._fetchone(conn, "SELECT name FROM cash_registers WHERE id=?", (payment["cash_register_id"],))
        if reprint:
            db._exec(
                conn,
                """INSERT INTO reprint_audit (ticket_id, user_id, reason, created_at, ip, kind)
                   VALUES (?,?,?,?,?,?)""",
                (ticket["id"], session["user_id"], "reimpresion premio", db.now_iso(), client_ip(), "PREMIO"),
            )
    src = config.SOURCES_BY_CODE.get(ticket["sorteo_code"], {})
    res = db.json_loads(payment.get("result_snapshot_json"), {})
    try:
        dt = datetime.fromisoformat(payment["paid_at"].replace("Z", "+00:00")).astimezone(TZ)
        fecha_pago = dt.strftime("%d/%m/%Y %I:%M %p")
    except Exception:
        fecha_pago = payment["paid_at"]
    data = {
        "banca": config.BANK_NAME,
        "ticket": ticket["public_number"],
        "codigo": ticket["security_code"],
        "sorteo": src.get("nombre", ticket["sorteo_code"]),
        "fecha_sorteo": ticket["draw_date"],
        "resultado": f"{res.get('primera')} - {res.get('segunda')} - {res.get('tercera')}",
        "lineas": db.json_loads(payment.get("receipt_json"), []),
        "total": payment["amount"],
        "cajero": (user or {}).get("username", ""),
        "fecha_pago": fecha_pago,
        "caja": (caja or {}).get("name", ""),
        "pago_uid": payment["payment_uid"],
        "reimpresion": reprint,
    }
    return ticket_thermal.render_ticket_page_html(data, width_mm=width, kind="premio")


@app.route("/admin/resultados", methods=["GET", "POST"])
@admin_required
def admin_resultados():
    if request.method == "POST":
        action = request.form.get("action")
        code = request.form.get("sorteo_code")
        draw_date = request.form.get("draw_date") or today_str()
        if action == "manual":
            r = collector.manual_enter_result(
                code,
                draw_date,
                request.form.get("primera"),
                request.form.get("segunda"),
                request.form.get("tercera"),
                session.get("username"),
            )
            flash("OK manual" if r.get("ok") else r.get("error"), "ok" if r.get("ok") else "error")
        elif action == "collect":
            r = collector.run_once(code, draw_date, confirm_wait=True)
            flash(str(r), "ok" if r.get("ok") else "error")
        elif action == "redetect":
            r = detect_winners(code, draw_date)
            flash(str(r), "ok" if r.get("ok") else "error")
        return redirect(url_for("admin_resultados"))

    with db.get_conn() as conn:
        results = db._fetchall(conn, "SELECT * FROM draw_results ORDER BY draw_date DESC, sorteo_code LIMIT 50")
        health = db._fetchall(conn, "SELECT * FROM collector_health ORDER BY sorteo_code")
        notes = db._fetchall(
            conn,
            "SELECT * FROM admin_notifications ORDER BY id DESC LIMIT 30",
        )
    return render_template(
        "admin_resultados.html",
        bank=config.BANK_NAME,
        user=session.get("username"),
        role=session.get("role"),
        sources=config.ANGUILLA_RESULT_SOURCES,
        results=results,
        health=health,
        notes=notes,
        today=today_str(),
    )


@app.route("/admin/anular/<int:ticket_id>", methods=["POST"])
@admin_required
def anular_ticket(ticket_id):
    with db.get_conn() as conn:
        ticket = db._fetchone(conn, "SELECT * FROM tickets WHERE id=?", (ticket_id,))
        if not ticket:
            flash("No encontrado", "error")
            return redirect(url_for("venta"))
        if ticket["status"] == "PAGADO":
            flash("No se puede anular un ticket pagado", "error")
            return redirect(url_for("premios", q=ticket["public_number"]))
        db._exec(conn, "UPDATE tickets SET status='ANULADO' WHERE id=?", (ticket_id,))
    flash("Ticket anulado", "ok")
    return redirect(url_for("premios", q=str(ticket_id)))


def _scheduler_job():
    try:
        collector.run_due()
    except Exception as e:
        db.notify_admin("ERROR", f"scheduler: {e}")


def create_app():
    db.init_db()
    if not scheduler.running:
        scheduler.add_job(_scheduler_job, "interval", seconds=60, id="collector_due", replace_existing=True)
        try:
            scheduler.start()
        except Exception:
            pass
    return app


# Init on import (gunicorn)
application = create_app()
app = application


if __name__ == "__main__":
    application.run(host="0.0.0.0", port=int(__import__("os").environ.get("PORT", 5000)), debug=True)
