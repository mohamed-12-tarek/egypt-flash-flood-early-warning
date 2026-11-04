from genai import smoke_check


def test_smoke_check_passes_on_fixture(with_predictions, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "x")
    res = smoke_check.run_checks("Hurghada", check_env=False)
    fails = [r for r in res if r[0] == smoke_check.FAIL]
    assert not fails, fails
    names = [r[1] for r in res]
    assert "tool get_current_risk" in names and "alert payload" in names


def test_smoke_check_reports_empty_warehouse(sql, monkeypatch):
    from sqlalchemy import text
    with sql.begin() as c:
        c.execute(text("DELETE FROM gold.fact_hourly_risk"))
    res = smoke_check.run_checks("Hurghada", check_env=False)
    assert any(r[0] == smoke_check.FAIL and "fact_hourly_risk" in r[1] for r in res)


def test_smoke_check_missing_env(monkeypatch):
    monkeypatch.delenv("SQLSERVER_HOST", raising=False)
    res = smoke_check.run_checks("Hurghada", check_env=True)
    assert res[0][0] == smoke_check.FAIL
