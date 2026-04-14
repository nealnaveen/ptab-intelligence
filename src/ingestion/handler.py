"""
PTAB Intelligence — Document Ingestion Lambda
Triggered by S3 ObjectCreated events. Chunks PTAB documents,
generates embeddings via Bedrock Titan, and upserts into Pinecone.
"""

import json
import os
import boto3
import logging
from typing import Generator

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")
bedrock = boto3.client("bedrock-runtime", region_name=os.environ["AWS_REGION_NAME"])
secrets = boto3.client("secretsmanager")

CHUNK_SIZE = 512
CHUNK_OVERLAP = 64


def get_secret(secret_arn: str) -> str:
    return secrets.get_secret_value(SecretId=secret_arn)["SecretString"]


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> Generator:
    words = text.split()
    for i in range(0, len(words), size - overlap):
        yield " ".join(words[i : i + size])


def embed(text: str) -> list[float]:
    response = bedrock.invoke_model(
        modelId="amazon.titan-embed-text-v1",
        body=json.dumps({"inputText": text}),
        contentType="application/json",
        accept="application/json",
    )
    return json.loads(response["body"].read())["embedding"]


def handler(event, context):
    from pinecone import Pinecone

    pinecone_key = get_secret(os.environ["PINECONE_SECRET_ARN"])
    pc = Pinecone(api_key=pinecone_key)
    index = pc.Index(os.environ["PINECONE_INDEX_NAME"])

    for record in event["Records"]:
        bucket = record["s3"]["bucket"]["name"]
        key = record["s3"]["object"]["key"]

        logger.info(f"Processing s3://{bucket}/{key}")

        obj = s3.get_object(Bucket=bucket, Key=key)
        text = obj["Body"].read().decode("utf-8")

        vectors = []
        for i, chunk in enumerate(chunk_text(text)):
            vector_id = f"{key.replace('/', '_')}_{i}"
            embedding = embed(chunk)
            vectors.append({
                "id": vector_id,
                "values": embedding,
                "metadata": {
                    "source_key": key,
                    "chunk_index": i,
                    "text": chunk[:500],  # Store preview for retrieval
                }
            })

        # Upsert in batches of 100
        for i in range(0, len(vectors), 100):
            index.upsert(vectors=vectors[i:i+100])

        logger.info(f"Upserted {len(vectors)} vectors for {key}")

    return {"statusCode": 200, "body": f"Processed {len(event['Records'])} documents"}
