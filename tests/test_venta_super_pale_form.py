"""Formulario Super Pale: ambos selectores de lotería habilitados y con lista."""
from __future__ import annotations

import pathlib
import time


def _session_cajero(client):
    with client.session_transaction() as sess:
        sess["u"] = "cajero_sp"
        sess["uid"] = 2
        sess["role"] = "cajero"
        sess["last_activity"] = time.time()
        sess["last_activity_touch"] = time.time()


def test_venta_super_pale_first_lotery_select_enabled(app_mod, client):
    _session_cajero(client)
    r = client.get("/venta")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'id="ventaLot1Pick"' in html
    assert 'id="ventaLot2Pick"' in html
    assert '1ª lotería (Super Pale)' in html
    assert '2ª lotería (Super Pale)' in html
    assert 'id="ventaLot1Pick" disabled' not in html
    assert "<select id=\"ventaLot1Pick\" disabled" not in html


def test_venta_pos_super_pale_both_pickers_use_same_lot_list(app_mod):
    root = pathlib.Path(__file__).resolve().parents[1]
    js = (root / "static" / "venta_pos.js").read_text(encoding="utf-8")
    assert "function superPaleLotOptionsHtml" in js
    assert "refreshLot1Pick" in js
    assert "refreshLot2Pick" in js
    assert "superPaleLotOptionsHtml()" in js
    assert 'getElementById("ventaLot1Pick")' in js
    assert "ventaLot1Pick" in js and "disabled" not in js.split("refreshLot1Pick")[1].split("function refreshLot2Pick")[0]
