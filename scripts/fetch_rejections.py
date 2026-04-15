"""
PTAB Intelligence — Rejection Fetcher
Calls USPTO Open Data Portal (ODP) OA Rejections API page by page, uploads each record as JSON to S3.
Checkpoints after every page so it can resume from where it left off.

Requires ODP API key — sign up at https://data.uspto.gov/apis/getting-started
Set ODP_API_KEY in your .env file.

Usage:
    python scripts/fetch_rejections.py              # fetch all
    python scripts/fetch_rejections.py --reset      # start from page 0
    python scripts/fetch_rejections.py --limit 5    # fetch 5 pages only (for testing)
"""

import argparse
import json
import os
import time
import urllib.parse
import urllib.request
import gzip
import boto3
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
BUCKET          = os.environ.get("PTAB_DOCS_BUCKET", "ptab-documents-604881392797")
AWS_PROFILE     = os.environ.get("AWS_PROFILE", "ptab")
AWS_REGION      = os.environ.get("AWS_REGION", "us-east-1")
ODP_API_KEY     = os.environ.get("ODP_API_KEY", "")
PAGE_SIZE       = 100          # records per page (max USPTO allows)
API_BASE        = "https://api.uspto.gov"
API_URL         = f"{API_BASE}/api/v1/patent/oa/oa_rejections/v2/records"
S3_PREFIX       = "rejections"
CHECKPOINT_KEY  = "_checkpoints/rejections.json"

# ── AWS clients ───────────────────────────────────────────────────────────────
session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
s3 = session.client("s3")

if not ODP_API_KEY:
    raise SystemExit(
        "ERROR: ODP_API_KEY is not set.\n"
        "Sign up at https://data.uspto.gov/apis/getting-started and add ODP_API_KEY to your .env"
    )


def load_checkpoint() -> int:
    """Load start_number from S3 checkpoint. Returns 0 if none exists."""
    try:
        obj = s3.get_object(Bucket=BUCKET, Key=CHECKPOINT_KEY)
        data = json.loads(obj["Body"].read())
        start = data.get("start_number", 0)
        print(f"  Resuming from record {start} (last run: {data.get('last_run', 'unknown')})")
        return start
    except s3.exceptions.NoSuchKey:
        print("  No checkpoint found — starting from record 0")
        return 0
    except Exception as e:
        print(f"  Warning: could not read checkpoint ({e}) — starting from 0")
        return 0


def save_checkpoint(start_number: int, total_fetched: int):
    """Save current position to S3 checkpoint."""
    data = {
        "start_number": start_number,
        "total_fetched": total_fetched,
        "last_run": datetime.now(timezone.utc).isoformat(),
    }
    s3.put_object(
        Bucket=BUCKET,
        Key=CHECKPOINT_KEY,
        Body=json.dumps(data, indent=2),
        ContentType="application/json",
    )


def fetch_page(start: int, rows: int) -> list:
    """Fetch one page from the USPTO ODP OA Rejections API (POST with form data)."""
    form_data = urllib.parse.urlencode({
        "criteria": "*:*",
        "start": str(start),
        "rows": str(rows),
    }).encode()

    req = urllib.request.Request(
        API_URL,
        data=form_data,
        method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "Accept-Encoding": "gzip, deflate",
            "X-API-KEY": ODP_API_KEY,
        },
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
        if resp.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
        data = json.loads(raw)

    return data.get("response", {}).get("docs", [])


def upload_record(record: dict, index: int):
    """Upload a single rejection record as JSON to S3."""
    record_id = record.get("id", f"unknown_{index}")
    key = f"{S3_PREFIX}/{record_id}.json"

    # Add metadata for RAG ingestion
    enriched = {
        "doc_type": "rejection",
        "source": "uspto_oa_rejections",
        "record_id": record_id,
        "proceeding_number": record.get("patentApplicationNumber"),
        "art_unit": record.get("groupArtUnitNumber"),
        "submission_date": record.get("submissionDate"),
        "has_rej_101": record.get("hasRej101"),
        "has_rej_102": record.get("hasRej102"),
        "has_rej_103": record.get("hasRej103"),
        "has_rej_112": record.get("hasRej112"),
        "action_type": record.get("actionTypeCategory"),
        "legal_section": record.get("legalSectionCode"),
        # Full raw record for completeness
        "raw": record,
        # Text representation for RAG chunking
        "text": build_text(record),
    }

    s3.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=json.dumps(enriched, indent=2),
        ContentType="application/json",
        Metadata={
            "doc-type": "rejection",
            "art-unit": str(record.get("groupArtUnitNumber", "")),
        }
    )


def build_text(record: dict) -> str:
    """Build a human-readable text representation for embedding."""
    rejections = []
    if record.get("hasRej101"): rejections.append("35 USC 101 (subject matter eligibility)")
    if record.get("hasRej102"): rejections.append("35 USC 102 (anticipation)")
    if record.get("hasRej103"): rejections.append("35 USC 103 (obviousness)")
    if record.get("hasRej112"): rejections.append("35 USC 112 (written description/enablement)")

    return f"""USPTO Office Action Rejection Record
Application Number: {record.get('patentApplicationNumber', 'N/A')}
Art Unit: {record.get('groupArtUnitNumber', 'N/A')}
Submission Date: {record.get('submissionDate', 'N/A')}
Action Type: {record.get('actionTypeCategory', 'N/A')}
Legal Section Code: {record.get('legalSectionCode', 'N/A')}
National Class: {record.get('nationalClass', 'N/A')}

Rejection Grounds:
{chr(10).join(f'- {r}' for r in rejections) if rejections else '- None recorded'}

Form Issues:
- Header missing: {record.get('headerMissing', False)}
- Form paragraph missing: {record.get('formParagraphMissing', False)}
- Closing missing: {record.get('closingMissing', False)}

Prior Art Citations:
- 102 citations > 1: {record.get('cite102GT1', False)}
- 103 citations > 3: {record.get('cite103GT3', False)}
- 103 citations = 1: {record.get('cite103EQ1', False)}
- Max 103 citations: {record.get('cite103Max', 0)}
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="Reset checkpoint and start from 0")
    parser.add_argument("--limit", type=int, default=0, help="Stop after N pages (0 = unlimited)")
    args = parser.parse_args()

    print("=== PTAB Intelligence — Rejection Fetcher (ODP v2) ===")
    print(f"  Bucket  : {BUCKET}")
    print(f"  API     : {API_URL}")
    print(f"  Page sz : {PAGE_SIZE}")
    print()

    start_number = 0 if args.reset else load_checkpoint()
    total_fetched = 0
    pages_fetched = 0

    while True:
        print(f"  Fetching records {start_number} – {start_number + PAGE_SIZE - 1}...")

        try:
            records = fetch_page(start_number, PAGE_SIZE)
        except Exception as e:
            print(f"  ERROR fetching page: {e}")
            print("  Saving checkpoint and exiting — safe to retry.")
            save_checkpoint(start_number, total_fetched)
            break

        if not records:
            print(f"\n  No more records. Done!")
            save_checkpoint(start_number, total_fetched)
            break

        # Upload each record to S3
        for i, record in enumerate(records):
            try:
                upload_record(record, start_number + i)
            except Exception as e:
                print(f"    Warning: failed to upload record {i}: {e}")

        total_fetched += len(records)
        pages_fetched += 1
        start_number += PAGE_SIZE

        # Save checkpoint after every page
        save_checkpoint(start_number, total_fetched)
        print(f"    ✓ {len(records)} records uploaded | total: {total_fetched} | checkpoint saved")

        if args.limit and pages_fetched >= args.limit:
            print(f"\n  Reached page limit ({args.limit}). Stopping.")
            break

        # Be polite to the USPTO API
        time.sleep(0.5)

    print(f"\n=== Complete: {total_fetched} rejection records uploaded to s3://{BUCKET}/{S3_PREFIX}/ ===")


if __name__ == "__main__":
    main()
