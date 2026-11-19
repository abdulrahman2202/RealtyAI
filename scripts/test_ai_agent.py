"""Manual end-to-end test for the RealtyAI AI agent.

Uses the actual Groq API and the existing local RAG database.
Single question: "Tell me about Albert Hall Mansions."
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the project root is importable when running this script directly.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Use UTF-8 for stdout so non-ASCII answer text prints on Windows consoles.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from backend.chatbot import chatbot
from backend.rag import get_all_records, init_from_processed_data

QUESTION = "Tell me about Albert Hall Mansions."


def main() -> None:
    # Initialise the vector database from processed data only if necessary.
    if not get_all_records():
        init_from_processed_data()

    print(f"Question: {QUESTION}\n")

    try:
        result = chatbot(QUESTION)
    except Exception as error:  # noqa: BLE001 - report any failure clearly
        print("RESULT: FAILED")
        print(f"Error: {type(error).__name__}: {error}")
        return

    print("Answer:")
    print(result["answer"])
    print()

    sources = result.get("sources", [])
    if sources:
        print("Sources:")
        for source in sources:
            title = source.get("title") or "Unknown"
            url = source.get("url") or ""
            print(f"  - {title}: {url}")
    else:
        print("Sources: none retrieved")

    print("\nRESULT: SUCCESS")


if __name__ == "__main__":
    main()
