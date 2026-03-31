AREAS = [
    {"id": "trabajo", "name": "Trabajo", "color": "#5a8fc9", "emoji": "\U0001f4bc"},
    {"id": "personal", "name": "Personal", "color": "#4a9e7a", "emoji": "\U0001f331"},
    {"id": "proyectos", "name": "Proyectos", "color": "#8a6ac9", "emoji": "\U0001f680"},
    {"id": "ideas", "name": "Ideas", "color": "#d4a853", "emoji": "\U0001f4a1"},
]

AREA_MAP = {a["id"]: a for a in AREAS}
AREA_OPTIONS = {f'{a["emoji"]} {a["name"]}': a["id"] for a in AREAS}
AREA_LABELS = {a["id"]: f'{a["emoji"]} {a["name"]}' for a in AREAS}

CAT_ICONS = {
    "alimentacion": "\U0001f354",
    "transporte": "\U0001f697",
    "salud": "\U0001f48a",
    "entretenimiento": "\U0001f3ac",
    "hogar": "\U0001f3e0",
    "ropa": "\U0001f455",
    "educacion": "\U0001f4da",
    "trabajo": "\U0001f4bc",
    "ingreso": "\U0001f4b0",
    "otro": "\U0001f4e6",
}

TX_CATS_GASTO = ["alimentacion", "transporte", "salud", "entretenimiento", "hogar", "ropa", "educacion", "trabajo", "otro"]
TX_CATS_INGRESO = ["ingreso", "trabajo", "otro"]

BUDGET_DEFAULT = {
    "alimentacion": 300000,
    "transporte": 100000,
    "salud": 80000,
    "entretenimiento": 80000,
    "hogar": 150000,
    "ropa": 50000,
    "educacion": 60000,
    "trabajo": 100000,
    "otro": 50000,
}

HABIT_CATS = {
    "salud": "\U0001f3cb\ufe0f",
    "mente": "\U0001f9e0",
    "trabajo": "\U0001f4bc",
    "social": "\U0001f465",
    "finanzas": "\U0001f4b0",
    "hogar": "\U0001f3e0",
    "educacion": "\U0001f4da",
    "creatividad": "\U0001f3a8",
    "espiritualidad": "\U0001f54a\ufe0f",
    "otro": "\u2b50",
}

HABIT_FREQ = {
    "diario": "Todos los dias",
    "laborables": "Lunes a viernes",
    "fines": "Fines de semana",
    "lunes": "Todos los lunes",
    "martes": "Todos los martes",
    "miercoles": "Todos los miercoles",
    "jueves": "Todos los jueves",
    "viernes": "Todos los viernes",
    "sabado": "Todos los sabados",
    "domingo": "Todos los domingos",
    "quincenal": "Quincenal (1 y 15)",
    "mensual": "Mensual (dia 1)",
}

INV_CATS = ["electrodomesticos", "electronica", "muebles", "cocina", "ropa", "herramientas", "jardin", "seguridad", "otro"]
INV_CAT_ICONS = {
    "electrodomesticos": "\U0001f3e0",
    "electronica": "\U0001f4f1",
    "muebles": "\U0001fa91",
    "cocina": "\U0001f373",
    "ropa": "\U0001f455",
    "herramientas": "\U0001f527",
    "jardin": "\U0001f33f",
    "seguridad": "\U0001f512",
    "otro": "\U0001f4e6",
}

INV_STATUS = {"bueno": "\U0001f7e2", "regular": "\U0001f7e1", "malo": "\U0001f534"}

PRIORITY_COLORS = {"alta": "#c96a6a", "media": "#c9943a", "baja": "#4a9e7a"}
PRIORITY_LABELS = {"alta": "\U0001f534 Alta", "media": "\U0001f7e1 Media", "baja": "\U0001f7e2 Baja"}

COLORS = {
    "gold": "#d4a853",
    "emerald": "#4a9e7a",
    "sky": "#5a8fc9",
    "rose": "#c96a6a",
    "amber": "#c9943a",
    "violet": "#8a6ac9",
}

def fmt(n):
    return f"\u20a1{int(round(n)):,}".replace(",", ".")
