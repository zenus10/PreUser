# PreUser

**PRD Automated Stress Testing Platform** — Upload your PRD, get 10 ai users. PreUser simulates real user behavior before your product ships.

**English** | [中文](./README.zh.md)

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![React](https://img.shields.io/badge/React-18-61dafb)
![FastAPI](https://img.shields.io/badge/FastAPI-latest-009688)
![License](https://img.shields.io/badge/License-MIT-green)

## Features

- **Intelligent Document Parsing** — Upload PDF or DOCX PRDs; structured information is extracted automatically
- **Knowledge Graph Construction** — LLM-powered multi-step chain decomposes your PRD into feature nodes and dependency graphs
- **Virtual User Generation** — Automatically generates diverse user personas (Personas), fully editable
- **Multi-Scenario Narrative Simulation** — Each virtual user independently simulates an operation path and produces an experience narrative
- **Stress Test Report** — Aggregates blind spots and bottlenecks into a visual report
- **Deep-Dive Conversation** — AI Q&A grounded in analysis results for deeper product exploration

## Architecture

```
┌──────────────────────────────────────────────────┐
│                  Frontend (React)                │
│         React 18 + TypeScript + Tailwind         │
│     React Flow · Recharts · Framer Motion        │
├──────────────────────────────────────────────────┤
│                  Backend (FastAPI)               │
│        LiteLLM · SQLAlchemy · AsyncPG            │
│     5-Stage LLM Pipeline with Checkpoints        │
├───────────────────┬──────────────────────────────┤
│   PostgreSQL 16   │         Redis 7              │
└───────────────────┴──────────────────────────────┘
```

### 5-Stage Analysis Pipeline

| Stage         | Name                               | Description                                                  |
| ------------- | ---------------------------------- | ------------------------------------------------------------ |
| Chain 1       | Structure Parsing                  | Splits the PRD into semantic blocks                          |
| Chain 2 / 2.5 | Relation Extraction & Graph Fusion | Extracts feature dependencies and builds the knowledge graph |
| Chain 3       | Persona Generation                 | Generates diverse virtual users from the graph               |
| Chain 4       | Narrative Simulation               | Simulates multi-scenario operation paths per user            |
| Chain 5       | Report Generation                  | Aggregates discovered blind spots and bottlenecks            |

Each stage supports **checkpointing** — a failed run resumes from the last successful stage.

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 16
- Redis 7
- A DeepSeek API Key (or any other LiteLLM-compatible LLM API)

### 1. Clone the repository

```bash
git clone https://github.com/your-username/PreUser.git
cd PreUser
```

### 2. Start databases (Docker)

```bash
docker compose up -d
```

This starts PostgreSQL and Redis. Skip this step if you already have them running locally.

### 3. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in your API key and database password:

```env
# Required: your LLM API key
DEEPSEEK_API_KEY=your_deepseek_api_key_here

# Database password
DB_PASSWORD=your_db_password_here
```

Then do the same for the backend:

```bash
cp .env.example backend/.env
```

> **Get a DeepSeek API Key:** Sign up at [DeepSeek Open Platform](https://platform.deepseek.com/) and create a key. Any [LiteLLM-compatible model](https://docs.litellm.ai/docs/providers) works — just change `LLM_MODEL`.

### 4. Start the backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 5. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Open your browser at `http://localhost:5173`.

## Usage

1. **Upload PRD** — Upload a PDF or DOCX product requirements document on the home page
2. **Wait for Analysis** — The 5-stage pipeline runs automatically with real-time progress updates
3. **Explore the Graph** — Browse the structured knowledge graph of your PRD
4. **Edit Personas** — View and adjust the generated user personas
5. **Read Narratives** — Browse each virtual user's simulated operation scenarios
6. **Review the Report** — Read the stress test report to discover blind spots and bottlenecks
7. **Deep Dive** — Ask follow-up questions via AI conversation

## Project Structure

```
PreUser/
├── frontend/                # React frontend
│   └── src/
│       ├── pages/           # Page components
│       ├── components/      # Shared components
│       ├── store/           # Zustand state management
│       ├── api/             # API request wrappers
│       └── hooks/           # Custom hooks
├── backend/                 # FastAPI backend
│   └── app/
│       ├── api/             # Routes (upload, analysis, conversation, ws)
│       ├── llm/             # LLM call wrappers
│       ├── models/          # Database models & Pydantic schemas
│       ├── prompts/         # LLM prompt templates (Chain 1–5)
│       ├── services/        # Core business logic (pipeline, parser, etc.)
│       └── config.py        # Configuration management
├── docker-compose.yml       # PostgreSQL + Redis
├── .env.example             # Environment variable template
└── README.md
```

## Configuration Reference

| Variable                  | Description                  | Default                  |
| ------------------------- | ---------------------------- | ------------------------ |
| `DEEPSEEK_API_KEY`        | DeepSeek API key             | (required)               |
| `ANTHROPIC_API_KEY`       | Anthropic API key (optional) | —                        |
| `LLM_MODEL`               | LLM model identifier         | `deepseek/deepseek-chat` |
| `LLM_TEMPERATURE`         | Generation temperature       | `0.7`                    |
| `DB_HOST`                 | PostgreSQL host              | `localhost`              |
| `DB_PORT`                 | PostgreSQL port              | `5432`                   |
| `DB_NAME`                 | Database name                | `vul`                    |
| `DB_USER`                 | Database username            | `postgres`               |
| `DB_PASSWORD`             | Database password            | (required)               |
| `REDIS_HOST`              | Redis host                   | `localhost`              |
| `REDIS_PORT`              | Redis port                   | `6379`                   |
| `MAX_UPLOAD_SIZE_MB`      | Max upload file size         | `10`                     |
| `MAX_CONCURRENT_ANALYSES` | Max concurrent analyses      | `3`                      |

## Switching LLM Models

PreUser uses [LiteLLM](https://docs.litellm.ai/) as the LLM gateway, supporting 100+ models. Just update `.env`:

```env
# OpenAI
LLM_MODEL=gpt-4o
OPENAI_API_KEY=sk-xxx

# Anthropic Claude
LLM_MODEL=claude-sonnet-4-20250514
ANTHROPIC_API_KEY=sk-ant-xxx

# See LiteLLM docs for other providers
```

## License

MIT
