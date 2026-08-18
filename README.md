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
- Database: PostgreSQL (planned for v1+ data model)
- Deployment: Vercel + managed API + PostgreSQL service

## Run locally

### One-command Windows startup

From the repository root, run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\start-styl.ps1
```

The script stops stale servers, starts the backend and frontend, verifies both services, and opens the product management page. If port 8000 is still reserved by Windows, it automatically selects a free API port and configures the frontend to use it.

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

## Design direction

- Premium, minimal, modern product marketing
- Mobile-friendly and responsive
- Product-first layout with simple cart and inquiry flow
- Frontend and backend fully decoupled through API boundaries
