"""
Create the Pinecone index for PTAB Intelligence.
Run once before first deploy: python scripts/init-pinecone.py
"""

import os
from dotenv import load_dotenv
from pinecone import Pinecone, ServerlessSpec

load_dotenv()

pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
index_name = os.environ.get("PINECONE_INDEX_NAME", "ptab-documents")

if index_name not in [i.name for i in pc.list_indexes()]:
    pc.create_index(
        name=index_name,
        dimension=1536,  # Bedrock Titan embedding dimension
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region="us-east-1"),
    )
    print(f"Created Pinecone index: {index_name}")
else:
    print(f"Index '{index_name}' already exists — skipping.")

index = pc.Index(index_name)
print(f"Index stats: {index.describe_index_stats()}")
