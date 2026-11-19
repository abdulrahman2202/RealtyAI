import json
import sys
sys.path.insert(0, 'backend')

import chromadb
from backend.indexing import preflight_chunks
from backend.embedding import cached_profile
from backend.data_access import DEFAULT_POLICY
from pathlib import Path

# Load the proposed ingestion manifest
manifest_path = Path('data/import_review/proposed_ingestion_manifest.json')
with open(manifest_path, encoding='utf-8') as f:
    manifest = json.load(f)

# Connect to existing ChromaDB collection
client = chromadb.PersistentClient(path='data/vector_db')
collection = client.get_collection('realtyai_properties', embedding_function=None)

profile = cached_profile()
print(f"Embedding profile: {profile.provenance()}")

# Extract chunks from the manifest
chunks_data = manifest['chunks']

# Load chunk_review.json for the chunk texts
review_path = Path('data/import_review/chunk_review.json')
try:
    with open(review_path, encoding='utf-8') as f:
        review = json.load(f)
except:
    with open(review_path, encoding='cp1252') as f:
        review = json.load(f)

# Build lookup from chunk id to chunk data
review_chunks = {c['id']: c for c in review['chunks']}

# Build PreparedChunk objects from manifest + review
class PreparedChunk:
    def __init__(self, id, text, body, metadata, token_count, body_token_count):
        self.id = id
        self.text = text
        self.body = body
        self.metadata = metadata
        self.token_count = token_count
        self.body_token_count = body_token_count

prepared_chunks = []
for mc in chunks_data:
    chunk_id = mc['id']
    if chunk_id in review_chunks:
        rc = review_chunks[chunk_id]
        metadata = mc['metadata']
        text = rc['text']
        body = rc['body']
        pc = PreparedChunk(
            id=chunk_id,
            text=text,
            body=body,
            metadata=metadata,
            token_count=mc['token_count'],
            body_token_count=rc.get('body_token_count', mc['token_count']),
        )
        prepared_chunks.append(pc)
    else:
        print(f"WARNING: Chunk {chunk_id} not found in review")

print(f"Prepared {len(prepared_chunks)} chunks for preflight")

# Run preflight WITH existing collection
print("\n" + "="*60)
print("Preflight WITH existing collection:")
result_with_collection = preflight_chunks(prepared_chunks, collection=collection, policy=DEFAULT_POLICY)
print(f"  State: {result_with_collection['state']}")
print(f"  Conflicts: {result_with_collection['conflicts']}")
print(f"  Duplicate input chunks: {result_with_collection['duplicate_input_chunks']}")
print(f"  Proposed chunk count: {result_with_collection['proposed_chunk_count']}")
print(f"  Identical count: {result_with_collection['identical_count']}")
print(f"  Added count: {result_with_collection['added_count']}")
print(f"  Pending count: {result_with_collection['pending_count']}")
print(f"  Source counts: {result_with_collection['source_counts']}")

# Count how many can be safely added
safe_to_add = 0
conflict_count = 0
identical_count = 0
for entry in result_with_collection['chunks']:
    status = entry['status']
    if status == 'pending':
        safe_to_add += 1
    elif status == 'identical':
        identical_count += 1
    elif status == 'added':
        safe_to_add += 1
    else:
        conflict_count += 1

print(f"\n=== SUMMARY ===")
print(f"Total proposed chunks: {result_with_collection['proposed_chunk_count']}")
print(f"Can be safely added (pending): {safe_to_add}")
print(f"Already identical to existing: {identical_count}")
print(f"Conflicts: {conflict_count}")
if result_with_collection['conflicts']:
    print(f"  Conflict details: {json.dumps(result_with_collection['conflicts'], indent=2)[:1500]}")