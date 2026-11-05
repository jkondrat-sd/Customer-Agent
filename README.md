#  FlowDesk

An intelligent, multi-agent customer support platform built with **LangGraph**, **hybrid RAG retrieval**, and **multi-model routing** (Groq Llama 3 + Google Gemini). FlowDesk automatically classifies customer intent, retrieves relevant documentation, generates grounded answers with confidence scoring, and seamlessly escalates to human agents when necessary.

---

## Architecture

## Architecture

```mermaid
graph TB
    %% External Users
    Customer((Customer)):::external
    SupportAgent((Support Agent)):::external

    %% Frontend
    Frontend[Next.js Frontend]:::frontend

    %% FlowDesk API
    FlowDeskAPI[FlowDesk API<br/>FastAPI]:::api

    %% Orchestrator
    subgraph FlowDesk[FlowDesk Support Agent]
        Router[Router Agent<br/>Groq Llama 3.3]:::agent
        RAG[RAG Agent<br/>Hybrid RAG + Reranking]:::agent
        Action[Action Agent<br/>Real API + Guardrails]:::agent
        Escalation[Escalation Agent<br/>Human Handoff]:::agent
    end

    %% Order Service
    subgraph OrderSvc[Order Service]
        OrderAPI[Order API<br/>FastAPI]:::api
        OrderSM[Order State Machine<br/>created→paid→processing→shipped→delivered→cancelled]:::db
        OrderDB[(PostgreSQL<br/>order_service)]:::db
    end

    %% Refund Service
    subgraph RefundSvc[Refund Service]
        RefundAPI[Refund API<br/>FastAPI]:::api
        RefundSM[Refund State Machine<br/>requested→approved→processing→completed/failed]:::db
        RefundDB[(PostgreSQL<br/>refund_service)]:::db
    end

    %% Delivery Simulator
    DeliverySim[Delivery Simulator<br/>Kafka Consumer + Emitter]:::sim

    %% Kafka
    Kafka[(Kafka<br/>Event Bus)]:::kafka

    %% FlowDesk DB
    FlowDeskDB[(PostgreSQL<br/>flowdesk<br/>telemetry + feedback)]:::db

    %% Connections
    Customer -->|Query| Frontend
    Frontend -->|SSE / REST| FlowDeskAPI
    FlowDeskAPI --> Router
    Router -->|faq| RAG
    Router -->|action| Action
    Router -->|complex| Escalation
    Router -->|proactive_delay| Action
    RAG --> FlowDeskDB
    Action --> FlowDeskDB
    Escalation --> FlowDeskDB

    %% Action Agent → Order/Refund APIs
    Action -->|HTTP REST| OrderAPI
    Action -->|HTTP REST| RefundAPI

    %% Order Service → Kafka
    OrderAPI -->|emit order.events| Kafka
    OrderSM --> OrderDB

    %% Refund Service → Kafka
    RefundAPI -->|emit refund.events| Kafka
    RefundSM --> RefundDB

    %% Kafka → Delivery Simulator
    Kafka -->|order.events<br/>(shipped)| DeliverySim

    %% Delivery Simulator → Kafka
    DeliverySim -->|delivery.events<br/>(delayed, delivered)| Kafka

    %% Kafka → FlowDesk (proactive delay)
    Kafka -->|delivery.events<br/>(delayed)| FlowDeskAPI
    FlowDeskAPI -->|proactive notification| Customer

    %% Classes
    classDef external fill:#e1f5fe,stroke:#01579b,stroke-width:2px
    classDef frontend fill:#fff3e0,stroke:#e65100,stroke-width:2px
    classDef api fill:#e8f5e9,stroke:#1b5e20,stroke-width:2px
    classDef agent fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef db fill:#ffebee,stroke:#b71c1c,stroke-width:2px
    classDef kafka fill:#fff8e1,stroke:#f57f17,stroke-width:2px
    classDef sim fill:#e0f2f1,stroke:#004d40,stroke-width:2px
```

### Data Flow

1. **Customer** submits a query via the Next.js frontend
2. **FlowDesk API** receives the request and invokes the LangGraph orchestrator
3. **Router Agent** classifies intent (faq / action / complex / proactive_delay)
4. **Action Agent** calls real Order/Refund APIs via HTTP with refund guardrails
5. **Order Service** emits state change events to Kafka (`order.events`)
6. **Delivery Simulator** consumes `order.events` (shipped orders), simulates delivery with possible delays, and emits `delivery.events` to Kafka
7. **FlowDesk API** consumes `delivery.events` (delayed) and proactively notifies the customer
8. All interactions are logged to PostgreSQL for telemetry and feedback


## Key Features

- **Hybrid Retrieval Pipeline**: Combines dense semantic search (Gemini embeddings) with sparse keyword search (BM25) using Reciprocal Rank Fusion (RRF), followed by Cross-Encoder reranking for high precision.
- **Dynamic Model Routing**: Routes latency-sensitive or simple queries to Groq (Llama 3.3), while reserving Gemini for complex reasoning and conversational retries.
- **LLMOps & Telemetry**: Every interaction is logged to a PostgreSQL database, tracking confidence scores, groundedness metrics, and explicit user feedback (thumbs up/down) for continuous improvement.
- **Graceful Degradation**: Built-in fallbacks ensure the system remains operational (e.g., seamlessly dropping to sparse-only search if the embedding API is unreachable).

## Tech Stack

- **Orchestration**: LangGraph (StateGraph with conditional edges + self-correction)
- **LLMs**: Groq (Llama 3.3 70B) & Google Gemini (3.5 Flash / 2.5 Pro)
- **Embeddings**: Google `models/gemini-embedding-2`
- **Vector Database**: Pinecone (Serverless)
- **Reranking**: Sentence Transformers (`cross-encoder/ms-marco-MiniLM-L-6-v2`)
- **Database**: PostgreSQL (Supabase) / SQLite (Local Dev)
- **API**: FastAPI + Uvicorn + Server-Sent Events (SSE) Streaming
- **UI**: Next.js (App Router) Demo Frontend + Tailwind CSS
- **CI/CD**: GitHub Actions → Google Cloud Run (Backend) & Vercel (Frontend)

---

## Quick Start

### Prerequisites
- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- Node.js 18+ (for the frontend)

### 1. Clone & Install
**Backend:**
```bash
git clone https://github.com/tonystalker/FlowDesk.git
cd FlowDesk
uv sync
```

**Frontend:**
```bash
cd flowdesk-demo
npm install
```

### 2. Configure Environment
```bash
# Backend (.env)
cp .env.example .env
# Edit .env with your API keys:
#   GEMINI_API_KEY, GROQ_API_KEY, PINECONE_API_KEY, PINECONE_ENV, DATABASE_URL

# Frontend (flowdesk-demo/.env.local)
echo "BACKEND_URL=http://127.0.0.1:8000" > flowdesk-demo/.env.local
```

### 3. Run Database Migrations
```bash
uv run alembic upgrade head
```

### 4. Ingest Support Documents
```bash
uv run python -m retrieval.ingest
```

### 5. Launch the App
**Start the REST API (Backend):**
```bash
uv run uvicorn gateway.main:app --reload
# Available at http://localhost:8000
```

**Start the Next.js UI (Frontend):**
```bash
cd flowdesk-demo
npm run dev
# Opens at http://localhost:3000
```

---

## Testing & Evaluation

The platform includes a comprehensive test suite and evaluation harness to benchmark retrieval accuracy and agent reliability.

```bash
# Run the test suite (50+ tests)
uv run pytest -v

# Run the linter
uv run ruff check .

# Run the evaluation harness for retrieval metrics
uv run python -m evaluation.eval_harness
```

---

## Project Structure
```text
FlowDesk/
├── gateway/              # FastAPI + Gradio UI
├── orchestrator/         # LangGraph multi-agent system & state
│   └── agents/           # Router, RAG, Action, and Escalation agents
├── retrieval/            # Hybrid RAG pipeline (Ingest, Dense/Sparse, Reranking)
├── evaluation/           # Benchmarking & confidence scoring
├── db/                   # SQLAlchemy models & Alembic migrations
├── docs/                 # Support knowledge base documents
├── tests/                # Pytest suite
├── Dockerfile            # Multi-stage production build
├── .github/workflows/    # CI/CD pipeline
└── config.py             # Centralized environment configuration
```

---

## Deployment

The project is configured to deploy automatically to **Google Cloud Run** via GitHub Actions on every push to the `main` branch. 

The CI pipeline automatically:
1. Lints the codebase with `ruff`
2. Runs the full `pytest` suite
3. Builds the Docker container
4. Deploys to Cloud Run

*Required GitHub Secrets:* `GCP_SA_KEY`, `PROJECT_ID`, `GEMINI_API_KEY`, `GROQ_API_KEY`, `PINECONE_API_KEY`, `PINECONE_ENV`, `DATABASE_URL`
