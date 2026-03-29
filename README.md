# Research Intelligence Agent

**An advanced automated research platform engineered with LangGraph, Groq, and Tavily**. In an era where LLMs often struggle with hallucinations and "black-box" reasoning, this system offers a robust solution by implementing a sophisticated Multi-Agent architecture. It doesn't just "search and summarize"; it orchestrates a team of specialized AI agents to deliver transparent, cross-verified, and high-fidelity research reports. By fusing real-time web intelligence with deep-indexing of local PDF sources, the agent ensures every claim is grounded in verifiable evidence.


## System Overview

This project represents a dynamic Agentic RAG framework, ensures "Full Transparency" through a real-time Reasoning Log, which has been built from an **Intelligent Feedback Loop** architecture:

- The core of the system is the **Verifier-Writer Loop**. The Verifier agent acts as a "hard-nosed editor," auditing the Writer’s draft against the raw source material. If the confidence score is low or contradictions are found, the state is routed back for revision—ensuring the final output is factually bulletproof.
- Unlike static pipelines, the **Researcher Agent** functions as a dispatcher. It analyzes the intent of each sub-query to decide the optimal source: fetching "breaking news" via **Tavily**, or extracting "technical specs" from user-uploaded **PDFs**.


To solve the "AI trust problem," the system features a real-time **Reasoning Log**. Powered by **Server-Sent Events (SSE)**, every thought, tool call, and internal decision is streamed to the UI as it happens. Users aren't just waiting for a result; they are watching the "thinking process" of a digital research team, providing a level of transparency and debuggability rarely seen in standard AI applications.

## Installation Instructions

### Prerequisites
* **Python 3.11+**
* **Conda** (recommended)
* **Docker & Docker Compose**
* **API Keys:** Groq, Tavily.

### Local Setup (Conda)
```bash
# Clone the repository
git clone https://github.com/your-username/research-intelligence-agent.git
cd research-intelligence-agent

# Create and activate environment
conda create -n research-agent python=3.11 -y
conda activate research-agent

# Install dependencies
pip install -r backend/requirements/base.txt
```

### Environment Variables (.env)
Create a `.env` file in the `backend/` directory:
```env
GROQ_API_KEY=your_groq_key_here
TAVILY_API_KEY=your_tavily_key_here
TAVILY_MAX_RESULTS=your_max_results_you_want
```

Create a `.env` file in the `frontend/app/api/chat/` directory:
```env
# FastAPI backend URL
BACKEND_URL=http://localhost:8000
```

### DVC Setup
I use **DVC (Data Version Control)** to manage our prompt templates and model parameters (`params.yaml`), ensuring experiments are reproducible.

```bash
# Initialize DVC
dvc init

# Track configuration files
# Update model params or prompts in params.yaml
dvc commit params.yaml
git add params.yaml.dvc
git commit -m "Experiment: Switch Analyst to Qwen 3.5"
```

---

## Model Experimentation & Selection

During development, I benchmarked multiple models on Groq to find the optimal balance between **TPM (Tokens Per Minute)** and **Reasoning Quality**.

| Agent | Selected Model | Reasoning |
| :--- | :--- | :--- |
| **Planner** | `openai/gpt-oss-20b` | Low latency, high-speed query decomposition. |
| **Analyst** | `qwen3-32b` | Superior JSON formatting and context understanding. |
| **Writer** | `openai/gpt-oss-120b` | High-fidelity academic writing and synthesis. |
| **Verifier** | `openai/gpt-oss-120b` | Zero-shot fact-checking and contradiction detection. |

---

## How to Run

### 1. Manual Start
**Backend:**
```bash
cd backend
uvicorn main:app --reload --port 8000
```
or
```bash
cd backend
python main.py
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

### 2. Docker Setup (Production Mode)
```bash
docker-compose up --build
```
The system will be available at `http://localhost:3000` with the API running at `http://localhost:8000`.

### 3. Run backend test case
```bash
cd backend
python -m tests.testbackend
python -m tests.test_streaming_latency
```

---

## Deployment

The system is containerized using **Multi-stage Docker builds** for the Frontend to minimize image size and **Uvicorn** for high-performance Backend serving.

* **Scaling:** Stateless FastAPI design allows for horizontal scaling behind a Load Balancer.
* **Streaming:** Uses **Server-Sent Events (SSE)** with `X-Accel-Buffering: no` to bypass Nginx buffering for real-time UI updates.

---

### Key Technical Highlights
* **Minimize-Hallucination Focus:** Implemented a Critic-Correction loop between Writer and Verifier.
* **Real-time Transparency:** Built a custom SSE streaming logic for the "Reasoning Log" to show Agent "Thinking" steps.
* **Tool Orchestration:** Intelligent routing between Web Search and local PDF context.

### Docs
- [PIPELINE.md](docs/PIPELINE.md) -- Algorithm pipeline
- [STRUCTURE.md](docs/STRUCTURE.md) -- Project structure