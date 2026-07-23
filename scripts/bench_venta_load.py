"""Prueba de carga local: POST /venta con muchas jugadas + GET concurrente."""
from __future__ import annotations

import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("SQLITE_DB", os.path.join(ROOT, "bench_venta_load.db"))
os.environ.pop("DATABASE_URL", None)
os.environ["ENABLE_RESULTADOS_SCHEDULER"] = ""

import app as app_module  # noqa: E402

app_module._DB_SCHEMA_READY = False
if os.path.exists(os.environ["SQLITE_DB"]):
    os.remove(os.environ["SQLITE_DB"])
app_module.init_db()

client = app_module.app.test_client()


def _patch(monkey=None):
    app_module.caja_cerrada_hoy = lambda: False
    app_module.is_admin_or_super = lambda: True
    app_module.loteria_cerrada_para_venta = lambda *a, **k: False
    app_module.ventas_loterias_permiso_horario_global = lambda: True
    app_module._validar_limites_banca_venta = lambda *a, **k: (True, "")
    app_module._reservar_sale_key = lambda *a, **k: (True, None)
    app_module._marcar_sale_key_ticket = lambda *a, **k: None
    app_module.banco_registrar_venta = lambda *a, **k: {"ok": True}
    app_module._venta_sync_balance_cajero_background = lambda *a, **k: None


_patch()

with client.session_transaction() as sess:
    sess["u"] = "bench_cajero"
    sess["uid"] = 1
    sess["last_activity"] = time.time()


def build_form(n_lines: int, sale_key: str) -> dict:
    data = {"sale_key": sale_key}
    for i in range(n_lines):
        data.setdefault("loteria[]", []).append("Loteka")
        data.setdefault("sorteo[]", []).append("7:55 PM")
        data.setdefault("numero[]", []).append(f"{i % 100:02d}")
        data.setdefault("jugada[]", []).append("Quiniela")
        data.setdefault("monto[]", []).append("10")
    return data


def post_venta(n_lines: int, sale_key: str):
    t0 = time.perf_counter()
    resp = client.post("/venta", data=build_form(n_lines, sale_key), follow_redirects=False)
    ms = (time.perf_counter() - t0) * 1000
    return resp.status_code, ms


def get_venta():
    t0 = time.perf_counter()
    resp = client.get("/venta")
    ms = (time.perf_counter() - t0) * 1000
    return resp.status_code, ms


if __name__ == "__main__":
    sizes = [50, 100, 200]
    print("=== Bench POST /venta (local SQLite) ===")
    for n in sizes:
        code, ms = post_venta(n, f"bench-sale-{n}-{time.time_ns()}")
        print(f"  {n:3d} jugadas -> HTTP {code} en {ms:.0f} ms")

    print("\n=== Bench concurrente: POST 100 jugadas + 3x GET /venta ===")
    with ThreadPoolExecutor(max_workers=4) as ex:
        futures = [ex.submit(post_venta, 100, f"bench-conc-{time.time_ns()}")]
        futures += [ex.submit(get_venta) for _ in range(3)]
        for fut in as_completed(futures):
            code, ms = fut.result()
            print(f"  HTTP {code} en {ms:.0f} ms")
