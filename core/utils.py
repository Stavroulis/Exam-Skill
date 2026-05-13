from pathlib import Path


def truncate_text(text: str, max_chars: int = 120000) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n[TEXT TRUNCATED]"