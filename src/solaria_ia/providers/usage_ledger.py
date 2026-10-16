import sqlite3
from datetime import UTC, datetime
from pathlib import Path


class UsageLimitError(RuntimeError):
    pass


class DailyUsageLedger:
    def __init__(self, database_path: str) -> None:
        self.path = Path(database_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.path, timeout=10) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS daily_usage (
                    usage_date TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    calls INTEGER NOT NULL DEFAULT 0,
                    tokens_used INTEGER NOT NULL DEFAULT 0,
                    tokens_reserved INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (usage_date, provider)
                )
                """
            )

    @staticmethod
    def today() -> str:
        return datetime.now(UTC).date().isoformat()

    def reserve(
        self,
        *,
        provider: str,
        estimated_tokens: int,
        call_limit: int,
        token_limit: int,
    ) -> tuple[str, int]:
        if estimated_tokens < 1:
            raise ValueError("A reserva de tokens deve ser positiva.")

        usage_date = self.today()

        with sqlite3.connect(self.path, timeout=10) as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT OR IGNORE INTO daily_usage (usage_date, provider) VALUES (?, ?)",
                (usage_date, provider),
            )
            row = connection.execute(
                "SELECT calls, tokens_used, tokens_reserved "
                "FROM daily_usage WHERE usage_date = ? AND provider = ?",
                (usage_date, provider),
            ).fetchone()

            calls, used, reserved = row
            if calls >= call_limit:
                raise UsageLimitError(
                    f"Limite diário de {call_limit} chamadas para {provider} atingido."
                )

            if used + reserved + estimated_tokens > token_limit:
                raise UsageLimitError(
                    f"Limite diário de {token_limit} tokens para {provider} atingido."
                )

            connection.execute(
                "UPDATE daily_usage SET calls = calls + 1, "
                "tokens_reserved = tokens_reserved + ? "
                "WHERE usage_date = ? AND provider = ?",
                (estimated_tokens, usage_date, provider),
            )
            connection.commit()

        return usage_date, estimated_tokens

    def settle(
        self,
        *,
        usage_date: str,
        provider: str,
        reserved_tokens: int,
        actual_tokens: int,
    ) -> None:
        with sqlite3.connect(self.path, timeout=10) as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                "UPDATE daily_usage SET "
                "tokens_reserved = MAX(0, tokens_reserved - ?), "
                "tokens_used = tokens_used + ? "
                "WHERE usage_date = ? AND provider = ?",
                (
                    reserved_tokens,
                    max(0, actual_tokens),
                    usage_date,
                    provider,
                ),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("Não foi encontrada a reserva de uso diário.")
            connection.commit()

    def release(
        self,
        *,
        usage_date: str,
        provider: str,
        reserved_tokens: int,
    ) -> None:
        """Release an unused token reservation after a failed provider call."""
        if reserved_tokens < 0:
            raise ValueError("A reserva de tokens não pode ser negativa.")

        with sqlite3.connect(self.path, timeout=10) as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                "UPDATE daily_usage SET "
                "tokens_reserved = MAX(0, tokens_reserved - ?) "
                "WHERE usage_date = ? AND provider = ?",
                (reserved_tokens, usage_date, provider),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("Não foi encontrada a reserva de uso diário.")
            connection.commit()

    def usage(self, provider: str, usage_date: str | None = None) -> dict[str, int]:
        day = usage_date or self.today()

        with sqlite3.connect(self.path, timeout=10) as connection:
            row = connection.execute(
                "SELECT calls, tokens_used, tokens_reserved "
                "FROM daily_usage WHERE usage_date = ? AND provider = ?",
                (day, provider),
            ).fetchone()

        if row is None:
            return {"calls": 0, "tokens_used": 0, "tokens_reserved": 0}

        return {
            "calls": int(row[0]),
            "tokens_used": int(row[1]),
            "tokens_reserved": int(row[2]),
        }
