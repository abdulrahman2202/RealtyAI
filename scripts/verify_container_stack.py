"""Verify an existing database in local production containers without indexing."""

from __future__ import annotations

import argparse
import json
import subprocess
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTAINER = "realtyai-phase78-backend-1"
SQL_INSPECTION = """
import json,os,sqlite3
from pathlib import Path
path=Path(os.environ['REALTYAI_VECTOR_DB_DIR'])/'chroma.sqlite3'
connection=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)
identity,name,dimension=connection.execute('SELECT id,name,dimension FROM collections WHERE name=?',('realtyai_multisource_v1',)).fetchone()
rows={}
for chunk,key,string,integer,floating,boolean in connection.execute('SELECT e.embedding_id,m.key,m.string_value,m.int_value,m.float_value,m.bool_value FROM embeddings e JOIN embedding_metadata m ON m.id=e.id WHERE e.segment_id IN (SELECT id FROM segments WHERE collection=?)',(identity,)):
    value=next((v for v in (string,integer,floating,boolean) if v is not None),None)
    rows.setdefault(chunk,{})[key]=value
connection.close()
print(json.dumps({'collection_id':identity,'collection_name':name,'dimension':dimension,'rows':rows}))
"""


def docker(*args):
    result = subprocess.run(["docker", *args], cwd=ROOT, text=True, capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError("Docker verification command failed: " + result.stderr[-1500:])
    return result.stdout


def inspect_database(container=CONTAINER):
    result = json.loads(docker("exec", container, "python", "-c", SQL_INSPECTION))
    preview = json.loads((ROOT / "data/import_review/chunk_review.json").read_text(encoding="utf-8"))
    expected = {chunk["id"]: chunk for chunk in preview["chunks"]}
    assert result["collection_id"] == "51cdb05c-3ee9-4b04-b85c-71cbf168ff0d"
    assert result["dimension"] == 384 and len(result["rows"]) == 84
    assert set(result["rows"]) == set(expected)
    for identity, metadata in result["rows"].items():
        assert metadata.pop("chroma:document") == expected[identity]["text"]
        assert metadata == expected[identity]["metadata"]
    counts = Counter(metadata["source"] for metadata in result["rows"].values())
    assert counts == {"darglobal": 46, "wasalt": 38}
    assert len({metadata["document_id"] for metadata in result["rows"].values()}) == 12
    return {"collection_id": result["collection_id"], "chunks": 84, "source_counts": dict(counts),
        "documents": 12, "all_reviewed_ids_text_and_metadata_match": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--after-recreation", action="store_true")
    parser.add_argument("--container", default=CONTAINER)
    parser.add_argument("--api-url", default="http://127.0.0.1:18000")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    with urllib.request.urlopen(args.api_url.rstrip("/") + "/ready", timeout=15) as response:
        ready = json.load(response)
    assert ready["status"] == "ready" and ready["chunks"] == 84
    result = inspect_database(args.container)
    result.update({"readiness": ready, "after_container_recreation": args.after_recreation,
        "no_indexing_performed": True})
    filename = "persistence-after-recreation.json" if args.after_recreation else "container-storage.json"
    output = args.output or ROOT / ".tmp/phase78" / filename
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
