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
        assert _has_any(body, *_id_attr("stat-dims"))
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


# --- TestStylePickers -------------------------------------------------------


def _style_form_base():
    """Minimal form body covering the pre-existing required fields.

    The style-picker tests add/override keys on top of this dict — keeps each
    test focused on the fields it actually cares about.
    """
    return {
        "seed": "42",
        "palette": "sci_fi_industrial",
        "length": "20",
        "width": "12",
        "height": "8",
        "engines": "1",
        "wing_prob": "0.0",
        "greeble_density": "0.0",
        "window_period": "4",
        "cockpit": "bubble",
        "structure_style": "frigate",
        "wing_style": "straight",
    }


@pytest.mark.ui
class TestStylePickers:
    """New style picker controls (hull_style, engine_style, wing_style,
    greeble_density slider) wired into the Styles panel of the form.

    The four dials route through ``build_params_from_source`` into the
    generator pipeline. ``wing_style`` was pre-existing and is verified
    alongside the three new pickers so the whole contract stays in one place.
    """

    # All four control names the spec asks for. ``wing_style`` already lived
    # in the Shape section before this change; the others (hull_style,
    # engine_style, greeble_density slider) were added in the Styles section.
    _NEW_CONTROL_NAMES = ("hull_style", "engine_style", "wing_style", "greeble_density")

    @pytest.mark.parametrize("name", _NEW_CONTROL_NAMES)
    def test_get_renders_all_four_controls(self, client, name):
        """GET / must render all four style-picker controls."""
        body = client.get("/").get_data(as_text=True)
        assert (
            f'name="{name}"' in body or f"name='{name}'" in body
        ), f"style picker name={name!r} missing from rendered index"

    def test_get_renders_auto_option_for_new_selects(self, client):
        """Both hull_style and engine_style selects must offer an ``auto``
        option as the user-picker default — "auto" maps to ``None`` in
        ``build_params_from_source`` and lets the generator decide."""
        body = client.get("/").get_data(as_text=True)
        # Each select has its own <option value="auto">auto</option>.
        # At least two "auto" option lines must be present (hull + engine).
        assert body.count('value="auto"') >= 2, (
            "expected at least two <option value=\"auto\"> entries "
            "(one each for hull_style and engine_style)"
        )

    def test_get_renders_every_hull_style_value(self, client):
        """The hull_style select must include every HullStyle enum value."""
        from spaceship_generator.structure_styles import HullStyle

        body = client.get("/").get_data(as_text=True)
        for h in HullStyle:
            assert f'value="{h.value}"' in body, (
                f"hull_style option {h.value!r} missing from select"
            )

    def test_get_renders_every_engine_style_value(self, client):
        """The engine_style select must include every EngineStyle enum value."""
        from spaceship_generator.engine_styles import EngineStyle

        body = client.get("/").get_data(as_text=True)
        for e in EngineStyle:
            assert f'value="{e.value}"' in body, (
                f"engine_style option {e.value!r} missing from select"
            )

    def test_greeble_density_is_range_slider_with_readout(self, client):
        """The greeble density control must be a <input type=range>
        min=0 max=1 step=0.05 with a live label (span readout)."""
        body = client.get("/").get_data(as_text=True)
        # The whole slider tag lives on one logical element; match just the
        # id= attribute and then verify the surrounding range attributes in
        # a regex-agnostic way so attribute order doesn't matter.
        slider_tag = re.search(
            r'<input[^>]*id="greeble_density"[^>]*>',
            body,
        )
        assert slider_tag is not None, "greeble_density <input> not found"
        tag = slider_tag.group()
        assert 'type="range"' in tag, "greeble_density must be type=range"
        assert 'min="0"' in tag, "greeble_density missing min=0"
        assert 'max="1"' in tag, "greeble_density missing max=1"
        # Live readout span wired to the slider.
        assert 'id="greeble_density_readout"' in body, (
            "greeble_density_readout span missing (live label)"
        )

    def test_post_with_valid_style_values_generates_200(self, client):
        """POST /generate with the new pickers set to valid values must
        complete successfully (HTMX path returns the result partial)."""
        form = _style_form_base() | {
            "hull_style": "arrow",
            "engine_style": "single_core",
            "wing_style": "straight",
            "greeble_density": "0.25",
        }
        resp = client.post(
            "/generate", data=form, headers={"HX-Request": "true"}
        )
        assert resp.status_code == 200, (
            f"POST /generate with valid style values returned "
            f"{resp.status_code}: {resp.get_data(as_text=True)[:300]}"
        )

    def test_post_with_auto_style_values_generates_200(self, client):
        """"auto" is the default sentinel and must not break generate —
        forwarded as ``None`` to ``generate`` so the pipeline keeps its own
        defaults."""
        form = _style_form_base() | {
            "hull_style": "auto",
            "engine_style": "auto",
            "greeble_density": "0.0",
        }
        resp = client.post(
            "/generate", data=form, headers={"HX-Request": "true"}
        )
        assert resp.status_code == 200, (
            f"auto-auto POST returned {resp.status_code}"
        )

    def test_post_with_invalid_hull_style_still_returns_ok_or_400(self, client):
        """An unknown hull_style must not 500. Acceptable outcomes are:

        * 200 — the fallback path silently dropped the bad kwarg and
          generation succeeded.
        * 400 — parser rejected the value as bad input.

        What matters is we never crash the worker with a 500."""
        form = _style_form_base() | {
            "hull_style": "not_a_real_style",
            "engine_style": "auto",
        }
        resp = client.post(
            "/generate", data=form, headers={"HX-Request": "true"}
        )
        assert resp.status_code in (200, 400), (
            f"invalid hull_style should be 200 or 400, got {resp.status_code}"
        )

    def test_post_with_greeble_density_out_of_range_is_clamped(self, client):
        """Values above 1.0 must be clamped to 1.0 server-side rather than
        rejected. The POST completes and the resulting generate call sees a
        clamped density ≤ 1.0 (verified indirectly by a 200 response — the
        generator validates ``greeble_density`` ∈ [0, 1] and would 400 if
        the clamp weren't applied)."""
        form = _style_form_base() | {
            "hull_style": "auto",
            "engine_style": "auto",
            # Way above the 0-1 slider range. build_params_from_source must
            # clamp this to 1.0 before forwarding to generate().
            "greeble_density": "5.0",
        }
        resp = client.post(
            "/generate", data=form, headers={"HX-Request": "true"}
        )
        assert resp.status_code == 200, (
            f"out-of-range greeble_density should be clamped + 200, got "
            f"{resp.status_code}: {resp.get_data(as_text=True)[:300]}"
        )

    def test_parse_clamps_greeble_density_directly(self):
        """Unit-level check on ``build_params_from_source``: the parser must
        clamp the returned ``extra_gen_kwargs['greeble_density']`` to [0, 1]
        regardless of incoming value. Verifies the clamp independently of
        the route pipeline."""
        from spaceship_generator.web.blueprints.ship_support import (
            build_params_from_source,
        )

        source = _style_form_base() | {"greeble_density": "2.5"}
        seed, _palette, _shape, _tex, extras = build_params_from_source(source)
        assert seed == 42
        assert 0.0 <= extras["greeble_density"] <= 1.0, (
            f"expected clamped greeble_density in [0, 1]; got "
            f"{extras['greeble_density']!r}"
        )
        # Sanity: ``extras`` must carry the three top-level style keys so
        # the route can forward them through ``**extras``.
        for key in ("hull_style", "engine_style", "greeble_density"):
            assert key in extras, (
                f"build_params_from_source missing extras key {key!r}"
            )

    def test_api_meta_exposes_hull_and_engine_style_lists(self, client):
        """``/api/meta`` must publish the hull_styles and engine_styles enum
        values so the JSON-driven frontend can render the same pickers."""
        from spaceship_generator.engine_styles import EngineStyle
        from spaceship_generator.structure_styles import HullStyle

        data = client.get("/api/meta").get_json()
        assert "hull_styles" in data, "/api/meta missing hull_styles key"
        assert "engine_styles" in data, "/api/meta missing engine_styles key"
        for h in HullStyle:
            assert h.value in data["hull_styles"]
        for e in EngineStyle:
            assert e.value in data["engine_styles"]


# --- TestCockpitWeaponControls ----------------------------------------------


@pytest.mark.ui
class TestCockpitWeaponControls:
    """New STYLES section controls: cockpit_style override, weapon_count,
    weapon_types (multi-select).

    All three feed :func:`build_params_from_source` into ``extra_gen_kwargs``
    and flow through the same ``try/except TypeError`` fallback helper as the
    pre-existing hull / engine pickers. ``cockpit_style`` is intentionally
    distinct from the shape-level ``cockpit`` field (which stays on
    ``ShapeParams``).
    """

    def test_get_renders_all_three_new_controls(self, client):
        """GET / must render every new form field name on the page."""
        body = client.get("/").get_data(as_text=True)
        for name in ("cockpit_style", "weapon_count", "weapon_types"):
            assert (
                f'name="{name}"' in body or f"name='{name}'" in body
            ), f"new control name={name!r} missing from rendered index"

    def test_cockpit_style_select_has_auto_and_all_enum_values(self, client):
        """The cockpit_style <select> must offer ``auto`` plus every
        :class:`CockpitStyle` value. ``auto`` maps to ``None`` server-side."""
        from spaceship_generator.shape import CockpitStyle

        body = client.get("/").get_data(as_text=True)
        # Find the <select name="cockpit_style"> ... </select> block so we
        # scope the option check tightly (``auto`` is reused elsewhere).
        m = re.search(
            r'<select[^>]*name="cockpit_style"[^>]*>(.*?)</select>',
            body,
            re.DOTALL,
        )
        assert m is not None, "cockpit_style <select> not found"
        block = m.group(1)
        assert 'value="auto"' in block, "cockpit_style missing auto option"
        for c in CockpitStyle:
            assert f'value="{c.value}"' in block, (
                f"cockpit_style option {c.value!r} missing"
            )

    def test_weapon_count_input_attributes(self, client):
        """weapon_count must be a number input with min=0, max=8, step=1,
        default value 0 — matches the server-side clamp range."""
        body = client.get("/").get_data(as_text=True)
        m = re.search(
            r'<input[^>]*name="weapon_count"[^>]*>',
            body,
        )
        assert m is not None, "weapon_count <input> not found"
        tag = m.group()
        assert 'type="number"' in tag, "weapon_count must be type=number"
        assert 'min="0"' in tag, "weapon_count missing min=0"
        assert 'max="8"' in tag, "weapon_count missing max=8"
        assert 'step="1"' in tag, "weapon_count missing step=1"
        assert 'value="0"' in tag, "weapon_count default should be 0"

    def test_weapon_types_is_multiple_select_with_all_enum_values(self, client):
        """weapon_types must be a <select multiple> with every WeaponType
        value as an option."""
        from spaceship_generator.weapon_styles import WeaponType

        body = client.get("/").get_data(as_text=True)
        m = re.search(
            r'<select[^>]*name="weapon_types"[^>]*>(.*?)</select>',
            body,
            re.DOTALL,
        )
        assert m is not None, "weapon_types <select> not found"
        tag = body[m.start():m.start() + 200]
        assert "multiple" in tag, "weapon_types must be a multi-select"
        block = m.group(1)
        for w in WeaponType:
            assert f'value="{w.value}"' in block, (
                f"weapon_types option {w.value!r} missing"
            )

    def test_post_with_wrap_bridge_cockpit_and_weapons_returns_200(self, client):
        """POST /generate with cockpit_style=wrap_bridge, weapon_count=2,
        weapon_types=[turret_large] must complete successfully."""
        form = _style_form_base() | {
            "cockpit_style": "wrap_bridge",
            "weapon_count": "2",
            "weapon_types": ["turret_large"],
        }
        resp = client.post(
            "/generate", data=form, headers={"HX-Request": "true"}
        )
        assert resp.status_code == 200, (
            f"POST with wrap_bridge + 2 turrets returned "
            f"{resp.status_code}: {resp.get_data(as_text=True)[:300]}"
        )

    def test_post_with_weapon_count_999_is_clamped_to_8(self, client):
        """Huge weapon_count values must be clamped server-side rather than
        rejected — we verify the clamp at the parser level so we don't need
        the generator to actually succeed with 999 weapons."""
        from spaceship_generator.web.blueprints.ship_support import (
            build_params_from_source,
        )

        form = _style_form_base() | {"weapon_count": "999"}
        _seed, _pal, _shape, _tex, extras = build_params_from_source(form)
        assert extras["weapon_count"] == 8, (
            f"expected weapon_count clamped to 8, got {extras['weapon_count']!r}"
        )
        # And the route doesn't crash with a clamped value.
        resp = client.post(
            "/generate", data=form, headers={"HX-Request": "true"}
        )
        assert resp.status_code == 200, (
            f"clamped-weapon-count POST returned {resp.status_code}"
        )

    def test_post_with_invalid_cockpit_style_returns_200_or_400(self, client):
        """Unknown cockpit_style values must never 500 — either the parser
        rejects with 400 or the generator fallback silently succeeds."""
        form = _style_form_base() | {"cockpit_style": "not_a_real_cockpit"}
        resp = client.post(
            "/generate", data=form, headers={"HX-Request": "true"}
        )
        assert resp.status_code in (200, 400), (
            f"invalid cockpit_style should be 200 or 400, got {resp.status_code}"
        )

    def test_api_meta_exposes_cockpit_and_weapon_types_lists(self, client):
        """``/api/meta`` must publish cockpit_styles (already present) and the
        new weapon_types enum list so a JSON-driven frontend can render
        the same pickers."""
        from spaceship_generator.shape import CockpitStyle
        from spaceship_generator.weapon_styles import WeaponType

        data = client.get("/api/meta").get_json()
        assert "cockpit_styles" in data, "/api/meta missing cockpit_styles key"
        assert "weapon_types" in data, "/api/meta missing weapon_types key"
        for c in CockpitStyle:
            assert c.value in data["cockpit_styles"]
        for w in WeaponType:
            assert w.value in data["weapon_types"]

    def test_default_values_auto_zero_empty_parse_cleanly(self):
        """Unit-level: default values for all three new controls must parse
        to ``(None, 0, None)`` in ``extra_gen_kwargs`` so the generator sees
        the "auto / none / all types" baseline."""
        from spaceship_generator.web.blueprints.ship_support import (
            build_params_from_source,
        )

        # Plain dict mirrors a JSON body. No weapon_types field = empty list
        # downstream. weapon_count absent = 0. cockpit_style = "auto" → None.
        source = _style_form_base() | {
            "cockpit_style": "auto",
            "weapon_count": "0",
        }
        _seed, _pal, _shape, _tex, extras = build_params_from_source(source)
        assert extras["cockpit_style"] is None, (
            f"expected cockpit_style=None for auto, got {extras['cockpit_style']!r}"
        )
        assert extras["weapon_count"] == 0, (
            f"expected weapon_count=0, got {extras['weapon_count']!r}"
        )
        assert extras["weapon_types"] is None, (
            f"expected weapon_types=None when unset, got {extras['weapon_types']!r}"
        )

    def test_unknown_weapon_type_token_dropped_with_warning(self, capsys):
        """Unknown tokens in weapon_types must be dropped (not raise) and a
        warning must be emitted on stderr."""
        from werkzeug.datastructures import ImmutableMultiDict

        from spaceship_generator.web.blueprints.ship_support import (
            build_params_from_source,
        )

        # Mix valid + invalid tokens. Use MultiDict so ``getlist`` works.
        items = list(_style_form_base().items()) + [
            ("weapon_types", "turret_large"),
            ("weapon_types", "bogus_weapon"),
        ]
        source = ImmutableMultiDict(items)
        _seed, _pal, _shape, _tex, extras = build_params_from_source(source)
        # Only the known token survived.
        assert extras["weapon_types"] is not None
        values = [w.value for w in extras["weapon_types"]]
        assert values == ["turret_large"], (
            f"expected only turret_large survived, got {values!r}"
        )
        # Warning emitted on stderr.
        captured = capsys.readouterr()
        assert "bogus_weapon" in captured.err, (
            f"expected stderr warning about bogus_weapon; got {captured.err!r}"
        )


# --- TestPreviewLite --------------------------------------------------------


@pytest.mark.ui
class TestPreviewLite:
    """``GET /preview-lite`` — debounced live-preview PNG endpoint.

    The live-preview sidebar toggle hits this route on every debounced
    form change. Contract assertions here pin the small footprint that the
    client-side code relies on: PNG mimetype, Cache-Control header, bad
    input → 400 (not a 500), and rate-limiter still applies (no bypass).
    """

    def test_preview_lite_returns_png_200(self, client):
        resp = client.get(
            "/preview-lite?seed=42&palette=sci_fi_industrial"
        )
        assert resp.status_code == 200, (
            f"expected 200 PNG, got {resp.status_code}"
        )
        assert resp.mimetype == "image/png", (
            f"expected image/png mimetype, got {resp.mimetype!r}"
        )
        # Real PNG magic header — we rendered a non-empty image.
        body = resp.get_data()
        assert body[:8] == b"\x89PNG\r\n\x1a\n", "response is not a valid PNG"
        assert len(body) > 0, "PNG body empty"

    def test_preview_lite_missing_required_param_returns_400(self, client):
        # ``palette`` has a safe default; to force 400, feed an invalid enum.
        resp = client.get(
            "/preview-lite?seed=1&palette=sci_fi_industrial"
            "&structure_style=not_a_real_structure"
        )
        assert resp.status_code == 400, (
            f"expected 400 on invalid structure_style, got {resp.status_code}"
        )

    def test_preview_lite_has_cache_control_header(self, client):
        resp = client.get(
            "/preview-lite?seed=7&palette=sci_fi_industrial"
        )
        assert resp.status_code == 200
        cc = resp.headers.get("Cache-Control", "")
        # Both ``public`` and a max-age directive must be present.
        assert "public" in cc and "max-age=30" in cc, (
            f"expected Cache-Control 'public, max-age=30', got {cc!r}"
        )

    def test_index_contains_live_preview_toggle(self, client):
        body = client.get("/").get_data(as_text=True)
        assert _has_any(body, *_id_attr("live-preview-toggle")), (
            "index.html missing #live-preview-toggle checkbox"
        )
        assert _has_any(body, *_id_attr("live-preview-img")), (
            "index.html missing #live-preview-img output img"
        )
        # Caption about reduced resolution, shown to set expectations.
        assert "1/4-resolution" in body, (
            "index.html missing live-preview resolution caption"
        )
        # Script include from the task spec.
        assert "live_preview.js" in body, (
            "index.html missing live_preview.js script include"
        )

    def test_preview_lite_rate_limiter_still_applies(self, tmp_path, monkeypatch):
        """Spam 31 requests with a non-loopback X-Forwarded-For header →
        the 31st must 429 (limit defaults to 30/min). Loopback is exempt
        so we inject the fake upstream IP via XFF so the limiter counts."""
        # Build a fresh app; reset default (30/min) so exactly one request
        # past the limit trips the limiter.
        monkeypatch.delenv("SHIPFORGE_RATE_LIMIT", raising=False)
        monkeypatch.delenv("SHIPFORGE_RATE_WINDOW", raising=False)
        app = create_app()
        app.config["TESTING"] = True
        monkeypatch.setattr(app, "instance_path", str(tmp_path))
        url = "/preview-lite?seed=1&palette=sci_fi_industrial"
        # Minimal ship dims so 30 renders complete fast enough under test.
        url += "&length=8&width=4&height=4&engines=0&wing_prob=0.0"
        headers = {"X-Forwarded-For": "203.0.113.42"}
        with app.test_client() as c:
            statuses: list[int] = []
            for _ in range(31):
                statuses.append(c.get(url, headers=headers).status_code)
        assert statuses.count(429) >= 1, (
            f"expected at least one 429 after 31 spam requests; statuses={statuses}"
        )


# --- TestPresetDropdown -----------------------------------------------------


@pytest.mark.ui
class TestPresetDropdown:
    """Top-of-form ``<select name="preset">`` drives preset merging.

    The dropdown lists every :func:`spaceship_generator.presets.list_presets`
    role with ``(none)`` (empty value) as the default. When the user picks a
    preset, the server seeds generation from ``apply_preset(name)`` and any
    explicitly-set form field wins — matching the CLI's ``--preset`` +
    per-flag override rule.
    """

    def test_index_renders_preset_select_with_all_values(self, client):
        """GET / must render ``<select name="preset">`` carrying the empty
        default plus every preset name from :func:`list_presets`."""
        from spaceship_generator.presets import list_presets

        body = client.get("/").get_data(as_text=True)
        # The <select> block itself; regex-scope so the preset-specific
        # options are checked inside the right element (``auto`` and other
        # common tokens live in sibling selects).
        m = re.search(
            r'<select[^>]*name="preset"[^>]*>(.*?)</select>',
            body,
            re.DOTALL,
        )
        assert m is not None, 'form missing <select name="preset">'
        block = m.group(1)
        # Empty default so the form submits "no preset" unless the user
        # opts in — matches the "(none)" sentinel parsed server-side.
        assert 'value=""' in block, "preset select missing empty (none) option"
        # Every list_presets() name must be an option value.
        names = list_presets()
        assert len(names) >= 6, (
            f"expected at least 6 presets; got {len(names)}: {names!r}"
        )
        for name in names:
            assert f'value="{name}"' in block, (
                f"preset option {name!r} missing from <select>"
            )

    def test_api_meta_exposes_presets_list(self, client):
        """``/api/meta`` must expose the same preset list as the template."""
        from spaceship_generator.presets import list_presets

        data = client.get("/api/meta").get_json()
        assert "presets" in data, "/api/meta missing 'presets' key"
        assert isinstance(data["presets"], list)
        assert data["presets"] == list_presets(), (
            f"/api/meta presets out of sync with list_presets(); "
            f"got {data['presets']!r}"
        )

    def test_post_with_preset_corvette_uses_preset_styles(self, client):
        """POST with ``preset=corvette`` and no style fields → 200 and the
        parser seeds generation from the preset. We verify via the parser
        directly so we don't depend on the generator's output shape."""
        from spaceship_generator.presets import apply_preset
        from spaceship_generator.structure_styles import HullStyle
        from spaceship_generator.web.blueprints.ship_support import (
            build_params_from_source,
        )

        # Form-level POST must succeed end-to-end.
        form = {
            "seed": "42",
            "palette": "sci_fi_industrial",
            "preset": "corvette",
        }
        resp = client.post(
            "/generate", data=form, headers={"HX-Request": "true"}
        )
        assert resp.status_code == 200, (
            f"preset=corvette POST returned {resp.status_code}: "
            f"{resp.get_data(as_text=True)[:300]}"
        )

        # Parser-level verification: the preset's hull/engine/greeble seep
        # through when no explicit style field is set.
        source = {"seed": "42", "palette": "sci_fi_industrial", "preset": "corvette"}
        _seed, _pal, shape_params, _tex, extras = build_params_from_source(source)
        expected = apply_preset("corvette")
        assert extras["hull_style"] == expected["hull_style"], (
            f"preset hull_style not applied; got {extras['hull_style']!r}, "
            f"expected {expected['hull_style']!r}"
        )
        assert extras["engine_style"] == expected["engine_style"], (
            f"preset engine_style not applied; got {extras['engine_style']!r}"
        )
        assert extras["hull_style"] == HullStyle.DAGGER, (
            "corvette preset's DAGGER hull not wired through"
        )
        # Preset's wing + cockpit flow into ShapeParams the same way as the CLI.
        assert shape_params.wing_style == expected["shape_params"].wing_style
        assert shape_params.cockpit_style == expected["shape_params"].cockpit_style

    def test_post_with_preset_and_explicit_hull_style_override_wins(self, client):
        """POST with ``preset=corvette`` + ``hull_style=saucer`` → user value
        wins. Mirrors the CLI rule: explicit flag beats preset default."""
        from spaceship_generator.structure_styles import HullStyle
        from spaceship_generator.web.blueprints.ship_support import (
            build_params_from_source,
        )

        form = {
            "seed": "42",
            "palette": "sci_fi_industrial",
            "preset": "corvette",
            # Explicit style pick must override corvette's DAGGER default.
            "hull_style": "saucer",
        }
        resp = client.post(
            "/generate", data=form, headers={"HX-Request": "true"}
        )
        assert resp.status_code == 200, (
            f"preset+override POST returned {resp.status_code}: "
            f"{resp.get_data(as_text=True)[:300]}"
        )
        # Parser-level verification of the priority rule.
        _seed, _pal, _shape, _tex, extras = build_params_from_source(form)
        assert extras["hull_style"] == HullStyle.SAUCER, (
            f"explicit hull_style=saucer must override preset; "
            f"got {extras['hull_style']!r}"
        )

    def test_post_with_unknown_preset_is_ignored(self, client):
        """POST with an unknown preset name must not 500 — the parser
        silently drops the preset and the request uses the raw form. We
        allow either 200 (silent-ignore path) or 400 (if a stricter future
        implementation chooses to reject) per the task spec."""
        from spaceship_generator.web.blueprints.ship_support import (
            _parse_preset,
            build_params_from_source,
        )

        # _parse_preset drops unknown names up front → returns None, so no
        # merge is attempted and the raw form drives parsing.
        assert _parse_preset({"preset": "nonexistent"}) is None
        assert _parse_preset({"preset": ""}) is None
        assert _parse_preset({}) is None

        # End-to-end: POST must not crash.
        form = {
            "seed": "42",
            "palette": "sci_fi_industrial",
            "preset": "nonexistent",
        }
        resp = client.post(
            "/generate", data=form, headers={"HX-Request": "true"}
        )
        assert resp.status_code in (200, 400), (
            f"unknown preset should be 200 (ignored) or 400, got "
            f"{resp.status_code}"
        )

        # Parser-level: the extras dict has no preset-specific side effects
        # when the preset name is unknown.
        _seed, _pal, _shape, _tex, extras = build_params_from_source(form)
        # Default hull_style is None (from "auto") when not picked.
        assert extras["hull_style"] is None, (
            f"unknown preset should not seed hull_style; got {extras['hull_style']!r}"
        )


# --- TestDownloadFleet ------------------------------------------------------


@pytest.mark.ui
class TestDownloadFleet:
    """``GET /download-fleet`` — bulk fleet planner + zipped litematic export.

    Packs ``count`` ships into a single ``application/zip`` response. Shares
    validation and the per-IP rate limiter with the rest of the web surface.
    Generation is heavy (count × full generate()), so tests drop ``count``
    to 2-3 and keep to the smallest valid size tier where possible.
    """

    def test_normal_request_returns_zip_with_n_litematic_entries(self, client):
        """count=3, small tier → zip with exactly 3 non-empty .litematic entries.

        ``small`` keeps each ship cheap (15x10x25-ish dims) so the test
        completes quickly even on CI. The zip envelope must be a proper
        PK-header zip; every entry name must end in ``.litematic``; every
        entry must be non-empty so we know generate() actually wrote bytes.
        """
        import io as _io
        import zipfile as _zipfile

        resp = client.get(
            "/download-fleet"
            "?seed=42&palette=sci_fi_industrial&count=3&size_tier=small"
            "&style_coherence=0.7"
        )
        assert resp.status_code == 200, (
            f"expected 200 zip, got {resp.status_code}: "
            f"{resp.get_data(as_text=True)[:300]}"
        )
        assert resp.mimetype == "application/zip", (
            f"expected application/zip, got {resp.mimetype!r}"
        )
        # Content-Disposition carries the documented filename shape.
        cd = resp.headers.get("Content-Disposition", "")
        assert "fleet_42_sci_fi_industrial.zip" in cd, (
            f"Content-Disposition missing fleet filename; got {cd!r}"
        )

        body = resp.get_data()
        # Real zip magic header (``PK\x03\x04``).
        assert body[:2] == b"PK", "response is not a valid zip archive"

        with _zipfile.ZipFile(_io.BytesIO(body)) as zf:
            names = zf.namelist()
            assert len(names) == 3, (
                f"expected 3 entries in zip, got {len(names)}: {names!r}"
            )
            for name in names:
                assert name.endswith(".litematic"), (
                    f"non-.litematic entry in fleet zip: {name!r}"
                )
                size = zf.getinfo(name).file_size
                assert size > 0, f"zip entry {name!r} is empty"

    @pytest.mark.parametrize("bad_count", ["0", "100", "-1", "21"])
    def test_invalid_count_returns_400(self, client, bad_count):
        """count outside [1, 20] must 400. Covers both the 0 and "too big"
        edges from the task spec plus the neighbouring boundary (21)."""
        resp = client.get(
            f"/download-fleet?seed=1&palette=sci_fi_industrial"
            f"&count={bad_count}&size_tier=small"
        )
        assert resp.status_code == 400, (
            f"expected 400 for count={bad_count!r}, got {resp.status_code}"
        )
        assert resp.is_json, "400 response should be JSON"
        assert "error" in resp.get_json()

    def test_invalid_palette_returns_400(self, client):
        """Unknown palette name must 400 with a JSON error, never 500 —
        we validate the palette up front so we never start generating."""
        resp = client.get(
            "/download-fleet"
            "?seed=1&palette=__definitely_not_a_palette__&count=2"
            "&size_tier=small"
        )
        assert resp.status_code == 400, (
            f"expected 400 for bad palette, got {resp.status_code}: "
            f"{resp.get_data(as_text=True)[:300]}"
        )
        assert resp.is_json
        assert "error" in resp.get_json()

    def test_determinism_same_seed_same_filenames_and_sizes(self, client):
        """Same seed+params → same filenames in the same order.

        Filenames are derived from per-ship seeds, which come straight from
        the deterministic ``fleet.generate_fleet`` planner, so the filename
        list itself is the rock-solid deterministic surface. We do NOT
        assert raw byte equality (litemapy's gzip stream bakes its own
        mtime into the ``.litematic`` payload) nor per-entry file size (the
        same gzip-mtime drift bumps the compressed length by a byte or two
        between calls). Per-entry sizes land within a small tolerance; we
        check that too so gross non-determinism (e.g. wrong seed threading)
        still fails the test.
        """
        import io as _io
        import zipfile as _zipfile

        url = (
            "/download-fleet?seed=7&palette=sci_fi_industrial"
            "&count=2&size_tier=small&style_coherence=0.9"
        )
        resp1 = client.get(url)
        resp2 = client.get(url)
        assert resp1.status_code == 200 and resp2.status_code == 200, (
            f"both determinism requests must succeed; got "
            f"{resp1.status_code}, {resp2.status_code}"
        )

        def _name_size_map(raw: bytes) -> dict[str, int]:
            with _zipfile.ZipFile(_io.BytesIO(raw)) as zf:
                return {info.filename: info.file_size for info in zf.infolist()}

        map1 = _name_size_map(resp1.get_data())
        map2 = _name_size_map(resp2.get_data())

        # Filename set + order must match exactly — this is the strong
        # determinism claim backed by fleet.generate_fleet.
        assert list(map1.keys()) == list(map2.keys()), (
            f"fleet zip filenames differ across calls; "
            f"first={list(map1.keys())!r} second={list(map2.keys())!r}"
        )
        # Per-entry sizes match within a tiny tolerance. litemapy's gzip
        # mtime can shift the compressed length by a single byte between
        # calls even when the raw voxel grid is identical; anything larger
        # indicates a real non-determinism bug.
        for name in map1:
            assert abs(map1[name] - map2[name]) <= 4, (
                f"entry {name!r} size drifted too much: "
                f"{map1[name]} vs {map2[name]}"
            )
        # Sanity: count matches what we asked for.
        assert len(map1) == 2, f"expected 2 ships, got {len(map1)}: {map1!r}"

    def test_rate_limiter_still_applies(self, tmp_path, monkeypatch):
        """31 spam requests with a non-loopback XFF → at least one 429.

        Uses count=1+size_tier=small so each request is as cheap as the
        pipeline allows. We can't truly undercut the generator's fixed
        cost, so this test is intentionally slow-ish (30+ tiny fleets) and
        still finishes well under the default per-test budget.
        """
        monkeypatch.delenv("SHIPFORGE_RATE_LIMIT", raising=False)
        monkeypatch.delenv("SHIPFORGE_RATE_WINDOW", raising=False)
        app = create_app()
        app.config["TESTING"] = True
        monkeypatch.setattr(app, "instance_path", str(tmp_path))
        url = (
            "/download-fleet?seed=1&palette=sci_fi_industrial"
            "&count=1&size_tier=small"
        )
        headers = {"X-Forwarded-For": "203.0.113.99"}
        with app.test_client() as c:
            statuses: list[int] = []
            for _ in range(31):
                statuses.append(c.get(url, headers=headers).status_code)
        assert statuses.count(429) >= 1, (
            f"expected at least one 429 after 31 spam requests; "
            f"statuses={statuses}"
        )

    def test_invalid_size_tier_returns_400(self, client):
        """Unknown size_tier must 400. Mirrors the count / palette 400 shape
        so the client error surface stays consistent across bad params."""
        resp = client.get(
            "/download-fleet"
            "?seed=1&palette=sci_fi_industrial&count=2&size_tier=gigantic"
        )
        assert resp.status_code == 400
        assert resp.is_json
        assert "error" in resp.get_json()

    def test_invalid_style_coherence_returns_400(self, client):
        """style_coherence outside [0, 1] must 400 (not a crash mid-fleet)."""
        resp = client.get(
            "/download-fleet"
            "?seed=1&palette=sci_fi_industrial&count=2&size_tier=small"
            "&style_coherence=5.0"
        )
        assert resp.status_code == 400
        assert resp.is_json
        assert "error" in resp.get_json()


# ---------------------------------------------------------------------------
# TestFormControlsFlowIntoGenerator
# ---------------------------------------------------------------------------
# These tests exercise the *contract* that hull_style / engine_style / preset
# choices actually differentiate the generated voxel grids. They serve as the
# red-tests that prove the bug described in the fix(web) commit before the fix
# is applied, and as regression guards after it lands.
# ---------------------------------------------------------------------------


def _base_form_browser_defaults():
    """Simulate what the browser submits when the user changes ONLY the fields
    under test.  The browser ALWAYS sends every named input's current value,
    so numeric controls (length/width/height) and style selects (wing_style,
    cockpit) arrive with their HTML default values even when the user has never
    touched them.  This mirrors the exact form data that caused the preset-
    merge guard (``if "length" not in merged``) to be a no-op.
    """
    return {
        "seed": "42",
        "palette": "sci_fi_industrial",
        # Numeric fields — the browser sends these even when untouched.
        "length": "40",
        "width": "20",
        "height": "12",
        "engines": "2",
        "wing_prob": "0.75",
        "greeble_density": "0.0",
        "window_period": "4",
        "accent_stripe_period": "8",
        "engine_glow_depth": "1",
        "hull_noise_ratio": "0.0",
        "panel_line_bands": "1",
        "rivet_period": "0",
        # Style selects — browser sends the currently-selected option value.
        "cockpit": "bubble",
        "structure_style": "frigate",
        "wing_style": "straight",
        "hull_style": "auto",
        "engine_style": "auto",
    }


def _grid_hash(client, form):
    """POST /generate with ``form``, then fetch the voxel grid and return a
    sha256 hex digest of the voxel buffer.  This gives a compact fingerprint
    that must differ whenever the generator produces a distinct shape."""
    import hashlib
    import re

    resp = client.post(
        "/generate", data=form, headers={"HX-Request": "true"}
    )
    assert resp.status_code == 200, (
        f"POST /generate failed ({resp.status_code}): "
        f"{resp.get_data(as_text=True)[:300]}"
    )
    body = resp.get_data(as_text=True)
    m = re.search(r'data-gen-id=["\']([^"\']+)["\']', body)
    assert m is not None, f"data-gen-id not found in response: {body[:400]}"
    gen_id = m.group(1)
    voxel_resp = client.get(f"/voxels/{gen_id}.json")
    assert voxel_resp.status_code == 200
    data = voxel_resp.get_json()
    # Stable fingerprint: dims + voxel base64 payload.
    fingerprint = f"{data['dims']}:{data['voxels']}"
    return hashlib.sha256(fingerprint.encode()).hexdigest()


@pytest.mark.ui
class TestFormControlsFlowIntoGenerator:
    """hull_style, engine_style, and preset dropdown must produce distinct
    voxel grids when the user selects different values.  Each test sends a
    full browser-realistic form (all fields present, numeric fields at their
    HTML defaults) and asserts the sha256 fingerprints of the voxel grids
    differ.

    These tests were written RED first (they prove the bug) and must pass
    GREEN after the fix lands.
    """

    def test_hull_style_saucer_vs_whale_grids_differ(self, client):
        """POST /generate with hull_style=saucer must produce a different
        voxel grid than hull_style=whale for the same seed and all other
        params equal.  Tests the full HTTP round-trip, not just the parser."""
        form_saucer = dict(_base_form_browser_defaults())
        form_saucer["hull_style"] = "saucer"

        form_whale = dict(_base_form_browser_defaults())
        form_whale["hull_style"] = "whale"

        h_saucer = _grid_hash(client, form_saucer)
        h_whale = _grid_hash(client, form_whale)
        assert h_saucer != h_whale, (
            "hull_style=saucer and hull_style=whale produced identical "
            "voxel grids — hull_style is not flowing into the generator"
        )

    def test_preset_corvette_vs_dropship_grids_differ(self, client):
        """POST /generate with preset=corvette must produce a different voxel
        grid than preset=dropship when both use the same seed.  This exercises
        the full preset-merge + generator pipeline.

        The browser sends all numeric fields (length/width/height/…) at their
        HTML-default values.  The preset must still override the dimensions and
        styles that differ from those defaults.
        """
        form_corvette = dict(_base_form_browser_defaults())
        form_corvette["preset"] = "corvette"

        form_dropship = dict(_base_form_browser_defaults())
        form_dropship["preset"] = "dropship"

        h_corvette = _grid_hash(client, form_corvette)
        h_dropship = _grid_hash(client, form_dropship)
        assert h_corvette != h_dropship, (
            "preset=corvette and preset=dropship produced identical voxel "
            "grids — preset dimensions/styles are not flowing into the "
            "generator when the form submits numeric fields at HTML defaults"
        )

    def test_preview_lite_hull_style_saucer_vs_whale_differ(self, client):
        """GET /preview-lite?hull_style=saucer vs whale must return different
        PNG payloads.  Exercises the lite preview path independently of the
        full generate + voxel pipeline."""
        import hashlib

        base_qs = (
            "seed=42&palette=sci_fi_industrial"
            "&length=20&width=12&height=8"
            "&engines=1&wing_prob=0.0&greeble_density=0.0"
            "&cockpit=bubble&structure_style=frigate&wing_style=straight"
        )
        r1 = client.get(f"/preview-lite?{base_qs}&hull_style=saucer")
        r2 = client.get(f"/preview-lite?{base_qs}&hull_style=whale")
        assert r1.status_code == 200
        assert r2.status_code == 200
        h1 = hashlib.sha256(r1.get_data()).hexdigest()
        h2 = hashlib.sha256(r2.get_data()).hexdigest()
        assert h1 != h2, (
            "/preview-lite hull_style=saucer and whale returned identical "
            "PNG bytes — hull_style is not flowing into preview_lite"
        )

    def test_preset_dimensions_override_html_defaults(self, client):
        """When preset=corvette is submitted alongside the form's HTML default
        length=40, the parser must replace length=40 with the corvette preset's
        length (50).  This pins the fix for the ``if 'length' not in merged``
        guard that was a no-op whenever the browser sent the default value."""
        from spaceship_generator.web.blueprints.ship_support import (
            build_params_from_source,
        )

        form = dict(_base_form_browser_defaults())
        form["preset"] = "corvette"
        # hull_style and engine_style are "auto" (from _base_form_browser_defaults),
        # so the preset's dagger/twin_nacelle should still win.
        _seed, _pal, shape, _tex, extras = build_params_from_source(form)
        assert shape.length == 50, (
            f"corvette preset length=50 was not applied; "
            f"parser returned length={shape.length} "
            f"(the html-default 40 was not overridden)"
        )
        assert shape.width_max == 20, (
            f"corvette preset width=20 was not applied; got {shape.width_max}"
        )
        assert extras["hull_style"].value == "dagger", (
            f"corvette hull_style=dagger not applied; got {extras['hull_style']!r}"
        )

    def test_preset_wing_style_overrides_html_default_straight(self, client):
        """When preset=corvette is submitted alongside wing_style=straight
        (the HTML default), the parser must apply the corvette preset's swept
        wing_style instead of leaving it as straight."""
        from spaceship_generator.web.blueprints.ship_support import (
            build_params_from_source,
        )

        form = dict(_base_form_browser_defaults())
        form["preset"] = "corvette"
        # wing_style=straight is the HTML default — should be overridden by preset
        _seed, _pal, shape, _tex, extras = build_params_from_source(form)
        from spaceship_generator.wing_styles import WingStyle
        assert shape.wing_style == WingStyle.SWEPT, (
            f"corvette preset wing_style=swept not applied; "
            f"parser returned {shape.wing_style!r} "
            f"(html-default 'straight' was not treated as unset)"
        )

    def test_palette_swatches_refresh_on_form_change(self, client):
        """GET / must include the palette dropdown and the swatch container.
        The swatch strip is refreshed by polish.js on palette change events —
        this test pins the HTML contract that makes that possible: the
        #palette-swatches host div and the palette <select> must both be
        present so the JS listener can attach and the ARIA live region works."""
        body = client.get("/").get_data(as_text=True)
        assert 'id="palette-swatches"' in body or "id='palette-swatches'" in body, (
            "#palette-swatches div missing — swatch refresh JS cannot attach"
        )
        # The palette select must carry id="palette" so polish.js can
        # bind to it with getElementById('palette').
        assert 'id="palette"' in body or "id='palette'" in body, (
            'palette <select id="palette"> missing — polish.js swatch '
            "refresh cannot bind to the dropdown"
        )
