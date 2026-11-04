import hashlib
import math

import chromadb
import pytest
from chromadb import Documents, EmbeddingFunction, Embeddings

from genai import rag, vector_store_setup as vs
from genai.settings import KNOWLEDGE_DIR


class HashEmbedding(EmbeddingFunction):
    """Deterministic bag-of-words embedding so tests need no model download."""

    def __init__(self): pass

    @staticmethod
    def name() -> str: return "hash-test"

    def get_config(self): return {}

    @staticmethod
    def build_from_config(config): return HashEmbedding()

    def __call__(self, input: Documents) -> Embeddings:
        out = []
        for text in input:
            v = [0.0] * 256
            for w in "".join(c.lower() if c.isalnum() else " " for c in text).split():
                v[int(hashlib.md5(w.encode()).hexdigest(), 16) % 256] += 1.0
            n = math.sqrt(sum(x * x for x in v)) or 1.0
            out.append([x / n for x in v])
        return out


@pytest.fixture()
def kb(tmp_path):
    client = chromadb.PersistentClient(path=str(tmp_path / "chroma"))
    emb = HashEmbedding()
    n = vs.build_index(KNOWLEDGE_DIR, client=client, embedding_function=emb)
    assert n > 0
    rag.set_collection(vs.get_collection(client, emb))
    yield
    rag.set_collection(None)


def test_templates_and_readme_not_indexed():
    sources = {i["metadata"]["source"] for i in vs.load_documents(KNOWLEDGE_DIR)}
    assert sources == {"safety_guidelines/flash_flood_safety_ar.md", "safety_guidelines/flash_flood_safety_en.md"}


def test_chunks_have_metadata_and_stable_ids():
    a, b = vs.load_documents(KNOWLEDGE_DIR), vs.load_documents(KNOWLEDGE_DIR)
    assert [i["id"] for i in a] == [i["id"] for i in b]
    assert all(i["metadata"]["origin"] and i["metadata"]["language"] in {"ar", "en"} for i in a)
    assert all(len(i["text"]) <= vs.MAX_CHUNK_CHARS + 200 for i in a)


def test_search_returns_relevant_passage_with_source(kb):
    r = rag.search_documents("never drive through flooded road floodwater")
    assert r["status"] == "ok"
    assert r["rows"][0]["source"].startswith("safety_guidelines/")
    assert "floodwater" in " ".join(x["text"] for x in r["rows"]).lower()


def test_search_irrelevant_is_no_data(kb, monkeypatch):
    monkeypatch.setattr(rag, "RAG_MAX_DISTANCE", 0.05)
    assert rag.search_documents("quantum chromodynamics lattice")["status"] == "no_data"


def test_reindex_removes_stale_chunks(tmp_path):
    client = chromadb.PersistentClient(path=str(tmp_path / "c"))
    emb = HashEmbedding()
    kdir = tmp_path / "k"; kdir.mkdir()
    f = kdir / "a.md"
    f.write_text("---\ntitle: A\nlanguage: en\norigin: test\n---\n# H\nold text about wadis\n")
    vs.build_index(str(kdir), client=client, embedding_function=emb)
    f.write_text("---\ntitle: A\nlanguage: en\norigin: test\n---\n# H\nnew text about roads\n")
    vs.build_index(str(kdir), client=client, embedding_function=emb)
    col = vs.get_collection(client, emb)
    assert col.count() == 1 and "new text" in col.get()["documents"][0]


def test_agent_uses_rag_for_safety_questions(kb, sql):
    from langchain_core.messages import AIMessage
    from genai.chatbot_chain import FloodAgent
    from genai.settings import DISCLAIMER
    from genai.tests.conftest import ScriptedLLM, tool_call

    llm = ScriptedLLM([tool_call("search_knowledge_base", query="what to do if my car is in floodwater"),
                       AIMessage(content="Leave the vehicle and move to higher ground if it is safe to do so.")])
    res = FloodAgent(llm).ask("What should I do if my car is surrounded by floodwater?")
    assert res.status == "ok" and res.tools_used == ["search_knowledge_base"]
    assert "Flash flood safety" in res.answer and DISCLAIMER["en"] in res.answer and res.data_as_of is None
