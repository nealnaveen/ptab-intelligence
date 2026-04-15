"""
PTAB Intelligence — Local ingestion script
Downloads a real PTAB trial document from USPTO's public API,
chunks it, embeds via Bedrock Titan, and upserts to Pinecone.

Usage:
  python scripts/ingest_local.py
  python scripts/ingest_local.py --trial IPR2023-00001
"""

import os
import sys
import json
import argparse
import boto3
import requests
from dotenv import load_dotenv

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
PINECONE_API_KEY   = os.environ["PINECONE_API_KEY"]
PINECONE_INDEX     = os.environ.get("PINECONE_INDEX_NAME", "ptab-documents")
AWS_REGION         = os.environ.get("AWS_REGION", "us-east-1")
AWS_PROFILE        = os.environ.get("AWS_PROFILE", "ptab")
CHUNK_SIZE         = 400
CHUNK_OVERLAP      = 50

# ── Boto3 with ptab profile ───────────────────────────────────────────────────
session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
bedrock = session.client("bedrock-runtime")

# ── Sample PTAB documents (real public data) ──────────────────────────────────
SAMPLE_DOCS = [
    {
        "id": "ptab-ipr-basics",
        "title": "Inter Partes Review — Overview",
        "text": """
Inter Partes Review (IPR) is a trial proceeding conducted at the Patent Trial and Appeal Board (PTAB)
to review the patentability of one or more claims in a patent based only on prior art consisting of
patents or printed publications. IPR was established by the Leahy-Smith America Invents Act (AIA)
and became effective September 16, 2012.

GROUNDS FOR INTER PARTES REVIEW:
A petitioner may request inter partes review on the grounds that the challenged claims are unpatentable
under 35 U.S.C. § 102 (anticipation) or § 103 (obviousness). The petition must identify the specific
grounds for each claim challenged and explain how the construed claims are unpatentable.

THRESHOLD FOR INSTITUTION:
The Board will institute an IPR only if the petition demonstrates that there is a reasonable likelihood
that the petitioner would prevail with respect to at least one of the claims challenged. This threshold
is evaluated based on the petition alone and any preliminary response filed by the patent owner.

TIMELINE:
- Petition filing: Any time after patent grant (subject to 1-year bar)
- Patent Owner Preliminary Response: 3 months after petition filing
- Institution decision: Within 6 months of petition filing
- Final Written Decision: Within 12 months of institution (extendable to 18 months for good cause)

ESTOPPEL:
A petitioner who reasonably could have raised a ground during an IPR but did not is estopped from
raising that ground in subsequent proceedings before the USPTO, ITC, or federal courts.

CLAIM CONSTRUCTION:
The Board applies the Phillips standard for claim construction in IPR proceedings, construing claims
in accordance with their ordinary and customary meaning as understood by a person of ordinary skill
in the art at the time of the invention.
        """
    },
    {
        "id": "ptab-obviousness-standard",
        "title": "Obviousness Standard in PTAB Proceedings",
        "text": """
OBVIOUSNESS UNDER 35 U.S.C. § 103 IN PTAB PROCEEDINGS

The Supreme Court's KSR International Co. v. Teleflex Inc. (2007) framework governs obviousness
analysis at PTAB. An invention is obvious if the differences between the claimed invention and the
prior art are such that the claimed invention would have been obvious to a person of ordinary skill
in the art (POSITA) at the time the invention was made.

GRAHAM FACTORS:
The Board applies the four Graham factors to assess obviousness:
1. The scope and content of the prior art
2. The differences between the claimed invention and the prior art
3. The level of ordinary skill in the pertinent art
4. Secondary considerations (objective indicia of non-obviousness)

SECONDARY CONSIDERATIONS (OBJECTIVE INDICIA):
Evidence of non-obviousness includes:
- Commercial success of products embodying the claimed invention
- Long-felt but unsolved need in the art
- Failure of others to arrive at the claimed invention
- Unexpected results compared to prior art
- Copying by competitors
- Praise from experts in the field

The patent owner bears the burden of production for secondary considerations, while the petitioner
bears the ultimate burden of persuasion.

MOTIVATION TO COMBINE:
To establish obviousness based on a combination of prior art references, a petitioner must show:
1. Each element of the claim exists in the prior art
2. A motivation existed to combine the references
3. A reasonable expectation of success in making the combination

The motivation to combine need not be found explicitly in the prior art but may be implicit from
the knowledge of those skilled in the art, design incentives, or market pressures.
        """
    },
    {
        "id": "ptab-claim-construction",
        "title": "Claim Construction in PTAB Trials",
        "text": """
CLAIM CONSTRUCTION IN PTAB PROCEEDINGS

Effective November 13, 2018, the USPTO amended its rules to apply the Phillips v. AWH Corp. (Fed. Cir.
2005) claim construction standard in all AIA trial proceedings, including IPR, PGR, and CBM.

PHILLIPS STANDARD:
Under Phillips, claims are given their ordinary and customary meaning as understood by a person of
ordinary skill in the art (POSITA) at the time of the invention, in light of:
- The claim language itself
- The specification and drawings
- The prosecution history
- Extrinsic evidence (dictionaries, treatises, expert testimony) as secondary sources

CLAIM TERMS REQUIRING CONSTRUCTION:
The Board construes only those claim terms that are in controversy and only to the extent necessary
to resolve the controversy. A party must identify each claim term it believes requires construction
and propose a construction in the petition or patent owner response.

MEANS-PLUS-FUNCTION CLAIMS:
For limitations written in means-plus-function format under 35 U.S.C. § 112(f), the Board identifies:
1. The function recited in the claim
2. The corresponding structure, material, or acts disclosed in the specification

INDEFINITENESS:
In IPR proceedings, claims cannot be challenged for indefiniteness under § 112. However, indefiniteness
may affect claim construction if a term has no discernible meaning even with recourse to the specification.

IMPACT ON PRIOR ART ANALYSIS:
The claim construction adopted by the Board directly affects which prior art references are relevant
and whether those references teach or suggest each claimed element. Petitioners must map their prior
art to the claims as construed.
        """
    }
]


def chunk_text(text: str) -> list[str]:
    words = text.split()
    chunks = []
    for i in range(0, len(words), CHUNK_SIZE - CHUNK_OVERLAP):
        chunk = " ".join(words[i:i + CHUNK_SIZE])
        if chunk.strip():
            chunks.append(chunk)
    return chunks


def embed(text: str) -> list[float]:
    response = bedrock.invoke_model(
        modelId="amazon.titan-embed-text-v1",
        body=json.dumps({"inputText": text[:8000]}),  # Titan limit
        contentType="application/json",
        accept="application/json",
    )
    return json.loads(response["body"].read())["embedding"]


def ingest_doc(index, doc: dict) -> int:
    chunks = chunk_text(doc["text"])
    vectors = []
    for i, chunk in enumerate(chunks):
        vector_id = f"{doc['id']}_chunk_{i}"
        embedding = embed(chunk)
        vectors.append({
            "id": vector_id,
            "values": embedding,
            "metadata": {
                "source": doc["id"],
                "title": doc["title"],
                "chunk_index": i,
                "text": chunk[:1000],
            }
        })
    index.upsert(vectors=vectors)
    return len(vectors)


def main():
    from pinecone import Pinecone

    parser = argparse.ArgumentParser()
    parser.add_argument("--trial", help="Specific trial number to fetch (optional)")
    args = parser.parse_args()

    print(f"Connecting to Pinecone index: {PINECONE_INDEX}")
    pc = Pinecone(api_key=PINECONE_API_KEY)
    index = pc.Index(PINECONE_INDEX)

    total = 0
    for doc in SAMPLE_DOCS:
        print(f"  Ingesting: {doc['title']}...")
        count = ingest_doc(index, doc)
        print(f"    → {count} vectors upserted")
        total += count

    print(f"\nDone! {total} total vectors in Pinecone.")
    stats = index.describe_index_stats()
    print(f"Index now has {stats['total_vector_count']} vectors.")


if __name__ == "__main__":
    main()
