"""
PTAB Intelligence — Pinecone Backfill Script
Reads all existing S3 documents and upserts embeddings into Pinecone.
Mirrors ingestion/handler.py logic — run this once after bulk S3 upload.

Usage:
    python scripts/backfill_pinecone.py                     # all doc types
    python scripts/backfill_pinecone.py --type rejections   # one type only
    python scripts/backfill_pinecone.py --limit 100         # test with 100 docs
    python scripts/backfill_pinecone.py --reset             # ignore checkpoint
"""

import argparse
import json
import os
import time
import boto3
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
BUCKET           = os.environ.get("PTAB_DOCS_BUCKET", "ptab-documents-604881392797")
AWS_PROFILE      = os.environ.get("AWS_PROFILE", "ptab")
AWS_REGION       = os.environ.get("AWS_REGION", "us-east-1")
PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY", "")
PINECONE_INDEX   = os.environ.get("PINECONE_INDEX_NAME", "ptab-documents")
CHUNK_SIZE       = 512
CHUNK_OVERLAP    = 64
UPSERT_BATCH     = 100
DOC_TYPES        = ["applications", "proceedings", "rejections"]
CHECKPOINT_KEY   = "_checkpoints/backfill.json"

session  = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
s3       = session.client("s3")
bedrock  = session.client("bedrock-runtime", region_name=AWS_REGION)


# ── Helpers ───────────────────────────────────────────────────────────────────

def chunk_text(text: str):
    words = text.split()
    for i in range(0, len(words), CHUNK_SIZE - CHUNK_OVERLAP):
        chunk = " ".join(words[i : i + CHUNK_SIZE])
        if chunk:
            yield chunk


def embed(text: str) -> list:
    resp = bedrock.invoke_model(
        modelId="amazon.titan-embed-text-v1",
        body=json.dumps({"inputText": text[:8000]}),  # Titan max input
        contentType="application/json",
        accept="application/json",
    )
    return json.loads(resp["body"].read())["embedding"]


def load_checkpoint() -> dict:
    try:
        obj = s3.get_object(Bucket=BUCKET, Key=CHECKPOINT_KEY)
        return json.loads(obj["Body"].read())
    except Exception:
        return {}


def save_checkpoint(data: dict):
    s3.put_object(
        Bucket=BUCKET,
        Key=CHECKPOINT_KEY,
        Body=json.dumps(data, indent=2),
        ContentType="application/json",
    )


def list_keys(prefix: str, continuation_token: str | None = None):
    """Yield all S3 keys under prefix, excluding checkpoints."""
    kwargs = {"Bucket": BUCKET, "Prefix": prefix}
    if continuation_token:
        kwargs["ContinuationToken"] = continuation_token

    while True:
        resp = s3.list_objects_v2(**kwargs)
        for obj in resp.get("Contents", []):
            key = obj["Key"]
            if "_checkpoints" not in key and key.endswith(".json") and obj["Size"] > 0:
                yield key
        if not resp.get("IsTruncated"):
            break
        kwargs["ContinuationToken"] = resp["NextContinuationToken"]


def process_doc_type(doc_type: str, index, checkpoint: dict, limit: int, reset: bool) -> int:
    prefix = f"{doc_type}/"
    processed_keys = set() if reset else set(checkpoint.get(doc_type, {}).get("processed_keys", []))
    total = 0

    print(f"\n  [{doc_type}] Starting — {len(processed_keys)} already done")

    for key in list_keys(prefix):
        if key in processed_keys:
            continue
        if limit and total >= limit:
            print(f"  [{doc_type}] Reached limit ({limit}). Stopping.")
            break

        try:
            # Read S3 object
            obj = s3.get_object(Bucket=BUCKET, Key=key)
            data = json.loads(obj["Body"].read())

            # Use the pre-built text field from the enriched record
            text = data.get("text") or json.dumps({k: v for k, v in data.items() if k != "raw"})

            # Build vectors
            vectors = []
            for i, chunk in enumerate(chunk_text(text)):
                vector_id = f"{key.replace('/', '_').replace('.', '_')}_{i}"
                try:
                    embedding = embed(chunk)
                except Exception as e:
                    print(f"    Warning: embed failed for chunk {i} of {key}: {e}")
                    continue

                vectors.append({
                    "id": vector_id,
                    "values": embedding,
                    "metadata": {
                        "source_key": key,
                        "doc_type": doc_type,
                        "chunk_index": i,
                        "text": chunk[:500],
                        # Top-level fields for filtering
                        "application_number": str(data.get("application_number") or data.get("proceeding_number") or ""),
                        "art_unit": str(data.get("art_unit") or ""),
                        "status": str(data.get("status") or ""),
                    }
                })

            # Upsert in batches
            for batch_start in range(0, len(vectors), UPSERT_BATCH):
                batch = vectors[batch_start : batch_start + UPSERT_BATCH]
                index.upsert(vectors=batch)

            processed_keys.add(key)
            total += 1

            if total % 10 == 0:
                # Save checkpoint every 10 docs
                checkpoint[doc_type] = {
                    "processed_keys": list(processed_keys),
                    "total": total,
                    "last_run": datetime.now(timezone.utc).isoformat(),
                }
                save_checkpoint(checkpoint)
                print(f"    ✓ {total} docs embedded | checkpoint saved")

            time.sleep(0.1)  # Bedrock rate limiting

        except Exception as e:
            print(f"    Warning: failed to process {key}: {e}")

    # Final checkpoint
    checkpoint[doc_type] = {
        "processed_keys": list(processed_keys),
        "total": total,
        "last_run": datetime.now(timezone.utc).isoformat(),
    }
    save_checkpoint(checkpoint)
    print(f"  [{doc_type}] Done — {total} new docs embedded")
    return total


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--type",  choices=DOC_TYPES, default=None, help="Process one doc type only")
    parser.add_argument("--limit", type=int, default=0, help="Max docs per type (0 = all)")
    parser.add_argument("--reset", action="store_true", help="Ignore checkpoint and reprocess everything")
    args = parser.parse_args()

    if not PINECONE_API_KEY:
        raise SystemExit("ERROR: PINECONE_API_KEY not set in .env")

    from pinecone import Pinecone
    pc    = Pinecone(api_key=PINECONE_API_KEY)
    index = pc.Index(PINECONE_INDEX)

    stats = index.describe_index_stats()
    print(f"=== PTAB Intelligence — Pinecone Backfill ===")
    print(f"  Index   : {PINECONE_INDEX}")
    print(f"  Vectors : {stats.total_vector_count:,} already in Pinecone")
    print(f"  Bucket  : {BUCKET}")
    print()

    checkpoint = {} if args.reset else load_checkpoint()
    types_to_run = [args.type] if args.type else DOC_TYPES
    grand_total  = 0

    for doc_type in types_to_run:
        grand_total += process_doc_type(doc_type, index, checkpoint, args.limit, args.reset)

    print(f"\n=== Complete: {grand_total} documents embedded into Pinecone ===")


if __name__ == "__main__":
    main()
