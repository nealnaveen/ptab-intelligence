"""
PTAB Intelligence — PTAB Proceedings Fetcher
Calls USPTO Open Data Portal (ODP) PTAB API page by page, uploads each proceeding as JSON to S3.
Mirrors PtabLambda.java logic with S3 checkpointing instead of DynamoDB.

Requires ODP API key — sign up at https://data.uspto.gov/apis/getting-started
Set ODP_API_KEY in your .env file.

Usage:
    python scripts/fetch_proceedings.py              # fetch all
    python scripts/fetch_proceedings.py --reset      # start from 0
    python scripts/fetch_proceedings.py --limit 5    # fetch 5 pages (testing)
    python scripts/fetch_proceedings.py --query "proceedingTypeCategory:IPR"
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
API_URL         = f"{API_BASE}/api/v1/patent/trials/proceedings/search"
S3_PREFIX       = "proceedings"
CHECKPOINT_KEY  = "_checkpoints/proceedings.json"

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
        if data.get("query") == query:
            start = data.get("start_number", 0)
            print(f"  Resuming from record {start} (last run: {data.get('last_run', 'unknown')})")
            return start
        else:
            print("  Query changed — starting from 0")
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
    """Fetch one page from USPTO ODP PTAB Proceedings API (GET with offset/limit)."""
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

    return (
        data.get("patentTrialProceedingDataBag")
        or data.get("results")
        or data.get("proceedingDataBag")
        or data.get("trialProceedingBag")
        or []
    )


def _get(record: dict, *keys) -> str:
    """Safely extract a value from nested or flat dict, trying each key in order."""
    for key in keys:
        # Support dot-notation for nested keys like "trialMetaData.trialNumber"
        parts = key.split(".")
        val = record
        for part in parts:
            if isinstance(val, dict):
                val = val.get(part)
            else:
                val = None
                break
        if val is not None:
            return str(val)
    return "N/A"


def build_text(p: dict) -> str:
    """Human-readable text representation for RAG embedding.
    Supports both ODP v3 nested fields and legacy v2 flat fields.
    """
    return f"""PTAB Proceeding Record
Trial/Proceeding Number: {_get(p, 'trialNumber', 'proceedingNumber')}
Type: {_get(p, 'trialMetaData.trialTypeCode', 'proceedingTypeCategory')}
Sub-Type: {_get(p, 'trialMetaData.subTrialTypeCode', 'subproceedingTypeCategory')}
Status: {_get(p, 'trialMetaData.trialStatusCode', 'proceedingStatusCategory')}
Filing Date: {_get(p, 'trialMetaData.filingDate', 'proceedingFilingDate')}
Institution Date: {_get(p, 'trialMetaData.institutionDate', 'institutionDate')}
Decision Date: {_get(p, 'trialMetaData.disposalDate', 'decisionDate')}

Patent Owner:
  Party Name: {_get(p, 'patentOwnerData.patentOwnerName', 'respondentPartyName')}
  Application Number: {_get(p, 'patentOwnerData.applicationNumber', 'respondentApplicationNumberText')}
  Technology Center: {_get(p, 'patentOwnerData.technologyCenterNumber', 'respondentTechnologyCenterNumber')}
  Art Unit: {_get(p, 'patentOwnerData.groupArtUnitNumber', 'respondentGroupArtUnitNumber')}
  Inventor: {_get(p, 'patentOwnerData.inventorName', 'appellantInventorName')}

Petitioner:
  Party Name: {_get(p, 'petitionerData.petitionerName', 'appellantPartyName')}
  Counsel: {_get(p, 'respondentData.counselName', 'appellantCounselName')}
"""


def upload_record(record: dict, index: int):
    # Support both ODP v3 "trialNumber" and legacy "proceedingNumber"
    proceeding_number = (
        record.get("trialNumber")
        or record.get("proceedingNumber")
        or f"unknown_{index}"
    )
    key = f"{S3_PREFIX}/{proceeding_number}.json"

    enriched = {
        "doc_type": "proceeding",
        "source": "uspto_ptab_odp_v3",
        "proceeding_number": proceeding_number,
        "proceeding_type": _get(record, "trialMetaData.trialTypeCode", "proceedingTypeCategory"),
        "status": _get(record, "trialMetaData.trialStatusCode", "proceedingStatusCategory"),
        "filing_date": _get(record, "trialMetaData.filingDate", "proceedingFilingDate"),
        "decision_date": _get(record, "trialMetaData.disposalDate", "decisionDate"),
        "patent_owner": _get(record, "patentOwnerData.patentOwnerName", "respondentPartyName"),
        "petitioner": _get(record, "petitionerData.petitionerName", "appellantPartyName"),
        "technology_center": _get(record, "patentOwnerData.technologyCenterNumber", "respondentTechnologyCenterNumber"),
        "art_unit": _get(record, "patentOwnerData.groupArtUnitNumber", "respondentGroupArtUnitNumber"),
        "application_number": _get(record, "patentOwnerData.applicationNumber", "respondentApplicationNumberText"),
        "raw": record,
        "text": build_text(record),
    }

    s3.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=json.dumps(enriched, indent=2),
        ContentType="application/json",
        Metadata={
            "doc-type": "proceeding",
            "proceeding-type": str(
                record.get("trialMetaData", {}).get("trialTypeCode")
                or record.get("proceedingTypeCategory", "")
            ),
        }
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--query", type=str, default="", help="ODP query string (e.g. 'proceedingTypeCategory:IPR')")
    args = parser.parse_args()

    print("=== PTAB Intelligence — Proceedings Fetcher (ODP v3) ===")
    print(f"  Bucket  : {BUCKET}")
    print(f"  API     : {API_URL}")
    print(f"  Query   : {args.query or '(all)'}")
    print()

    start_number = 0 if args.reset else load_checkpoint(args.query)
    total_fetched = 0
    pages_fetched = 0

    while True:
        print(f"  Fetching records {start_number} – {start_number + PAGE_SIZE - 1}...")

        try:
            records = fetch_page(start_number, PAGE_SIZE, args.query)
        except Exception as e:
            print(f"  ERROR: {e} — saving checkpoint and exiting.")
            save_checkpoint(start_number, total_fetched, args.query)
            break

        if not records:
            print(f"\n  No more records. Done!")
            save_checkpoint(start_number, total_fetched, args.query)
            break

        for i, record in enumerate(records):
            try:
                upload_record(record, start_number + i)
            except Exception as e:
                print(f"    Warning: failed to upload record {i}: {e}")

        total_fetched += len(records)
        pages_fetched += 1
        start_number += PAGE_SIZE

        save_checkpoint(start_number, total_fetched, args.query)
        print(f"    ✓ {len(records)} records uploaded | total: {total_fetched} | checkpoint saved")

        if args.limit and pages_fetched >= args.limit:
            print(f"\n  Reached page limit ({args.limit}). Stopping.")
            break

        time.sleep(0.5)

    print(f"\n=== Complete: {total_fetched} proceedings uploaded to s3://{BUCKET}/{S3_PREFIX}/ ===")


if __name__ == "__main__":
    main()
