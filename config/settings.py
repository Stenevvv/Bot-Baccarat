# ============================================================
#  BACCARAT BOT - CONFIGURACIÓN PRINCIPAL
#  Edita este archivo para cambiar mesas, tiempos, etc.
# ============================================================
import os

# ── Cargador simple de archivo .env ─────────────────────────
# Lee un archivo ".env" en la raíz del proyecto (junto a main.py).
# Formato:  TELEGRAM_TOKEN=123456:ABC-tu_token
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

# ── TELEGRAM ────────────────────────────────────────────────
# El token NO se escribe aquí: se lee del archivo .env
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
if not TELEGRAM_TOKEN:
    raise SystemExit(
        "❌ Falta el token. Crea un archivo .env en la carpeta del proyecto con:\n"
        "   TELEGRAM_TOKEN=tu_token_nuevo"
    )
CANAL_SENALES_ID = -1003740408493
CANAL_ESTADISTICAS_ID = -1004218181454

# ── MESAS A MONITOREAR ──────────────────────────────────────
#   region    : (left, top, width, height) en píxeles de tu monitor
#   banner_roi: (x, y, w, h) RELATIVO a la region → donde sale "JUGADOR/BANCA/EMPATE"
MESAS = [
    {
        "nombre": "Baccarat 6",                  # mesa de la IZQUIERDA
        "region":     (88, 395, 430, 275),
        "banner_roi": (120, 50, 190, 50),
        "activa": True,
    },
    {
        "nombre": "Super 8 Baccarat",             # mesa del CENTRO
        "region":     (535, 395, 443, 275),
        "banner_roi": (123, 50, 197, 50),
        "activa": True,
    },
    {
        "nombre": "Baccarat 1",                   # mesa de la DERECHA
        "region":     (988, 395, 444, 275),
        "banner_roi": (123, 50, 198, 50),
        "activa": True,
    },
]

# ── DETECCIÓN ───────────────────────────────────────────────
INTERVALO_CAPTURA = 1.5         # segundos entre capturas (más bajo = atrapa mejor el banner)

CONFIRMAR_RESULTADO  = 4.0
PAUSA_PERDIDA_GLOBAL = 1800     # 30 minutos de pausa global tras una pérdida
COOLDOWN_RESULTADO   = 10.0     # mínimo entre dos resultados distintos

# ── MODO PRUEBA ─────────────────────────────────────────────
# True  = NO envía a Telegram (solo consola + carpeta prueba_envios/)
# False = operación normal (envía a Telegram)
MODO_PRUEBA = False

# Detección del banner: píxeles mínimos del color dominante y cuánto debe
# dominar un color sobre el otro para considerarlo un resultado válido.
UMBRAL_BANNER = 2000
DOMINANCIA_COLOR = 1.6

# ── ESPACIADO ENTRE SEÑALES (POR MESA, creciente con el tiempo) ─
# Cada mesa espera un tiempo aleatorio entre [min, max] DESPUÉS de que su
# apuesta se resuelve, antes de su siguiente señal. El rango crece con el tiempo.
ESPACIADO_MIN_INICIAL     = 45    # s — mínimo del rango al arrancar
ESPACIADO_MAX_INICIAL     = 120   # s — máximo del rango al arrancar
ESPACIADO_INCREMENTO_CADA = 900   # s — cada 15 minutos de ejecución...
ESPACIADO_INCREMENTO_SEG  = 30    # s — ...sube 30 s ambos extremos del rango
ESPACIADO_TOPE_MAX        = 300   # s — tope duro: nunca esperar más de 5 minutos
ESPACIADO_ANTIRRAFAGA     = 20    # s — mínimo entre señales de CUALQUIER mesa (0 = off)
