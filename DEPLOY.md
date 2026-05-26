# Deployment Guide - Electrical Compliance Agent

## Architecture

| Component | Platform | URL |
|-----------|----------|-----|
| Frontend  | Vercel   | `https://<your-app>.vercel.app` |
| Backend   | Render   | `https://<your-api>.onrender.com` |
| Database  | Supabase | `https://<your-project>.supabase.co` |

## Prerequisites

You need accounts (all have free tiers) on:
- [Supabase](https://supabase.com) — database + pgvector
- [OpenAI](https://platform.openai.com) — LLM API key
- [Render](https://render.com) — backend hosting
- [Vercel](https://vercel.com) — frontend hosting

---

## Step 1: Supabase Setup

1. Create a new project at [supabase.com/dashboard](https://supabase.com/dashboard).
2. Go to **SQL Editor** and run the migration file:
   - Copy the contents of `supabase/migrations/20260505000000_init_compliance.sql`
   - Execute it in the SQL Editor
3. Then run the seed data:
   - Copy the contents of `supabase/seed.sql`
   - Execute it in the SQL Editor
4. Get your credentials from **Settings > API**:
   - `SUPABASE_URL` — Project URL
   - `SUPABASE_SERVICE_ROLE_KEY` — service_role key (secret)

## Step 2: Deploy Backend on Render

### Option A: One-click via Blueprint
1. Go to [render.com/deploy](https://render.com/deploy)
2. Connect your GitHub repo (`johnfelipe/Electrical-Compliance-Agent`)
3. Render will detect `render.yaml` and configure the service
4. Set the environment variables:
   - `OPENAI_API_KEY` — your OpenAI API key
   - `SUPABASE_URL` — from Step 1
   - `SUPABASE_SERVICE_ROLE_KEY` — from Step 1
   - `CORS_ORIGINS` — `https://<your-app>.vercel.app` (update after Vercel deploy)

### Option B: Manual
1. Create a new **Web Service** on Render
2. Connect your GitHub repo
3. Settings:
   - **Root Directory**: `backend`
   - **Runtime**: Docker
   - **Dockerfile Path**: `Dockerfile`
4. Add the environment variables listed above
5. Deploy

Your API will be available at `https://<service-name>.onrender.com`

Verify: `curl https://<service-name>.onrender.com/health`

## Step 3: Deploy Frontend on Vercel

1. Go to [vercel.com/new](https://vercel.com/new)
2. Import your GitHub repo (`johnfelipe/Electrical-Compliance-Agent`)
3. Settings:
   - **Root Directory**: `web`
   - **Framework Preset**: Next.js
4. Add environment variable:
   - `NEXT_PUBLIC_API_URL` = `https://<your-render-service>.onrender.com`
5. Deploy

Your frontend will be at `https://<project>.vercel.app`

## Step 4: Update CORS

After both are deployed, go back to Render and update:
- `CORS_ORIGINS` = `https://<your-project>.vercel.app`

---

## Local Development with Docker Compose

```bash
# Copy env files
cp backend/.env.example backend/.env
# Edit backend/.env with your keys

# Run everything
docker-compose up --build
```

- Frontend: http://localhost:3000
- Backend: http://localhost:8000
- Health check: http://localhost:8000/health

## Environment Variables Reference

### Backend (`backend/.env`)
| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | OpenAI API key for GPT-4o-mini |
| `OPENAI_MODEL` | No | Default: `gpt-4o-mini` |
| `EMBEDDING_MODEL` | No | Default: `text-embedding-3-small` |
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes | Supabase service role key |
| `CORS_ORIGINS` | No | Comma-separated allowed origins |
| `GEMINI_API_KEY` | No | For data ingestion pipeline |

### Frontend (`web/.env`)
| Variable | Required | Description |
|----------|----------|-------------|
| `NEXT_PUBLIC_API_URL` | Yes | Backend API URL |
