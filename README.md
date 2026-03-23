# Internal Media Storage

A lightweight internal file storage service for document upload and retrieval. Designed to run on a private network — no authentication required.

## Architecture

```
Client → Nginx (HTTPS) → FastAPI (upload + validate) → Disk (/app/data/media)
User   → Nginx (HTTPS) → serve static files directly
```

## Stack

- **Backend**: FastAPI (Python 3.12)
- **Web server**: Nginx 1.27
- **Storage**: Local disk
- **Deployment**: Docker Compose

---

## Project Structure

```
internal-media-storage/
├── app/
│   ├── main.py                     # Upload API
│   └── requirements.txt
├── nginx/
│   └── nginx.conf.template         # Nginx config template (domain injected at startup)
├── data/
│   └── media/                      # Uploaded files stored here
├── cert/                           # SSL certificate (server.crt, server.key)
├── Dockerfile
├── docker-compose.yml
├── .env                            # Dev environment config
└── .env.prod                       # Production environment config
```

---

## Quick Start

### 1. Set your domain

Edit `.env`:

```env
DOMAIN=media.local          # dev
```

Or `.env.prod` for production:

```env
DOMAIN=media.yourcompany.com
```

### 2. Point the domain to this server

**Option A — `/etc/hosts` (dev/testing):**
```
127.0.0.1   media.local
```

**Option B — Internal DNS (recommended for teams):**
Add an A record in your internal DNS server pointing `DOMAIN` → server IP.

### 3. Generate a certificate

```bash
# Self-signed (dev)
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout cert/server.key \
  -out cert/server.crt \
  -subj "/CN=media.local"
```

> For production, use a certificate signed by your internal CA so browsers trust it without warnings.

### 4. Start services

```bash
# Development
docker compose up --build

# Production
docker compose --env-file .env.prod up --build -d
```

Nginx reads `DOMAIN` and `NGINX_MAX_BODY_SIZE` from the environment and injects them into the config at container startup — no manual config edits needed.

---

## API

### Upload a single file

```
POST https://<DOMAIN>/upload
Content-Type: multipart/form-data
```

| Field | Type | Description |
|-------|------|-------------|
| `file` | file | Document to upload |

**Success response `200`:**
```json
{
  "url": "https://media.local/files/2026-03/3f2a1b4c-....pdf"
}
```

**Example:**
```bash
curl -k -X POST https://media.local/upload \
  -F "file=@/path/to/report.pdf"
```

---

### Upload multiple files (batch)

```
POST https://<DOMAIN>/upload/batch
Content-Type: multipart/form-data
```

| Field | Type | Description |
|-------|------|-------------|
| `files` | file[] | One or more documents to upload |

**Success response `200`:**
```json
{
  "urls": [
    "https://media.local/files/2026-03/3f2a1b4c-....pdf",
    "https://media.local/files/2026-03/7c9d2e1a-....docx"
  ]
}
```

Each URL in the array corresponds to the uploaded file at the same position in the request.

If **any** file fails validation (wrong type or too large), the entire request is rejected and no files are saved.

**Example:**
```bash
curl -k -X POST https://media.local/upload/batch \
  -F "files=@/path/to/report.pdf" \
  -F "files=@/path/to/summary.docx" \
  -F "files=@/path/to/data.xlsx"
```

---

### Error responses (both endpoints)

| Status | Reason |
|--------|--------|
| `400` | Invalid file type |
| `400` | File too large (per-file limit: `MAX_FILE_SIZE`) |
| `413` | Total request too large (Nginx limit: `NGINX_MAX_BODY_SIZE`) |

---

### Health check

```
GET https://<DOMAIN>/health
```

```json
{ "status": "ok" }
```

---

## File Access

Files are served directly by Nginx (bypasses FastAPI):

```
GET https://<DOMAIN>/files/{yyyy-mm}/{filename}
```

- No directory listing
- Files are served as plain downloads (`Content-Disposition: attachment`)
- `X-Content-Type-Options: nosniff` header applied

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_ENV` | `dev` | Environment (`dev` or `prod`) |
| `DOMAIN` | `media.local` | Domain name used by Nginx `server_name` and returned URLs |
| `PORT` | `8000` | FastAPI internal port |
| `MAX_FILE_SIZE` | `10485760` | Max size **per file** in bytes (10 MB) — enforced by FastAPI |
| `NGINX_MAX_BODY_SIZE` | `104857600` | Max total request body size in bytes (100 MB) — enforced by Nginx; should be ≥ `MAX_FILE_SIZE` and large enough for batch uploads |
| `ALLOWED_EXTENSIONS` | `pdf,doc,docx,xls,xlsx,ppt,pptx,txt` | Comma-separated allowed extensions |
| `MEDIA_ROOT` | `/app/data/media` | Directory where files are stored |
| `BASE_URL` | `https://media.local/files` | Base URL returned in upload response |

> `MAX_FILE_SIZE` controls per-file validation inside FastAPI. `NGINX_MAX_BODY_SIZE` controls the total request size allowed by Nginx — set it to accommodate the largest expected batch (e.g., `10 × MAX_FILE_SIZE`).

---

## Volumes

| Host path | Container path | Purpose |
|-----------|---------------|---------|
| `./data` | `/app/data` | File storage (shared between FastAPI and Nginx) |
| `./cert` | `/etc/nginx/certs` | SSL certificates |

---

## Allowed File Types

`pdf` `doc` `docx` `xls` `xlsx` `ppt` `pptx` `txt`

Validation is done by file extension (case-insensitive). The original filename is never used — files are stored as `{yyyy-mm}/{uuid}.{ext}`.

---

## Notes

- **Domain config is zero-touch**: `DOMAIN` is injected into the Nginx config via `envsubst` at container startup. Changing the domain only requires updating `.env` and restarting.
- Files are stored under monthly subdirectories (`{MEDIA_ROOT}/yyyy-mm/`) — easy to archive or clean up by month.
- Files are streamed to disk in 64 KB chunks — memory usage stays flat regardless of file size.
- Batch uploads are atomic: if any file fails, all already-saved files from that request are cleaned up and nothing is kept.
- No database is used. No metadata is stored.
- Intended for internal network use only. Do not expose to the public internet.
