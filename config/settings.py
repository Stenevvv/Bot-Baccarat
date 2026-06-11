import os

def _cargar_env():
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ruta_env = os.path.join(raiz, ".env")
    if not os.path.exists(ruta_env):
        return
    with open(ruta_env, "r", encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea or linea.startswith("#") or "=" not in linea:
                continue
            clave, valor = linea.split("=", 1)
            os.environ.setdefault(clave.strip(), valor.strip().strip('"').strip("'"))

_cargar_env()

# ── TELEGRAM ───────────────────────────────
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
if not TELEGRAM_TOKEN:
    raise SystemExit("Falta el token. Crea un archivo .env con: TELEGRAM_TOKEN=tu_token")
CANAL_SENALES_ID = -1003740408493
CANAL_ESTADISTICAS_ID = -1004218181454

# ── MESAS ───────────────────────────────────
MESAS = [
    {"nombre": "Baccarat 6",       "region": (88, 395, 430, 275),  "banner_roi": (120, 50, 190, 50), "activa": True},
    {"nombre": "Super 8 Baccarat", "region": (535, 395, 443, 275), "banner_roi": (123, 50, 197, 50), "activa": True},
    {"nombre": "Baccarat 1",       "region": (988, 395, 444, 275), "banner_roi": (123, 50, 198, 50), "activa": True},
]

# ── DETECCIÓN ───────────────────────────────
INTERVALO_CAPTURA = 1.5
CONFIRMAR_RESULTADO  = 4.0
PAUSA_PERDIDA_GLOBAL = 1800
COOLDOWN_RESULTADO   = 10.0

# ── MODO PRUEBA ─────────────────────────────
MODO_PRUEBA = False

UMBRAL_BANNER = 2000
DOMINANCIA_COLOR = 1.6

# ── ESPACIADO ENTRE SEÑALES (por mesa, creciente) ─
ESPACIADO_MIN_INICIAL     = 45
ESPACIADO_MAX_INICIAL     = 120
ESPACIADO_INCREMENTO_CADA = 900
ESPACIADO_INCREMENTO_SEG  = 30
ESPACIADO_TOPE_MAX        = 300
ESPACIADO_ANTIRRAFAGA     = 20

# ── ANTI-INACTIVIDAD ────────────────────────
ANTIINACTIVIDAD_ACTIVO = True
ANTIINACTIVIDAD_CADA   = 300
ANTIINACTIVIDAD_POS    = (1667, 661)
ANTIINACTIVIDAD_CLIC   = True
