from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from genai import chatbot_api
from genai.chatbot_chain import FloodAgent
from genai.tests.conftest import ScriptedLLM, tool_call


def client_with(llm, monkeypatch):
    agent = FloodAgent(llm)
    monkeypatch.setattr(chatbot_api, "get_agent", lambda: agent)
    return TestClient(chatbot_api.app)


def test_ask_contract_returns_answer(sql, monkeypatch):
    llm = ScriptedLLM([tool_call("get_current_risk", city="Aswan"),
                       AIMessage(content="Aswan is Safe, score 4.")])
    r = client_with(llm, monkeypatch).post("/chatbot/ask", json={"question": "risk in Aswan?"})
    assert r.status_code == 200 and "Aswan is Safe" in r.json()["answer"] and r.json()["data_as_of"]


def test_ask_validation(sql, monkeypatch):
    c = client_with(ScriptedLLM([]), monkeypatch)
    assert c.post("/chatbot/ask", json={"question": ""}).status_code == 422
    assert c.post("/chatbot/ask", json={"question": "x" * 5000}).status_code == 422
    assert c.post("/chatbot/ask", json={"question": "hi", "history": [{"role": "system", "content": "x"}]}).status_code == 422


def test_missing_key_gives_503(sql, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setattr(chatbot_api, "get_agent", lambda: FloodAgent())   # real build_llm -> RuntimeError
    r = TestClient(chatbot_api.app).post("/chatbot/ask", json={"question": "risk in Aswan?"})
    assert r.status_code == 503


def test_alert_endpoint(sql, monkeypatch):
    c = client_with(ScriptedLLM([]), monkeypatch)
    ok = c.get("/chatbot/alert/Aswan?lang=en").json()
    assert ok["status"] == "ok" and ok["source"] == "template"
    assert c.get("/chatbot/alert/Cairo").status_code == 404
    assert c.get("/chatbot/alert/Aswan?lang=fr").status_code == 422
