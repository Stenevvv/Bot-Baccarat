import asyncio
import logging
import time
import random
import sys
import os
import mss
import cv2
import numpy as np
import io
from PIL import Image, ImageDraw
from telegram import Bot
from telegram.error import TelegramError

# ══════════════════════════════════════════════════════════════
#  Toda la configuración vive ahora en config/settings.py
#  (token, canales, mesas, coordenadas y tiempos).
#  👉 Edita SOLO ese archivo para cambiar mesas o coordenadas.
# ══════════════════════════════════════════════════════════════
from config.settings import (
    TELEGRAM_TOKEN,
    CANAL_SENALES_ID,
    CANAL_ESTADISTICAS_ID,
    MESAS,
    INTERVALO_CAPTURA,
    CONFIRMAR_RESULTADO,
    PAUSA_PERDIDA_GLOBAL,
    COOLDOWN_RESULTADO,
    MODO_PRUEBA,
    UMBRAL_BANNER,
    DOMINANCIA_COLOR,
)

# ── Constantes ────────────────────────────────────────────────
JUGADOR = "JUGADOR"
BANCA   = "BANCA"
EMPATE  = "EMPATE"
PASOS   = 6

# ── 6 Patrones Martingala ─────────────────────────────────────
# Basados en tendencias reales del baccarat:
# J=Jugador (🔵)  B=Banca (🔴)
# Cada patrón tiene lógica propia explicada abajo
J = JUGADOR
B = BANCA

PATRONES = [
    # Patrón 1: Seguir tendencia — empezar con el último ganador 2 veces, luego alternar
    [J, J, B, B, J, B],
    # Patrón 2: Inverso — empezar con el opuesto al último ganador
    [B, B, J, J, B, J],
    # Patrón 3: Alternado puro empezando jugador
    [J, B, J, B, J, B],
    # Patrón 4: Alternado puro empezando banca
    [B, J, B, J, B, J],
    # Patrón 5: Rachas de 3
    [J, J, J, B, B, B],
    # Patrón 6: Rachas de 3 inverso
    [B, B, B, J, J, J],
]

# ── Logging ───────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("baccarat_bot.log"),
    ]
)
log = logging.getLogger("bot")

# ── Pausa global ──────────────────────────────────────────────
pausa_global_hasta = 0.0   # timestamp hasta donde todas las mesas pausan

def en_pausa_global():
    return time.time() < pausa_global_hasta

def activar_pausa_global():
    global pausa_global_hasta
    pausa_global_hasta = time.time() + PAUSA_PERDIDA_GLOBAL
    minutos = PAUSA_PERDIDA_GLOBAL // 60
    log.info("PAUSA GLOBAL activada — " + str(minutos) + " minutos sin señales")

# ── Emojis ────────────────────────────────────────────────────
def ec(r):
    if r == JUGADOR: return "🔵"
    if r == BANCA:   return "🔴"
    return "⚪"

def opuesto(r):
    return BANCA if r == JUGADOR else JUGADOR

# ── Selección de patrón ───────────────────────────────────────
def elegir_patron(historial, ultimo_resultado):
    """
    Elige el patrón más apropiado según el historial reciente.
    Lógica:
    - Si hay racha de 3+ del mismo color → usar patrón de racha opuesta
    - Si hay alternancia → usar patrón alternado
    - Si no hay patrón claro → aleatorio entre los 6
    Luego adapta el patrón al último resultado (rota J/B según corresponda)
    """
    validos = [r for r in historial if r != EMPATE]

    patron_base = None

    if len(validos) >= 3:
        ultimos3 = validos[-3:]
        # Racha de 3 del mismo → apostar al opuesto en patrón de racha
        if all(r == ultimos3[0] for r in ultimos3):
            if ultimos3[0] == JUGADOR:
                patron_base = PATRONES[5]  # rachas de 3 empezando banca
            else:
                patron_base = PATRONES[4]  # rachas de 3 empezando jugador
        else:
            # Verificar alternancia en últimas 4
            ultimos4 = validos[-4:] if len(validos) >= 4 else validos
            alternando = all(ultimos4[i] != ultimos4[i+1] for i in range(len(ultimos4)-1))
            if alternando:
                # Si alterna, seguir alternando desde el último
                if ultimo_resultado == JUGADOR:
                    patron_base = PATRONES[3]  # alternado empezando banca
                else:
                    patron_base = PATRONES[2]  # alternado empezando jugador

    # Si no se detectó patrón claro → aleatorio
    if patron_base is None:
        patron_base = random.choice(PATRONES)

    # Adaptar: si el último fue BANCA y el patrón empieza con JUGADOR → invertir
    # Esto orienta el patrón hacia la tendencia actual
    if ultimo_resultado == BANCA and patron_base[0] == JUGADOR:
        patron_adaptado = [opuesto(p) for p in patron_base]
    elif ultimo_resultado == JUGADOR and patron_base[0] == BANCA:
        patron_adaptado = [opuesto(p) for p in patron_base]
    else:
        patron_adaptado = patron_base[:]

    return patron_adaptado

# ── Captura ───────────────────────────────────────────────────
def capturar(region):
    left, top, w, h = region
    with mss.mss() as sct:
        mon = {"left": left, "top": top, "width": w, "height": h}
        shot = sct.grab(mon)
        img = np.array(shot)
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

def capturar_bytes(region):
    img = capturar(region)
    _, buf = cv2.imencode('.png', img)
    return buf.tobytes()

# ── Detección de banner (resultado) ───────────────────────────
def contar_banner(img, banner_roi):
    """Cuenta píxeles azules (Jugador) y rojos (Banca) dentro de la banner_roi."""
    x, y, w, h = banner_roi
    recorte = img[y:y+h, x:x+w]
    if recorte.size == 0:
        return 0, 0
    hsv = cv2.cvtColor(recorte, cv2.COLOR_BGR2HSV)

    # Azul (JUGADOR)
    mask_azul = cv2.inRange(hsv,
        np.array([100, 100, 80]),
        np.array([135, 255, 255]))

    # Rojo (BANCA) — dos rangos por wrap HSV
    mask_rojo1 = cv2.inRange(hsv, np.array([0, 100, 80]),  np.array([12, 255, 255]))
    mask_rojo2 = cv2.inRange(hsv, np.array([168,100, 80]), np.array([180,255,255]))
    mask_rojo  = cv2.bitwise_or(mask_rojo1, mask_rojo2)

    return cv2.countNonZero(mask_azul), cv2.countNonZero(mask_rojo)

def detectar_banner(img, banner_roi):
    """
    Detecta JUGADOR o BANCA por el color del banner de resultado.
    Solo cuenta como resultado si un color supera UMBRAL_BANNER y ADEMÁS
    domina al otro por un factor DOMINANCIA_COLOR (un banner real es casi
    todo de un color; el tablero de roads tiene azul y rojo mezclados).
    Retorna None si no hay un banner claro.
    """
    px_azul, px_rojo = contar_banner(img, banner_roi)

    if px_azul < UMBRAL_BANNER and px_rojo < UMBRAL_BANNER:
        return None   # nada destacado
    if px_azul > px_rojo * DOMINANCIA_COLOR:
        return JUGADOR
    if px_rojo > px_azul * DOMINANCIA_COLOR:
        return BANCA
    return None       # ambos altos pero ninguno domina → ambiguo, no es banner

def confirmar_resultado(region, banner_roi, intentos=4, espera=1.0):
    """
    Captura varias veces para confirmar que el banner está estable.
    Evita falsos positivos durante transiciones.
    Retorna el resultado si se confirma, None si no.
    """
    resultados = []
    for _ in range(intentos):
        img = capturar(region)
        r = detectar_banner(img, banner_roi)
        if r:
            resultados.append(r)
        time.sleep(espera)

    if not resultados:
        return None

    # Mayoría simple
    conteo = {JUGADOR: resultados.count(JUGADOR), BANCA: resultados.count(BANCA)}
    ganador = max(conteo, key=conteo.get)
    if conteo[ganador] >= (intentos // 2 + 1):
        return ganador
    return None

# ── Creación de imágenes ──────────────────────────────────────
def crear_img_senal(cap_bytes, nombre, patron):
    """
    Imagen de señal:
    - Captura real del banner del resultado anterior
    - Nombre de la mesa
    - Patrón de 6 pasos (sin texto extra)
    """
    img = Image.open(io.BytesIO(cap_bytes)).convert("RGB")
    draw = ImageDraw.Draw(img)
    w, h = img.size

    # Barra superior con nombre de mesa
    draw.rectangle([0, 0, w, 30], fill=(10, 10, 20))
    draw.text((w//2, 15), nombre, fill=(220, 220, 220), anchor="mm")

    # Barra inferior con el patrón
    draw.rectangle([0, h-38, w, h], fill=(0, 0, 0))
    seq = "  ".join(str(i+1)+"."+ec(p) for i, p in enumerate(patron))
    draw.text((w//2, h-19), seq, fill=(255, 255, 255), anchor="mm")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def crear_img_stats(cap_bytes, nombre, patron, paso_acierto):
    """
    Imagen de estadísticas:
    - Captura real del banner ganador (limpia, sin overlay)
    - Solo nombre de mesa arriba
    - Sin texto encima del banner
    """
    img = Image.open(io.BytesIO(cap_bytes)).convert("RGB")
    draw = ImageDraw.Draw(img)
    w, h = img.size

    # Solo barra superior con nombre
    draw.rectangle([0, 0, w, 30], fill=(10, 10, 20))
    draw.text((w//2, 15), nombre, fill=(220, 220, 220), anchor="mm")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

# ── Telegram ──────────────────────────────────────────────────
async def enviar_foto(bot, chat_id, img_bytes, caption):
    if MODO_PRUEBA:
        os.makedirs("prueba_envios", exist_ok=True)
        nombre_arch = "prueba_envios/" + str(chat_id) + "_" + time.strftime("%H%M%S") + ".png"
        with open(nombre_arch, "wb") as f:
            f.write(img_bytes)
        log.info("[PRUEBA] (NO enviado a Telegram) imagen -> " + nombre_arch)
        log.info("[PRUEBA] caption:\n" + caption)
        return True
    try:
        await bot.send_photo(
            chat_id=chat_id,
            photo=io.BytesIO(img_bytes),
            caption=caption,
            parse_mode="Markdown"
        )
        return True
    except TelegramError as e:
        log.error("Error Telegram foto: " + str(e))
        return False

async def enviar_texto(bot, chat_id, texto):
    if MODO_PRUEBA:
        log.info("[PRUEBA] (NO enviado a Telegram) texto: " + texto)
        return True
    try:
        await bot.send_message(chat_id=chat_id, text=texto, parse_mode="Markdown")
        return True
    except TelegramError as e:
        log.error("Error Telegram texto: " + str(e))
        return False

# ── Caption de señal ──────────────────────────────────────────
def caption_senal(nombre, patron):
    seq = "  ".join(str(i+1)+"."+ec(p) for i, p in enumerate(patron))
    return "🃏 *" + nombre + "*\n\n" + seq

def caption_ganada(nombre, patron, paso):
    partes = []
    for i, p in enumerate(patron):
        marca = "✅" if i+1 == paso else ""
        partes.append(str(i+1)+"."+ec(p)+marca)
    seq = "  ".join(partes)
    return "🃏 *" + nombre + "*\n\n" + seq + "\n\n✅ *GANADA* — Acierto en el intento " + str(paso)

def caption_perdida(nombre, patron):
    seq = "  ".join(str(i+1)+"."+ec(p)+"❌" for i, p in enumerate(patron))
    return "🃏 *" + nombre + "*\n\n" + seq + "\n\n❌ *PERDIDA* — Sin aciertos en 6 intentos"

# ── Detector de cambio ────────────────────────────────────────
class DetectorCambio:
    def __init__(self):
        self._ultimo = None
        self._t = 0.0

    def es_nuevo(self, r):
        if r is None:
            return False
        ahora = time.time()
        if r == self._ultimo and (ahora - self._t) < COOLDOWN_RESULTADO:
            return False
        self._ultimo = r
        self._t = ahora
        return True

# ── Loop de una mesa ──────────────────────────────────────────
async def loop_mesa(mesa_cfg, bot, estado, detector):
    nombre      = mesa_cfg["nombre"]
    region      = mesa_cfg["region"]
    banner_roi  = mesa_cfg["banner_roi"]

    log.info("▶ Iniciando mesa: " + nombre)

    # Estado inicial
    historial   = estado["historial"]
    patron      = estado["patron"]
    paso        = estado["paso"]      # paso actual en la secuencia (1-6)
    en_secuencia = estado["en_secuencia"]  # True si ya se envió señal y esperamos resultado

    while True:
        try:
            await asyncio.sleep(INTERVALO_CAPTURA)

            # ── Pausa global ──────────────────────────────────
            if en_pausa_global():
                restante = int(pausa_global_hasta - time.time())
                if restante % 60 == 0:
                    log.info("[" + nombre + "] En pausa global — " + str(restante//60) + " min restantes")
                continue

            # ── Capturar y detectar ───────────────────────────
            img_bgr = capturar(region)
            if MODO_PRUEBA:
                _pa, _pr = contar_banner(img_bgr, banner_roi)
                log.info("[%s] azul=%d rojo=%d" % (nombre, _pa, _pr))
            resultado_raw = detectar_banner(img_bgr, banner_roi)

            if not detector.es_nuevo(resultado_raw):
                continue

            # ── Confirmar resultado estable ───────────────────
            log.info("[" + nombre + "] Banner detectado: " + str(resultado_raw) + " — confirmando...")
            resultado = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: confirmar_resultado(region, banner_roi, intentos=3, espera=1.2)
            )

            if resultado is None:
                log.info("[" + nombre + "] No confirmado — ignorando")
                continue

            if resultado == EMPATE:
                log.info("[" + nombre + "] Empate — sin acción")
                historial.append(EMPATE)
                continue

            log.info("[" + nombre + "] Resultado confirmado: " + resultado)
            historial.append(resultado)

            # Captura limpia del banner para usar en mensajes
            cap = capturar_bytes(region)

            # ── ¿Estamos en una secuencia activa? ─────────────
            if en_secuencia and patron and paso <= PASOS:
                prediccion = patron[paso - 1]
                acerto = prediccion == resultado

                if acerto:
                    # ── GANADA ────────────────────────────────
                    log.info("[" + nombre + "] GANADA en intento " + str(paso))
                    img_stats = crear_img_stats(cap, nombre, patron, paso)
                    await enviar_foto(bot, CANAL_ESTADISTICAS_ID, img_stats,
                                      caption_ganada(nombre, patron, paso))
                    # Reset secuencia
                    en_secuencia = False
                    paso = 1

                elif paso >= PASOS:
                    # ── PERDIDA ───────────────────────────────
                    log.info("[" + nombre + "] PERDIDA — activando pausa global 30 min")
                    img_stats = crear_img_stats(cap, nombre, patron, paso)
                    await enviar_foto(bot, CANAL_ESTADISTICAS_ID, img_stats,
                                      caption_perdida(nombre, patron))
                    activar_pausa_global()
                    en_secuencia = False
                    paso = 1
                    # Guardar estado
                    estado["historial"]    = historial
                    estado["patron"]       = patron
                    estado["paso"]         = paso
                    estado["en_secuencia"] = en_secuencia
                    continue

                else:
                    # ── SIGUIENTE PASO ────────────────────────
                    paso += 1
                    log.info("[" + nombre + "] Fallo → ahora en paso " + str(paso))
                    estado["paso"] = paso
                    continue

            # ── Nueva señal ───────────────────────────────────
            # Elegir patrón basado en historial y último resultado
            patron = elegir_patron(historial, resultado)
            paso = 1
            en_secuencia = True

            log.info("[" + nombre + "] Nueva señal — patrón: " +
                     " ".join(ec(p) for p in patron))

            # Captura con el banner del resultado recién terminado
            img_senal = crear_img_senal(cap, nombre, patron)
            await enviar_foto(bot, CANAL_SENALES_ID, img_senal,
                              caption_senal(nombre, patron))
            log.info("[" + nombre + "] Señal enviada")

            # Guardar estado
            estado["historial"]    = historial
            estado["patron"]       = patron
            estado["paso"]         = paso
            estado["en_secuencia"] = en_secuencia

        except Exception as e:
            log.error("Error en " + nombre + ": " + str(e), exc_info=True)
            await asyncio.sleep(5)

# ── Main ──────────────────────────────────────────────────────
async def main():
    print("=" * 55)
    print("  BACCARAT BOT v2 — Rushbet Pragmatic Play")
    print("=" * 55)

    bot = Bot(token=TELEGRAM_TOKEN)
    if MODO_PRUEBA:
        print("🧪 MODO PRUEBA ACTIVO — NO se enviará nada a Telegram.")
        print("   (Las imágenes que enviaría se guardan en la carpeta prueba_envios/)")
        try:
            me = await bot.get_me()
            print("✅ Token válido: @" + me.username)
        except TelegramError as e:
            print("⚠ No se pudo verificar el token (no importa en modo prueba): " + str(e))
    else:
        try:
            me = await bot.get_me()
            print("✅ Bot conectado: @" + me.username)
        except TelegramError as e:
            print("❌ Error conectando: " + str(e))
            return

    mesas_activas = [m for m in MESAS if m.get("activa", True)]
    print("📋 Mesas: " + ", ".join(m["nombre"] for m in mesas_activas))
    print("⏱  Intervalo: " + str(INTERVALO_CAPTURA) + "s")
    print("⏸  Pausa tras pérdida: 30 minutos globales")
    print("\n🚀 Monitoreando — minimiza esta ventana y deja Rushbet al frente\n")

    # Estado inicial por mesa
    estados    = {}
    detectores = {}
    for m in mesas_activas:
        estados[m["nombre"]] = {
            "historial":    [],
            "patron":       [],
            "paso":         1,
            "en_secuencia": False,
        }
        detectores[m["nombre"]] = DetectorCambio()

    tasks = [
        loop_mesa(m, bot, estados[m["nombre"]], detectores[m["nombre"]])
        for m in mesas_activas
    ]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⛔ Bot detenido")
