# -*- coding: utf-8 -*-
"""Configuración JDM Anguila — fuente Conectate auditada 2026-07-23."""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

SECRET_KEY = os.environ.get("SECRET_KEY", "jdm-anguila-dev-change-me")
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
SQLITE_PATH = os.environ.get("SQLITE_PATH", str(BASE_DIR / "data" / "jdm_anguila.db"))

BANK_NAME = os.environ.get("BANK_NAME", "JDM ANGUILA")
BANK_ADDRESS = os.environ.get("BANK_ADDRESS", "Sucursal Principal")
BANK_PHONE = os.environ.get("BANK_PHONE", "")
TICKET_MESSAGE = os.environ.get("TICKET_MESSAGE", "Conserve este ticket")
TIMEZONE = "America/Santo_Domingo"

CLOSE_BEFORE_DRAW_MINUTES = int(os.environ.get("CLOSE_BEFORE_DRAW_MINUTES", "5"))

# Pagos iniciales por RD$1
PAY_QUINIELA_PRIMERA = float(os.environ.get("PAY_QUINIELA_PRIMERA", "70"))
PAY_QUINIELA_SEGUNDA = float(os.environ.get("PAY_QUINIELA_SEGUNDA", "8"))
PAY_QUINIELA_TERCERA = float(os.environ.get("PAY_QUINIELA_TERCERA", "4"))
PAY_PALE = float(os.environ.get("PAY_PALE", "1200"))

DEFAULT_PAY_SNAPSHOT = {
    "quiniela_primera": PAY_QUINIELA_PRIMERA,
    "quiniela_segunda": PAY_QUINIELA_SEGUNDA,
    "quiniela_tercera": PAY_QUINIELA_TERCERA,
    "pale": PAY_PALE,
}

API_SESSIONS_URL = "https://api.conectate.com.do/conectate/sessions"
USER_AGENT = "JDM-Anguila-Collector/1.0 (+results; no-bot-evasion)"
COLLECTOR_TIMEOUT_SEC = int(os.environ.get("COLLECTOR_TIMEOUT_SEC", "25"))
COLLECTOR_MAX_RETRIES = int(os.environ.get("COLLECTOR_MAX_RETRIES", "3"))

ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
CAJERO_USER = os.environ.get("CAJERO_USER", "jose")
CAJERO_PASSWORD = os.environ.get("CAJERO_PASSWORD", "jose123")

# Mapa editable — investigación Conectate (no inventar URLs)
ANGUILLA_RESULT_SOURCES = [
    {
        "code": "ANGUILA_0800",
        "nombre": "Anguila 8:00 AM",
        "hora_oficial": "08:00",
        "url": "https://loterias.conectate.com.do/anguilla/anguila-8-am/",
        "seo_url": "anguila-8-am",
        "game_id": "6a5114d907d516b9c5101dd5",
        "estado_fuente": "VERIFICADO",
    },
    {
        "code": "ANGUILA_0900",
        "nombre": "Anguila 9:00 AM",
        "hora_oficial": "09:00",
        "url": "https://loterias.conectate.com.do/anguilla/anguila-9-am/",
        "seo_url": "anguila-9-am",
        "game_id": "6a3e91bd5036a431f5f3e801",
        "estado_fuente": "VERIFICADO",
    },
    {
        "code": "ANGUILA_1000",
        "nombre": "Anguila 10:00 AM",
        "hora_oficial": "10:00",
        "url": "https://loterias.conectate.com.do/anguilla/anguila-10-am/",
        "seo_url": "anguila-10-am",
        "game_id": "6966a6d3ea7015c3b8a3d635",
        "estado_fuente": "VERIFICADO",
    },
    {
        "code": "ANGUILA_1100",
        "nombre": "Anguila 11:00 AM",
        "hora_oficial": "11:00",
        "url": "https://loterias.conectate.com.do/anguilla/anguila-11-am/",
        "seo_url": "anguila-11-am",
        "game_id": "6a3e935d5036a431f5f3e8b2",
        "estado_fuente": "VERIFICADO",
    },
    {
        "code": "ANGUILA_1200",
        "nombre": "Anguila 12:00 PM",
        "hora_oficial": "12:00",
        "url": None,
        "seo_url": None,
        "game_id": "6a3e94f85036a431f5f407b0",
        "estado_fuente": "FUENTE_NO_DISPONIBLE",
        "nota": "Sin página propia verificable. Entrada manual solamente.",
    },
    {
        "code": "ANGUILA_1300",
        "nombre": "Anguila 1:00 PM",
        "hora_oficial": "13:00",
        "url": "https://loterias.conectate.com.do/anguilla/anguila-12-pm/",
        "seo_url": "anguila-12-pm",
        "game_id": "6966a6d3ea7015c3b8a3d611",
        "estado_fuente": "VERIFICADO_CON_RIESGO",
        "nota": "Slug engañoso: anguila-12-pm es 1 PM en HTML.",
    },
    {
        "code": "ANGUILA_1400",
        "nombre": "Anguila 2:00 PM",
        "hora_oficial": "14:00",
        "url": "https://loterias.conectate.com.do/anguilla/anguila-2-pm/",
        "seo_url": "anguila-2-pm",
        "game_id": "6a3e96e25036a431f5f40c87",
        "estado_fuente": "VERIFICADO",
    },
    {
        "code": "ANGUILA_1500",
        "nombre": "Anguila 3:00 PM",
        "hora_oficial": "15:00",
        "url": "https://loterias.conectate.com.do/anguilla/anguila-3-pm/",
        "seo_url": "anguila-3-pm",
        "game_id": "6a3e97a25036a431f5f41eef",
        "estado_fuente": "VERIFICADO",
    },
    {
        "code": "ANGUILA_1600",
        "nombre": "Anguila 4:00 PM",
        "hora_oficial": "16:00",
        "url": "https://loterias.conectate.com.do/anguilla/anguila-4pm/",
        "seo_url": "anguila-4pm",
        "game_id": "6a5116a607d516b9c5102db7",
        "estado_fuente": "VERIFICADO",
    },
    {
        "code": "ANGUILA_1700",
        "nombre": "Anguila 5:00 PM",
        "hora_oficial": "17:00",
        "url": "https://loterias.conectate.com.do/anguilla/anguila-5pm/",
        "seo_url": "anguila-5pm",
        "game_id": "6a5116f607d516b9c510302f",
        "estado_fuente": "VERIFICADO",
    },
    {
        "code": "ANGUILA_1800",
        "nombre": "Anguila 6:00 PM",
        "hora_oficial": "18:00",
        "url": "https://loterias.conectate.com.do/anguilla/anguila-5-pm/",
        "seo_url": "anguila-5-pm",
        "game_id": "6966a6d3ea7015c3b8a3d617",
        "estado_fuente": "VERIFICADO_CON_RIESGO",
        "nota": "Slug engañoso: anguila-5-pm es 6 PM (no confundir con anguila-5pm).",
    },
    {
        "code": "ANGUILA_1900",
        "nombre": "Anguila 7:00 PM",
        "hora_oficial": "19:00",
        "url": "https://loterias.conectate.com.do/anguilla/anguila-7pm/",
        "seo_url": "anguila-7pm",
        "game_id": "6a51185b07d516b9c5104c69",
        "estado_fuente": "VERIFICADO",
    },
    {
        "code": "ANGUILA_2000",
        "nombre": "Anguila 8:00 PM",
        "hora_oficial": "20:00",
        "url": "https://loterias.conectate.com.do/anguilla/anguila-8pm/",
        "seo_url": "anguila-8pm",
        "game_id": "6a511ab407d516b9c510788d",
        "estado_fuente": "VERIFICADO",
    },
    {
        "code": "ANGUILA_2100",
        "nombre": "Anguila 9:00 PM",
        "hora_oficial": "21:00",
        "url": "https://loterias.conectate.com.do/anguilla/anguila-9-pm/",
        "seo_url": "anguila-9-pm",
        "game_id": "6966a6d3ea7015c3b8a3d61d",
        "estado_fuente": "VERIFICADO",
    },
    {
        "code": "ANGUILA_2200",
        "nombre": "Anguila 10:00 PM",
        "hora_oficial": "22:00",
        "url": "https://loterias.conectate.com.do/anguilla/anguila-10pm/",
        "seo_url": "anguila-10pm",
        "game_id": "6a511b0a07d516b9c5107d05",
        "estado_fuente": "VERIFICADO",
    },
]

CUARTETA_EXCLUDED = [
    {
        "code": "CUARTETA_1000",
        "nombre": "La Cuarteta 10:00 AM",
        "url": "https://loterias.conectate.com.do/anguilla/la-cuarteta-manana/",
        "game_id": "6966a6d3ea7015c3b8a3d63b",
    },
    {
        "code": "CUARTETA_1300",
        "nombre": "La Cuarteta 1:00 PM",
        "url": "https://loterias.conectate.com.do/anguilla/cuarteta-medio-dia/",
        "game_id": "6966a6d3ea7015c3b8a3d623",
    },
    {
        "code": "CUARTETA_1800",
        "nombre": "La Cuarteta 6:00 PM",
        "url": "https://loterias.conectate.com.do/anguilla/cuarteta-tarde/",
        "game_id": "6966a6d3ea7015c3b8a3d629",
    },
    {
        "code": "CUARTETA_2100",
        "nombre": "La Cuarteta 9:00 PM",
        "url": "https://loterias.conectate.com.do/anguilla/cuarteta-noche/",
        "game_id": "6966a6d3ea7015c3b8a3d62f",
    },
]

CUARTETA_GAME_IDS = {c["game_id"] for c in CUARTETA_EXCLUDED}
SOURCES_BY_CODE = {s["code"]: s for s in ANGUILLA_RESULT_SOURCES}
SOURCES_BY_GAME_ID = {s["game_id"]: s for s in ANGUILLA_RESULT_SOURCES if s.get("game_id")}
