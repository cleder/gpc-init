"""Small, dependency-free helpers shared across gpc_init modules."""


def deduplicate_preserving_order(values: list[str]) -> list[str]:
    """Remove duplicate values from a list, preserving first-occurrence order."""
    seen: set[str] = set()
    result: list[str] = []
    for v in values:
        if v not in seen:
            seen.add(v)
            result.append(v)
    return result
