# ⚡ Electrical Compliance Agent
> **Track 1: AI Agents and Agentic Workflows**

The **Electrical Compliance Agent** is a multi-agent system designed to automate the technical auditing of low-voltage electrical projects. Using the **CrewAI** framework and **RAG (Retrieval-Augmented Generation)**, the system analyzes project descriptions, consults technical standards (NBR 5410:2004) stored in **Supabase (pgvector)**, and generates compliance reports with traceable evidence and component recommendations.

## 🚀 Business Value
Electrical audits are slow, manual, and highly prone to critical errors when information is incomplete. Our solution:
- **Reduces review time** from minutes to seconds.
- **Eliminates hallucinations** by forcing the AI to cite real clauses from technical standards.
- **Provides immediate remediation suggestions** by connecting technical failures to a product catalog (SKUs).

## 🤖 The Agentic Workflow
The key differentiator of this project is the orchestration of 4 layers of intelligence:

1. **Triage Agent:** Normalizes informal user inputs into structured data (kW, Voltage, Wire Gauges).
2. **Research Agent (RAG):** Performs semantic search in Supabase to retrieve only the relevant excerpts from NBR 5410.
3. **Audit Agent:** Cross-checks project data against the standard, classifying risks by severity and citing clauses as evidence.
4. **Support Layer:** Handles remediation by suggesting exact catalog replacements to fix wire gauge or protection issues.

## 🛠️ Technology Stack
- **Orchestration:** [CrewAI](https://www.crewai.com/?utm_source=chatgpt.com)
- **Backend:** [FastAPI](https://fastapi.tiangolo.com/?utm_source=chatgpt.com) (Python)
- **Frontend:** [Next.js](https://nextjs.org/?utm_source=chatgpt.com) + [Tailwind CSS](https://tailwindcss.com/?utm_source=chatgpt.com)
- **Database:** [Supabase](https://supabase.com/?utm_source=chatgpt.com) with the `pgvector` extension for semantic search.
- **LLMs:** [OpenAI GPT-4o](https://openai.com/?utm_source=chatgpt.com) / [Google Gemini 1.5 Pro](https://deepmind.google/technologies/gemini/?utm_source=chatgpt.com)

## 📦 Installation and Setup

### Backend
1. Navigate to the `/backend` folder.
2. Create the virtual environment: `python -m venv .venv` and activate it.
3. Install dependencies: `pip install -r requirements.txt`.
4. Configure the keys in the `.env` file (according to `.env.example`).
5. Start the server: `uvicorn api.main:app --reload`.

### Frontend
1. Navigate to the `/web` folder.
2. Install dependencies: `npm install`.
3. Start the development server: `npm run dev`.

## 📖 Data Ingestion (RAG)
The system was powered using **NBR 5410:2004**. We used a data ingestion pipeline with Gemini 1.5 Pro to ensure that technical tables and texts were accurately converted into Markdown before being vectorized in Supabase.

---
*This project was developed for Hackathon demonstration purposes and does not replace the technical responsibility of a licensed electrical engineer.*