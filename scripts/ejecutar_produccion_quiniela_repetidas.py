#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ejecuta reporte/apply de Quiniela repetidas contra producción Render vía API admin."""
from __future__ import annotations

import argparse
import json
import os
import sys

try:
    import requests
except ImportError:
    print("pip install requests", file=sys.stderr)
    sys.exit(2)

BASE = os.environ.get("BANCA_PROD_URL", "https://banca-la-que-nunca-falla.onrender.com").rstrip("/")


def login(session, username, password):
    r = session.post(
        f"{BASE}/login",
        data={"username": username, "password": password},
        timeout=90,
        allow_redirects=True,
    )
    if r.status_code not in (200, 302):
        return False, "HTTP %s" % r.status_code
    if "Contraseña incorrecta" in r.text or "Usuario no existe" in r.text:
        return False, "credenciales inválidas"
    if "/admin" in r.url or session.cookies:
        return True, "ok"
    if "logout" in r.text.lower() or "cerrar sesión" in r.text.lower():
        return True, "ok"
    return True, "ok (asumido)"


def call_impacto(session, dry_run=True, fecha_desde=None, fecha_hasta=None):
    payload = {"dry_run": dry_run}
    if not dry_run:
        payload = {"apply": True}
    if fecha_desde:
        payload["fecha_desde"] = fecha_desde
    if fecha_hasta:
        payload["fecha_hasta"] = fecha_hasta
    r = session.post(
        f"{BASE}/api/admin/quiniela_repetidas_impacto",
        json=payload,
        timeout=300,
    )
    try:
        data = r.json()
    except Exception:
        data = {"ok": False, "error": r.text[:500]}
    return r.status_code, data


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--user", default=os.environ.get("BANCA_ADMIN_USER", "jose0219"))
    p.add_argument("--password", default=os.environ.get("BANCA_ADMIN_PASSWORD", ""))
    p.add_argument("--apply", action="store_true")
    p.add_argument("--fecha-desde", default="")
    p.add_argument("--fecha-hasta", default="")
    args = p.parse_args()
    if not args.password:
        print("Define BANCA_ADMIN_PASSWORD o --password", file=sys.stderr)
        sys.exit(2)
    s = requests.Session()
    s.headers.update({"User-Agent": "banca-quiniela-repetidas-script/1"})
    ok, msg = login(s, args.user, args.password)
    if not ok:
        print("Login falló:", msg, file=sys.stderr)
        sys.exit(1)
    code, data = call_impacto(
        s,
        dry_run=not args.apply,
        fecha_desde=(args.fecha_desde or None),
        fecha_hasta=(args.fecha_hasta or None),
    )
    print(json.dumps(data, ensure_ascii=False, indent=2))
    if code != 200 or not data.get("ok"):
        sys.exit(1)


if __name__ == "__main__":
    main()
