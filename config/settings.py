# ============================================================
#  BACCARAT BOT - CONFIGURACIÓN PRINCIPAL
#  Edita este archivo antes de correr el bot
# ============================================================

# ── TELEGRAM ────────────────────────────────────────────────
TELEGRAM_TOKEN = "8767073134:AAGWZYUZmG4k3UHVteYe7gRrl2Njkvn89yc"
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

MESAS = [
    {
        "nombre": "Baccarat 2",
        "region":     (50, 305, 365, 230),
        "banner_roi": (0, 38, 365, 50),
        "activa": True,
    },
    {
        "nombre": "Super 8 Baccarat",
        "region":     (420, 305, 360, 230),
        "banner_roi": (0, 38, 360, 50),
        "activa": True,
    },
    {
        "nombre": "Baccarat 5",
        "region":     (785, 305, 345, 230),
        "banner_roi": (0, 38, 345, 50),
        "activa": True,
    },
]

# ── DETECCIÓN ───────────────────────────────────────────────
# Intervalo entre capturas en segundos
INTERVALO_CAPTURA = 3.0

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
