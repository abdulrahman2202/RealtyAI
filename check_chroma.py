import chromadb
import json

client = chromadb.PersistentClient(path='data/vector_db')
collections = client.list_collections()
for c in collections:
    print(f'Collection: {c.name}, ID: {c.id}')
    count = c.count()
    print(f'  Document count: {count}')
    items = c.get(include=['metadatas', 'documents', 'embeddings'])
    ids = items.get('ids', [])
    print(f'  IDs count: {len(ids)}')
    print(f'  First 5 IDs: {ids[:5]}')
    # Check metadata
    metadatas = items.get('metadatas', [])
    for i, m in enumerate(metadatas[:3]):
        print(f'  Metadata {i}: {json.dumps(m, indent=2)[:200]}')