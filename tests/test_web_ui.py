"""UI surface tests for the revamped Flask web app.

These tests cover the new console-style frontend introduced by the parallel
Style / Markup / Interactions / Viewport / Backend agents. They assert HTML
contract only — no JS execution — and are grouped by concern:

* Topbar & sidebar structure (#app root, topbar buttons, HUD quadrants)
* CDN asset links (htmx, alpine, lucide, Google Fonts)
* New static files (shortcuts / presets / history / hud JS; design-token CSS)
* /api/meta metadata endpoint shape
* Content-Security-Policy header + SHIPFORGE_CSP=0 opt-out
* JSON 404 negotiation via Accept header
* DOM contract preservation (form name=, hx-post, randomize-all alias)
* Accessibility basics (aria-labels on topbar buttons / gizmo, reduced motion)
* HTMX wiring preservation (hx-target, hx-swap, hx-indicator)

Tests follow the same Flask test-client fixture pattern as ``test_web.py`` so
the two files stay idiomatically consistent. All new tests carry the
``@pytest.mark.ui`` marker for easy grouping (``pytest -m ui``) but we do not
register the marker in ``pyproject.toml``; pytest treats unknown markers as a
warning (not an error), so older configs keep working.
"""

from __future__ import annotations

import re

import pytest

from spaceship_generator.web.app import create_app


# --- Fixtures ---------------------------------------------------------------


@pytest.fixture
def client(tmp_path, monkeypatch):
    app = create_app()
    app.config["TESTING"] = True
    monkeypatch.setattr(app, "instance_path", str(tmp_path))
    with app.test_client() as c:
        yield c


# --- Small helpers ----------------------------------------------------------


def _has_any(body: str, *needles: str) -> bool:
    """Return True if any of ``needles`` appears in ``body``.

    Used to tolerate attribute quote-style variance (``id='x'`` vs
    ``id="x"``) without writing long ``or`` chains in every assert.
    """
    return any(n in body for n in needles)


def _id_attr(ident: str) -> tuple[str, str]:
    """Return both double-quoted and single-quoted ``id="..."`` forms.

    Spreading the result with ``*`` makes call sites concise::

        assert _has_any(body, *_id_attr("btn-generate"))
    """
    return (f'id="{ident}"', f"id='{ident}'")


# --- TestTopbarAndSidebar ---------------------------------------------------


@pytest.mark.ui
class TestTopbarAndSidebar:
    """#app root, topbar buttons, sidebar, viewport, HUD quadrants."""

    def test_app_root_present(self, client):
        body = client.get("/").get_data(as_text=True)
        assert _has_any(body, *_id_attr("app")), (
            "root <div id=\"app\"> not found in index"
        )

    def test_btn_generate_in_topbar(self, client):
        body = client.get("/").get_data(as_text=True)
        assert _has_any(body, *_id_attr("btn-generate"))

    def test_btn_random_or_alias_present(self, client):
        """Random button: contract allows either ``btn-random`` or the legacy
        ``randomize-all`` alias. At least one must be present."""
        body = client.get("/").get_data(as_text=True)
        assert _has_any(
            body,
            *_id_attr("btn-random"),
            *_id_attr("randomize-all"),
        ), "no random button id (btn-random or randomize-all) in index"

    def test_panel_params_sidebar(self, client):
        body = client.get("/").get_data(as_text=True)
        assert _has_any(body, *_id_attr("panel-params")), (
            "parameters sidebar #panel-params not found"
        )

    def test_viewport_main_area(self, client):
        body = client.get("/").get_data(as_text=True)
        assert _has_any(body, *_id_attr("viewport")), (
            "main viewport #viewport not found"
        )

    def test_viewport_hud_and_four_quadrants(self, client):
        body = client.get("/").get_data(as_text=True)
        assert _has_any(body, *_id_attr("viewport-hud")), "missing #viewport-hud"
        # The four HUD quadrants (top-left, top-right, bottom-left, bottom-right).
        for quadrant in ("hud-tl", "hud-tr", "hud-bl", "hud-br"):
            assert quadrant in body, f"HUD quadrant {quadrant!r} missing"

    @pytest.mark.parametrize(
        "btn_id",
        [
            "btn-view-top",
            "btn-view-front",
            "btn-view-side",
            "btn-view-persp",
            "btn-view-reset",
        ],
    )
    def test_view_preset_buttons(self, client, btn_id):
        body = client.get("/").get_data(as_text=True)
        assert _has_any(body, *_id_attr(btn_id)), f"missing view preset {btn_id}"

    def test_keyboard_help_button(self, client):
        body = client.get("/").get_data(as_text=True)
        assert _has_any(body, *_id_attr("btn-help"))

    def test_fullscreen_button(self, client):
        body = client.get("/").get_data(as_text=True)
        assert _has_any(body, *_id_attr("btn-fullscreen"))

    def test_history_toggle_button(self, client):
        body = client.get("/").get_data(as_text=True)
        assert _has_any(body, *_id_attr("btn-toggle-history"))

    def test_stat_readouts(self, client):
        body = client.get("/").get_data(as_text=True)
        assert _has_any(body, *_id_attr("stat-voxels"))
        assert _has_any(body, *_id_attr("stat-fps"))

    def test_axis_gizmo_canvas(self, client):
        body = client.get("/").get_data(as_text=True)
        assert _has_any(body, *_id_attr("axis-gizmo")), "#axis-gizmo canvas missing"

    def test_history_drawer_panel(self, client):
        body = client.get("/").get_data(as_text=True)
        assert _has_any(body, *_id_attr("panel-history"))


# --- TestCdnAssets ----------------------------------------------------------


@pytest.mark.ui
class TestCdnAssets:
    """CDN script tags and Google Fonts link must be present in <head>."""

    def test_htmx_cdn_script(self, client):
        body = client.get("/").get_data(as_text=True)
        assert "https://unpkg.com/htmx.org" in body, "htmx CDN script missing"

    def test_alpinejs_cdn_script(self, client):
        body = client.get("/").get_data(as_text=True)
        assert "https://unpkg.com/alpinejs@" in body, "Alpine.js CDN script missing"

    def test_lucide_cdn_script(self, client):
        body = client.get("/").get_data(as_text=True)
        assert "https://unpkg.com/lucide@" in body, "Lucide CDN script missing"

    def test_google_fonts_inter_and_mono(self, client):
        body = client.get("/").get_data(as_text=True)
        # Google Fonts CSS import. The href carries both Inter and JetBrains Mono
        # as a single ``family=...&family=...`` pair.
        assert "fonts.googleapis.com" in body, "Google Fonts link missing"
        assert "Inter" in body
        assert "JetBrains+Mono" in body or "JetBrains Mono" in body


# --- TestNewStaticFiles -----------------------------------------------------


@pytest.mark.ui
class TestNewStaticFiles:
    """Script / CSS files referenced from base.html must resolve (200)."""

    @pytest.mark.parametrize(
        "path",
        [
            "/static/shortcuts.js",
            "/static/presets.js",
            "/static/history.js",
            "/static/hud.js",
            "/static/app.js",
        ],
    )
    def test_js_asset_served(self, client, path):
        resp = client.get(path)
        assert resp.status_code == 200, f"{path} returned {resp.status_code}"

    def test_style_css_served_and_has_design_token(self, client):
        resp = client.get("/static/style.css")
        assert resp.status_code == 200
        body = resp.get_data(as_text=True)
        # Design-token sanity check: the console theme exposes `--accent-cyan`.
        assert "--accent-cyan" in body, (
            "style.css missing --accent-cyan design token"
        )


# --- TestApiMeta ------------------------------------------------------------


@pytest.mark.ui
class TestApiMeta:
    """``GET /api/meta`` returns UI metadata used by the frontend."""

    def test_returns_json_200(self, client):
        resp = client.get("/api/meta")
        assert resp.status_code == 200
        assert resp.is_json, "/api/meta must return JSON"

    def test_shape_has_expected_keys(self, client):
        data = client.get("/api/meta").get_json()
        for key in ("palettes", "cockpit_styles", "structure_styles",
                    "param_help", "defaults", "version"):
            assert key in data, f"/api/meta response missing key {key!r}"

    def test_palettes_is_non_empty_list(self, client):
        data = client.get("/api/meta").get_json()
        assert isinstance(data["palettes"], list)
        assert len(data["palettes"]) > 0, "/api/meta palettes list empty"

    def test_structure_styles_covers_enum(self, client):
        from spaceship_generator.shape import StructureStyle

        data = client.get("/api/meta").get_json()
        styles = data["structure_styles"]
        assert isinstance(styles, list)
        for s in StructureStyle:
            assert s.value in styles, (
                f"/api/meta missing StructureStyle.{s.name} ({s.value!r})"
            )

    def test_defaults_shape(self, client):
        """Defaults must include at least the anchor params the UI wires up."""
        data = client.get("/api/meta").get_json()
        defaults = data["defaults"]
        assert isinstance(defaults, dict)
        for key in ("seed", "palette", "length", "width", "height"):
            assert key in defaults, f"/api/meta defaults missing {key!r}"


# --- TestCsp ----------------------------------------------------------------


@pytest.mark.ui
class TestCsp:
    """Content-Security-Policy header: default on, opt-out via env var."""

    def test_csp_header_present_by_default(self, client):
        resp = client.get("/")
        assert "Content-Security-Policy" in resp.headers, (
            "CSP header missing on default /"
        )

    def test_csp_allows_unpkg_cdn(self, client):
        resp = client.get("/")
        csp = resp.headers.get("Content-Security-Policy", "")
        assert "https://unpkg.com" in csp, (
            "CSP must allow https://unpkg.com (htmx/alpine/lucide CDN)"
        )

    def test_csp_allows_google_fonts_styles(self, client):
        resp = client.get("/")
        csp = resp.headers.get("Content-Security-Policy", "")
        assert "https://fonts.googleapis.com" in csp, (
            "CSP must allow https://fonts.googleapis.com"
        )

    def test_csp_can_be_disabled_via_env(self, tmp_path, monkeypatch):
        """``SHIPFORGE_CSP=0`` disables the header (dev escape hatch).

        We build a fresh client here because the env var is read per-request
        by the ``after_request`` hook; the standard ``client`` fixture doesn't
        set this env var.
        """
        monkeypatch.setenv("SHIPFORGE_CSP", "0")
        app = create_app()
        app.config["TESTING"] = True
        monkeypatch.setattr(app, "instance_path", str(tmp_path))
        with app.test_client() as c:
            resp = c.get("/")
            assert "Content-Security-Policy" not in resp.headers, (
                "SHIPFORGE_CSP=0 should suppress CSP header, but it was present"
            )


# --- TestJsonFourOhFour -----------------------------------------------------


@pytest.mark.ui
class TestJsonFourOhFour:
    """404 negotiation: JSON vs HTML based on Accept header."""

    def test_json_404_returns_structured_body(self, client):
        resp = client.get(
            "/definitely-not-a-real-path",
            headers={"Accept": "application/json"},
        )
        assert resp.status_code == 404
        # Must be JSON with the documented shape.
        assert resp.is_json, "JSON-Accept 404 should return JSON"
        data = resp.get_json()
        assert data.get("error") == "not_found"
        assert data.get("path") == "/definitely-not-a-real-path"

    def test_html_404_still_text(self, client):
        resp = client.get(
            "/definitely-not-a-real-path",
            headers={"Accept": "text/html"},
        )
        assert resp.status_code == 404
        # HTML accept path: body is not JSON — just a plain text-y response.
        assert not resp.is_json, (
            "HTML-Accept 404 should not be JSON (preserves Flask default)"
        )


# --- TestDomContractPreserved -----------------------------------------------


# All 17 input names the backend accepts on /generate. Kept in a class-level
# constant so the parametrized test and any future coverage see the same list.
_EXPECTED_FORM_INPUTS = (
    "seed",
    "palette",
    "length",
    "width",
    "height",
    "engines",
    "wing_prob",
    "greeble_density",
    "cockpit",
    "structure_style",
    "window_period",
    "accent_stripe_period",
    "engine_glow_depth",
    "hull_noise_ratio",
    "panel_line_bands",
    "rivet_period",
    "engine_glow_ring",
)


@pytest.mark.ui
class TestDomContractPreserved:
    """Post-revamp, the pre-existing backend contract must not regress."""

    def test_form_has_hx_post_to_generate(self, client):
        body = client.get("/").get_data(as_text=True)
        # ``url_for('do_generate')`` resolves to /generate. Accept either
        # bare path or any single-quoted variant.
        assert (
            'hx-post="/generate"' in body
            or "hx-post='/generate'" in body
        ), "form missing hx-post=/generate"

    @pytest.mark.parametrize("name", _EXPECTED_FORM_INPUTS)
    def test_form_input_name_present(self, client, name):
        body = client.get("/").get_data(as_text=True)
        assert (
            f'name="{name}"' in body or f"name='{name}'" in body
        ), f"form input name={name!r} missing after revamp"

    def test_randomize_all_alias_still_resolves(self, client):
        """The DOM contract says ``randomize-all`` is preserved either as a
        literal id or as an alias on the new topbar random button."""
        body = client.get("/").get_data(as_text=True)
        assert _has_any(body, *_id_attr("randomize-all")) or _has_any(
            body, *_id_attr("btn-random")
        ), "randomize-all / btn-random alias missing"

    def test_engine_glow_ring_checkbox_with_label(self, client):
        body = client.get("/").get_data(as_text=True)
        # Checkbox input with explicit id + name.
        assert _has_any(body, *_id_attr("engine_glow_ring")), (
            "engine_glow_ring input id missing"
        )
        assert 'name="engine_glow_ring"' in body, "engine_glow_ring name= missing"
        # Label must be associated with the input — either via wrapping
        # <label> + nested input, or explicit ``for="engine_glow_ring"``.
        assert (
            'for="engine_glow_ring"' in body
            or "for='engine_glow_ring'" in body
        ), "no <label for=engine_glow_ring> associated with the checkbox"

    def test_progressbar_role_present(self, client):
        """Progress / generating indicator must expose ``role="progressbar"``
        so assistive tech can announce it, per the DOM contract."""
        body = client.get("/").get_data(as_text=True)
        assert 'role="progressbar"' in body or "role='progressbar'" in body, (
            "no element with role=progressbar found (generating indicator)"
        )


# --- TestAccessibilityBasics ------------------------------------------------


@pytest.mark.ui
class TestAccessibilityBasics:
    """Low-cost accessibility smoke tests on the static HTML surface."""

    def test_topbar_buttons_carry_aria_label(self, client):
        """Every topbar button id must have an ``aria-label`` somewhere on the
        same element. We scope the check by scanning each button tag that
        carries one of the expected ids and verifying ``aria-label=`` appears
        inside the same tag.
        """
        body = client.get("/").get_data(as_text=True)

        topbar_ids = (
            "btn-generate",
            "btn-toggle-history",
            "btn-help",
            "btn-fullscreen",
        )
        for ident in topbar_ids:
            # Match the <button ... id="ident" ... > opening tag; tolerate
            # attributes in any order / either quote style.
            tag_match = re.search(
                r"<button\b[^>]*\b"
                + r"id=['\"]" + re.escape(ident) + r"['\"]"
                + r"[^>]*>",
                body,
            )
            assert tag_match is not None, (
                f"<button id={ident!r}> opening tag not found"
            )
            tag = tag_match.group()
            assert "aria-label" in tag, (
                f"<button id={ident!r}> has no aria-label attribute"
            )

    def test_axis_gizmo_has_aria_label(self, client):
        body = client.get("/").get_data(as_text=True)
        # Match the <canvas ... id="axis-gizmo" ... > opening tag and verify
        # aria-label is inside it.
        tag = re.search(
            r"<canvas\b[^>]*\bid=['\"]axis-gizmo['\"][^>]*>",
            body,
        )
        assert tag is not None, "<canvas id=axis-gizmo> not found"
        assert "aria-label" in tag.group(), (
            "<canvas id=axis-gizmo> has no aria-label"
        )

    def test_css_respects_prefers_reduced_motion(self, client):
        """CSS must include a ``prefers-reduced-motion`` media query so users
        who opted out of motion get a calmer UI (Style agent requirement)."""
        resp = client.get("/static/style.css")
        assert resp.status_code == 200
        css = resp.get_data(as_text=True)
        assert "prefers-reduced-motion" in css, (
            "style.css must include a prefers-reduced-motion media query"
        )


# --- TestHtmxPreservation ---------------------------------------------------


@pytest.mark.ui
class TestHtmxPreservation:
    """HTMX attributes on the generator form must survive the revamp."""

    def test_hx_target_points_at_result_panel(self, client):
        body = client.get("/").get_data(as_text=True)
        assert (
            'hx-target="#result-panel"' in body
            or "hx-target='#result-panel'" in body
        ), "form hx-target=#result-panel missing"

    def test_hx_swap_inner_html(self, client):
        body = client.get("/").get_data(as_text=True)
        assert (
            'hx-swap="innerHTML"' in body
            or "hx-swap='innerHTML'" in body
        ), "form hx-swap=innerHTML missing"

    def test_hx_indicator_present(self, client):
        body = client.get("/").get_data(as_text=True)
        # Accept any hx-indicator= selector; the concrete target (#gen-indicator)
        # is not load-bearing for this test.
        assert re.search(r"hx-indicator\s*=", body) is not None, (
            "form hx-indicator attribute missing"
        )
