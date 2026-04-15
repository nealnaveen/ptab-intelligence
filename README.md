# PTAB Intelligence

**AI-powered patent intelligence platform** — natural language search across USPTO PTAB proceedings, patent applications, and Office Action rejection statistics.

Built by [Naveen Arjunan](https://www.linkedin.com/in/naveenarjunan) — Principal Architect with hands-on USPTO domain experience (led AWS cloud migration of USPTO's Patent Examination Data System, 2018–2019; built RAG pipeline for 14M+ patent records at USPTO, 2025).

---

## What It Does

PTAB Intelligence lets patent attorneys, IP analysts, and technologists ask natural language questions across:

- **PTAB Proceedings** — IPR and PGR inter partes review cases, institution decisions, final written decisions, petitioner/patent owner data
- **Patent Applications** — filing dates, art units, technology centers, applicant assignments, prosecution status
- **Rejection Statistics** — §101, §102, §103, §112 rejection rates by application

**Example queries the AI answers:**
- *"What §101 arguments have been successful against Alice rejections for AI/ML inventions?"*
- *"What are the most common grounds petitioners use to challenge semiconductor patents at PTAB?"*
- *"What prior art does the USPTO most commonly cite against neural network patent claims?"*
- *"Which technology areas have the highest IPR petition volume in recent years?"*

---

## Architecture

```
USPTO ODP API (api.uspto.gov)
        │
        ▼
  Fetch Lambdas (Python)          ← scheduled via EventBridge
  fetch_applications.py
  fetch_proceedings.py
  fetch_rejections.py
        │
        ▼
  S3 Bucket (ptab-documents)      ← JSON records per doc type
        │
        ├──► Browse Lambda         ← GET /browse/{docType}
        │    enrich() maps ODP     ← paginated, continuation token
        │    nested schema →
        │    flat display fields
        │
        └──► Ingest Lambda         ← S3 event trigger (on PutObject)
             chunk + embed          ← Amazon Bedrock Titan embeddings
                  │
                  ▼
            Pinecone Vector DB      ← semantic search index
                  │
                  ▼
           RAG Query Lambda         ← POST /query
           retrieve top-k chunks
           + Claude synthesis       ← claude-haiku-4-5-20251001
                  │
                  ▼
        API Gateway (HTTP API)
                  │
                  ▼
        Next.js 15 UI (App Router)  ← deployed on AWS Amplify
        /api/query (server proxy)
        /api/browse/[type] (server proxy)
```

**Infrastructure:** All AWS resources managed by Terraform (Lambda, API Gateway, S3, Secrets Manager, ECR, IAM).

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 15 App Router, Tailwind CSS |
| API | AWS API Gateway (HTTP), Next.js server-side proxy routes |
| Compute | AWS Lambda (Python 3.12, ARM64) |
| Vector DB | Pinecone |
| Embeddings | Amazon Bedrock — Titan Text Embeddings v1 |
| LLM | Anthropic Claude (claude-haiku-4-5-20251001) |
| Storage | AWS S3 |
| Secrets | AWS Secrets Manager |
| IaC | Terraform |
| Hosting | AWS Amplify |
| Data Source | USPTO Open Data Portal (api.uspto.gov) |

---

## Project Structure

```
ptab-intelligence/
├── src/
│   ├── browse/
│   │   └── handler.py          # Browse Lambda — paginated S3 reads + field enrichment
│   └── query/                  # RAG query Lambda (Docker/ECR)
├── scripts/
│   ├── fetch_applications.py   # USPTO ODP → S3 (applications)
│   ├── fetch_proceedings.py    # USPTO ODP → S3 (PTAB proceedings)
│   ├── fetch_rejections.py     # USPTO ODP → S3 (OA rejection stats)
│   ├── backfill_pinecone.py    # One-time: embed + index all S3 docs into Pinecone
│   ├── debug_s3_record.py      # Inspect raw ODP field structure from S3
│   └── env-setup.sh            # AWS SSO session setup for Git Bash
├── terraform/
│   ├── main.tf                 # All AWS resources
│   ├── variables.tf
│   └── outputs.tf
├── ui/
│   ├── app/
│   │   ├── page.tsx            # Main page — 4 tabs
│   │   └── api/
│   │       ├── query/route.ts            # Server proxy → POST /query
│   │       └── browse/[type]/route.ts   # Server proxy → GET /browse/{type}
│   └── components/
│       ├── ChatTab.tsx         # Ask AI — RAG chat interface
│       └── BrowseTab.tsx       # Data browser — paginated S3 records
├── amplify.yml                 # AWS Amplify build spec
└── README.md
```

---

## Key Engineering Decisions

**Why Lambda over ECS for the browse function?** The browse Lambda only uses `boto3`, which is built into the Python Lambda runtime — no container needed. ZIP deployment takes under 10 seconds. The RAG query function uses Docker/ECR because it requires `pinecone-client`, `anthropic`, and other dependencies.

**Why Pinecone over OpenSearch?** Managed vector DB with zero operational overhead. The vector store is behind an abstraction layer so it could be swapped for OpenSearch Serverless without changing the Lambda interface.

**Why Next.js SSR instead of static export?** The `/api/query` and `/api/browse` routes are server-side proxies that forward browser requests to API Gateway without exposing the AWS URL client-side. This requires SSR — a static export cannot run server-side code.

**ODP API field mapping:** The USPTO Open Data Portal stores application metadata in a deeply nested structure (`raw.applicationMetaData.*`). The browse Lambda's `enrich()` function maps from actual ODP field paths to a flat display schema, handling multiple fallback field names per attribute across different API response versions.

---

## Roadmap

See [`ptab_execution_plan.docx`](./ptab_execution_plan.docx) for the full phased plan.

| Phase | Description | Status |
|---|---|---|
| 0 | Security — rotate API keys, commit to GitHub | ✅ Done |
| 1 | Deploy to AWS Amplify with CI/CD | 🔄 In progress |
| 2 | Automated USPTO sync (EventBridge + S3 event trigger → Pinecone) | 📋 Planned |
| 3 | Terminology normalization — canonical schema + query rewriting | 📋 Planned |
| 4 | AI Document Intelligence — PTAB PDF analysis, structured Claude extraction, analytics dashboard | 📋 Planned |

---

## Local Development

```bash
# Prerequisites: Python 3.12, Node 18+, AWS profile configured

# 1. AWS session setup (run in every new Git Bash window)
source scripts/env-setup.sh

# 2. Set up environment
cp .env.example .env
# Fill in: ODP_API_KEY, PINECONE_API_KEY, PINECONE_INDEX_NAME

# 3. Fetch USPTO data into S3
python scripts/fetch_proceedings.py --limit 100
python scripts/fetch_applications.py --limit 100
python scripts/fetch_rejections.py --limit 100

# 4. Backfill Pinecone index
python scripts/backfill_pinecone.py --limit 20  # test run first

# 5. Deploy AWS infrastructure
cd terraform && terraform init && terraform apply -auto-approve

# 6. Run UI locally
cd ui
cp .env.local.example .env.local
# Set API_GATEWAY_URL from terraform output
npm install && npm run dev
# Open http://localhost:3000
```

---

## Data Sources

- **USPTO Open Data Portal:** [api.uspto.gov](https://api.uspto.gov) — requires free API key from [developer.uspto.gov](https://developer.uspto.gov)
- **PTAB Proceedings:** `GET /api/v1/patent/trials/proceedings/search`
- **Patent Applications:** `GET /api/v1/patent/applications/search`
- **Office Action Rejections:** `POST /api/v1/patent/oa/oa_rejections/v2/records`

---

*Built with Python · Next.js · AWS Lambda · Pinecone · Amazon Bedrock · Anthropic Claude · Terraform*
