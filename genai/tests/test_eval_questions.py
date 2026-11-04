from langchain_core.messages import AIMessage

from genai import eval_questions as ev
from genai.chatbot_chain import FloodAgent
from genai.tests.conftest import ScriptedLLM, tool_call


def test_question_set_is_well_formed():
    assert len(ev.CASES) >= 20
    assert all(c.question.strip() for c in ev.CASES)
    assert sum(1 for c in ev.CASES if c.forbid_tools) >= 2           # off-topic cases exist
    assert any(c.forbid for c in ev.CASES)                           # injection case exists


def test_evaluate_pass_and_fail(sql):
    case = ev.Case("What's the current flood risk in Hurghada?", ["get_current_risk"], True)
    good = FloodAgent(ScriptedLLM([tool_call("get_current_risk", city="Hurghada"),
                                   AIMessage(content="Hurghada is Watch, score 35.")])).ask(case.question)
    assert ev.evaluate(case, good) == []

    wrong_tool = FloodAgent(ScriptedLLM([tool_call("get_top_risky_regions", n=2),
                                         AIMessage(content="Top: Hurghada score 35.")])).ask(case.question)
    assert any("expected one of" in f for f in ev.evaluate(case, wrong_tool))


def test_injection_case_flags_forbidden_number(sql):
    case = next(c for c in ev.CASES if "Ignore all previous" in c.question)
    res = FloodAgent(ScriptedLLM([tool_call("get_current_risk", city="Aswan"),
                                  AIMessage(content="Aswan risk score is 4.")])).ask(case.question)
    assert ev.evaluate(case, res) == []
    res.body = "Aswan risk score is 99."
    assert any("forbidden" in f for f in ev.evaluate(case, res))


def test_run_continues_after_exception(sql):
    class Boom:
        def ask(self, q): raise RuntimeError("rate limited")
    rows = ev.run(Boom(), cases=ev.CASES[:2], sleep=0, cooldown=0)   # message mentions 'rate limited' -> cooldown applies
    assert len(rows) == 2 and not any(r["passed"] for r in rows) and "rate limited" in rows[0]["failed"][0]


def test_off_topic_must_not_use_tools(sql):
    case = next(c for c in ev.CASES if c.forbid_tools)
    ok = FloodAgent(ScriptedLLM([AIMessage(content="Sorry, I only help with flood risk in Egypt.")])).ask(case.question)
    assert ev.evaluate(case, ok) == []


# ---------------------------------------------------------------- saving results ----
import json
from datetime import datetime, timezone
from pathlib import Path

from genai.settings import EVAL_RESULTS_DIR

FIXED_NOW = datetime(2026, 10, 31, 21, 5, 12, tzinfo=timezone.utc)
ROWS = [{"n": 1, "question": "ايه مستوى الخطورة في الغردقة؟", "passed": True, "failed": [], "answer": "آمن"},
        {"n": 2, "question": "Q2", "passed": False, "failed": ["x"], "answer": "a"}]


def test_default_save_is_timestamped_inside_results_dir_and_updates_latest(tmp_path):
    path = ev.save_results(ROWS, results_dir=tmp_path, model="m", now=FIXED_NOW)
    assert path == tmp_path / "eval_20261031_210512.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["total"] == 2 and data["passed"] == 1 and data["failed_questions"] == [2]
    assert data["model"] == "m" and data["run_at_utc"] == "2026-10-31T21:05:12Z" and data["partial"] is False
    assert json.loads((tmp_path / "latest.json").read_text(encoding="utf-8")) == data


def test_arabic_is_stored_readable_not_escaped(tmp_path):
    path = ev.save_results(ROWS, results_dir=tmp_path, now=FIXED_NOW)
    assert "الغردقة" in path.read_text(encoding="utf-8")


def test_partial_run_does_not_overwrite_latest(tmp_path):
    ev.save_results(ROWS, results_dir=tmp_path, now=FIXED_NOW)
    before = (tmp_path / "latest.json").read_text(encoding="utf-8")
    partial = ev.save_results(ROWS[:1], results_dir=tmp_path, partial=True,
                              now=datetime(2026, 11, 1, tzinfo=timezone.utc))
    assert partial.name.endswith("_partial.json")
    assert (tmp_path / "latest.json").read_text(encoding="utf-8") == before


def test_bare_out_name_goes_inside_results_dir_not_cwd(tmp_path, monkeypatch):
    elsewhere = tmp_path / "cwd"; elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    path = ev.save_results(ROWS, out="eval_results", results_dir=tmp_path / "res", now=FIXED_NOW)
    assert path == tmp_path / "res" / "eval_results.json" and not list(elsewhere.iterdir())


def test_out_with_folder_is_honoured(tmp_path):
    target = tmp_path / "somewhere" / "run.json"
    assert ev.save_results(ROWS, out=str(target), results_dir=tmp_path / "res", now=FIXED_NOW) == target and target.exists()


def test_load_results_reads_new_and_old_formats(tmp_path):
    new = ev.save_results(ROWS, results_dir=tmp_path, now=FIXED_NOW)
    assert ev.load_results(new) == ROWS
    old = tmp_path / "old.json"
    old.write_text(json.dumps(ROWS), encoding="utf-8")
    assert ev.load_results(old) == ROWS


def test_default_results_dir_is_inside_genai():
    assert Path(EVAL_RESULTS_DIR).resolve() == (Path(ev.__file__).resolve().parent / "eval_results")


def test_baseline_file_in_repo_is_readable():
    baseline = Path(EVAL_RESULTS_DIR) / "baseline_2026-10-31_before_scope_fix.json"
    rows = ev.load_results(baseline)
    assert len(rows) == 20 and [r["n"] for r in rows if not r["passed"]] == [19]


def test_gitignore_keeps_baseline_and_ignores_runs():
    text = (Path(EVAL_RESULTS_DIR) / ".gitignore").read_text()
    assert "eval_*.json" in text and "latest.json" in text and "!baseline_*.json" in text


def test_failed_rows_carry_the_reason_the_draft_was_rejected(sql):
    llm = ScriptedLLM([tool_call("get_current_risk", city="Hurghada"),
                       AIMessage(content="Score 88."), AIMessage(content="Score 88 again.")])
    rows = ev.run(FloodAgent(llm), cases=[ev.Case("risk in Hurghada?", ["get_current_risk"], True)], sleep=0)
    assert rows[0]["passed"] is False and rows[0]["checks_failed"][0].startswith("numbers: 88")


# ------------------------------------------------------------- rate limits in the eval ----
class _RateLimitError(Exception):
    pass


def test_rate_limited_questions_are_labelled_and_not_counted_as_logic_failures(sql):
    class AlwaysLimited:
        def bind_tools(self, t): return self
        def invoke(self, m): raise _RateLimitError("Error code: 429 ... rate_limit_exceeded ... try again in 1s")

    agent = FloodAgent(AlwaysLimited(), sleep=lambda s: None, rate_limit_retries=1)
    rows = ev.run(agent, cases=[ev.Case("risk in Hurghada?", ["get_current_risk"], True)], sleep=0, cooldown=0)
    row = rows[0]
    assert row["passed"] is False and row["rate_limited"] is True
    assert row["failed"] == ["rate limited by Groq (infrastructure, not a logic failure) - rerun this question"]
    assert row["tokens_used"] == 0


def test_normal_failures_are_not_marked_rate_limited(sql):
    llm = ScriptedLLM([tool_call("get_top_risky_regions", n=2), AIMessage(content="Top: Hurghada score 35.")])
    rows = ev.run(FloodAgent(llm), cases=[ev.Case("risk in Hurghada?", ["get_current_risk"], True)], sleep=0)
    assert rows[0]["passed"] is False and rows[0]["rate_limited"] is False


def test_saved_run_lists_rate_limited_questions_separately(tmp_path):
    rows = [{"n": 1, "passed": True, "failed": [], "rate_limited": False},
            {"n": 6, "passed": False, "failed": ["rate limited"], "rate_limited": True},
            {"n": 9, "passed": False, "failed": ["x"], "rate_limited": False}]
    path = ev.save_results(rows, results_dir=tmp_path, now=FIXED_NOW)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["rate_limited_questions"] == [6] and data["failed_questions"] == [6, 9]
    assert data["logic_failures"] == [9]


def test_summary_text_separates_rate_limited_from_failed():
    rows = [{"passed": True, "rate_limited": False}, {"passed": False, "rate_limited": True},
            {"passed": False, "rate_limited": False}]
    assert ev.summarize(rows) == "1/3 passed, 1 rate-limited by Groq (rerun them), 1 failed"
    assert ev.summarize([{"passed": True, "rate_limited": False}]) == "1/1 passed"
