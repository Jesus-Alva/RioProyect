OPERATIONAL_ROLES = (
    "directivo",
    "analista",
    "gerente",
    "bodega",
    "ti",
)
ADMIN_ROLE = "admin"
ALL_ROLES = frozenset((*OPERATIONAL_ROLES, ADMIN_ROLE))

AGENT_NAMES = {
    "directivo": "rio-directivo",
    "analista": "rio-analista",
    "gerente": "rio-gerente",
    "bodega": "rio-bodega",
    "ti": "rio-ti",
}
