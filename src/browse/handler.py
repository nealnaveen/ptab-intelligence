"""
PTAB Intelligence — Browse Lambda
GET /browse/{docType}?limit=25&token=<continuation>

Reads paginated records from S3 and returns enriched, normalized JSON.
docType: applications | proceedings | rejections
"""

import json
import os
import boto3
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

BUCKET = os.environ["S3_BUCKET"]
_REGION = os.environ.get("AWS_REGION_NAME", os.environ.get("AWS_REGION", "us-east-1"))

s3 = boto3.client("s3", region_name=_REGION)

VALID_TYPES = {"applications", "proceedings", "rejections"}

# ── Inline normalization maps ─────────────────────────────────────────────────
# Kept inline (not imported from src/schema) so this Lambda stays a single-file
# ZIP deployment with no external dependencies.

_STATUS_MAP = {
    "pend":                          "Pending",
    "pending":                       "Pending",
    "patented case":                 "Patented",
    "issued":                        "Patented",
    "patent issued":                 "Patented",
    "allowed":                       "Allowed",
    "allowance":                     "Allowed",
    "notice of allowance":           "Allowed",
    "abandoned":                     "Abandoned",
    "abandon":                       "Abandoned",
    "applicant abandoned":           "Abandoned",
    "failure to respond":            "Abandoned",
    "expired":                       "Expired",
    "withdrawn":                     "Withdrawn",
    "fwd":                           "Final Written Decision",
    "final written decision issued": "Final Written Decision",
    "terminated-settlement":         "Settled",
    "settled":                       "Settled",
    "terminated":                    "Terminated",
    "instituted":                    "Instituted",
    "institution granted":           "Instituted",
    "denied":                        "Petition Denied",
    "not instituted":                "Petition Denied",
    "joinder":                       "Joinder",
}

_PROCEEDING_TYPE_MAP = {
    "ipr":                     "IPR",
    "inter partes review":     "IPR",
    "inter-partes review":     "IPR",
    "pgr":                     "PGR",
    "post grant review":       "PGR",
    "post-grant review":       "PGR",
    "cbm":                     "CBM",
    "covered business method": "CBM",
    "derivation":              "Derivation",
    "der":                     "Derivation",
}


def _norm_status(val) -> str:
    if not val:
        return val
    return _STATUS_MAP.get(str(val).lower().strip(), str(val))


def _norm_type(val) -> str:
    if not val:
        return val
    return _PROCEEDING_TYPE_MAP.get(str(val).lower().strip(), str(val).upper())


# ── Field extraction + normalization ──────────────────────────────────────────

def enrich(record: dict, doc_type: str) -> dict:
    """Extract display fields from raw ODP sub-object and normalize values."""
    raw = record.get("raw") or {}

    if doc_type == "applications":
        meta = raw.get("applicationMetaData") or {}

        record["filing_date"] = (
            meta.get("filingDate")
            or meta.get("applicationFilingDate")
            or record.get("filing_date")
        )
        record["invention_title"] = (
            meta.get("inventionTitle")
            or meta.get("inventionTitleText")
            or meta.get("applicationTitle")
            or record.get("invention_title")
        )
        # Normalize status to clean display string
        raw_status = (
            meta.get("applicationStatusDescriptionText")
            or meta.get("applicationStatusCategoryText")
            or meta.get("applicationStatusCode")
            or record.get("status")
        )
        record["status"] = _norm_status(raw_status)

        record["art_unit"] = meta.get("groupArtUnitNumber") or record.get("art_unit")
        record["technology_center"] = meta.get("technologyCenterNumber") or record.get("technology_center")

        assignments = raw.get("assignmentBag") or []
        if assignments:
            a = assignments[0]
            record["applicant"] = (
                a.get("assigneeName")
                or a.get("assigneeEntityName")
                or a.get("assigneeNameText")
                or record.get("applicant")
            )

    elif doc_type == "proceedings":
        trial   = raw.get("trialMetaData") or {}
        owner   = raw.get("patentOwnerData") or {}
        pet_raw = raw.get("regularPetitionerData") or {}
        pet     = pet_raw[0] if isinstance(pet_raw, list) and pet_raw else (pet_raw if isinstance(pet_raw, dict) else {})

        record["filing_date"]   = trial.get("accordedFilingDate") or trial.get("filingDate") or record.get("filing_date")
        record["decision_date"] = trial.get("terminationDate") or trial.get("finalWrittenDecisionDate") or record.get("decision_date")

        # Normalize proceeding type and status
        record["proceeding_type"] = _norm_type(trial.get("trialTypeCode") or record.get("proceeding_type"))
        record["status"]          = _norm_status(trial.get("trialStatusCode") or trial.get("proceedingStatus") or record.get("status"))

        record["patent_owner"] = owner.get("patentOwnerName") or record.get("patent_owner")
        record["petitioner"]   = (
            pet.get("realPartyInInterestName")
            or pet.get("petitionerName")
            or record.get("petitioner")
        )

    elif doc_type == "rejections":
        # ODP stores hasRej* as integers 0/1 — convert to proper booleans
        for field in ["has_rej_101", "has_rej_102", "has_rej_103", "has_rej_112"]:
            val = record.get(field)
            if val is not None:
                record[field] = bool(int(val))
        # Normalize status if present
        if record.get("status"):
            record["status"] = _norm_status(record["status"])

    return record


# ── Handler ───────────────────────────────────────────────────────────────────

def handler(event, context):
    try:
        path_params = event.get("pathParameters") or {}
        doc_type = path_params.get("docType", "applications").lower()

        if doc_type not in VALID_TYPES:
            return _resp(400, {"error": f"Invalid docType '{doc_type}'. Must be one of: {', '.join(VALID_TYPES)}"})

        query_params = event.get("queryStringParameters") or {}
        limit = min(int(query_params.get("limit", "25")), 100)
        token = query_params.get("token")

        prefix = f"{doc_type}/"
        list_kwargs = {
            "Bucket": BUCKET,
            "Prefix": prefix,
            "MaxKeys": limit,
        }
        if token:
            list_kwargs["ContinuationToken"] = token

        list_resp = s3.list_objects_v2(**list_kwargs)
        contents  = list_resp.get("Contents", [])

        keys = [
            obj["Key"] for obj in contents
            if obj["Key"].endswith(".json")
            and obj["Size"] > 0
            and "_checkpoints" not in obj["Key"]
            and "_insights" not in obj["Key"]
        ]

        records = []
        for key in keys:
            try:
                obj  = s3.get_object(Bucket=BUCKET, Key=key)
                data = json.loads(obj["Body"].read())
                data = enrich(data, doc_type)
                record = {k: v for k, v in data.items() if k not in ("raw", "text")}
                record["_key"] = key
                records.append(record)
            except Exception as e:
                logger.warning(f"Failed to read {key}: {e}")

        next_token = list_resp.get("NextContinuationToken")
        logger.info(f"Browse {doc_type}: returned {len(records)} records")

        return _resp(200, {
            "doc_type":   doc_type,
            "records":    records,
            "count":      len(records),
            "next_token": next_token,
            "has_more":   bool(next_token),
        })

    except Exception as e:
        logger.error(f"Error: {e}")
        return _resp(500, {"error": "Internal server error"})


def _resp(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body, default=str),
    }
