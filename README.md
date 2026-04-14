# PTAB Intelligence

AI-powered Patent Trial and Appeal Board (PTAB) document intelligence — RAG pipeline on AWS + Pinecone + Bedrock.

## Architecture

```
USPTO/PTAB Data → S3 → Lambda (Ingestion) → Bedrock Titan Embeddings → Pinecone
                                                                              ↓
Next.js (Vercel) ← API Gateway ← Lambda (RAG Query) ← Anthropic Claude ←───┘
```

## Stack

| Layer | Technology |
|---|---|
| Embeddings | AWS Bedrock (Titan Embed Text v1) |
| Vector store | Pinecone Serverless (free tier) |
| LLM | Anthropic Claude 3.5 Sonnet |
| Compute | AWS Lambda (container image) |
| API | AWS API Gateway v2 (HTTP) |
| Storage | S3 (documents + Terraform state) |
| Container registry | ECR |
| Secrets | AWS Secrets Manager |
| IaC | Terraform |
| Frontend | Next.js on Vercel |

## Setup

### Prerequisites
- AWS CLI configured with `ptab` profile
- Docker
- Terraform >= 1.5
- Python 3.12

### First-time setup

```bash
# 1. Clone and configure environment
cp .env.example .env
# Fill in your Pinecone and Anthropic API keys

# 2. Initialize Pinecone index
pip install pinecone python-dotenv
python scripts/init-pinecone.py

# 3. Deploy everything
chmod +x scripts/deploy.sh
./scripts/deploy.sh
```

### Test the API

```bash
curl -X POST <API_GATEWAY_URL>/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the grounds for inter partes review?"}'
```

## Data Sources

Raw PTAB document ingestion handled by companion repos:
- [applpatentdatacollector](https://github.com/nealnaveen/applpatentdatacollector) — USPTO patent application data
- [rejectionsdownloader](https://github.com/nealnaveen/rejectionsdownloader) — USPTO rejection documents
- [paperdocdownloader](https://github.com/nealnaveen/paperdocdownloader) — Paper documents
- [ptabdatacollector](https://github.com/nealnaveen/ptabdatacollector) — PTAB-specific data

Documents are ingested into `s3://ptab-documents-604881392797` and automatically indexed on upload.
