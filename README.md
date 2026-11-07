# 🛡️ AegisOps — AI-Powered SRE & Autonomous Incident Response Platform

**An intelligent AI-powered Site Reliability Engineering platform that detects infrastructure anomalies, investigates incidents through multi-agent reasoning, retrieves relevant operational runbooks, and recommends safe remediation with mandatory human approval.**

<p align="center">
  <strong>AI Agents · Anomaly Detection · Hybrid RAG · AI Security · Human-in-the-Loop · MLOps · Observability</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue?logo=python" />
  <img src="https://img.shields.io/badge/FastAPI-Backend-009688?logo=fastapi" />
  <img src="https://img.shields.io/badge/LangGraph-Multi--Agent-orange" />
  <img src="https://img.shields.io/badge/Groq-LLM-black" />
  <img src="https://img.shields.io/badge/RAG-Hybrid%20Retrieval-purple" />
  <img src="https://img.shields.io/badge/Docker-Supported-2496ED?logo=docker" />
  <img src="https://img.shields.io/badge/Tests-66%20Passing-success" />
</p>

---

## 📸 Application Screenshots

### Dashboard
<!-- Replace with your actual screenshot if the image filename differs -->
![AegisOps Dashboard](docs/screenshots/dashboard.jpeg)

### Incident Analysis
![Incident Analysis](docs/screenshots/incident_analysis.jpeg)

### Security Guardrails
![Security Guardrails](docs/screenshots/guardrails.jpeg)

---

## 📌 Overview

Modern infrastructure systems generate large volumes of metrics, logs, and traces. When an incident occurs, SRE engineers must investigate these signals, identify the root cause, consult internal documentation, and decide how to recover the affected services.

This process can be time-consuming and operationally complex.

**AegisOps addresses this challenge by bringing Machine Learning, Generative AI, multi-agent orchestration, Retrieval-Augmented Generation, and security guardrails into one incident-response platform.**

The system simulates an infrastructure environment, detects anomalies using Isolation Forest, investigates incidents through six specialized AI agents, and generates evidence-based remediation recommendations.

Unlike fully autonomous execution systems, AegisOps requires human approval before executing a proposed remediation.

### What AegisOps does

1. Simulates infrastructure telemetry across multiple microservices.
2. Detects unusual infrastructure behavior using Machine Learning.
3. Investigates incidents through six specialized AI agents.
4. Retrieves relevant SRE runbooks using Hybrid RAG.
5. Identifies potential root causes using LLM reasoning.
6. Validates remediation proposals through security guardrails.
7. Requests human approval before remediation execution.
8. Records execution outcomes and audit information.
9. Tracks application and agent performance through observability tools.

---

## 🎯 Problem Statement

Traditional incident response involves multiple manual activities:

- Identifying abnormal infrastructure behavior.
- Investigating CPU, memory, latency, and error metrics.
- Analyzing application logs and request traces.
- Identifying the root cause of an incident.
- Searching operational runbooks.
- Selecting an appropriate remediation.
- Executing recovery procedures and verifying results.

AegisOps aims to reduce this investigation effort by creating an intelligent workflow that combines anomaly detection, multi-agent investigation, knowledge retrieval, security validation, and human oversight.

---

## ✨ Key Features

### 1. Intelligent Infrastructure Anomaly Detection

Uses **Isolation Forest** to identify unusual infrastructure behavior.

Key capabilities:
- Baseline-aware feature engineering.
- Rolling statistical features.
- Z-score-based anomaly signals.
- Detection across simulated microservices.
- Support for multiple infrastructure incident scenarios.

Engineered features include:

| Feature | Purpose |
|---|---|
| `value_ratio` | Compares current values against baseline |
| `zscore` | Measures deviation from normal behavior |
| `rolling_mean_ratio` | Compares values against rolling averages |
| `rolling_std_ratio` | Captures changes in variability |
| `delta_zscore` | Measures abnormal changes over time |

### 2. Six-Agent AI Investigation Pipeline

AegisOps uses **LangGraph** to orchestrate six specialized agents.

| AI Agent | Responsibility |
|---|---|
| Metric Agent | Investigates infrastructure metrics |
| Log Agent | Analyzes application and system logs |
| Trace Agent | Examines request traces |
| Runbook Agent | Retrieves relevant operational documentation |
| Reasoner Agent | Combines evidence and identifies the likely root cause |
| Remediation Agent | Recommends a suitable corrective action |

The agents collaborate to generate structured incident analysis rather than relying on a single LLM response.

### 3. Hybrid Retrieval-Augmented Generation (RAG)

The platform uses a hybrid retrieval pipeline to ground incident investigation in internal SRE documentation.

**Retrieval workflow:**

```text
SRE Runbook Documents
        |
        v
   Document Parsing
        |
        v
   BM25 Retrieval
        |
        +
        |
        v
 ChromaDB Vector Search
        |
        v
 Reciprocal Rank Fusion
        |
        v
 Cross-Encoder Reranking
        |
        v
 Relevant Runbook Context
        |
        v
     LLM Reasoning
```

Components:
- BM25 keyword retrieval.
- ChromaDB vector database.
- Sentence Transformers embeddings.
- Reciprocal Rank Fusion (RRF).
- Cross-encoder reranking.
- Context-grounded LLM reasoning.

### 4. Five-Layer AI Security Guardrails

Security is implemented at the remediation boundary to reduce the risk of unsafe AI-generated actions.

| Layer | Security Mechanism |
|---|---|
| 1 | PII Redaction |
| 2 | Dangerous Command Blocking |
| 3 | Safe Command Allowlist |
| 4 | Role-Based Access Control (RBAC) |
| 5 | Prompt Injection Detection |

Additional protections:
- Sensitive information detection.
- Dangerous shell command blocking.
- Restricted Kubernetes command patterns.
- Role-based authorization.
- Suspicious prompt instruction detection.

### 5. Human-in-the-Loop Remediation

AegisOps separates remediation recommendation from execution.

```text
Incident Investigation
        |
        v
Remediation Proposal
        |
        v
Security Validation
        |
        v
Human Approval
        |
        +------ Reject
        |          |
        |          v
        |      Audit Record
        |
        +------ Approve
                   |
                   v
             Dry-Run Execution
                   |
                   v
             Execution Result
                   |
                   v
               Audit Trail
```

Capabilities:
- Approval and rejection workflow.
- Approver identity and timestamp.
- Execution audit trail.
- Dry-run command execution.
- Simulated Kubernetes execution.

**Important:** Human approval is mandatory before remediation execution.

### 6. Observability & MLOps

The platform integrates monitoring and experiment-tracking capabilities.

| Component | Purpose |
|---|---|
| Prometheus | Application and agent metrics |
| MLflow | Experiment and model tracking |
| Structlog | Structured application logging |
| Token Tracking | LLM token usage and API cost |
| Latency Monitoring | Agent execution performance |
| Prompt Versioning | Prompt tracking |

---

## 🏗️ System Architecture

```text
              SIMULATED INFRASTRUCTURE
       +----------------------------------+
       | Frontend | API | Auth | Orders   |
       | Payment  | PostgreSQL            |
       +----------------+-----------------+
                        |
                        v
              Metrics / Logs / Traces
                        |
                        v
              +--------------------+
              |   Data Ingestion   |
              |   SQLite Storage   |
              +---------+----------+
                        |
                        v
              +--------------------+
              |  Isolation Forest  |
              | Anomaly Detection  |
              +---------+----------+
                        |
                        v
              +--------------------+
              |  LangGraph Engine  |
              |                    |
              | 1. Metric Agent    |
              | 2. Log Agent       |
              | 3. Trace Agent     |
              | 4. Runbook Agent   |
              | 5. Reasoner Agent  |
              | 6. Remediation     |
              +---------+----------+
                        |
                        v
              +--------------------+
              | Groq LLM + Hybrid  |
              | RAG / ChromaDB     |
              +---------+----------+
                        |
                        v
              +--------------------+
              | Security Guardrails|
              | PII / RBAC / CMD   |
              | Injection Checks   |
              +---------+----------+
                        |
                        v
              +--------------------+
              |   Streamlit UI     |
              | Human Approval     |
              +---------+----------+
                        |
                        v
              +--------------------+
              | Dry-Run Execution  |
              |    Audit Trail     |
              +--------------------+

           Prometheus | MLflow | Structlog
```

---

## 📊 Evaluation Results

The following results are reported by the project's supplied six-scenario evaluation and automated test suite.

| Evaluation Metric | Reported Result |
|---|---:|
| Incident Category Accuracy | 100% (6/6) |
| Service Identification Accuracy | 100% (6/6) |
| Metric Accuracy | 100% (6/6) |
| RAG Precision | 100% |
| Average End-to-End Latency | ~26.73 seconds |
| Estimated Cost per Incident | ~$0.0011 |
| Automated Tests | 66/66 Passing |
| Guardrail Block Rate | 100% in tested cases |

### Incident Scenario Evaluation

| Scenario | Expected Classification | Result |
|---|---|---|
| Normal | Healthy | Passed |
| Memory Leak | Memory | Passed |
| Slow Database | Latency | Passed |
| Service Outage | Errors | Passed |
| CPU Spike | CPU | Passed |
| Error Cascade | Errors | Passed |

<sub>Note: These results are based on the project's simulated scenarios and test environment. They are not independently validated production benchmarks. Latency and API cost may vary depending on the model, network, hardware, and execution environment.</sub>

---

## 🧰 Technology Stack

| Category | Technologies |
|---|---|
| Programming Language | Python 3.11+ |
| Backend | FastAPI, Uvicorn |
| Frontend | Streamlit, Plotly |
| AI Orchestration | LangGraph, LangChain |
| LLM | Groq — gpt-oss-120b |
| Machine Learning | Scikit-learn, Isolation Forest |
| RAG | ChromaDB, BM25 |
| Embeddings | Sentence Transformers |
| Reranking | Cross-Encoder |
| Data Validation | Pydantic v2 |
| Database | SQLite, SQLAlchemy |
| Monitoring | Prometheus |
| Experiment Tracking | MLflow |
| Logging | Structlog |
| Testing | Pytest |
| Deployment | Docker, Docker Compose |

---

## 🚀 Getting Started

### Prerequisites

Make sure you have:

- Python 3.11 or newer
- Git
- Groq API key
- Docker Desktop (optional)

### 1. Clone the Repository

```bash
git clone https://github.com/vaibhav07772/aegisops.git
cd aegisops
```

### 2. Create a Virtual Environment

**Windows:**

```bash
python -m venv .venv
.venv\Scripts\activate
```

**Linux / macOS:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements-dev.txt
```

### 4. Configure Environment Variables

Create your local environment file:

**Windows CMD:**

```cmd
copy .env.example .env
```

**Linux / macOS:**

```bash
cp .env.example .env
```

Open `.env` and configure your Groq API key:

```env
GROQ_API_KEY=your_groq_api_key_here
```

Get your API key:

[Groq Console](https://console.groq.com/keys)

**Security:** Never commit `.env` or expose API keys in source code, screenshots, logs, or public repositories.

### 5. Initialize Runbooks and Simulation Data

Run the bootstrap and data preparation commands:

```bash
python scripts/setup_runbooks.py --force
```

Generate the simulated infrastructure scenarios:

```bash
python scripts/run_simulation.py --scenario normal --duration 30 --speedup 10

python scripts/run_simulation.py --scenario memory_leak --duration 30 --speedup 10

python scripts/run_simulation.py --scenario slow_database --duration 30 --speedup 10

python scripts/run_simulation.py --scenario service_outage --duration 30 --speedup 10

python scripts/run_simulation.py --scenario cpu_spike --duration 30 --speedup 10

python scripts/run_simulation.py --scenario error_cascade --duration 30 --speedup 10
```

Ingest telemetry and runbooks:

```bash
python scripts/ingest_data.py

python scripts/ingest_runbooks.py --force
```

Train the anomaly detection model:

```bash
python scripts/train_anomaly.py
```

### 6. Start the Backend

```bash
python run.py
```

FastAPI documentation:

http://localhost:8000/docs

### 7. Start the Frontend

Open another terminal, activate the same virtual environment, and execute:

```bash
streamlit run admin/app.py
```

Open the dashboard:

http://localhost:8501

### 8. Run with Docker (Optional)

Configure `.env` with your Groq API key and run:

```bash
docker-compose up --build
```

---

## 🎬 Demo Workflow

Follow these steps to explore AegisOps:

1. Open the Streamlit dashboard.
2. Select an incident from the incident queue.
3. Click **Analyze this run**.
4. Observe the six-agent investigation pipeline.
5. Review the identified issue and retrieved runbook.
6. Inspect the proposed remediation.
7. Approve or reject the recommendation.
8. Review the execution result and audit trail.
9. Open the Guardrails page to test command validation.

### Example Security Checks

**Dangerous command:**

```bash
rm -rf /var/data
```

Expected: Blocked by the dangerous-command guardrail.

**Safe command:**

```bash
kubectl get pods
```

Expected: Permitted when it matches the configured safe-command policy.

---

## 🧪 Testing

Run the complete automated test suite:

```bash
pytest -v
```

### Test Coverage

| Test Module | Coverage | Tests |
|---|---|---:|
| `test_sim.py` | Telemetry Simulation | 4 |
| `test_ingestion.py` | SQLite Ingestion | 3 |
| `test_anomaly.py` | Anomaly Detection | 5 |
| `test_agents.py` | Agent Orchestration | 4 |
| `test_llm.py` | LLM Integration and Fallback | 9 |
| `test_rag.py` | Runbook Retrieval | 5 |
| `test_security.py` | Security and Guardrails | 30 |
| `test_evaluation.py` | Evaluation Metrics | 6 |
| **Total** | | **66** |

---

## 📈 Run System Evaluation

Execute:

```bash
python scripts/evaluate_system.py
```

The evaluation script checks:

- Incident category prediction.
- Service identification.
- Metric consistency.
- RAG retrieval quality.
- End-to-end latency.
- Estimated API cost.

---

## 🛡️ Security Design Principles

AegisOps follows five important engineering principles:

| Principle | Implementation |
|---|---|
| Least Privilege | Role-based permissions |
| Defense in Depth | Multiple security validation layers |
| Human Oversight | Approval before remediation |
| Safe Execution | Dry-run and simulated execution |
| Auditability | Recorded approval and execution events |

The system also provides rule-based fallback behavior when LLM reasoning is unavailable.

---

## 💡 Key Engineering Decisions

### 1. Hybrid Retrieval Instead of Vector Search Alone

Combining BM25 keyword search with vector retrieval helps retrieve runbooks using exact operational terms as well as semantic similarity.

### 2. Multi-Agent Investigation

Separating metric, log, trace, retrieval, reasoning, and remediation responsibilities makes the investigation workflow modular and easier to evaluate.

### 3. LLM with Rule-Based Fallback

LLM services can fail or become unavailable. A rule-based fallback provides an alternative inference path when LLM reasoning cannot be completed.

### 4. Structured LLM Outputs

Pydantic validation helps validate structured model responses and normalize outputs before downstream processing.

### 5. Human Approval Before Remediation

The system separates recommendation from execution to reduce the risk of blindly executing AI-generated commands.

### 6. Security at the Action Boundary

Proposed commands are checked against security policies before reaching the execution workflow.

---

## 📁 Project Structure

```text
aegisops/
│
├── admin/
│   ├── pages/                  # Dashboard and security pages
│   └── app.py                  # Streamlit application
│
├── app/
│   ├── agents/                 # Six-agent LangGraph pipeline
│   ├── api/                    # FastAPI routes and endpoints
│   ├── evaluation/             # Ground truth and evaluation
│   ├── llm/                    # Groq client, prompts and schemas
│   ├── ml/                     # Isolation Forest and features
│   ├── pipeline/               # Telemetry ingestion
│   ├── rag/                    # Hybrid retrieval and runbooks
│   ├── security/               # Security guardrails
│   ├── storage/                # Database models and repositories
│   └── monitoring/             # Prometheus metrics
│
├── data/
│   └── runbooks/               # Internal SRE runbook documents
│
├── docs/
│   └── screenshots/            # Application screenshots
│
├── scripts/                    # Setup, training and evaluation
├── sim/                        # Infrastructure simulator
├── tests/                      # Automated test suite
│
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
├── .env.example
├── .gitignore
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
├── pytest.ini
└── run.py
```

---

## 🚧 Limitations & Future Improvements

AegisOps currently operates with simulated infrastructure and dry-run remediation.

Potential improvements:

- Integration with real Kubernetes clusters.
- Real Prometheus and Grafana infrastructure telemetry.
- Production-grade persistent incident storage.
- More diverse real-world incident datasets.
- Expanded evaluation across larger incident datasets.
- Additional authentication and authorization integrations.
- Cloud deployment and scalable infrastructure.
- Advanced incident correlation and root-cause analysis.
- Real infrastructure recovery verification.

The project should not be treated as a production incident-response system without additional testing, security review, and operational integrations.

---

## 🧠 What This Project Demonstrates

AegisOps showcases practical engineering experience across multiple AI and software engineering domains.

- Python Backend Engineering
- Machine Learning and Anomaly Detection
- Generative AI and LLM Integration
- Multi-Agent Systems with LangGraph
- Retrieval-Augmented Generation (RAG)
- Hybrid Search and Reranking
- Structured LLM Output Validation
- AI Security and Prompt Injection Defense
- Human-in-the-Loop Workflows
- MLOps and Experiment Tracking
- Monitoring and Observability
- REST API Development with FastAPI
- Docker-Based Application Packaging
- Automated Testing and Evaluation

---

## 👨‍💻 Author

**Vaibhav Singh**

Aspiring AI/ML Engineer | GenAI & Agentic AI Developer

- GitHub: [@vaibhav07772](https://github.com/vaibhav07772)
- Project Repository: [AegisOps](https://github.com/vaibhav07772/aegisops)

---

## 📄 License

Add a `LICENSE` file to the repository before declaring a specific open-source license. Until then, the project's license is not explicitly specified.

---

<p align="center">
  <strong>Built with ❤️ using Python, LangGraph, FastAPI, Groq and Machine Learning.</strong>
  <br />
  Making incident response smarter, safer and more intelligent.
</p>