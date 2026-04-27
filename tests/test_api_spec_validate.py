"""Validate the live ``/api/spec`` response against the OpenAPI 3.0 meta-schema.

The endpoint is shipped as a hand-written document (no codegen), so the only
guard against silent drift — e.g. a future endpoint that omits ``responses``
or breaks the ``info``/``paths`` shape — is to validate the JSON body against
the official OAS 3.0 meta-schema on every CI run.

The schema is vendored under ``tests/fixtures/openapi-3.0-schema.json`` so the
test runs fully offline (no network, no flake on locked-down CI runners). It
was fetched verbatim from ``https://spec.openapis.org/oas/3.0/schema/2021-09-28``
which is JSON-Schema draft-04. ``jsonschema`` is the validator: lightweight,
pure-Python, and the canonical implementation.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

jsonschema = pytest.importorskip("jsonschema")

from spaceship_generator.web.app import create_app  # noqa: E402

SCHEMA_PATH = Path(__file__).parent / "fixtures" / "openapi-3.0-schema.json"


@pytest.fixture
def client(tmp_path, monkeypatch):
    app = create_app()
    app.config["TESTING"] = True
    monkeypatch.setattr(app, "instance_path", str(tmp_path))
    with app.test_client() as c:
        yield c


@pytest.fixture(scope="module")
def openapi_meta_schema():
    """Load the vendored OpenAPI 3.0 JSON-Schema (draft-04)."""
    assert SCHEMA_PATH.is_file(), f"vendored schema missing: {SCHEMA_PATH}"
    with SCHEMA_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def test_vendored_meta_schema_is_oas_3_0(openapi_meta_schema):
    """Sanity-check the fixture itself before using it as a validator."""
    schema = openapi_meta_schema
    # 2021-09-28 release of the OAS 3.0 meta-schema, draft-04 dialect.
    assert schema.get("$schema", "").startswith("http://json-schema.org/draft-04/")
    assert schema.get("id") == "https://spec.openapis.org/oas/3.0/schema/2021-09-28"


def test_api_spec_validates_against_openapi_3_0_meta_schema(client, openapi_meta_schema):
    rv = client.get("/api/spec")
    assert rv.status_code == 200
    spec = rv.get_json()
    assert isinstance(spec, dict)

    # Use the explicit Draft4 validator since the vendored meta-schema declares
    # draft-04. ``iter_errors`` collects every violation (rather than bailing on
    # the first) so a CI failure points at every drift site at once.
    Draft4Validator = jsonschema.Draft4Validator
    validator = Draft4Validator(openapi_meta_schema)
    errors = sorted(validator.iter_errors(spec), key=lambda e: list(e.absolute_path))

    if errors:
        formatted = "\n".join(
            f"  - {'/'.join(str(p) for p in err.absolute_path) or '<root>'}: {err.message}"
            for err in errors
        )
        pytest.fail(
            f"/api/spec response failed OpenAPI 3.0 meta-schema validation "
            f"({len(errors)} error(s)):\n{formatted}"
        )
