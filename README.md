# CTF as Code

A small self-hosted CTF stack built around CTFd, MariaDB, Redis, Pi-hole, and a lightweight Caddy reverse proxy.

The repo is intended to keep both the platform and starter challenge content under version control.

## Services

| Service | Purpose | Default local URL |
|---|---|---|
| Caddy | Reverse proxy | http://localhost |
| CTFd | CTF platform | http://localhost |
| Pi-hole | DNS and admin UI | http://localhost/pihole/admin/ |
| MariaDB | CTFd database | Internal only |
| Redis | CTFd cache | Internal only |

Pi-hole also publishes DNS on host port `53` by default.

## Prerequisites

- Docker v24+
- Docker Compose v2+
- Ports `80`, `443`, and `53` available, or adjusted in `.env`
- Python 3.10+ if you want to run the challenge sync script

## Quick Start

1. Copy the environment template:

```powershell
Copy-Item .env.example .env
```

2. Replace every `change-me` value in `.env`.

Generate a CTFd secret with:

```powershell
openssl rand -hex 32
```

3. Start the stack:

```powershell
docker compose up -d
```

4. Check service state:

```powershell
docker compose ps
```

5. Open CTFd:

```text
http://localhost
```

## Lightweight Proxy

Caddy is included as the reverse proxy because the config is tiny and it can obtain TLS certificates automatically for real public hostnames.

Local defaults in `.env.example` use plain HTTP on any hostname:

```env
CTFD_SITE_ADDRESS=http://:80
PIHOLE_PATH_PREFIX=/pihole
```

For public HTTPS, change them to real DNS names that point at the host:

```env
CTFD_SITE_ADDRESS=ctf.example.com
PIHOLE_PATH_PREFIX=/pihole
```

Caddy will then handle ACME certificates on ports `80` and `443`. Pi-hole remains available under the configured path, for example `https://ctf.example.com/pihole/admin/`.

## Configuration

All sensitive settings belong in `.env`, which is ignored by git.

Important variables:

| Variable | Purpose |
|---|---|
| `CTFD_SECRET_KEY` | CTFd session signing secret |
| `CTFD_DB_ROOT_PASSWORD` | MariaDB root password |
| `CTFD_DB_PASSWORD` | MariaDB password for the CTFd user |
| `PIHOLE_WEBPASSWORD` | Pi-hole admin password, mapped to `FTLCONF_webserver_api_password` |
| `PIHOLE_UPSTREAM_DNS` | Pi-hole upstream DNS servers, mapped to `FTLCONF_dns_upstreams` |
| `CTFD_SITE_ADDRESS` | Caddy site address for CTFd |
| `PIHOLE_PATH_PREFIX` | Subpath for Pi-hole, mapped to `FTLCONF_webserver_paths_prefix` |
| `DNS_PORT` | Host DNS port for Pi-hole |

Image versions are pinned in `.env.example` and can be updated deliberately.

## Challenge as Code

Challenges live under `challenges/<slug>/challenge.json`.

Example:

```json
{
  "name": "Sanity Check",
  "category": "Warmups",
  "description": "Submit the flag to confirm your account and the platform are working.",
  "value": 50,
  "type": "standard",
  "state": "hidden",
  "flags": ["CTF{welcome_to_the_game}"],
  "files": ["files/readme.txt"]
}
```

Create an admin API token in CTFd, then sync challenge manifests:

```powershell
$env:CTFD_URL = "http://localhost"
$env:CTFD_TOKEN = "<admin-api-token>"
python scripts/sync-challenges.py
```

You can also load from an explicit top-level manifest:

```powershell
$env:CTFD_URL = "http://localhost"
$env:CTFD_TOKEN = "<admin-api-token>"
$env:CTFD_MANIFEST = "ctfd-load.example.json"
python scripts/sync-challenges.py
```

The example load manifest looks like this:

```json
{
  "ctfd": {
    "url": "http://localhost",
    "notes": "Create an admin API token in CTFd and expose it as CTFD_TOKEN before loading."
  },
  "challenges": [
    "challenges/example/challenge.json"
  ]
}
```

The sync script creates or updates challenges by name, adds missing flags, and uploads listed files.
Files are uploaded when a challenge is first created. To re-upload files for existing challenges, set:

```powershell
$env:CTFD_UPLOAD_FILES_ON_UPDATE = "true"
```

## Backups

Run:

```powershell
.\scripts\backup.ps1
```

This writes timestamped database and Pi-hole config backups into `backups/`.

Restore the CTFd database:

```powershell
.\scripts\restore.ps1 -DatabaseBackup backups\ctfd_db_YYYY-MM-DD_HHMMSS.sql
docker compose restart
```

Restore both database and Pi-hole config:

```powershell
.\scripts\restore.ps1 `
  -DatabaseBackup backups\ctfd_db_YYYY-MM-DD_HHMMSS.sql `
  -PiholeBackup backups\pihole_config_YYYY-MM-DD_HHMMSS.tar.gz
docker compose restart
```

## Operations

View logs:

```powershell
docker compose logs -f
docker compose logs -f ctfd
docker compose logs -f pihole
docker compose logs -f proxy
```

Stop services while preserving data:

```powershell
docker compose down
```

Destroy all service data:

```powershell
docker compose down -v
```

Update pinned images:

```powershell
docker compose pull
docker compose up -d
```

Back up before changing image pins.

## CI Checks

GitHub Actions runs the checks in `.github/workflows/checks.yml` on pushes to `main` or `master` and on pull requests.

It verifies:

- `docker compose --env-file .env.example config`
- Python syntax for the helper scripts
- Challenge manifest structure and referenced files
- The top-level CTFd load manifest

## Troubleshooting

### Port 53 is already in use

On Linux, `systemd-resolved` often binds DNS port `53`. For a desktop or shared host, change `.env`:

```env
DNS_PORT=5353
```

Then point clients at the host IP and port `5353`.

### CTFd is unhealthy during first boot

MariaDB initialization can take a minute. Check:

```powershell
docker compose logs -f ctfd-db
docker compose logs -f ctfd
```

### Accessing Pi-hole

Pi-hole is served under `PIHOLE_PATH_PREFIX`, so the default local admin URL is:

```text
http://localhost/pihole/admin/
```

If you publish Caddy on a non-default port for testing, include that port:

```text
http://localhost:8080/pihole/admin/
```

## File Structure

```text
.
|-- .env.example
|-- .gitignore
|-- docker-compose.yml
|-- ctfd-load.example.json
|-- README.md
|-- .github/
|   `-- workflows/
|       `-- checks.yml
|-- config/
|   `-- Caddyfile
|-- challenges/
|   `-- example/
|       |-- challenge.json
|       `-- files/
|           `-- readme.txt
`-- scripts/
    |-- backup.ps1
    |-- restore.ps1
    |-- validate-manifests.py
    `-- sync-challenges.py
```
