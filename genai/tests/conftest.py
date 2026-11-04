"""Test fixtures: SQLite stands in for SQL Server (schema 'gold' via ATTACH), scripted fake LLM."""

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage
from sqlalchemy import create_engine, event, text

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from genai import db, tools  # noqa: E402

T0 = datetime(2026, 10, 20, 0, 0)          # first hour in the fixture data
HOURS = 48
LATEST = T0 + timedelta(hours=HOURS - 1)   # newest data point: 2026-10-21 23:00


class ScriptedLLM:
    """Fake chat model. `script` items are AIMessage or callables(messages) -> AIMessage."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = 0

    def bind_tools(self, tools_):
        return self

    def invoke(self, messages):
        self.calls += 1
        item = self.script.pop(0)
        return item(messages) if callable(item) else item


def tool_call(name, **args):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": f"call_{name}"}])


def last_tool_json(messages):
    import json
    from langchain_core.messages import ToolMessage
    msgs = [m for m in messages if isinstance(m, ToolMessage)]
    return json.loads(msgs[-1].content)


@pytest.fixture()
def sql(tmp_path, monkeypatch):
    path = tmp_path / "gold.db"
    engine = create_engine(f"sqlite:///{tmp_path / 'main.db'}")

    @event.listens_for(engine, "connect")
    def _attach(conn, _):
        conn.execute(f"ATTACH DATABASE '{path}' AS gold")

    with engine.begin() as c:
        c.execute(text("CREATE TABLE gold.fact_hourly_risk (city TEXT, event_time TEXT, avg_rainfall REAL, "
                       "rain_sum_24h REAL, rain_sum_72h REAL, risk_score INT, risk_level TEXT)"))
        c.execute(text("CREATE TABLE gold.predictions (city TEXT, predicted_for TEXT, predicted_rainfall REAL, "
                       "predicted_risk_score INT, predicted_risk_level TEXT, model_version TEXT, generated_at TEXT)"))
        c.execute(text("CREATE TABLE gold.dim_location (city TEXT, slope_degree REAL, elevation REAL)"))
        for city, slope in [("Aswan", 3.0), ("Hurghada", 6.0), ("St_Catherine", 18.0)]:
            c.execute(text("INSERT INTO gold.dim_location VALUES (:c,:s,100)"), {"c": city, "s": slope})
        for i in range(HOURS):
            t = (T0 + timedelta(hours=i)).strftime("%Y-%m-%d %H:%M:%S")
            # Aswan: always Safe. Hurghada: Watch in last hour. St_Catherine: a Danger event at hours 10-13
            rows = [("Aswan", 0.0, 0.0, 0.0, 4, "Safe")]
            rows.append(("Hurghada", 1.0 if i == HOURS - 1 else 0.0, 12.5 if i == HOURS - 1 else 0.0, 12.5, 35 if i == HOURS - 1 else 5,
                         "Watch" if i == HOURS - 1 else "Safe"))
            if 10 <= i <= 13:
                rows.append(("St_Catherine", 9.0 + i, 40.0 + i, 55.0, 60 + i, "Danger"))
            else:
                rows.append(("St_Catherine", 0.0, 0.5, 2.0, 9, "Safe"))
            for city, rain, s24, s72, score, level in rows:
                c.execute(text("INSERT INTO gold.fact_hourly_risk VALUES (:c,:t,:r,:a,:b,:s,:l)"),
                          dict(c=city, t=t, r=rain, a=s24, b=s72, s=score, l=level))
    db.set_engine(engine)
    monkeypatch.setattr(tools, "utcnow", lambda: LATEST + timedelta(minutes=30))
    yield engine
    db.set_engine(None)


@pytest.fixture()
def with_predictions(sql):
    gen = (LATEST + timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
    with sql.begin() as c:
        for k, (score, level) in enumerate([(40, "Watch"), (72, "Danger"), (55, "Watch")], start=1):
            c.execute(text("INSERT INTO gold.predictions VALUES ('Hurghada', :f, :r, :s, :l, 'v1', :g)"),
                      dict(f=(LATEST + timedelta(hours=k)).strftime("%Y-%m-%d %H:%M:%S"), r=2.5 * k, s=score, l=level, g=gen))
    return sql
