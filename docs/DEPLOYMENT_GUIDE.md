# Deployment Guide

**AI Contract Reviewer & Negotiation Copilot**

This guide covers deploying the application using Docker, which is the recommended method for both local development and production environments.

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start (Docker)](#quick-start-docker)
- [Configuration](#configuration)
- [Deployment Options](#deployment-options)
  - [Local Docker Deployment](#local-docker-deployment)
  - [Dokploy Deployment](#dokploy-deployment)
  - [Manual Deployment (Without Docker)](#manual-deployment-without-docker)
- [Testing the Deployment](#testing-the-deployment)
- [Troubleshooting](#troubleshooting)
- [Production Checklist](#production-checklist)

---

## Prerequisites

- **Docker** and **Docker Compose** installed ([Get Docker](https://docs.docker.com/get-docker/))
- **Google Gemini API Key** ([Get one here](https://aistudio.google.com/app/apikey))

---

## Quick Start (Docker)

Get up and running in under 5 minutes:

```bash
# 1. Clone the repository
git clone https://github.com/amitgoesbrr/contract-copilot.git
cd contract-copilot

# 2. Create and configure environment file
cp .env.example .env

# 3. Edit .env and set your Google API key
#    GOOGLE_API_KEY=your_gemini_api_key_here

# 4. Start all services
docker-compose up -d

# 5. Check status
docker-compose ps
```

**Access the application:**

- 🖥️ **UI**: http://localhost:3000
- 🔌 **API**: http://localhost:8000
- ❤️ **Health Check**: http://localhost:8000/health

---

## Configuration

### Required Environment Variables

| Variable         | Description                | Example     |
| ---------------- | -------------------------- | ----------- |
| `GOOGLE_API_KEY` | Your Google Gemini API key | `AIzaSy...` |

### Optional Environment Variables

| Variable                | Default                                       | Description                                        |
| ----------------------- | --------------------------------------------- | -------------------------------------------------- |
| `ADMIN_ACCESS_CODE`     | _(empty)_                                     | Password to access the UI (leave empty to disable) |
| `GEMINI_MODEL`          | `gemini-2.0-flash-exp`                        | Gemini model to use                                |
| `DB_USER`               | `contract_user`                               | PostgreSQL username                                |
| `DB_PASSWORD`           | `contract_password`                           | PostgreSQL password                                |
| `DB_NAME`               | `contract_copilot`                            | PostgreSQL database name                           |
| `API_PORT`              | `8000`                                        | API server port                                    |
| `UI_PORT`               | `3000`                                        | UI server port                                     |
| `CORS_ORIGINS`          | `http://localhost:3000,http://localhost:8000` | Allowed CORS origins                               |
| `LOG_LEVEL`             | `INFO`                                        | Logging level (DEBUG, INFO, WARNING, ERROR)        |
| `SESSION_PERSISTENCE`   | `true`                                        | Keep session data after processing                 |
| `SESSION_CLEANUP_HOURS` | `24`                                          | Hours before inactive sessions are deleted         |
| `MAX_FILE_SIZE_MB`      | `10`                                          | Maximum upload file size                           |
| `ALLOWED_FILE_TYPES`    | `pdf,txt`                                     | Allowed file extensions                            |
| `ENVIRONMENT`           | `production`                                  | Environment mode (affects cookie security)         |

### Example `.env` File

```bash
# Required
GOOGLE_API_KEY=your_gemini_api_key_here

# Security (recommended for production)
ADMIN_ACCESS_CODE=your_secure_password

# Optional customization
GEMINI_MODEL=gemini-2.0-flash-exp
LOG_LEVEL=INFO
```

---

## Deployment Options

### Local Docker Deployment

Best for development and testing.

```bash
# Start all services (builds images if needed)
docker-compose up -d

# View logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f api
docker-compose logs -f ui

# Stop all services
docker-compose down

# Stop and remove all data (WARNING: deletes database!)
docker-compose down -v

# Rebuild after code changes
docker-compose up -d --build
```

### Manual Deployment (Without Docker)

For environments where Docker isn't available.

#### Backend (API)

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Start the API
python run_api.py
```

#### Frontend (UI)

```bash
cd ui

# Install dependencies
npm install

# Create environment file
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local

# Development mode
npm run dev

# Production build
npm run build
npm start
```

---

## Testing the Deployment

### Health Check

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{
  "status": "healthy",
  "timestamp": "2025-11-28T12:54:45.831760"
}
```

### Upload a Contract

```bash
curl -X POST http://localhost:8000/upload \
  -F "file=@sample_contracts/sample_nda.md" \
  -F "user_id=test_user"
```

### Check Processing Status

```bash
curl http://localhost:8000/status/{session_id}
```

### Get Results

```bash
curl http://localhost:8000/results/{session_id}
```

---

## Troubleshooting

### Common Issues

| Issue                           | Solution                                                                  |
| ------------------------------- | ------------------------------------------------------------------------- |
| `GOOGLE_API_KEY is required`    | Set `GOOGLE_API_KEY` in your `.env` file                                  |
| `Port 8000/3000 already in use` | Change `API_PORT` or `UI_PORT` in `.env`, or stop the conflicting process |
| UI shows "Bad Gateway"          | Check if API is running: `docker-compose logs api`                        |
| UI bypasses login               | Ensure `ADMIN_ACCESS_CODE` is set in environment                          |
| Cookies not working             | Set `ENVIRONMENT=production` and use HTTPS                                |
| CORS errors                     | Add your domain to `CORS_ORIGINS`                                         |
| Database connection failed      | Wait for db health check, or check `docker-compose logs db`               |

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f api
docker-compose logs -f ui
docker-compose logs -f db

# Application logs (inside container)
docker-compose exec api cat /app/logs/contract_copilot_*.log
```

### Restart Services

```bash
# Restart all
docker-compose restart

# Restart specific service
docker-compose restart api

# Full rebuild
docker-compose down
docker-compose up -d --build
```

### Reset Everything

```bash
# Stop and remove containers, networks, and volumes
docker-compose down -v

# Remove built images
docker-compose down --rmi all

# Fresh start
docker-compose up -d --build
```

---

## Production Checklist

Before deploying to production, ensure:

### Security

- [ ] `GOOGLE_API_KEY` is set to a valid production API key
- [ ] `ADMIN_ACCESS_CODE` is set to a strong, unique password
- [ ] `DB_PASSWORD` is changed from the default
- [ ] `ENVIRONMENT` is set to `production`
- [ ] `CORS_ORIGINS` only includes your domains
- [ ] HTTPS is enabled (use a reverse proxy like Traefik, Nginx, or Caddy)

### Configuration

- [ ] `NEXT_PUBLIC_API_URL` points to your public API URL (with HTTPS)
- [ ] `LOG_LEVEL` is set to `INFO` or `WARNING` (not DEBUG)
- [ ] `SESSION_PERSISTENCE` is configured based on privacy requirements

### Infrastructure

- [ ] Database backups are configured
- [ ] Log rotation is set up
- [ ] Monitoring/alerting is enabled
- [ ] SSL certificates are valid and auto-renewing

### Testing

- [ ] Health endpoint returns healthy status
- [ ] File upload works correctly
- [ ] Results are generated successfully
- [ ] Access code protection works (if enabled)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                         Docker Network                       │
│                                                              │
│  ┌──────────┐      ┌──────────┐      ┌──────────────────┐   │
│  │    UI    │──────│   API    │──────│    PostgreSQL    │   │
│  │ (Next.js)│      │(FastAPI) │      │    (Database)    │   │
│  │  :3000   │      │  :8000   │      │      :5432       │   │
│  └──────────┘      └──────────┘      └──────────────────┘   │
│                          │                                   │
│                          ▼                                   │
│                 ┌─────────────────┐                         │
│                 │  Google Gemini  │                         │
│                 │      API        │                         │
│                 └─────────────────┘                         │
└─────────────────────────────────────────────────────────────┘
```

---

## Support

- **Issues**: [GitHub Issues](https://github.com/amitgoesbrr/contract-copilot/issues)
- **Documentation**: [Architecture Guide](./ARCHITECTURE.md)
