"""
PTAB Intelligence — Browse Lambda
GET /browse/{docType}?limit=25&token=<continuation>

Reads paginated records from S3 and returns enriched JSON (without raw field).
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


def enrich(record: dict, doc_type: str) -> dict:
    """Extract display fields from raw sub-object using actual ODP field paths."""
    raw = record.get("raw") or {}

    if doc_type == "applications":
        meta = raw.get("applicationMetaData") or {}
        # Filing date
        record["filing_date"] = (
            meta.get("filingDate")
            or meta.get("applicationFilingDate")
            or record.get("filing_date")
        )
        # Title
        record["invention_title"] = (
            meta.get("inventionTitle")
            or meta.get("inventionTitleText")
            or meta.get("applicationTitle")
            or record.get("invention_title")
        )
        # Status — prefer description text over code number
        record["status"] = (
            meta.get("applicationStatusDescriptionText")
            or meta.get("applicationStatusCategoryText")
            or meta.get("applicationStatusCode")
            or record.get("status")
        )
        # Art unit / tech center
        record["art_unit"] = meta.get("groupArtUnitNumber") or record.get("art_unit")
        record["technology_center"] = meta.get("technologyCenterNumber") or record.get("technology_center")
        # Applicant — try assignment bag first
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
        trial  = raw.get("trialMetaData") or {}
        owner  = raw.get("patentOwnerData") or {}
        # regularPetitionerData can be a dict or a list
        pet_raw = raw.get("regularPetitionerData") or {}
        if isinstance(pet_raw, list):
            pet = pet_raw[0] if pet_raw else {}
        else:
            pet = pet_raw

        record["filing_date"]     = trial.get("accordedFilingDate") or trial.get("filingDate") or record.get("filing_date")
        record["decision_date"]   = trial.get("terminationDate") or trial.get("finalWrittenDecisionDate") or record.get("decision_date")
        record["proceeding_type"] = trial.get("trialTypeCode") or record.get("proceeding_type")
        record["status"]          = trial.get("trialStatusCode") or trial.get("proceedingStatus") or record.get("status")
        record["patent_owner"]    = owner.get("patentOwnerName") or record.get("patent_owner")
        record["petitioner"]      = (
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

    return record


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
        contents = list_resp.get("Contents", [])

        keys = [
            obj["Key"] for obj in contents
            if obj["Key"].endswith(".json") and obj["Size"] > 0 and "_checkpoints" not in obj["Key"]
        ]

        records = []
        for key in keys:
            try:
                obj = s3.get_object(Bucket=BUCKET, Key=key)
                data = json.loads(obj["Body"].read())

                # Enrich with correct field paths from raw
                data = enrich(data, doc_type)

                # Strip raw and text before returning (too large)
                record = {k: v for k, v in data.items() if k not in ("raw", "text")}
                record["_key"] = key
                records.append(record)
            except Exception as e:
                logger.warning(f"Failed to read {key}: {e}")

        next_token = list_resp.get("NextContinuationToken")

        logger.info(f"Browse {doc_type}: returned {len(records)} records")

        return _resp(200, {
            "doc_type": doc_type,
            "records": records,
            "count": len(records),
            "next_token": next_token,
            "has_more": bool(next_token),
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
