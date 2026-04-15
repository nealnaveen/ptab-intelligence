"""Quick debug — prints the raw field structure of one S3 record per doc type."""
import json, os, boto3
from dotenv import load_dotenv
load_dotenv()

BUCKET = os.environ.get("PTAB_DOCS_BUCKET", "ptab-documents-604881392797")
session = boto3.Session(profile_name=os.environ.get("AWS_PROFILE","ptab"), region_name="us-east-1")
s3 = session.client("s3")

for prefix in ["applications/", "proceedings/", "rejections/"]:
    resp = s3.list_objects_v2(Bucket=BUCKET, Prefix=prefix, MaxKeys=1)
    for obj in resp.get("Contents", []):
        key = obj["Key"]
        data = json.loads(s3.get_object(Bucket=BUCKET, Key=key)["Body"].read())
        raw  = data.get("raw", {})
        print(f"\n=== {prefix} — top-level enriched keys ===")
        print(list(data.keys()))
        print(f"\n=== raw record keys ===")
        print(list(raw.keys()))
        print(f"\n=== sample raw values ===")
        for k, v in list(raw.items())[:20]:
            print(f"  {k}: {str(v)[:80]}")
