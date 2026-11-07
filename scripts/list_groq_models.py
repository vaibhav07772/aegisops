"""List models available on your Groq account."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from groq import Groq

from app.config import get_settings


def main() -> None:
    settings = get_settings()
    if not settings.groq_api_key:
        print("[error] GROQ_API_KEY not set in .env")
        return

    client = Groq(api_key=settings.groq_api_key)
    try:
        models = client.models.list()
    except Exception as e:
        print(f"[error] Failed to list models: {e}")
        return

    print()
    print("=" * 80)
    print(f" Available models on your Groq account ({len(models.data)}):")
    print("=" * 80)
    for m in sorted(models.data, key=lambda x: x.id):
        ctx = getattr(m, "context_window", "?")
        print(f"  {m.id:<55} ctx={ctx:<10} {m.owned_by}")
    print("=" * 80)
    print(f"\n Current model in .env: {settings.groq_model}")
    print(" Pick a chat-capable model from above and set GROQ_MODEL in .env")


if __name__ == "__main__":
    main()