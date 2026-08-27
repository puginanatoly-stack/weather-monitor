"""Reads data/latest_summary.json (written by build.py) and sends a
cyberpunk-styled Telegram status readout. Deterministic script, no LLM in
the loop — runs as a plain GitHub Actions step reading secrets, exactly the
pattern already proven for this account's daily family broadcast.

NOTIFY_MODE (repo secret, optional):
  "always"    — send every run, whether calm or not (for tuning the message
                style; this is the current default while the text is being
                reviewed — see module history / the principal's own request).
  "condition" — only send when a trigger fires (see evaluate()). Falls back
                to this if NOTIFY_MODE is unset or any other value.

Trigger conditions in "condition" mode (any one fires the alert):
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
the whole workflow run), NOTIFY_MODE (see above).
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
        reasons.append(f"ИНТЕГРАЛЬНЫЙ ИНДЕКС: {summary['index_level']} ({summary.get('index_score')}/100)")

    has_enough_history = (summary.get("history_sample_size") or 0) >= MIN_HISTORY_FOR_RELATIVE_CHECKS

    vol = summary.get("market_volatility_pct")
    avg_vol = summary.get("history_avg_market_volatility_pct")
    if has_enough_history and vol is not None and avg_vol:
        if vol > avg_vol * RELATIVE_THRESHOLD:
            reasons.append(f"РЫНОЧНАЯ ВОЛАТИЛЬНОСТЬ: {vol:.2f}% (норма ~{avg_vol:.2f}%)")

    news = summary.get("news_count")
    avg_news = summary.get("history_avg_news_count")
    if has_enough_history and news is not None and avg_news:
        if news > avg_news * RELATIVE_THRESHOLD:
            reasons.append(f"НОВОСТНОЙ ШУМ: {news} загол. (норма ~{avg_news:.0f})")

    return reasons


def _fmt(value, suffix: str = "", none_text: str = "н/д") -> str:
    if value is None:
        return none_text
    if isinstance(value, float):
        return f"{value:.1f}{suffix}"
    return f"{value}{suffix}"


def build_message(summary: dict, reasons: list[str]) -> str:
    """Cyberpunk-terminal-styled status readout — HTML parse_mode."""
    calm = not reasons
    header = "⚡ WEATHER-MONITOR // СКАНИРОВАНИЕ ЗАВЕРШЕНО ⚡"
    status_line = "СТАТУС: ▓▓▓ СЕТЬ СТАБИЛЬНА ▓▓▓" if calm else "СТАТУС: ⚠ АНОМАЛИЯ ЗАФИКСИРОВАНА ⚠"

    readout = (
        f"ИНДЕКС АКТИВНОСТИ ... {_fmt(summary.get('index_score'))}/100 [{summary.get('index_level', '—')}]\n"
        f"Kp-ГЕОМАГНИТКА ....... {_fmt(summary.get('kp'))}\n"
        f"СОЛНЕЧНЫЙ ВЕТЕР ....... {_fmt(summary.get('solar_wind_speed'), ' км/с')}\n"
        f"ФАЗА ЛУНЫ ............. {summary.get('moon_phase') or 'н/д'}\n"
        f"ЦИФРОВОЙ ШУМ .......... {_fmt(summary.get('news_count'))} загол.\n"
        f"РЫНОЧНЫЙ ШУМ .......... {_fmt(summary.get('market_volatility_pct'), '%')}"
    )

    if reasons:
        anomaly_block = "⚠ ТРИГГЕРЫ:\n" + "\n".join(f" » {r}" for r in reasons)
    else:
        anomaly_block = "✓ ТРИГГЕРОВ НЕ ОБНАРУЖЕНО"

    return (
        f"<b>{header}</b>\n"
        f"{status_line}\n\n"
        f"<pre>{readout}</pre>\n\n"
        f"{anomaly_block}\n\n"
        f"// КОНЕЦ ПЕРЕДАЧИ //"
    )


def send_telegram(token: str, chat_id: str, text: str) -> None:
    resp = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
        timeout=15,
    )
    resp.raise_for_status()


def main() -> None:
    summary = load_summary()
    if summary is None:
        print("No latest_summary.json found — nothing to evaluate.")
        return

    reasons = evaluate(summary)
    mode = os.environ.get("NOTIFY_MODE", "condition").strip().lower()
    should_send = mode == "always" or bool(reasons)

    print(f"mode={mode} reasons={reasons or 'none'} should_send={should_send}")

    if not should_send:
        print("All calm — no alert (condition mode, no triggers).")
        return

    message = build_message(summary, reasons)
    print(message)

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set — logged only, not sent.", file=sys.stderr)
        return

    send_telegram(token, chat_id, message)
    print("Telegram message sent.")


if __name__ == "__main__":
    main()
