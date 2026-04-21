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
