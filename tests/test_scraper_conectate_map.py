"""Regresión: mapeo títulos Conectate/LD → La Suerte Dominicana y King Lottery."""
from __future__ import annotations

import pytest


@pytest.mark.parametrize(
    "title,expected_key,lottery,draw",
    [
        ("La Suerte Día", "La Suerte MD", "La Suerte Dominicana", "12:30 PM"),
        ("La Suerte Dia", "La Suerte MD", "La Suerte Dominicana", "12:30 PM"),
        ("La Suerte Tarde", "La Suerte 6PM", "La Suerte Dominicana", "6:00 PM"),
        ("La Suerte 12:30", "La Suerte MD", "La Suerte Dominicana", "12:30 PM"),
        ("La Suerte 18:00", "La Suerte 6PM", "La Suerte Dominicana", "6:00 PM"),
        ("King Lottery Día", "King Lottery 12:30", "King Lottery", "12:30 PM"),
        ("King Lottery Dia", "King Lottery 12:30", "King Lottery", "12:30 PM"),
        ("King Lottery Noche", "King Lottery 7:30", "King Lottery", "7:30 PM"),
        ("King Lottery 12:30", "King Lottery 12:30", "King Lottery", "12:30 PM"),
        ("King Lottery 7:30", "King Lottery 7:30", "King Lottery", "7:30 PM"),
    ],
)
def test_conectate_label_suerte_king_dia_noche(app_mod, title, expected_key, lottery, draw):
    app = app_mod
    key = app._conectate_label_to_internal_key(title)
    assert key == expected_key
    lot_db, draw_db = app.RESULT_LOTTERY_TO_TICKET[key]
    assert lot_db == lottery
    assert draw_db == draw


def test_conectate_label_anguila_8am_doble_espacio(app_mod):
    """Conectate publica a veces «Anguila 8:00  AM» (doble espacio) — debe mapear igual."""
    app = app_mod
    for title in ("Anguila 8:00  AM", "Anguila  8:00 AM", "  Anguila 8:00 AM  "):
        key = app._conectate_label_to_internal_key(title)
        assert key == "Anguila 8:00 AM", title
        lot_db, draw_db = app.RESULT_LOTTERY_TO_TICKET[key]
        assert lot_db == "La Anguila"
        assert draw_db == "8:00 AM"


def test_parse_sites_env_payload_anguila_8am_doble_espacio(app_mod):
    app = app_mod
    payload = {
        "siteCompanies": [
            {
                "siteGames": [
                    {
                        "title": "Anguila 8:00  AM",
                        "game": {
                            "sessions": [
                                {"score": [["97", "96", "14"]], "date": "2026-07-23T04:00:00.000Z"}
                            ]
                        },
                    }
                ]
            }
        ]
    }
    data = app._resultados_parse_sites_env_payload(payload, "2026-07-23", "Conectate-test")
    k = app._resultados_scraper_storage_key("Anguila 8:00 AM", "2026-07-23")
    assert k in data
    assert data[k]["loteria"] == "La Anguila"
    assert data[k]["sorteo"] == "8:00 AM"
    assert (data[k]["n1"], data[k]["n2"], data[k]["n3"]) == ("97", "96", "14")



def test_parse_sites_env_payload_suerte_king(app_mod):
    app = app_mod
    payload = {
        "siteCompanies": [
            {
                "siteGames": [
                    {
                        "title": "La Suerte Día",
                        "game": {"sessions": [{"score": [["20", "41", "77"]], "date": "2026-06-27"}]},
                    },
                    {
                        "title": "La Suerte Tarde",
                        "game": {"sessions": [{"score": [["22", "59", "19"]], "date": "2026-06-27"}]},
                    },
                    {
                        "title": "King Lottery Día",
                        "game": {"sessions": [{"score": [["27", "97", "66"]], "date": "2026-06-27"}]},
                    },
                    {
                        "title": "King Lottery Noche",
                        "game": {"sessions": [{"score": [["55", "75", "09"]], "date": "2026-06-27"}]},
                    },
                ]
            }
        ]
    }
    data = app._resultados_parse_sites_env_payload(payload, "2026-06-27", "Conectate-test")
    assert set(data.keys()) == {
        app._resultados_scraper_storage_key("La Suerte MD", "2026-06-27"),
        app._resultados_scraper_storage_key("La Suerte 6PM", "2026-06-27"),
        app._resultados_scraper_storage_key("King Lottery 12:30", "2026-06-27"),
        app._resultados_scraper_storage_key("King Lottery 7:30", "2026-06-27"),
    }
    k_md = app._resultados_scraper_storage_key("La Suerte MD", "2026-06-27")
    k_kn = app._resultados_scraper_storage_key("King Lottery 7:30", "2026-06-27")
    assert data[k_md]["loteria"] == "La Suerte Dominicana"
    assert data[k_md]["sorteo"] == "12:30 PM"
    assert data[k_kn]["sorteo"] == "7:30 PM"
