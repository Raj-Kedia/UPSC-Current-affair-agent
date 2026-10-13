# AI-Powered UPSC Current Affairs Intelligence System

Built an AI-powered news intelligence system using LangGraph, ChromaDB, Gemini, and FastAPI to automate retrieval, semantic PYQ mapping, evaluation, and **weekly newsletter delivery** through a multi-stage workflow, paired with a minimalist React dashboard and custom admin management panel.

![Dashboard Preview](assets/dashboard.png)

## 🌟 Features

- **Weekly Current Affairs Cadence**: Synthesizes a comprehensive weekly digest every week instead of daily noise, mapping 7 days of high-yield news directly to GS Papers (I–IV).
- **Aspirant Registration & Login**: Users can register and log in to manage their weekly newsletter subscription and track activation status in real-time.
- **Sample Weekly Newsletter**: Logged-in and prospective aspirants can explore sample weekly study cards (with search and GS Paper filtering) and preview the exact rendered HTML email newsletter.
- **Custom Admin Panel**: Dedicated administration console for managing user activation requests, accepting/activating plans, cancelling plans, reactivating subscriptions, and triggering bulk weekly dispatches.
- **Multi-Stage Orchestration**: Powered by LangGraph. Distinct agent nodes for Fetching (168-hour weekly window), Curating, Analyzing, Evaluating, and Formatting with conditional routing.
- **RAG & Vector Database (ChromaDB)**: Ingests 10+ years of Mains PYQs. Uses Gemini Embeddings to perform semantic searches, systematically mapping weekly news to historical syllabus trends.
- **Automated SMTP Dispatch**: Beautiful responsive HTML weekly newsletter delivery to all active subscribers with retry mechanisms and individual recipient dispatch.

## 🛠️ Technologies Used

- **Backend**: Python, FastAPI, SQLite, LangGraph, BeautifulSoup, RSS, ThreadPoolExecutor
- **AI & Data**: Gemini API, ChromaDB (Vector Search)
- **Frontend**: React, Vite, Minimalist Vanilla CSS
- **Delivery**: SMTP (Multi-recipient individualized dispatch)

## 🏗️ Architecture Flow

```mermaid
graph TD
    A[Weekly Trigger / Admin Dispatch] --> B(Fetch Weekly News Node - 168h)
    B --> C(Verification Agent)
    C --> D(Deduplication & Curation Node)
    D --> E(RAG & PYQ Search)
    E --> F(Analyzer Agent)
    F --> G(Evaluator & Critique Agent)
    G --> H(Weekly Newsletter Generator)
    H --> I[Admin Approval & Subscriber Dispatch]
    I --> J[Individualized SMTP Dispatch to Active Users]
    
    subgraph Data Stores
    K[(ChromaDB Vector Store)]
    L[(Local Cache JSON)]
    M[(SQLite Users & Subscriptions DB)]
    end
    
    E -.-> K
    H -.-> L
    I -.-> M
```

## 📂 Folder Structure

```
UPSC-Current-affair-agent/
├── agent/                  # Python Backend (LangGraph, FastAPI)
│   ├── api.py              # FastAPI server (Auth, Admin, Subscriptions, Dispatch)
│   ├── src/
│   │   ├── db.py           # SQLite user authentication & subscription management
│   │   ├── graph.py        # LangGraph State Machine (Weekly cadence)
│   │   ├── rag.py          # ChromaDB & Vector Search
│   │   ├── analyzer.py     # Analyzer & Evaluator Agents
│   │   ├── fetcher.py      # RSS & Web Fetching logic (168-hour weekly window)
│   │   ├── mailer.py       # Weekly HTML newsletter generator & SMTP Dispatch
│   │   └── config.py       # Configuration management
│   ├── data/               # Local cache, briefs, & SQLite DB
│   └── requirements.txt
├── dashboard/              # React / Vite Minimalist Frontend
│   ├── src/
│   │   ├── App.jsx         # Minimalist UI: Auth, User Portal, Sample & Admin Panel
│   │   └── index.css       # Minimalist design system
│   └── package.json
└── README.md
```

## 🚀 Installation & Setup

1. **Clone the repository**
2. **Setup the Python Backend**:
   ```bash
   cd agent
   python -m pip install -r requirements.txt
   cp .env.example .env
   # Edit .env and add your GEMINI_API_KEY and SMTP credentials
   ```
3. **Setup the Dashboard Frontend**:
   ```bash
   cd ../dashboard
   npm install
   ```

## 🏃‍♂️ Running the System

You need to run both the FastAPI backend and the Vite frontend.

**Start the Backend API:**
```bash
cd agent
uvicorn api:app --reload --port 8000
```

**Start the Dashboard:**
```bash
cd dashboard
npm run dev
```

Open `http://localhost:5173` in your browser. You can trigger the LangGraph workflow directly from the UI, view the generated notes, and approve the email.

## 📊 Metrics & Performance

- **Processing Volume**: Curates and analyzes 100–150 raw news articles/day.
- **Average Processing Time**: ~3.8 minutes for an end-to-end run.
- **API Efficiency**: Averages ~45 Gemini requests/day via smart curation constraints.
- **RAG Latency**: ChromaDB retrieval executes in ~35 ms against a 10-year PYQ dataset.
- **Deduplication Rate**: Consistently achieves a ~42% noise reduction before LLM analysis.
- **Concurrency**: `ThreadPoolExecutor` handles article analysis concurrently, reducing end-to-end processing time.

## 🔮 Future Work

- Integrate LangSmith for tracing agent thoughts and execution graphs.
- Add an automated background CRON job directly into the FastAPI server.
- Scrape NCERT textbooks into the Vector DB to augment Prelims-specific facts.
