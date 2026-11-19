"""Trace actual /api/chat answers; isolated mode cannot open the production database."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from backend import chatbot, rag
from backend.main import app
from scripts.diagnose_chat import isolated_collection

QUESTIONS = [
    "What services does Wasalt provide?",
    "What information is available about THE ALBERT HALL MANSION?",
]

OUTPUT = Path("data/import_review/phase6112_chat_verification.json")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--isolated", action="store_true")
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--serve-only", action="store_true")
    args = parser.parse_args()
    if args.isolated:
        collection, _, encoder = isolated_collection()
        rag._collection = collection
        rag._encoder = encoder
        rag._client_target = None
    else:
        collection = rag._resolve_collection()
        if collection is None:
            raise RuntimeError("No explicitly configured, indexed collection is available.")
    reports = []
    original_generate = chatbot.generate
    original_handler = chatbot.chatbot
    active = {}

    def generate(messages, **kwargs):
        active["llm_messages"] = messages
        answer = original_generate(messages, **kwargs)
        active["raw_llm_answer"] = answer
        return answer

    def handler(*args, **kwargs):
        nonlocal active
        if args_namespace.serve_only:
            active = {"question": args[0]}
        result = original_handler(*args, **kwargs)
        active["chatbot_result"] = result
        if args_namespace.serve_only:
            records = result.get("records", [])
            active["http_status"] = 200
            active["response"] = {"answer": result["answer"], "sources": result["sources"], "success": True}
            active["verification"] = {
                "full_chunk_text_in_context": bool(records) and all(record["body"] in result["context"] for record in records),
                "citations_match_context": {source["url"] for source in result["sources"]}
                    == {record["metadata"]["url"] for record in records},
                "context_passed_to_llm": result["context"] in active["llm_messages"][1]["content"]
                    if "llm_messages" in active else None,
                "llm_called": "llm_messages" in active,
            }
            reports.append(active)
            OUTPUT.write_text(json.dumps({"isolated": args_namespace.isolated, "collection_name": collection.name,
                "collection_id": str(collection.id), "collection_count": collection.count(), "questions": reports},
                indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return result

    args_namespace = args
    chatbot.generate = generate
    import backend.api.routes
    backend.api.routes.chatbot = handler
    if args.serve_only:
        import uvicorn
        uvicorn.run(app, host="127.0.0.1", port=8000)
        return
    client = TestClient(app)
    stored = collection.get(include=["documents", "metadatas"])
    stored_by_id = dict(zip(stored["ids"], stored["documents"], strict=True))
    for question in QUESTIONS:
        active = {"question": question}
        response = client.post("/api/chat", json={"question": question})
        active["http_status"] = response.status_code
        active["response"] = response.json()
        result = active.get("chatbot_result", {})
        records = result.get("records", [])
        active["verification"] = {
            "full_chunk_text_in_context": bool(records) and all(
                record["document"] == stored_by_id[record["id"]]
                and record["body"] in result["context"] for record in records),
            "citations_match_context": bool(records) and
                {item["url"] for item in active["response"].get("sources", [])}
                == {record["metadata"]["url"] for record in records},
            "context_passed_to_llm": result.get("context", "") in
                active.get("llm_messages", [{}, {"content": ""}])[1].get("content", "")
                if "llm_messages" in active else None,
            "llm_called": "llm_messages" in active,
        }
        reports.append(active)
        OUTPUT.write_text(json.dumps({"isolated": args.isolated, "collection_name": collection.name,
            "collection_id": str(collection.id), "collection_count": collection.count(), "questions": reports},
            indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps({"question": question, "http_status": response.status_code,
            "retrieved": result.get("retrieved_count"), "context_chunks": len(records),
            "llm_called": active["verification"]["llm_called"], "answer": active["response"].get("answer"),
            "verification": active["verification"]}), flush=True)
        if response.status_code != 200:
            raise RuntimeError("Manual API verification failed with HTTP " + str(response.status_code))
    if args.serve:
        import uvicorn
        uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
