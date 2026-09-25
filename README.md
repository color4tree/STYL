# STYL

STYL is a premium fitness equipment brand website and lightweight commerce MVP.

## Project structure

- [docs/STYL Portal Design.md](docs/STYL%20Portal%20Design.md) — product strategy, UX goals, and technical proposal
- [docs/business-trademark-summary.zh-CN.md](docs/business-trademark-summary.zh-CN.md) — business, trademark, and operating context
- [frontend](frontend) — Next.js frontend for marketing site and product showcase
- [backend](backend) — FastAPI backend for catalog and inquiry APIs

## Stack

- Frontend: Next.js + TypeScript + Tailwind CSS
- Backend: FastAPI + Python
- Catalog storage: JSON and local uploads for the lightweight MVP
- Deployment: Single AWS Lightsail instance with Caddy and automatic HTTPS

## Run locally

### One-command Windows startup

From the repository root, run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\start-styl.ps1
```

The script stops stale servers, starts the backend and frontend, verifies both services, and opens the product management page. If port 8000 is still reserved by Windows, it automatically selects a free API port and configures the frontend to use it.
The local admin token is printed in the terminal when startup completes.

### Production

Follow [the minimal AWS Lightsail deployment guide](docs/lightsail-deployment.md).
Production catalog writes require `STYL_ADMIN_TOKEN`; writable catalog data and
uploads are stored under `STYL_DATA_DIR`.

### Inquiry email

The inquiry API saves each submission under `STYL_DATA_DIR/inquiries/` before
sending a notification to `styl@stylfitness.com`. Locally, submissions are stored
in `backend/app/data/inquiries/`, which is excluded from Git. These files contain
customer contact details; keep them and their backups private and remove them
when no longer needed.

For Google Workspace, configure these values in `/etc/styl/styl.env`:

```dotenv
STYL_SMTP_HOST=smtp.gmail.com
STYL_SMTP_PORT=587
STYL_SMTP_USERNAME=styl@stylfitness.com
STYL_SMTP_PASSWORD=replace-with-google-app-password
STYL_SMTP_FROM=styl@stylfitness.com
```

Use an app password for the sending Google account, not its regular password.
Google requires 2-Step Verification; Workspace policy may disable app passwords.
If unavailable, ask the Workspace administrator for an approved SMTP relay or
email service. If `styl@stylfitness.com` is an alias, authenticate with the actual
mailbox account and ensure that it is authorized to send as this alias.
Enter credentials directly on the server, never in chat or Git, then restart
`styl-api`. Port 587 uses STARTTLS with certificate verification; port 465 uses
implicit TLS. No inbound SMTP firewall rule is needed.

The customer's email is used as Reply-To, not as the sender. Sending is disabled
when SMTP host, username, or password is missing. Saved records track
`emailStatus` as `pending`, `sent` (accepted by SMTP, not proof of inbox delivery),
`failed`, or `unconfigured`. The API reports receipt only after saving the inquiry;
failed or unconfigured email delivery is logged without customer details or
credentials. There is currently no automatic retry or admin inbox UI: inspect
private saved inquiries on the server when an email warning occurs.

After deployment and configuration, submit one test inquiry and confirm it
arrives in the mailbox (including checking spam) and Reply-To points to the test
customer. Existing production versions must be redeployed to use this handler.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Then open http://localhost:3000

### Backend

```bash
cd backend
python -m venv .venv
. .venv/Scripts/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Then open http://localhost:8000/docs

## Current phase

Initial storefront MVP plus a lightweight product management workflow for catalog editing.

## Product management requirement

The project includes a lightweight admin page for editing product catalog data, including category, photo/image, name, description, price, feature list, and product details. Admin users can upload JPG, PNG, WebP, or GIF product photos up to 8 MB, preview them, and replace them later. Any update saved from the management page is persisted in the backend and reflected in the public storefront after the next page refresh.

## Product and accessory videos

Products and accessories support CAD and USD only. New admin entries default to
CAD; existing entries retain their saved currency. Storefront prices display
only `$`, while cart totals remain grouped by currency without conversion.
Home product cards use the same photo/video gallery as accessories and product
detail pages, managed through the shared admin media editor.

Galleries support up to 12 photos and videos combined. Photos retain the 8 MiB
per-file limit. Uploaded videos are limited to 50 MiB (52,428,800 bytes), checked
by both the admin UI and API. Supported containers: MP4, iPhone MOV, M4V, WebM,
MKV, and AVI. Video URLs added directly are not uploaded or converted; prefer
uploading files for consistent browser playback and generated thumbnails.

`imageio-ffmpeg` provides FFmpeg binaries on supported Windows/Linux platforms
through the backend requirements. Uploaded clips, including HEVC/10-bit MOV,
are converted to H.264/AAC MP4 with a maximum dimension of 1280 pixels. Rotation
is handled by FFmpeg, location metadata is removed, and a JPEG cover is generated.
Original source files are temporary and are not retained. HDR/Dolby Vision
appearance is not guaranteed to match the original; use an SDR export when color
accuracy matters. A real iPhone recording should be checked before launch.

Conversion accepts one video at a time per backend process and times out after
three minutes (plus 30 seconds for the cover). Oversized converted output is
rejected, not published as a shortened clip. Large/long recordings should be
trimmed or compressed first. Videos stay on disk alongside photos and are
included in the existing data backups. Public MP4 responses support byte ranges
for seeking. The homepage banner remains image-only.

Install updated backend requirements and redeploy both frontend and backend to
enable video uploads. Other proxy/upload gateways must permit multipart requests
slightly larger than 50 MiB and allow conversion time. This is intended for short
product clips on a single server, not high-volume video hosting.

## Design direction

- Premium, minimal, modern product marketing
- Mobile-friendly and responsive
- Product-first layout with simple cart and inquiry flow
- Frontend and backend fully decoupled through API boundaries
