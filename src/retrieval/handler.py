"""
PTAB Intelligence — RAG Query Lambda
Handles POST /query requests. Embeds the question via Bedrock Titan,
retrieves top-k chunks from Pinecone, then generates an answer via Anthropic.
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


def get_secret(secret_arn: str) -> str:
    return secrets.get_secret_value(SecretId=secret_arn)["SecretString"]


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

        query_vector = embed_query(question)
        context_text = retrieve_context(index, query_vector)
        answer = generate_answer(context_text, question, anthropic_key)

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps({"answer": answer, "question": question}),
        }

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Internal server error"}),
        }
