# ============================================================
#  BACCARAT BOT - CONFIGURACIÓN PRINCIPAL
#  Edita este archivo antes de correr el bot
# ============================================================
import os

# ── Cargador simple de archivo .env ─────────────────────────
# Lee un archivo llamado ".env" en la raíz del proyecto (junto a main.py)
# y carga sus variables. El archivo .env está en .gitignore, así que
# NUNCA se sube a GitHub. Formato del .env:
#     TELEGRAM_TOKEN=123456:ABC-tu_token
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
# ⚠️ SEGURIDAD: el token NO se escribe aquí. Se lee del archivo .env
# (o de una variable de entorno TELEGRAM_TOKEN).
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
if not TELEGRAM_TOKEN:
    raise SystemExit(
        "❌ Falta el token. Crea un archivo .env en la carpeta del proyecto con:\n"
        "   TELEGRAM_TOKEN=tu_token_nuevo"
    )
CANAL_SENALES_ID = -1003740408493
CANAL_ESTADISTICAS_ID = -1004218181454

# ── MESAS A MONITOREAR ──────────────────────────────────────
# Cada mesa tiene:
#   nombre    : string identificador
#   region    : (left, top, width, height) en píxeles de tu monitor
#               → la región donde está esa mesa en el navegador
#   banner_roi: (x, y, w, h) RELATIVO a la region → donde aparece "BANCA"/"JUGADOR"
#   score_roi : (x, y, w, h) RELATIVO a la region → donde están los puntos (opcional)
#
# ⚠️  Debes calibrar estas coordenadas con calibrar_coordenadas.py
#     antes de correr el bot por primera vez

# ⚠️ COORDENADAS ESTIMADAS a partir de la captura (pantalla 1920x1080,
#    vista "Baccarat Multiplay" a pantalla completa).
#    Hay que VERIFICARLAS con calibrar_coordenadas.py (ver guía paso a paso).
MESAS = [
    {
        "nombre": "Baccarat 6",                  # mesa de la IZQUIERDA
        "region":     (88, 395, 430, 275),        # (left, top, width, height)
        "banner_roi": (120, 50, 190, 50),         # banner "JUGADOR"/"BANCA": franja ARRIBA, al centro
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
# Intervalo entre capturas en segundos
INTERVALO_CAPTURA = 3.0

# Tiempos adicionales usados por main.py (en segundos)
CONFIRMAR_RESULTADO  = 4.0     # espera para confirmar que el banner es estable
PAUSA_PERDIDA_GLOBAL = 1800    # 30 minutos de pausa global tras una pérdida
COOLDOWN_RESULTADO   = 10.0    # mínimo entre dos resultados distintos

# ── MODO PRUEBA ─────────────────────────────────────────────
# True  = el bot NO envía nada a Telegram. Solo escribe en consola lo que
#         detecta y guarda localmente (carpeta prueba_envios/) las imágenes
#         que enviaría. Sirve para verificar la detección sin llenar el canal.
# False = operación normal (envía a Telegram).
MODO_PRUEBA = True

# Umbral de detección del banner (píxeles del color dominante) y cuánto debe
# dominar un color sobre el otro para considerar un resultado válido.
UMBRAL_BANNER = 2000
DOMINANCIA_COLOR = 1.6

# ── ESPACIADO ENTRE SEÑALES (POR MESA, creciente con el tiempo) ─
# El espaciado es INDIVIDUAL por mesa: cada mesa espera un tiempo ALEATORIO
# entre [min, max] segundos antes de su PROPIA siguiente señal. Además ese rango
# CRECE con el tiempo que lleva corriendo el bot (más activo al inicio, más
# calmado luego), con tope duro. Y hay un anti-ráfaga global para que no salgan
# dos señales casi pegadas aunque sean de mesas distintas.
ESPACIADO_MIN_INICIAL     = 45    # s — mínimo del rango al arrancar (45 segundos)
ESPACIADO_MAX_INICIAL     = 120   # s — máximo del rango al arrancar (2 minutos)
ESPACIADO_INCREMENTO_CADA = 900   # s — cada 15 minutos de ejecución...
ESPACIADO_INCREMENTO_SEG  = 30    # s — ...sube 30 s ambos extremos del rango
ESPACIADO_TOPE_MAX        = 300   # s — tope duro: nunca esperar más de 5 minutos
ESPACIADO_ANTIRRAFAGA     = 20    # s — mínimo entre señales de CUALQUIER mesa (0 = desactivado)

# Umbral de confianza del OCR (0.0 - 1.0)
OCR_CONFIANZA_MINIMA = 0.5

# Colores del banner (HSV) para detección por color como backup
# Azul = Jugador  |  Rojo = Banca
COLOR_JUGADOR_HSV_BAJO  = (100, 120, 100)   # azul oscuro
COLOR_JUGADOR_HSV_ALTO  = (130, 255, 255)
COLOR_BANCA_HSV_BAJO    = (0,   120, 100)   # rojo
COLOR_BANCA_HSV_ALTO    = (10,  255, 255)
COLOR_BANCA_HSV_BAJO2   = (170, 120, 100)   # rojo (wrap)
COLOR_BANCA_HSV_ALTO2   = (180, 255, 255)

# Píxeles mínimos de color para considerar el banner activo
COLOR_MIN_PIXELES = 1500

# ── MARTINGALA / SECUENCIA ──────────────────────────────────
PASOS_SECUENCIA = 6                         # siempre 6

# Estrategia de predicción: "ultimo" | "frecuencia" | "alternado"
#   ultimo      → repite el último resultado
#   frecuencia  → elige el más frecuente en las últimas N manos
#   alternado   → alterna el último resultado
ESTRATEGIA = "frecuencia"
VENTANA_FRECUENCIA = 8                      # últimas N manos para frecuencia

# ── OVERLAYS / IMÁGENES ─────────────────────────────────────
# Tamaño del overlay de resultado pegado sobre la captura
OVERLAY_ALTO   = 60
OVERLAY_FONT_SIZE = 28

# Directorio temporal para guardar capturas antes de enviar
CAPTURAS_DIR = "/tmp/baccarat_capturas"
