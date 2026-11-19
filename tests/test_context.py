"""Complete evidence budgets, source citations, property isolation, and missing answers."""

from unittest.mock import Mock

from backend import chatbot
from backend.context import build_context, extract_sources
from backend.document_preparation import prepare_documents


def _retrieved(chunks):
    return [{"id": chunk.id, "document": chunk.text, "body": chunk.body, "metadata": chunk.metadata, "distance": 0.25} for chunk in chunks]


def test_context_counts_headers_and_keeps_only_complete_chunks(actual_documents, profile):
    records = _retrieved(prepare_documents(actual_documents, profile=profile))
    bundle = build_context(records, profile=profile, max_tokens=500, max_bytes=2500)
    assert bundle.records
    assert bundle.token_count == profile.count(bundle.text) <= 500
    assert bundle.byte_count <= 2500
    for record in bundle.records:
        assert record["body"] in bundle.text
        assert record["metadata"]["url"] in bundle.text
    empty = build_context(records, profile=profile, max_tokens=1)
    assert not empty.records and empty.text == ""


def test_context_separates_source_documents_and_retains_page_kind_and_identity(actual_imports, profile):
    records = [actual_imports["darglobal"].records[-1], actual_imports["wasalt"].records[1]]
    retrieved = _retrieved(prepare_documents(records, profile=profile))
    bundle = build_context(retrieved, profile=profile, max_tokens=4000, max_bytes=20000)
    assert "SEPARATE SOURCE DOCUMENT" in bundle.text
    assert "Source: darglobal" in bundle.text and "Source: wasalt" in bundle.text
    assert "Page type: individual_property" in bundle.text
    assert "Page type: company" in bundle.text
    assert all(record["metadata"]["document_id"] in bundle.text for record in bundle.records)


def test_citations_deduplicate_by_identity_and_preserve_original_urls(actual_imports, profile):
    record = actual_imports["darglobal"].records[-1]
    retrieved = _retrieved(prepare_documents([record], profile=profile))
    sources = extract_sources(retrieved + retrieved)
    assert len(sources) == 1
    assert sources[0]["title"] == "THE ALBERT HALL MANSION"
    assert sources[0]["url"] == record.url
    assert "?utm_source=chatgpt.com" in sources[0]["url"]
    assert sources[0]["source"] == "darglobal"


def test_missing_information_does_not_trigger_generation_or_ingestion(monkeypatch):
    generate = Mock(side_effect=AssertionError("No LLM call is permitted for unavailable data"))
    monkeypatch.setattr(chatbot, "generate", generate)
    result = chatbot.chatbot("What property information is available?")
    assert "unavailable" in result["answer"]
    assert result["records"] == [] and result["sources"] == []
    generate.assert_not_called()


def test_albert_hall_does_not_borrow_another_property_handover_date(actual_imports, profile, monkeypatch):
    record = actual_imports["darglobal"].records[-1]
    records = _retrieved(prepare_documents([record], profile=profile))
    monkeypatch.setattr(chatbot, "search", Mock(return_value=records))
    generator = Mock(side_effect=AssertionError("Missing property attribute must not be generated"))
    monkeypatch.setattr(chatbot, "generate", generator)
    result = chatbot.chatbot("When is the handover for THE ALBERT HALL MANSION?", profile=profile)
    assert "unavailable" in result["answer"]
    assert "December 2028" not in result["answer"]
    generator.assert_not_called()


def test_available_property_information_quotes_real_source_evidence(actual_imports, profile, monkeypatch):
    record = next(item for item in actual_imports["darglobal"].records if "/the-astera?" in item.url)
    records = _retrieved(prepare_documents([record], profile=profile))
    # Place the relevant FAQ first so the safe context budget contains its complete evidence.
    records.sort(key=lambda item: "December 2028" not in item["body"])
    monkeypatch.setattr(chatbot, "search", Mock(return_value=records))
    monkeypatch.setattr(chatbot, "generate", Mock(side_effect=AssertionError("Attribute answer uses source quotes")))
    result = chatbot.chatbot("When is The Astera handover?", profile=profile)
    assert "December 2028" in result["answer"]
    assert record.url in result["answer"]
    assert result["sources"][0]["url"] == record.url


def test_unsupported_generated_numbers_are_rejected(actual_imports, profile, monkeypatch):
    record = actual_imports["darglobal"].records[-1]
    monkeypatch.setattr(chatbot, "search", Mock(return_value=_retrieved(prepare_documents([record], profile=profile))))
    monkeypatch.setattr(chatbot, "generate", Mock(return_value="The building has 999999999999 units."))
    result = chatbot.chatbot("Tell me about Albert Hall Mansions.", profile=profile)
    assert "999999999999" not in result["answer"]
    assert record.data["title"] in result["answer"]


def test_visa_investment_amount_is_not_claimed_as_the_property_price(actual_imports, profile, monkeypatch):
    record = next(item for item in actual_imports["darglobal"].records if "/the-astera?" in item.url)
    records = _retrieved(prepare_documents([record], profile=profile))
    records.sort(key=lambda item: "Golden Visa" not in item["body"])
    monkeypatch.setattr(chatbot, "search", Mock(return_value=records))
    monkeypatch.setattr(chatbot, "generate", Mock(side_effect=AssertionError("No invented property price")))
    result = chatbot.chatbot("What is The Astera price?", profile=profile)
    assert "price" in result["answer"] and "unavailable" in result["answer"]
