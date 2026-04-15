"""
PTAB Intelligence — RAG Query Lambda
Handles POST /query requests.

Pipeline:
  1. Normalize the query using Claude haiku (terminology rewriting)
  2. Embed the normalized query via Bedrock Titan
  3. Retrieve top-k chunks from Pinecone
  4. Generate a grounded answer via Claude
"""

import json
import os
import boto3
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

_REGION = os.environ.get("AWS_REGION_NAME", os.environ.get("AWS_REGION", "us-east-1"))
bedrock = boto3.client("bedrock-runtime", region_name=_REGION)
secrets = boto3.client("secretsmanager", region_name=_REGION)

# In-memory cache: raw query → normalized query (cleared on cold start)
_NORMALIZE_CACHE: dict[str, str] = {}

# Canonical terminology context injected into the normalization prompt
_TERM_CONTEXT = """
Canonical USPTO/PTAB term mappings (always use the LEFT side in output):
- proceeding_number  ← case #, case no., case no, trial number, IPR no, PGR no
- application_number ← app no, appl no, serial number, serial no
- section_101        ← §101, 35 USC 101, Alice, subject matter eligibility, SME, abstract idea
- section_102        ← §102, 35 USC 102, anticipation, not novel, lack of novelty
- section_103        ← §103, 35 USC 103, obviousness, OBV, obvious, non-statutory obviousness
- section_112        ← §112, 35 USC 112, written description, enablement, indefiniteness
- IPR                ← inter partes review, inter-partes review
- PGR                ← post grant review, post-grant review
- CBM                ← covered business method
- institution_decision ← decision to institute, DTI, instituted, institution granted
- final_written_decision ← FWD, final decision, final written, final determination
- claims_unpatentable  ← claims cancelled, claims invalidated, found unpatentable
- claims_patentable    ← claims upheld, claims confirmed, survived challenge
- petition_denied      ← denied, not instituted, institution denied
- petitioner           ← challenger, requester, real party in interest, RPI
- patent_owner         ← patentee, respondent, patent holder
- office_action        ← OA, non-final rejection, NFOA, final rejection, FOA
- prior_art            ← prior art reference, cited reference, anticipatory reference
"""


def get_secret(secret_arn: str) -> str:
    return secrets.get_secret_value(SecretId=secret_arn)["SecretString"]


def normalize_query(question: str, api_key: str) -> str:
    """
    Rewrite the user's query into canonical USPTO/PTAB terminology
    before embedding. Uses Claude haiku for speed and low cost.
    Falls back to the original question on any error.
    """
    if question in _NORMALIZE_CACHE:
        return _NORMALIZE_CACHE[question]

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        result = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=256,
            messages=[{
                "role": "user",
                "content": f"""You are a USPTO/PTAB terminology normalizer.
Rewrite the query below using standard patent terminology.
Replace informal or variant terms with the canonical ones shown.
Keep the meaning identical — only change terminology, not intent.
Return ONLY the rewritten query, nothing else.

{_TERM_CONTEXT}

Query: {question}"""
            }]
        )
        normalized = result.content[0].text.strip()
        _NORMALIZE_CACHE[question] = normalized
        logger.info(f"Query normalized: '{question[:80]}' → '{normalized[:80]}'")
        return normalized
    except Exception as e:
        logger.warning(f"Query normalization failed, using original: {e}")
        return question


def embed_query(text: str) -> list[float]:
    response = bedrock.invoke_model(
        modelId="amazon.titan-embed-text-v1",
        body=json.dumps({"inputText": text}),
        contentType="application/json",
        accept="application/json",
    )
    return json.loads(response["body"].read())["embedding"]


def retrieve_context(index, query_vector: list[float], top_k: int = 5) -> str:
    results = index.query(vector=query_vector, top_k=top_k, include_metadata=True)
    chunks = [match["metadata"]["text"] for match in results["matches"]]
    return "\n\n---\n\n".join(chunks)


def generate_answer(context: str, question: str, api_key: str) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=os.environ.get("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"),
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": f"""You are a PTAB (Patent Trial and Appeal Board) legal intelligence assistant.
Use the following context from PTAB documents to answer the question.
If the answer isn't in the context, say so clearly.

CONTEXT:
{context}

QUESTION:
{question}

Answer concisely and cite relevant document sections where possible.""",
            }
        ],
    )
    return message.content[0].text


def handler(event, context):
    from pinecone import Pinecone

    try:
        body = json.loads(event.get("body", "{}"))
        question = body.get("question", "").strip()

        if not question:
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "Missing 'question' in request body"}),
            }

        pinecone_key = get_secret(os.environ["PINECONE_SECRET_ARN"])
        anthropic_key = get_secret(os.environ["ANTHROPIC_SECRET_ARN"])

        pc = Pinecone(api_key=pinecone_key)
        index = pc.Index(os.environ["PINECONE_INDEX_NAME"])

        logger.info(f"Processing query: {question[:100]}")

        # Step 1: Normalize terminology before embedding
        normalized = normalize_query(question, anthropic_key)

        # Step 2: Embed the normalized query
        query_vector = embed_query(normalized)

        # Step 3: Retrieve relevant chunks
        context_text = retrieve_context(index, query_vector)

        # Step 4: Generate grounded answer using the original question
        # (so Claude's answer matches the user's phrasing, not the normalized form)
        answer = generate_answer(context_text, question, anthropic_key)

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps({
                "answer": answer,
                "question": question,
                "normalized_query": normalized,  # useful for debugging
            }),
        }

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Internal server error"}),
        }
