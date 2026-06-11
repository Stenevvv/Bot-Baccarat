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
#  Toda la configuración vive en config/settings.py
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
    ESPACIADO_MIN_INICIAL,
    ESPACIADO_MAX_INICIAL,
    ESPACIADO_INCREMENTO_CADA,
    ESPACIADO_INCREMENTO_SEG,
    ESPACIADO_TOPE_MAX,
    ESPACIADO_ANTIRRAFAGA,
)

# ── Constantes ────────────────────────────────────────────────
JUGADOR = "JUGADOR"
BANCA   = "BANCA"
EMPATE  = "EMPATE"
PASOS   = 6

J = JUGADOR
B = BANCA

PATRONES = [
    [J, J, B, B, J, B],
    [B, B, J, J, B, J],
    [J, B, J, B, J, B],
    [B, J, B, J, B, J],
    [J, J, J, B, B, B],
    [B, B, B, J, J, J],
]

# ── Logging (UTF-8 para que la consola de Windows no falle con emojis) ─
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("baccarat_bot.log", encoding="utf-8"),
    ]
)
log = logging.getLogger("bot")

# ── Pausa global ──────────────────────────────────────────────
pausa_global_hasta = 0.0

def en_pausa_global():
    return time.time() < pausa_global_hasta

def activar_pausa_global():
    global pausa_global_hasta
    pausa_global_hasta = time.time() + PAUSA_PERDIDA_GLOBAL
    minutos = PAUSA_PERDIDA_GLOBAL // 60
    log.info("PAUSA GLOBAL activada — " + str(minutos) + " minutos sin señales")

# ── Espaciado entre señales (POR MESA, creciente; arranca al RESOLVERSE) ─
tiempo_inicio = time.time()
proxima_senal_por_mesa = {}
proxima_senal_global = 0.0

def _rango_espaciado_actual():
    transcurrido = time.time() - tiempo_inicio
    pasos = int(transcurrido // ESPACIADO_INCREMENTO_CADA)
    lo = min(ESPACIADO_MIN_INICIAL + pasos * ESPACIADO_INCREMENTO_SEG, ESPACIADO_TOPE_MAX)
    hi = min(ESPACIADO_MAX_INICIAL + pasos * ESPACIADO_INCREMENTO_SEG, ESPACIADO_TOPE_MAX)
    if lo >= hi:
        lo = max(ESPACIADO_MIN_INICIAL, hi - 15)
    return lo, hi

def senal_permitida(nombre):
    ahora = time.time()
    if ahora < proxima_senal_global:
        return False
    return ahora >= proxima_senal_por_mesa.get(nombre, 0.0)

def marcar_antirrafaga():
    global proxima_senal_global
    if ESPACIADO_ANTIRRAFAGA > 0:
        proxima_senal_global = time.time() + ESPACIADO_ANTIRRAFAGA

def iniciar_lapso_mesa(nombre):
    lo, hi = _rango_espaciado_actual()
    espera = random.uniform(lo, hi)
    proxima_senal_por_mesa[nombre] = time.time() + espera
    log.info("[%s] Apuesta resuelta - proxima senal de esta mesa en ~%ds (rango %d-%ds)"
             % (nombre, int(espera), int(lo), int(hi)))

# ── Emojis ────────────────────────────────────────────────────
def ec(r):
    if r == JUGADOR: return "🔵"
    if r == BANCA:   return "🔴"
    return "⚪"

def opuesto(r):
    return BANCA if r == JUGADOR else JUGADOR

# ── Selección de patrón ───────────────────────────────────────
def elegir_patron(historial, ultimo_resultado):
    validos = [r for r in historial if r != EMPATE]
    patron_base = None
    if len(validos) >= 3:
        ultimos3 = validos[-3:]
        if all(r == ultimos3[0] for r in ultimos3):
            if ultimos3[0] == JUGADOR:
                patron_base = PATRONES[5]
            else:
                patron_base = PATRONES[4]
        else:
            ultimos4 = validos[-4:] if len(validos) >= 4 else validos
            alternando = all(ultimos4[i] != ultimos4[i+1] for i in range(len(ultimos4)-1))
            if alternando:
                if ultimo_resultado == JUGADOR:
                    patron_base = PATRONES[3]
                else:
                    patron_base = PATRONES[2]
    if patron_base is None:
        patron_base = random.choice(PATRONES)
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
    """Cuenta píxeles azul (Jugador), rojo (Banca) y verde (Empate) en la ROI."""
    x, y, w, h = banner_roi
    recorte = img[y:y+h, x:x+w]
    if recorte.size == 0:
        return 0, 0, 0
    hsv = cv2.cvtColor(recorte, cv2.COLOR_BGR2HSV)
    mask_azul = cv2.inRange(hsv, np.array([100, 100, 80]), np.array([135, 255, 255]))
    mask_rojo1 = cv2.inRange(hsv, np.array([0, 100, 80]),  np.array([12, 255, 255]))
    mask_rojo2 = cv2.inRange(hsv, np.array([168,100, 80]), np.array([180,255,255]))
    mask_rojo  = cv2.bitwise_or(mask_rojo1, mask_rojo2)
    mask_verde = cv2.inRange(hsv, np.array([40, 80, 60]), np.array([90, 255, 255]))
    return cv2.countNonZero(mask_azul), cv2.countNonZero(mask_rojo), cv2.countNonZero(mask_verde)

def detectar_banner(img, banner_roi):
    """JUGADOR (azul) / BANCA (rojo) / EMPATE (verde) / None (sin banner)."""
    px_azul, px_rojo, px_verde = contar_banner(img, banner_roi)
    # Empate (verde dominante) — es un PUSH: ni gana ni pierde
    if px_verde > UMBRAL_BANNER and px_verde > px_azul and px_verde > px_rojo:
        return EMPATE
    if px_azul < UMBRAL_BANNER and px_rojo < UMBRAL_BANNER:
        return None
    if px_azul > px_rojo * DOMINANCIA_COLOR:
        return JUGADOR
    if px_rojo > px_azul * DOMINANCIA_COLOR:
        return BANCA
    return None

def confirmar_resultado(region, banner_roi, intentos=3, espera=0.4):
    """Confirma rápido (mientras el banner sigue visible). Devuelve el más frecuente."""
    resultados = []
    for _ in range(intentos):
        img = capturar(region)
        r = detectar_banner(img, banner_roi)
        if r:
            resultados.append(r)
        time.sleep(espera)
    if not resultados:
        return None
    return max(set(resultados), key=resultados.count)

# ── Creación de imágenes ──────────────────────────────────────
def crear_img_senal(cap_bytes, nombre, patron):
    img = Image.open(io.BytesIO(cap_bytes)).convert("RGB")
    w, h = img.size
    img = img.crop((0, 0, w, h - 38))   # recorta la franja inferior (1000 COP / ID)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def crear_img_stats(cap_bytes, nombre, patron, paso_acierto):
    """Captura tal cual (con el nombre ORIGINAL de la mesa y el banner ganador)."""
    img = Image.open(io.BytesIO(cap_bytes)).convert("RGB")
    w, h = img.size
    img = img.crop((0, 0, w, h - 38))   # recorta la franja inferior (1000 COP / ID)
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
        log.info("[PRUEBA] caption: " + caption.replace(chr(10), " | "))
        return True
    try:
        await bot.send_photo(chat_id=chat_id, photo=io.BytesIO(img_bytes),
                             caption=caption, parse_mode="Markdown")
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

# ── Captions ──────────────────────────────────────────────────
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
    historial   = estado["historial"]
    patron      = estado["patron"]
    paso        = estado["paso"]
    en_secuencia = estado["en_secuencia"]

    while True:
        try:
            await asyncio.sleep(INTERVALO_CAPTURA)

            if en_pausa_global():
                restante = int(pausa_global_hasta - time.time())
                if restante % 60 == 0:
                    log.info("[" + nombre + "] En pausa global — " + str(restante//60) + " min restantes")
                continue

            img_bgr = capturar(region)
            if MODO_PRUEBA:
                _pa, _pr, _pv = contar_banner(img_bgr, banner_roi)
                log.info("[%s] azul=%d rojo=%d verde=%d" % (nombre, _pa, _pr, _pv))
            resultado_raw = detectar_banner(img_bgr, banner_roi)

            if not detector.es_nuevo(resultado_raw):
                continue

            log.info("[" + nombre + "] Banner detectado: " + str(resultado_raw) + " — confirmando...")
            resultado = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: confirmar_resultado(region, banner_roi, intentos=3, espera=0.4)
            )

            if resultado is None:
                log.info("[" + nombre + "] No confirmado — ignorando")
                continue

            # ── EMPATE: es un PUSH. No gana ni pierde, NO avanza el movimiento ─
            if resultado == EMPATE:
                log.info("[%s] EMPATE — push: no gana ni pierde, se mantiene el movimiento %d" % (nombre, paso))
                historial.append(EMPATE)
                continue

            log.info("[" + nombre + "] Resultado confirmado: " + resultado)
            historial.append(resultado)

            # Reusar el frame que YA detectó el banner para que la imagen
            # SIEMPRE muestre el banner del color ganador.
            _ok, _buf = cv2.imencode('.png', img_bgr)
            cap = _buf.tobytes() if _ok else capturar_bytes(region)

            if en_secuencia and patron and paso <= PASOS:
                prediccion = patron[paso - 1]
                acerto = prediccion == resultado
                if acerto:
                    log.info("[" + nombre + "] GANADA en intento " + str(paso))
                    img_stats = crear_img_stats(cap, nombre, patron, paso)
                    await enviar_foto(bot, CANAL_ESTADISTICAS_ID, img_stats,
                                      caption_ganada(nombre, patron, paso))
                    en_secuencia = False
                    paso = 1
                    iniciar_lapso_mesa(nombre)
                elif paso >= PASOS:
                    log.info("[" + nombre + "] PERDIDA — activando pausa global 30 min")
                    img_stats = crear_img_stats(cap, nombre, patron, paso)
                    await enviar_foto(bot, CANAL_ESTADISTICAS_ID, img_stats,
                                      caption_perdida(nombre, patron))
                    activar_pausa_global()
                    en_secuencia = False
                    paso = 1
                    iniciar_lapso_mesa(nombre)
                    estado["historial"]    = historial
                    estado["patron"]       = patron
                    estado["paso"]         = paso
                    estado["en_secuencia"] = en_secuencia
                    continue
                else:
                    paso += 1
                    log.info("[" + nombre + "] Fallo → ahora en paso " + str(paso))
                    estado["paso"] = paso
                    continue

            # ── Nueva señal (con espaciado por mesa + anti-ráfaga) ─
            if not senal_permitida(nombre):
                objetivo = max(proxima_senal_por_mesa.get(nombre, 0.0), proxima_senal_global)
                restante = int(objetivo - time.time())
                log.info("[" + nombre + "] Oportunidad de señal, pero en espaciado — faltan " + str(restante) + "s")
                continue

            patron = elegir_patron(historial, resultado)
            paso = 1
            en_secuencia = True
            log.info("[" + nombre + "] Nueva señal — patrón: " +
                     " ".join(ec(p) for p in patron))
            img_senal = crear_img_senal(cap, nombre, patron)
            await enviar_foto(bot, CANAL_SENALES_ID, img_senal,
                              caption_senal(nombre, patron))
            marcar_antirrafaga()
            log.info("[" + nombre + "] Señal enviada")

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

    estados    = {}
    detectores = {}
    for m in mesas_activas:
        estados[m["nombre"]] = {"historial": [], "patron": [], "paso": 1, "en_secuencia": False}
        detectores[m["nombre"]] = DetectorCambio()

    tasks = [loop_mesa(m, bot, estados[m["nombre"]], detectores[m["nombre"]]) for m in mesas_activas]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⛔ Bot detenido")
