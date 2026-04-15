"""
PTAB Intelligence — Patent Applications Fetcher
Calls USPTO Open Data Portal (ODP) Patent File Wrapper API page by page.
Uploads each application as JSON to S3 with S3 checkpointing.

Requires ODP API key — sign up at https://data.uspto.gov/apis/getting-started
Set ODP_API_KEY in your .env file.

Usage:
    python scripts/fetch_applications.py              # fetch all
    python scripts/fetch_applications.py --reset      # start from 0
    python scripts/fetch_applications.py --limit 5    # fetch 5 pages (testing)
    python scripts/fetch_applications.py --query "groupArtUnitNumber:3600"  # filter
"""

import argparse
import json
import os
import time
import urllib.parse
import urllib.request
import boto3
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
BUCKET          = os.environ.get("PTAB_DOCS_BUCKET", "ptab-documents-604881392797")
AWS_PROFILE     = os.environ.get("AWS_PROFILE", "ptab")
AWS_REGION      = os.environ.get("AWS_REGION", "us-east-1")
ODP_API_KEY     = os.environ.get("ODP_API_KEY", "")
PAGE_SIZE       = 25   # ODP default; max varies — start conservative
API_BASE        = "https://api.uspto.gov"
API_URL         = f"{API_BASE}/api/v1/patent/applications/search"
S3_PREFIX       = "applications"
CHECKPOINT_KEY  = "_checkpoints/applications.json"

session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
s3 = session.client("s3")

if not ODP_API_KEY:
    raise SystemExit(
        "ERROR: ODP_API_KEY is not set.\n"
        "Sign up at https://data.uspto.gov/apis/getting-started and add ODP_API_KEY to your .env"
    )


def load_checkpoint(query: str) -> int:
    try:
        obj = s3.get_object(Bucket=BUCKET, Key=CHECKPOINT_KEY)
        data = json.loads(obj["Body"].read())
        # Only resume if same query
        if data.get("query") == query:
            start = data.get("start_number", 0)
            print(f"  Resuming from record {start} (last run: {data.get('last_run', 'unknown')})")
            return start
        else:
            print(f"  Query changed — starting from 0")
            return 0
    except Exception:
        print("  No checkpoint found — starting from record 0")
        return 0


def save_checkpoint(start_number: int, total_fetched: int, query: str):
    data = {
        "start_number": start_number,
        "total_fetched": total_fetched,
        "query": query,
        "last_run": datetime.now(timezone.utc).isoformat(),
    }
    s3.put_object(
        Bucket=BUCKET,
        Key=CHECKPOINT_KEY,
        Body=json.dumps(data, indent=2),
        ContentType="application/json",
    )


def fetch_page(offset: int, limit: int, query: str) -> list:
    """Fetch one page from USPTO ODP Patent Applications API (GET with offset/limit)."""
    params = {"offset": str(offset), "limit": str(limit)}
    if query and query != "*:*":
        params["q"] = query
    url = f"{API_URL}?{urllib.parse.urlencode(params)}"

    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "X-API-KEY": ODP_API_KEY,
        }
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())

    # ODP returns {"results": [...]} or {"patentFileWrapperDataBag": [...]}
    return (
        data.get("results")
        or data.get("patentFileWrapperDataBag")
        or data.get("applicationDataBag")
        or []
    )


def _get(record: dict, *keys) -> str:
    """Safely extract a value from nested or flat dict, trying each key in order."""
    for key in keys:
        parts = key.split(".")
        val = record
        for part in parts:
            if isinstance(val, dict):
                val = val.get(part)
            else:
                val = None
                break
        if val is not None:
            if isinstance(val, list):
                return ", ".join(str(v) for v in val)
            return str(val)
    return "N/A"


def build_text(app: dict) -> str:
    """Human-readable text for RAG embedding.
    Supports ODP v3 nested fields and legacy flat fields.
    """
    return f"""USPTO Patent Application
Application Number: {_get(app, 'applicationNumberText', 'patentApplicationNumber')}
Filing Date: {_get(app, 'filingDate')}
Application Type: {_get(app, 'applicationTypeCode', 'applicationTypeCategory')}
Status: {_get(app, 'applicationStatusCode', 'applicationStatusCategory')}
Status Date: {_get(app, 'applicationStatusDate')}

Invention Title: {_get(app, 'inventionTitle')}

Inventors: {_get(app, 'inventorData.inventorName', 'inventorNameArrayText')}
Applicant: {_get(app, 'applicantData.applicantName', 'applicantNameText')}
Assignee: {_get(app, 'assigneeData.assigneeName', 'assigneeNameText')}

Classification:
  Group Art Unit: {_get(app, 'groupArtUnitNumber')}
  Technology Center: {_get(app, 'technologyCenterNumber')}
  CPC Class: {_get(app, 'cpcSectionCode')}

Examination:
  Examiner: {_get(app, 'primaryExaminerData.examinerName', 'primaryExaminerName')}
  Entity Type: {_get(app, 'entityStatusCode', 'smallEntityStatusCategory')}
"""


def upload_record(record: dict, index: int):
    app_number = (
        record.get("applicationNumberText")
        or record.get("patentApplicationNumber")
        or f"unknown_{index}"
    )
    safe_id = app_number.replace("/", "_").replace(" ", "_")
    key = f"{S3_PREFIX}/{safe_id}.json"

    enriched = {
        "doc_type": "application",
        "source": "uspto_peds_odp_v1",
        "application_number": app_number,
        "filing_date": _get(record, "filingDate"),
        "invention_title": _get(record, "inventionTitle"),
        "status": _get(record, "applicationStatusCode", "applicationStatusCategory"),
        "art_unit": _get(record, "groupArtUnitNumber"),
        "technology_center": _get(record, "technologyCenterNumber"),
        "applicant": _get(record, "applicantData.applicantName", "applicantNameText"),
        "assignee": _get(record, "assigneeData.assigneeName", "assigneeNameText"),
        "raw": record,
        "text": build_text(record),
    }

    s3.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=json.dumps(enriched, indent=2),
        ContentType="application/json",
        Metadata={
            "doc-type": "application",
            "art-unit": str(_get(record, "groupArtUnitNumber")),
        }
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--query", type=str, default="", help="ODP query (e.g. 'groupArtUnitNumber:3600')")
    args = parser.parse_args()

    print("=== PTAB Intelligence — Applications Fetcher (ODP v1) ===")
    print(f"  Bucket  : {BUCKET}")
    print(f"  API     : {API_URL}")
    print(f"  Query   : {args.query or '(all)'}")
    print()

    offset = 0 if args.reset else load_checkpoint(args.query)
    total_fetched = 0
    pages_fetched = 0

    while True:
        print(f"  Fetching records {offset} – {offset + PAGE_SIZE - 1}...")

        try:
            records = fetch_page(offset, PAGE_SIZE, args.query)
        except Exception as e:
            print(f"  ERROR: {e} — saving checkpoint and exiting.")
            save_checkpoint(offset, total_fetched, args.query)
            break

        if not records:
            print(f"\n  No more records. Done!")
            save_checkpoint(offset, total_fetched, args.query)
            break

        for i, record in enumerate(records):
            try:
                upload_record(record, offset + i)
            except Exception as e:
                print(f"    Warning: failed to upload record {i}: {e}")

        total_fetched += len(records)
        pages_fetched += 1
        offset += PAGE_SIZE

        save_checkpoint(offset, total_fetched, args.query)
        print(f"    ✓ {len(records)} records uploaded | total: {total_fetched} | checkpoint saved")

        if args.limit and pages_fetched >= args.limit:
            print(f"\n  Reached page limit ({args.limit}). Stopping.")
            break

        time.sleep(0.5)

    print(f"\n=== Complete: {total_fetched} applications uploaded to s3://{BUCKET}/{S3_PREFIX}/ ===")


if __name__ == "__main__":
    main()
