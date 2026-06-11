# nvskills — skill-query service

Corp skill-query tool: build a skills-only boolean query and see which NV
members (across all their characters) satisfy it. Runs as an authenticated
iframe inside NV Tools (`tools.novacancies.space`) under `/skillquery`.

## Local development

    uv sync
    uv run python scripts/refresh_sde.py        # populate var/sde/skills.json (~80 MB once)
    DEV_MODE=1 DEV_USER_RANK=CEO DATA_SOURCE=demo uv run uvicorn app.main:app --reload

`DATA_SOURCE=demo` serves the committed fixtures in `data_demo/`; the SDE step
is optional in demo mode (it falls back to `data_demo/sde_skills.json`). Run
the tests with `uv run pytest -q`.

## Configuration

Secrets and per-deployment values come from `.env` (gitignored; copy
`.env.example`). The access-gate allowlist (which ranks/teams may query) is in
`config.toml` / `config.local.toml`.

| Var | Purpose |
|---|---|
| `NV_TOKEN` | Shared bearer the NV Tools proxy sends; the app 401s without it. |
| `NV_API_URL` | Base host for the real APIs (default `https://tools.novacancies.space/api`). |
| `NV_API_TOKEN` | **Bearer for the upstream users/character_skills APIs. Put it in `.env` only.** Obtain from the NV Tools admin. |
| `URL_PREFIX` | Path the app mounts under; `/skillquery` in production, empty for local root. |
| `DATA_SOURCE` | `real` (hits the NV APIs) or `demo` (committed fixtures). |

The upstream API contract is documented in `docs/upstream-api.md`.

## Deployment (shared VM behind NV Tools)

Topology: NV Tools authenticates the user and forwards over HTTPS to this VM;
Caddy terminates TLS on `:443` and reverse-proxies to the loopback-bound
container. The container binds `127.0.0.1:8083` only. See the
`nv-tools-service-deploy` skill / `~/dev/router/nvtools.txt` for the full
contract.

1. **Build and run the container** (on the VM):

       cd ~/dev/nvskills
       echo "NV_TOKEN=<shared-proxy-secret>"  >> .env
       echo "NV_API_TOKEN=<upstream-api-token>" >> .env
       echo "URL_PREFIX=/skillquery"           >> .env
       echo "DATA_SOURCE=real"                  >> .env
       docker compose build && docker compose up -d

   `URL_PREFIX=/skillquery` is passed as both the runtime env var and the
   `VITE_URL_PREFIX` build arg (wired in `docker-compose.yml`) so the SPA and
   the backend agree on the prefix.

2. **Add the Caddy entry on the remote.** This VM already fronts eve-router and
   nvinfo from a single shared `/etc/caddy/Caddyfile`. Edit that file (do **not**
   overwrite it) and add the nvskills matcher **inside** the existing
   `tools-integration-raz.novacancies.space { … }` block:

       # nvskills skill-query — mounted at /skillquery. No SSE; keep the prefix.
       @skillquery path /skillquery /skillquery/*
       reverse_proxy @skillquery 127.0.0.1:8083

   The canonical full file (all three apps) is committed at `deploy/Caddyfile`.
   Do **not** use `handle_path` — the app serves its routes under `/skillquery`
   and a stripped prefix 404s. Then validate and reload:

       sudo caddy validate --config /etc/caddy/Caddyfile
       sudo systemctl reload caddy

3. **Tell the NV Tools admin** the public path is `/skillquery` and confirm the
   exact path their proxy forwards to your upstream (it must equal
   `URL_PREFIX`). Give them the VM's public IP + hostname; they set DNS and
   point NV Tools at your `https://` upstream, and hand you the `NV_TOKEN`
   bearer (must match `.env` exactly).

### Verify

    # 401 = bearer boundary works (loopback, no auth)
    curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8083/skillquery/
    # 401 over TLS = Caddy reaches the app
    curl -is https://tools-integration-raz.novacancies.space/skillquery/ | head -1
    # 200 + CSP = authed request works
    curl -is -H "Authorization: Bearer <NV_TOKEN>" -H "X-User-Name: You" \
         -H "X-User-Rank: CEO" \
         https://tools-integration-raz.novacancies.space/skillquery/ \
      | grep -iE "HTTP/|content-security-policy"
