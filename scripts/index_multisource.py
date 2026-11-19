"""Propose a separate collection; persistent creation/ingestion requires reviewed user approval."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.collection_setup import (
    PLAN_PATH,
    execute_approved_plan,
    proposed_collection,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--create-collection", action="store_true")
    parser.add_argument("--approved-plan", type=Path)
    parser.add_argument("--approval-reference")
    parser.add_argument("--collection-id")
    args = parser.parse_args()
    if args.execute:
        if not args.approved_plan or not args.approval_reference:
            parser.error("Execution requires the reviewed plan and an explicit user approval reference.")
        plan = json.loads(args.approved_plan.read_text(encoding="utf-8"))
        result = execute_approved_plan(plan, approval_reference=args.approval_reference,
            create_collection=args.create_collection, collection_id=args.collection_id)
        print(json.dumps({key: result[key] for key in
            ("state", "collection_name", "collection_id", "added_count", "identical_count")}, indent=2))
    else:
        if args.create_collection:
            parser.error("Creating a collection requires explicit execution approval.")
        plan = proposed_collection()
        PLAN_PATH.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({key: plan[key] for key in
            ("state", "collection_name", "database_dir", "chunk_count", "source_counts")}, indent=2))


if __name__ == "__main__":
    main()
