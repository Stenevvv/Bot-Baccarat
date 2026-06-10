"""
Captura de pantalla y detección de resultado
Para las mesas de Pragmatic Play en Rushbet (Super 8, Baccarat 2, Baccarat 5)

Estrategia dual:
  1. OCR con EasyOCR → lee el texto "BANCA" / "JUGADOR" del banner
  2. Detección de color como fallback → analiza el color dominante del banner
"""
import cv2
import numpy as np
import mss
import easyocr
from PIL import Image, ImageDraw, ImageFont
import io
import os
import time
from datetime import datetime

from config.settings import (
    COLOR_JUGADOR_HSV_BAJO, COLOR_JUGADOR_HSV_ALTO,
    COLOR_BANCA_HSV_BAJO,   COLOR_BANCA_HSV_ALTO,
    COLOR_BANCA_HSV_BAJO2,  COLOR_BANCA_HSV_ALTO2,
    COLOR_MIN_PIXELES, OCR_CONFIANZA_MINIMA, CAPTURAS_DIR
)

JUGADOR = "JUGADOR"
BANCA   = "BANCA"
EMPATE  = "EMPATE"
SIN_CAMBIO = None   # no hubo nuevo resultado

# Inicializar OCR una sola vez (es costoso)
_reader = None

def get_reader():
    global _reader
    if _reader is None:
        print("Cargando EasyOCR (primera vez, puede tardar ~30s)...")
        _reader = easyocr.Reader(['es', 'en'], gpu=False)
    return _reader


# ── Captura ───────────────────────────────────────────────────

def capturar_region(region: tuple) -> np.ndarray:
    """
    Captura una región de pantalla.
    region = (left, top, width, height)
    Retorna imagen BGR (numpy array)
    """
    left, top, width, height = region
    with mss.mss() as sct:
        monitor = {"left": left, "top": top, "width": width, "height": height}
        screenshot = sct.grab(monitor)
        img = np.array(screenshot)
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)


def capturar_a_bytes(region: tuple) -> bytes:
    """Captura región y retorna como bytes PNG (para Telegram)"""
    img = capturar_region(region)
    _, buffer = cv2.imencode('.png', img)
    return buffer.tobytes()


# ── Detección de resultado ────────────────────────────────────

def detectar_resultado_ocr(img_bgr: np.ndarray, banner_roi: tuple) -> str | None:
    """
    Recorta la zona del banner y usa OCR para leer BANCA/JUGADOR.
    banner_roi = (x, y, w, h) RELATIVO a img_bgr
    """
    x, y, w, h = banner_roi
    recorte = img_bgr[y:y+h, x:x+w]

    # Preprocesamiento: aumentar contraste para el OCR
    recorte_gray = cv2.cvtColor(recorte, cv2.COLOR_BGR2GRAY)
    recorte_proc = cv2.convertScaleAbs(recorte_gray, alpha=2.0, beta=0)

    reader = get_reader()
    resultados = reader.readtext(recorte_proc, detail=1)

    for (bbox, texto, conf) in resultados:
        if conf < OCR_CONFIANZA_MINIMA:
            continue
        texto_upper = texto.upper().strip()
        if "JUGADOR" in texto_upper or "PLAYER" in texto_upper:
            return JUGADOR
        if "BANCA" in texto_upper or "BANKER" in texto_upper:
            return BANCA
        if "EMPATE" in texto_upper or "TIE" in texto_upper:
            return EMPATE

    return None


def detectar_resultado_color(img_bgr: np.ndarray, banner_roi: tuple) -> str | None:
    """
    Fallback: detecta por color del banner iluminado.
    Azul dominante → JUGADOR  |  Rojo dominante → BANCA
    """
    x, y, w, h = banner_roi
    recorte = img_bgr[y:y+h, x:x+w]
    hsv = cv2.cvtColor(recorte, cv2.COLOR_BGR2HSV)

    # Máscara azul (JUGADOR)
    mask_azul = cv2.inRange(
        hsv,
        np.array(COLOR_JUGADOR_HSV_BAJO),
        np.array(COLOR_JUGADOR_HSV_ALTO)
    )

    # Máscara roja (BANCA) - dos rangos por el wrap del rojo en HSV
    mask_rojo1 = cv2.inRange(
        hsv,
        np.array(COLOR_BANCA_HSV_BAJO),
        np.array(COLOR_BANCA_HSV_ALTO)
    )
    mask_rojo2 = cv2.inRange(
        hsv,
        np.array(COLOR_BANCA_HSV_BAJO2),
        np.array(COLOR_BANCA_HSV_ALTO2)
    )
    mask_rojo = cv2.bitwise_or(mask_rojo1, mask_rojo2)

    pixeles_azul = cv2.countNonZero(mask_azul)
    pixeles_rojo = cv2.countNonZero(mask_rojo)

    if pixeles_azul < COLOR_MIN_PIXELES and pixeles_rojo < COLOR_MIN_PIXELES:
        return None  # banner no iluminado / mano en curso

    if pixeles_azul > pixeles_rojo:
        return JUGADOR
    return BANCA


def detectar_resultado(img_bgr: np.ndarray, banner_roi: tuple) -> str | None:
    """
    Intenta OCR primero, luego color como fallback.
    Retorna JUGADOR | BANCA | EMPATE | None (sin resultado todavía)
    """
    resultado = detectar_resultado_ocr(img_bgr, banner_roi)
    if resultado is not None:
        return resultado

    return detectar_resultado_color(img_bgr, banner_roi)


# ── Detección de cambio (evita duplicados) ────────────────────

class DetectorCambio:
    """
    Detecta si el resultado de una mano cambió respecto al anterior.
    Evita enviar el mismo resultado varias veces mientras el banner
    sigue iluminado.
    """
    def __init__(self):
        self._ultimo: str | None = None
        self._tiempo_ultimo: float = 0
        self.COOLDOWN = 8.0   # segundos mínimos entre resultados distintos

    def nuevo_resultado(self, resultado: str | None) -> str | None:
        """
        Retorna el resultado si es NUEVO (distinto al último),
        o None si es el mismo o no hay resultado.
        """
        if resultado is None:
            return None

        ahora = time.time()
        if resultado == self._ultimo and (ahora - self._tiempo_ultimo) < self.COOLDOWN:
            return None   # mismo resultado dentro del cooldown → ignorar

        self._ultimo = resultado
        self._tiempo_ultimo = ahora
        return resultado


# ── Composición de imagen ─────────────────────────────────────

def crear_imagen_senal(
    captura_bytes: bytes,
    nombre_mesa: str,
    secuencia: list[str],
    paso_actual: int,
) -> bytes:
    """
    Crea la imagen de SEÑAL:
    - captura de la mesa
    - nombre de la mesa arriba
    - secuencia de círculos abajo: 1.🔵 2.🔴 ...
    """
    img = Image.open(io.BytesIO(captura_bytes)).convert("RGB")
    draw = ImageDraw.Draw(img)

    # Fondo semitransparente en la parte inferior para el texto
    w, h = img.size
    overlay = Image.new("RGBA", (w, 60), (0, 0, 0, 160))
    img_rgba = img.convert("RGBA")
    img_rgba.paste(overlay, (0, h - 60), overlay)
    img = img_rgba.convert("RGB")
    draw = ImageDraw.Draw(img)

    # Nombre de la mesa (arriba)
    draw.rectangle([0, 0, w, 30], fill=(20, 20, 20, 200))
    draw.text((10, 6), nombre_mesa, fill=(255, 255, 255))

    # Secuencia (abajo)
    emojis = {"JUGADOR": "🔵", "BANCA": "🔴"}
    partes = []
    for i, pred in enumerate(secuencia, start=1):
        marcado = "→" if i == paso_actual else ""
        partes.append(f"{marcado}{i}.{emojis.get(pred,'?')}")
    texto_seq = "  ".join(partes)
    draw.text((10, h - 50), texto_seq, fill=(255, 255, 255))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def crear_imagen_resultado(
    captura_bytes: bytes,
    nombre_mesa: str,
    tipo: str,          # "acierto" | "perdida"
    paso: int,
    secuencia: list[str],
) -> bytes:
    """
    Crea la imagen de RESULTADO:
    - captura de la mesa
    - overlay verde (GANADA) o rojo (PERDIDA) con texto grande
    """
    img = Image.open(io.BytesIO(captura_bytes)).convert("RGB")
    draw = ImageDraw.Draw(img)
    w, h = img.size

    if tipo == "acierto":
        color_overlay = (0, 160, 60, 200)
        texto = f"GANADA ✅  Acierto en el intento {paso}"
    else:
        color_overlay = (180, 20, 20, 200)
        texto = "PERDIDA ❌  Sin aciertos"

    overlay = Image.new("RGBA", (w, 70), color_overlay)
    img_rgba = img.convert("RGBA")
    img_rgba.paste(overlay, (0, h // 2 - 35), overlay)
    img = img_rgba.convert("RGB")
    draw = ImageDraw.Draw(img)

    # Texto de resultado
    draw.text((w // 2, h // 2), texto, fill=(255, 255, 255), anchor="mm")

    # Nombre de mesa arriba
    draw.rectangle([0, 0, w, 28], fill=(20, 20, 20))
    draw.text((8, 6), nombre_mesa, fill=(220, 220, 220))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ── Guardado temporal ─────────────────────────────────────────

def guardar_captura(img_bytes: bytes, nombre: str) -> str:
    """Guarda captura en disco temporal para debug"""
    os.makedirs(CAPTURAS_DIR, exist_ok=True)
    ts = datetime.now().strftime("%H%M%S")
    path = os.path.join(CAPTURAS_DIR, f"{nombre}_{ts}.png")
    with open(path, "wb") as f:
        f.write(img_bytes)
    return path
