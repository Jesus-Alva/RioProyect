BRANCHES = (
    "guadalajara",
    "zapopan",
    "leon",
    "queretaro",
    "aguascalientes",
)

BRANCH_SET = frozenset(BRANCHES)


def expand_legacy_branches(value: str | None) -> list[str] | None:
    """Convert a previous scalar assignment to its canonical branch list."""
    if value is None:
        return None
    if value == "all":
        return list(BRANCHES)
    if value in BRANCH_SET:
        return [value]
    return []


def normalize_branches(values: list[str]) -> list[str]:
    """Return a unique, canonical-order list or reject unknown branches."""
    if not isinstance(values, list) or not values:
        raise ValueError("Se requiere al menos una sucursal.")
    if any(not isinstance(value, str) or value not in BRANCH_SET for value in values):
        raise ValueError("La selección contiene una sucursal no válida.")
    if len(set(values)) != len(values):
        raise ValueError("La selección contiene sucursales duplicadas.")
    return [branch for branch in BRANCHES if branch in values]
