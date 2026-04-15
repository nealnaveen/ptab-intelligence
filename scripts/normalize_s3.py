"""
PTAB Intelligence — One-Time S3 Normalization Script
=====================================================
Reads every JSON record in S3, applies canonical terminology normalization
to key fields, and writes back only the records that changed.

Usage:
    # Dry run — preview changes without writing
    python scripts/normalize_s3.py --dry-run

    # Full run — normalize all records in S3
    python scripts/normalize_s3.py

    # Limit to one doc type
    python scripts/normalize_s3.py --type proceedings

    # Limit number of records (for testing)
    python scripts/normalize_s3.py --dry-run --limit 20
"""

import json
import os
import sys
import argparse
import boto3
import logging
from dotenv import load_dotenv

# Allow importing from src/schema even when running from repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.schema.terminology import normalize_status, normalize_proceeding_type, FIELD_ALIASES

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BUCKET  = os.environ.get("PTAB_DOCS_BUCKET", "ptab-documents-604881392797")
PROFILE = os.environ.get("AWS_PROFILE", "ptab")
REGION  = os.environ.get("AWS_REGION_NAME", "us-east-1")

DOC_TYPES = ["applications", "proceedings", "rejections"]

# Fields whose values should be normalized per doc type
NORMALIZE_CONFIG = {
    "applications": {
        "status": normalize_status,
    },
    "proceedings": {
        "status":          normalize_status,
        "proceeding_type": normalize_proceeding_type,
    },
    "rejections": {
        "status": normalize_status,
    },
}


def normalize_record(record: dict, doc_type: str) -> tuple[dict, list[str]]:
    """
    Apply normalization to a record's top-level fields.
    Returns (updated_record, list_of_changes).
    Changes are strings like "status: 'pend' → 'Pending'".
    """
    changes = []
    field_map = NORMALIZE_CONFIG.get(doc_type, {})

    for field, fn in field_map.items():
        raw_val = record.get(field)
        if raw_val is None:
            continue
        normalized = fn(str(raw_val))
        if normalized != str(raw_val):
            changes.append(f"{field}: '{raw_val}' → '{normalized}'")
            record[field] = normalized

    return record, changes


def process_prefix(s3, prefix: str, doc_type: str, dry_run: bool, limit: int) -> dict:
    stats = {"scanned": 0, "changed": 0, "written": 0, "errors": 0}
    paginator = s3.get_paginator("list_objects_v2")

    for page in paginator.paginate(Bucket=BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]

            # Skip non-data files
            if not key.endswith(".json"):
                continue
            if "_checkpoints" in key or "_insights" in key:
                continue
            if obj["Size"] == 0:
                continue

            if limit and stats["scanned"] >= limit:
                logger.info(f"  Reached --limit {limit}, stopping.")
                return stats

            stats["scanned"] += 1

            try:
                resp = s3.get_object(Bucket=BUCKET, Key=key)
                record = json.loads(resp["Body"].read())

                record, changes = normalize_record(record, doc_type)

                if changes:
                    stats["changed"] += 1
                    for c in changes:
                        logger.info(f"  [{key}] {c}")

                    if not dry_run:
                        s3.put_object(
                            Bucket=BUCKET,
                            Key=key,
                            Body=json.dumps(record, default=str),
                            ContentType="application/json",
                        )
                        stats["written"] += 1

            except Exception as e:
                logger.warning(f"  ERROR processing {key}: {e}")
                stats["errors"] += 1

    return stats


def main():
    parser = argparse.ArgumentParser(description="Normalize S3 PTAB records in place")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    parser.add_argument("--type", choices=DOC_TYPES, help="Only process this doc type")
    parser.add_argument("--limit", type=int, default=0, help="Max records per doc type (0 = no limit)")
    args = parser.parse_args()

    if args.dry_run:
        logger.info("=== DRY RUN — no S3 writes will occur ===")

    session = boto3.Session(profile_name=PROFILE, region_name=REGION)
    s3 = session.client("s3")

    types_to_process = [args.type] if args.type else DOC_TYPES
    totals = {"scanned": 0, "changed": 0, "written": 0, "errors": 0}

    for doc_type in types_to_process:
        logger.info(f"\n── Processing {doc_type}/ ──────────────────────────────────")
        stats = process_prefix(s3, f"{doc_type}/", doc_type, args.dry_run, args.limit)
        for k, v in stats.items():
            totals[k] += v
        logger.info(
            f"  {doc_type}: scanned={stats['scanned']} "
            f"changed={stats['changed']} "
            f"written={stats['written']} "
            f"errors={stats['errors']}"
        )

    logger.info(
        f"\n── TOTAL: scanned={totals['scanned']} "
        f"changed={totals['changed']} "
        f"written={totals['written']} "
        f"errors={totals['errors']}"
    )

    if args.dry_run and totals["changed"] > 0:
        logger.info("\nRun without --dry-run to apply these changes.")


if __name__ == "__main__":
    main()
