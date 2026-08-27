"""Reads data/latest_summary.json (written by build.py) and sends a Telegram
alert when things aren't calm. Deterministic script, no LLM in the loop —
this runs as a plain GitHub Actions step reading secrets.env, exactly the
pattern already proven for this account's daily family broadcast.

Trigger conditions (any one fires the alert):
  1. Integral index level != "Спокойно" (geomagnetic/solar activity elevated).
  2. Market volatility this run > 1.5x the historical average — only once
     there's at least MIN_HISTORY_FOR_RELATIVE_CHECKS prior runs to compare
     against, so a thin history doesn't produce false positives.
  3. News-feed headline volume > 1.5x the historical average — same
     history-size guard.

Usage:
    python notify.py
Env: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID (both required to actually send;
missing either just logs and exits 0 — a notify failure should never fail
the whole workflow run).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import requests

SUMMARY_PATH = Path(__file__).parent / "data" / "latest_summary.json"
MIN_HISTORY_FOR_RELATIVE_CHECKS = 3
RELATIVE_THRESHOLD = 1.5


def load_summary() -> dict | None:
    if not SUMMARY_PATH.exists():
        return None
    return json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))


def evaluate(summary: dict) -> list[str]:
    """Returns a list of human-readable reasons the alert fired (empty = calm)."""
    reasons = []

    if summary.get("index_level") and summary["index_level"] != "Спокойно":
        reasons.append(f"Интегральный индекс: {summary['index_level']} ({summary.get('index_score')}/100)")

    has_enough_history = (summary.get("history_sample_size") or 0) >= MIN_HISTORY_FOR_RELATIVE_CHECKS

    vol = summary.get("market_volatility_pct")
    avg_vol = summary.get("history_avg_market_volatility_pct")
    if has_enough_history and vol is not None and avg_vol:
        if vol > avg_vol * RELATIVE_THRESHOLD:
            reasons.append(f"Рыночная волатильность: {vol:.2f}% (обычно ~{avg_vol:.2f}%)")

    news = summary.get("news_count")
    avg_news = summary.get("history_avg_news_count")
    if has_enough_history and news is not None and avg_news:
        if news > avg_news * RELATIVE_THRESHOLD:
            reasons.append(f"Новостной шум: {news} заголовков (обычно ~{avg_news:.0f})")

    return reasons


def send_telegram(token: str, chat_id: str, text: str) -> None:
    resp = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": text},
        timeout=15,
    )
    resp.raise_for_status()


def main() -> None:
    summary = load_summary()
    if summary is None:
        print("No latest_summary.json found — nothing to evaluate.")
        return

    reasons = evaluate(summary)
    if not reasons:
        print("All calm — no alert.")
        return

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    message = "Погода/космопогода — не спокойно:\n" + "\n".join(f"- {r}" for r in reasons)
    print(message)

    if not token or not chat_id:
        print("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set — logged only, not sent.", file=sys.stderr)
        return

    send_telegram(token, chat_id, message)
    print("Telegram alert sent.")


if __name__ == "__main__":
    main()
