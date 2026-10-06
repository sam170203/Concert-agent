import re


_RATING = re.compile(r"(?<!\d)(10(?:\.0+)?|[0-9](?:\.\d+)?)(?:\s*/\s*10)?(?!\d)")


def parse_rating(text: str) -> float | None:
    """Return the first plausible 0–10 rating in a message."""
    match = _RATING.search(text.strip())
    if not match:
        return None
    value = float(match.group(1))
    return value if 0 <= value <= 10 else None
