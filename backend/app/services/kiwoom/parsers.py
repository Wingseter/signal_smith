"""Kiwoom API response parsing utilities."""


def parse_int(val) -> int:
    """String to int with sign/comma handling."""
    if val is None:
        return 0
    try:
        cleaned = str(val).strip().replace(",", "")
        if not cleaned:
            return 0
        if cleaned.startswith("-"):
            return -int(cleaned[1:])
        elif cleaned.startswith("+"):
            return int(cleaned[1:])
        return int(cleaned)
    except (ValueError, TypeError):
        return 0


def parse_float(val) -> float:
    """String to float with sign/comma handling."""
    if val is None:
        return 0.0
    try:
        cleaned = str(val).strip().replace(",", "")
        if not cleaned:
            return 0.0
        if cleaned.startswith("-"):
            return -float(cleaned[1:])
        elif cleaned.startswith("+"):
            return float(cleaned[1:])
        return float(cleaned)
    except (ValueError, TypeError):
        return 0.0
