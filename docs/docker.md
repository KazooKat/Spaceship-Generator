# Docker

Spaceship Generator ships a two-stage `Dockerfile` that produces a ~200 MB
image running the Flask web UI behind gunicorn. The same image can also be
invoked as a CLI by overriding the entrypoint.

## Build

```bash
docker build -t spaceship-generator .
```

The builder stage compiles the project into a wheel; the runtime stage only
carries `python:3.12-slim`, the installed wheel, `gunicorn`, and `curl` (used
by the healthcheck).

## Run — web UI

```bash
docker run --rm -p 8000:8000 spaceship-generator
```

Then open <http://localhost:8000>. The container listens on port 8000 and
runs a `HEALTHCHECK` that polls `/` every 30 s.

## Run — CLI

Override the entrypoint and mount an output directory so the `.litematic`
file is written to the host:

```bash
docker run --rm \
    -v "$(pwd)/out:/app/out" \
    --entrypoint spaceship-generator \
    spaceship-generator \
    --seed 42 --palette neon_arcade --out /app/out
```

On Windows PowerShell, replace `$(pwd)` with `${PWD}`.

## Production notes

- **Scale workers.** The entrypoint honours `GUNICORN_WORKERS` (default `2`)
  and `PORT` (default `8000`). Scale per host:

  ```bash
  docker run -p 8000:8000 -e GUNICORN_WORKERS=8 spaceship-generator
  ```

- **Mount an output volume** so generated schematics survive container
  restarts: `-v spaceship-out:/app/out` (named volume) or a bind mount as
  shown above.

- **Non-root by default.** The image runs as the unprivileged user `app`
  (UID 1000). Ensure any host-side bind mount is writable by that UID.

- **Healthcheck.** Orchestrators (Compose, Kubernetes, ECS) can read the
  built-in `HEALTHCHECK` directly; no probe config is required.

- **PyPI image.** Once the package is published, you can skip the local
  build entirely and pull a pre-built image (when available):

  ```bash
  docker pull ghcr.io/kazookat/spaceship-generator:latest
  docker run --rm -p 8000:8000 ghcr.io/kazookat/spaceship-generator:latest
  ```

  Until then, `docker build` from a clone is the supported path.
