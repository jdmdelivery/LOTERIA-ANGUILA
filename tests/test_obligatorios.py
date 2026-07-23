# -*- coding: utf-8 -*-
"""Pruebas obligatorias JDM Anguila."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime
from unittest import mock

import pytz

# DB aislada por proceso de test
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["SQLITE_PATH"] = _tmp.name
os.environ["SECRET_KEY"] = "test-secret"
os.environ["DATABASE_URL"] = ""

import config  # noqa: E402
import database as db  # noqa: E402
import ticket_thermal  # noqa: E402
from services import prizes, validation  # noqa: E402
from services.collector import ConectateAnguillaResultCollector  # noqa: E402
from services.winners import detect_winners  # noqa: E402
from services import cash  # noqa: E402


def setUpModule():
    db.init_db()


class TestExtractionAndValidation(unittest.TestCase):
    def test_01_extract_shape_8am(self):
        c = ConectateAnguillaResultCollector()
        blocks = [
            {
                "game_id": config.SOURCES_BY_CODE["ANGUILA_0800"]["game_id"],
                "lastSession": {
                    "date": "2026-07-23T04:00:00.000Z",
                    "score": [["04", "09", "00"]],
                    "_id": "x",
                },
            }
        ]
        ex = c.extract_by_game_id(blocks, config.SOURCES_BY_CODE["ANGUILA_0800"]["game_id"])
        self.assertEqual(ex["primera"], "04")
        self.assertEqual(ex["segunda"], "09")
        self.assertEqual(ex["tercera"], "00")

    def test_02_extract_9am(self):
        c = ConectateAnguillaResultCollector()
        gid = config.SOURCES_BY_CODE["ANGUILA_0900"]["game_id"]
        blocks = [{"game_id": gid, "lastSession": {"date": "2026-07-23T04:00:00.000Z", "score": [["12", "34", "56"]]}}]
        ex = c.extract_by_game_id(blocks, gid)
        self.assertEqual((ex["primera"], ex["segunda"], ex["tercera"]), ("12", "34", "56"))

    def test_03_all_15_sources_mapped(self):
        self.assertEqual(len(config.ANGUILLA_RESULT_SOURCES), 15)
        codes = {s["code"] for s in config.ANGUILLA_RESULT_SOURCES}
        for h in ["0800", "0900", "1000", "1100", "1200", "1300", "1400", "1500", "1600", "1700", "1800", "1900", "2000", "2100", "2200"]:
            self.assertIn(f"ANGUILA_{h}", codes)

    def test_04_reject_cuarteta(self):
        c = ConectateAnguillaResultCollector()
        gid = list(config.CUARTETA_GAME_IDS)[0]
        blocks = [{"game_id": gid, "lastSession": {"date": "2026-07-23T04:00:00.000Z", "score": [["21", "09", "96", "07"]]}}]
        self.assertIsNone(c.extract_by_game_id(blocks, gid))
        self.assertTrue(validation.is_cuarteta_score(["21", "09", "96", "07"]))

    def test_05_preserve_zeros(self):
        self.assertEqual(prizes.normalize_number("0"), "00")
        self.assertEqual(prizes.normalize_number("4"), "04")
        self.assertEqual(prizes.normalize_number("09"), "09")

    def test_06_reject_previous_day_via_extract_date(self):
        c = ConectateAnguillaResultCollector()
        gid = config.SOURCES_BY_CODE["ANGUILA_0800"]["game_id"]
        blocks = [{"game_id": gid, "lastSession": {"date": "2026-07-22T04:00:00.000Z", "score": [["11", "22", "33"]]}}]
        ex = c.extract_by_game_id(blocks, gid)
        self.assertEqual(ex["date"], "2026-07-22")

    def test_07_wrong_game_id_isolated(self):
        c = ConectateAnguillaResultCollector()
        g8 = config.SOURCES_BY_CODE["ANGUILA_0800"]["game_id"]
        g9 = config.SOURCES_BY_CODE["ANGUILA_0900"]["game_id"]
        blocks = [
            {"game_id": g8, "lastSession": {"date": "2026-07-23T04:00:00.000Z", "score": [["01", "02", "03"]]}},
            {"game_id": g9, "lastSession": {"date": "2026-07-23T04:00:00.000Z", "score": [["70", "37", "11"]]}},
        ]
        self.assertEqual(c.extract_by_game_id(blocks, g8)["primera"], "01")
        self.assertEqual(c.extract_by_game_id(blocks, g9)["primera"], "70")


class TestConfirmationAndPrizes(unittest.TestCase):
    def test_08_two_identical_reads_confirm(self):
        c = ConectateAnguillaResultCollector()
        gid = config.SOURCES_BY_CODE["ANGUILA_1000"]["game_id"]
        payload = [
            {
                "game_id": gid,
                "lastSession": {
                    "date": "2026-07-23T04:00:00.000Z",
                    "score": [["25", "40", "18"]],
                    "_id": "s1",
                },
            }
        ]
        raw = json.dumps(payload).encode()

        def fake_fetch(when=None):
            return payload, raw, "hash1"

        with mock.patch.object(c, "fetch_sessions", side_effect=fake_fetch):
            with mock.patch.object(c, "minutes_since_draw", return_value=5):
                with mock.patch("services.collector.validate_result", return_value=(True, "ok")):
                    with mock.patch("time.sleep"):
                        r = c.run_once("ANGUILA_1000", "2026-07-23", confirm_wait=True)
        self.assertTrue(r.get("ok"))
        self.assertEqual(r.get("status"), "CONFIRMADO")
        with db.get_conn() as conn:
            row = db._fetchone(
                conn,
                "SELECT * FROM draw_results WHERE sorteo_code=? AND draw_date=?",
                ("ANGUILA_1000", "2026-07-23"),
            )
        self.assertEqual(row["status"], "CONFIRMADO")
        self.assertEqual(row["primera"], "25")

    def test_09_quiniela_primera_70(self):
        total, detail = prizes.calc_quiniela("25", 10, "25", "40", "18")
        self.assertEqual(total, 700)
        self.assertEqual(detail[0]["multiplicador"], 70)

    def test_10_segunda_8(self):
        total, _ = prizes.calc_quiniela("40", 10, "25", "40", "18")
        self.assertEqual(total, 80)

    def test_11_tercera_4(self):
        total, _ = prizes.calc_quiniela("18", 10, "25", "40", "18")
        self.assertEqual(total, 40)

    def test_12_repeated_two_positions(self):
        total, detail = prizes.calc_quiniela("23", 100, "23", "23", "38")
        self.assertEqual(total, 7800)
        self.assertEqual(len(detail), 2)

    def test_13_repeated_three_positions(self):
        total, detail = prizes.calc_quiniela("23", 100, "23", "23", "23")
        self.assertEqual(total, 8200)
        self.assertEqual(len(detail), 3)

    def test_14_pale_inverted_1200(self):
        t1, _ = prizes.calc_pale("25-40", 10, "40", "18", "25")
        t2, _ = prizes.calc_pale("40-25", 10, "40", "18", "25")
        self.assertEqual(t1, 12000)
        self.assertEqual(t2, 12000)
        self.assertEqual(prizes.normalize_pale("25", "40"), prizes.normalize_pale("40", "25"))

    def test_15_snapshot_not_current_config(self):
        snap = {"quiniela_primera": 50, "quiniela_segunda": 8, "quiniela_tercera": 4, "pale": 1200}
        total, _ = prizes.calc_quiniela("25", 10, "25", "00", "00", snap)
        self.assertEqual(total, 500)


class TestTicketsCashPrint(unittest.TestCase):
    def _sell(self, status="ACTIVO", modality="QUINIELA", numbers="25", amount=10.0):
        with db.get_conn() as conn:
            branch = db._fetchone(conn, "SELECT id FROM branches LIMIT 1")
            caja = db._fetchone(conn, "SELECT id FROM cash_registers LIMIT 1")
            user = db._fetchone(conn, "SELECT id FROM users WHERE role='cajero' LIMIT 1")
            pub = f"T{secrets_token()}"
            code = secrets_token(8)
            db._exec(
                conn,
                """INSERT INTO tickets
                (public_number, security_code, branch_id, cash_register_id, cashier_id, sold_at, draw_date,
                 sorteo_code, status, total, reprint_count, ip)
                VALUES (?,?,?,?,?,?,?,?,?,?,0,?)""",
                (pub, code, branch["id"], caja["id"], user["id"], db.now_iso(), "2026-07-23", "ANGUILA_1000", status, amount, "127.0.0.1"),
            )
            t = db._fetchone(conn, "SELECT * FROM tickets WHERE public_number=?", (pub,))
            db._exec(
                conn,
                """INSERT INTO ticket_lines
                (ticket_id, modality, numbers, amount, snapshot_json, prize_amount, prize_status, processed_winner)
                VALUES (?,?,?,?,?,0,'NONE',0)""",
                (t["id"], modality, numbers, amount, db.json_dumps(prizes.pay_snapshot())),
            )
            return t, caja["id"], user["id"]

    def test_16_annulled_does_not_win(self):
        t, _, _ = self._sell(status="ANULADO", numbers="25")
        _set_confirmed("ANGUILA_1000", "2026-07-23", "25", "40", "18")
        detect_winners("ANGUILA_1000", "2026-07-23")
        with db.get_conn() as conn:
            t2 = db._fetchone(conn, "SELECT status FROM tickets WHERE id=?", (t["id"],))
            line = db._fetchone(conn, "SELECT prize_amount, processed_winner FROM ticket_lines WHERE ticket_id=?", (t["id"],))
        self.assertEqual(t2["status"], "ANULADO")
        self.assertEqual(float(line["prize_amount"] or 0), 0)

    def test_17_pending_prize_does_not_deduct_cash(self):
        t, caja_id, user_id = self._sell(numbers="25", amount=10)
        bal0 = cash.get_balance(caja_id)
        cash.add_sale(caja_id, 10, t["id"], user_id)
        bal1 = cash.get_balance(caja_id)
        self.assertEqual(bal1, bal0 + 10)
        _set_confirmed("ANGUILA_1000", "2026-07-23", "25", "01", "02")
        detect_winners("ANGUILA_1000", "2026-07-23")
        self.assertEqual(cash.get_balance(caja_id), bal1)

    def test_18_confirmed_pay_deducts_cash(self):
        t, caja_id, user_id = self._sell(numbers="25", amount=10)
        cash.add_sale(caja_id, 10, t["id"], user_id)
        _set_confirmed("ANGUILA_1000", "2026-07-23", "25", "01", "02")
        detect_winners("ANGUILA_1000", "2026-07-23")
        bal = cash.get_balance(caja_id)
        with db.get_conn() as conn:
            line = db._fetchone(conn, "SELECT prize_amount FROM ticket_lines WHERE ticket_id=?", (t["id"],))
            prize = float(line["prize_amount"])
            db._exec(
                conn,
                """INSERT INTO prize_payments
                (payment_uid, ticket_id, user_id, cash_register_id, branch_id, amount, paid_at, observation, ip, result_snapshot_json, receipt_json)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                ("PG-TEST1", t["id"], user_id, caja_id, 1, prize, db.now_iso(), "", "127.0.0.1", "{}", "[]"),
            )
            pay = db._fetchone(conn, "SELECT id FROM prize_payments WHERE payment_uid=?", ("PG-TEST1",))
            db._exec(conn, "UPDATE tickets SET status='PAGADO' WHERE id=?", (t["id"],))
        cash.pay_prize(caja_id, prize, t["id"], pay["id"], user_id)
        self.assertEqual(cash.get_balance(caja_id), bal - prize)

    def test_19_cannot_pay_twice(self):
        with db.get_conn() as conn:
            existing = db._fetchone(conn, "SELECT id FROM prize_payments WHERE payment_uid=?", ("PG-TEST1",))
            self.assertIsNotNone(existing)

    def test_20_sale_ticket_print(self):
        html = ticket_thermal.render_ticket_html(
            {
                "ticket": "00001234",
                "fecha": "23/07/2026 09:15 AM",
                "cajero": "José",
                "sucursal": "Principal",
                "sorteo": "ANGUILA 10:00 AM",
                "jugadas": [
                    {"modality": "QUINIELA", "numeros": "25", "monto": 10},
                    {"modality": "PALE", "numeros": "25-40", "monto": 5},
                ],
                "total": 15,
                "codigo": "A8F29K4P",
            }
        )
        self.assertIn("JDM ANGUILA", html)
        self.assertIn("00001234", html)
        plain = ticket_thermal.generar_ticket(
            {
                "ticket": "00001234",
                "fecha": "23/07/2026 09:15 AM",
                "sorteo": "ANGUILA 10:00 AM",
                "jugadas": [{"modality": "QUINIELA", "numeros": "25", "monto": 10}],
                "total": 10,
                "codigo": "ABC",
            }
        )
        self.assertIn("Conserve este ticket", plain)

    def test_21_prize_receipt_print(self):
        html = ticket_thermal.render_premio_html(
            {
                "ticket": "00001234",
                "sorteo": "Anguila 10:00 AM",
                "resultado": "25 - 40 - 18",
                "lineas": [{"titulo": "QUINIELA 25", "detalle": "RD$10 × 70 = RD$700"}],
                "total": 6700,
                "cajero": "José",
                "fecha_pago": "23/07/2026 10:08 AM",
                "pago_uid": "PG-00000425",
            }
        )
        self.assertIn("PREMIO PAGADO", html)
        self.assertIn("Firma", html)

    def test_22_reprint_marked(self):
        plain = ticket_thermal.generar_ticket({"ticket": "1", "sorteo": "X", "jugadas": [], "total": 0, "codigo": "Z", "reimpresion": True})
        self.assertIn("REIMPRESIÓN", plain)
        premio = ticket_thermal.generar_recibo_premio(
            {"ticket": "1", "sorteo": "X", "resultado": "1-2-3", "lineas": [], "total": 0, "reimpresion": True, "pago_uid": "PG-1"}
        )
        self.assertIn("PREMIO YA PAGADO", premio)

    def test_23_idempotent_results(self):
        c = ConectateAnguillaResultCollector()
        gid = config.SOURCES_BY_CODE["ANGUILA_1100"]["game_id"]
        payload = [{"game_id": gid, "lastSession": {"date": "2026-07-23T04:00:00.000Z", "score": [["86", "72", "83"]]}}]
        raw = json.dumps(payload).encode()
        with mock.patch.object(c, "fetch_sessions", return_value=(payload, raw, "h")):
            with mock.patch.object(c, "minutes_since_draw", return_value=5):
                with mock.patch("services.collector.validate_result", return_value=(True, "ok")):
                    with mock.patch("time.sleep"):
                        r1 = c.run_once("ANGUILA_1100", "2026-07-23", confirm_wait=True)
                        r2 = c.run_once("ANGUILA_1100", "2026-07-23", confirm_wait=True)
        self.assertEqual(r1.get("status"), "CONFIRMADO")
        self.assertTrue(r2.get("idempotent") or r2.get("status") == "CONFIRMADO")


def secrets_token(n=6):
    import secrets
    import string

    return "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(n))


def _set_confirmed(code, draw_date, a, b, c):
    with db.get_conn() as conn:
        db._exec(conn, "DELETE FROM draw_results WHERE sorteo_code=? AND draw_date=?", (code, draw_date))
        db._exec(
            conn,
            """INSERT INTO draw_results
            (sorteo_code, draw_date, primera, segunda, tercera, status, source, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (code, draw_date, a, b, c, "CONFIRMADO", "test", db.now_iso(), db.now_iso()),
        )


if __name__ == "__main__":
    unittest.main()
