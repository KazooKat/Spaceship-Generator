"""Tests for the Flask web UI using the test client."""

from __future__ import annotations

import re

import pytest

from spaceship_generator.web.app import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    app = create_app()
    app.config["TESTING"] = True
    # Route instance_path to tmp_path so generated files land outside the repo.
    monkeypatch.setattr(app, "instance_path", str(tmp_path))
    with app.test_client() as c:
        yield c


def test_get_index(client):
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Spaceship Generator" in body
    assert "<form" in body
    assert "sci_fi_industrial" in body


def test_generate_flow(client):
    resp = client.post(
        "/generate",
        data={
            "seed": "7",
            "palette": "sci_fi_industrial",
            "length": "24",
            "width": "12",
            "height": "8",
            "engines": "2",
            "wing_prob": "0.5",
            "greeble_density": "0.05",
            "window_period": "4",
            "cockpit": "bubble",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert resp.headers["Location"].startswith("/result/")
    # Extract gen_id
    gen_id = resp.headers["Location"].rsplit("/", 1)[-1]

    # GET /result/<gen_id>
    result_resp = client.get(f"/result/{gen_id}")
    assert result_resp.status_code == 200
    body = result_resp.get_data(as_text=True)
    assert "Download .litematic" in body
    assert f'src="/preview/{gen_id}.png"' in body

    # GET preview PNG
    preview_resp = client.get(f"/preview/{gen_id}.png")
    assert preview_resp.status_code == 200
    assert preview_resp.mimetype == "image/png"
    assert preview_resp.data.startswith(b"\x89PNG")

    # GET download
    dl_resp = client.get(f"/download/{gen_id}")
    assert dl_resp.status_code == 200
    assert "attachment" in dl_resp.headers.get("Content-Disposition", "")
    assert len(dl_resp.data) > 0


def test_generate_invalid_param_shows_error(client):
    resp = client.post(
        "/generate",
        data={
            "seed": "1",
            "palette": "sci_fi_industrial",
            "length": "4",  # invalid
            "width": "12",
            "height": "8",
            "engines": "2",
            "wing_prob": "0.5",
            "greeble_density": "0.05",
            "window_period": "4",
            "cockpit": "bubble",
        },
    )
    assert resp.status_code == 400
    body = resp.get_data(as_text=True)
    assert "Error" in body
    assert "length" in body.lower()


def test_generate_missing_palette_shows_error(client):
    resp = client.post(
        "/generate",
        data={
            "seed": "1",
            "palette": "does_not_exist",
            "length": "20",
            "width": "12",
            "height": "8",
            "engines": "2",
            "wing_prob": "0.5",
            "greeble_density": "0.05",
            "window_period": "4",
            "cockpit": "bubble",
        },
    )
    assert resp.status_code == 400


def test_missing_gen_id_404(client):
    assert client.get("/result/nonexistent").status_code == 404
    assert client.get("/preview/nonexistent.png").status_code == 404
    assert client.get("/download/nonexistent").status_code == 404
