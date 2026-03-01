# Deployment Guide

## Docker Compose (Recommended)

```bash
git clone https://github.com/Garl-Protocol/garl.git
cd garl
cp backend/.env.example backend/.env
# Edit backend/.env with your credentials (see Environment Variables below)
docker compose up --build -d
```

Backend runs on `http://localhost:8000`, frontend on `http://localhost:3000`.

## Manual Setup

### Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm install && npm run build && npm start
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_ANON_KEY` | Yes | Supabase anon/public key |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes | Supabase service role key |
| `SIGNING_PRIVATE_KEY_HEX` | No | ECDSA private key (auto-generated if empty) |
| `READ_AUTH_ENABLED` | No | Require API key for detail endpoints (default: true) |
| `ALLOWED_ORIGINS` | No | Comma-separated CORS origins |
| `NEXT_PUBLIC_API_URL` | No | Frontend API base URL |

## Health Check

```bash
curl https://api.garl.ai/health
# {"status": "healthy", "version": "1.0.2", "protocol": "garl"}
```

## Production Deployment

GARL Protocol is deployed on [Railway](https://railway.app) with automatic deploys from the `main` branch. The live instance is available at:

- **API**: `https://api.garl.ai`
- **Frontend**: `https://garl.ai`
