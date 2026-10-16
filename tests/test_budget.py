import pytest

from solaria_ia.orchestration.budget import (
    RunTokenBudget,
    TokenBudgetExceeded,
)
from solaria_ia.providers.usage_ledger import (
    DailyUsageLedger,
    UsageLimitError,
)


def test_run_token_budget_caps_output_and_counts_usage():
    budget = RunTokenBudget(limit=300)

    first_limit = budget.prepare(
        system_prompt="sys",
        user_prompt="x" * 147,
        requested_output_tokens=200,
    )
    assert first_limit == 200

    budget.record(input_tokens=42, output_tokens=200)
    assert budget.spent == 250

    second_limit = budget.prepare(
        system_prompt="",
        user_prompt="",
        requested_output_tokens=200,
    )
    assert second_limit == 49

    budget.record(input_tokens=1, output_tokens=49)
    assert budget.spent == 300


def test_run_token_budget_rejects_call_with_insufficient_budget():
    budget = RunTokenBudget(limit=100)

    with pytest.raises(TokenBudgetExceeded):
        budget.prepare(
            system_prompt="",
            user_prompt="x" * 240,
            requested_output_tokens=200,
        )

    assert budget.spent == 0


def test_daily_ledger_reserve_and_settle(tmp_path):
    ledger = DailyUsageLedger(str(tmp_path / "usage.sqlite3"))
    day, reserved = ledger.reserve(
        provider="gemini",
        estimated_tokens=100,
        call_limit=2,
        token_limit=500,
    )

    assert reserved == 100
    assert ledger.usage("gemini", day) == {
        "calls": 1,
        "tokens_used": 0,
        "tokens_reserved": 100,
    }

    ledger.settle(
        usage_date=day,
        provider="gemini",
        reserved_tokens=reserved,
        actual_tokens=83,
    )

    assert ledger.usage("gemini", day) == {
        "calls": 1,
        "tokens_used": 83,
        "tokens_reserved": 0,
    }


def test_daily_ledger_releases_reservation_after_failure(tmp_path):
    ledger = DailyUsageLedger(str(tmp_path / "usage.sqlite3"))
    day, reserved = ledger.reserve(
        provider="gemini",
        estimated_tokens=50,
        call_limit=2,
        token_limit=100,
    )

    ledger.release(
        usage_date=day,
        provider="gemini",
        reserved_tokens=reserved,
    )

    usage = ledger.usage("gemini", day)
    assert usage["calls"] == 1
    assert usage["tokens_reserved"] == 0
    assert usage["tokens_used"] == 0


def test_daily_ledger_blocks_excess_call_count(tmp_path):
    ledger = DailyUsageLedger(str(tmp_path / "usage.sqlite3"))

    for _ in range(2):
        ledger.reserve(
            provider="gemini",
            estimated_tokens=10,
            call_limit=2,
            token_limit=1000,
        )

    with pytest.raises(UsageLimitError, match="Limite diário"):
        ledger.reserve(
            provider="gemini",
            estimated_tokens=10,
            call_limit=2,
            token_limit=1000,
        )


def test_daily_ledger_blocks_excess_token_reservation(tmp_path):
    ledger = DailyUsageLedger(str(tmp_path / "usage.sqlite3"))
    day, _ = ledger.reserve(
        provider="gemini",
        estimated_tokens=80,
        call_limit=10,
        token_limit=100,
    )

    with pytest.raises(UsageLimitError, match="Limite diário"):
        ledger.reserve(
            provider="gemini",
            estimated_tokens=30,
            call_limit=10,
            token_limit=100,
        )

    assert ledger.usage("gemini", day)["tokens_reserved"] == 80
