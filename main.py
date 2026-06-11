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

from config.settings import (
    TELEGRAM_TOKEN, CANAL_SENALES_ID, CANAL_ESTADISTICAS_ID, MESAS,
    INTERVALO_CAPTURA, CONFIRMAR_RESULTADO, PAUSA_PERDIDA_GLOBAL, COOLDOWN_RESULTADO,
    MODO_PRUEBA, UMBRAL_BANNER, DOMINANCIA_COLOR,
    ESPACIADO_MIN_INICIAL, ESPACIADO_MAX_INICIAL, ESPACIADO_INCREMENTO_CADA,
    ESPACIADO_INCREMENTO_SEG, ESPACIADO_TOPE_MAX, ESPACIADO_ANTIRRAFAGA,
    ANTIINACTIVIDAD_ACTIVO, ANTIINACTIVIDAD_CADA, ANTIINACTIVIDAD_POS, ANTIINACTIVIDAD_CLIC,
)

JUGADOR = "JUGADOR"
BANCA   = "BANCA"
EMPATE  = "EMPATE"
PASOS   = 6
NL      = chr(10)
RECORTE_INFERIOR = 38

J = JUGADOR
B = BANCA
PATRONES = [
    [J, J, B, B, J, B], [B, B, J, J, B, J], [J, B, J, B, J, B],
    [B, J, B, J, B, J], [J, J, J, B, B, B], [B, B, B, J, J, J],
]

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("baccarat_bot.log", encoding="utf-8")]
)
log = logging.getLogger("bot")

pausa_global_hasta = 0.0

def en_pausa_global():
    return time.time() < pausa_global_hasta

def activar_pausa_global():
    global pausa_global_hasta
    pausa_global_hasta = time.time() + PAUSA_PERDIDA_GLOBAL
    log.info("PAUSA GLOBAL activada - " + str(PAUSA_PERDIDA_GLOBAL // 60) + " minutos sin senales")

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
    log.info("[%s] Apuesta resuelta - proxima senal en ~%ds (rango %d-%ds)" % (nombre, int(espera), int(lo), int(hi)))

def _actividad_neutral():
    import pyautogui
    pyautogui.FAILSAFE = False
    x, y = ANTIINACTIVIDAD_POS
    pyautogui.moveTo(x, y, duration=0.2)
    if ANTIINACTIVIDAD_CLIC:
        pyautogui.click(x, y)
    else:
        pyautogui.moveRel(3, 0, duration=0.1)
        pyautogui.moveRel(-3, 0, duration=0.1)

async def loop_antiinactividad():
    try:
        import pyautogui  # noqa
    except Exception as e:
        log.warning("Anti-inactividad desactivado: pyautogui no disponible (" + str(e) + ")")
        return
    log.info("Anti-inactividad activo - cada " + str(ANTIINACTIVIDAD_CADA) + "s en " + str(ANTIINACTIVIDAD_POS))
    while True:
        await asyncio.sleep(ANTIINACTIVIDAD_CADA)
        try:
            await asyncio.get_event_loop().run_in_executor(None, _actividad_neutral)
            log.info("Anti-inactividad: actividad simulada en " + str(ANTIINACTIVIDAD_POS))
        except Exception as e:
            log.error("Error en anti-inactividad: " + str(e))

def ec(r):
    if r == JUGADOR: return "◦"
    if r == BANCA:   return "●"
    return "⚪"

def opuesto(r):
    return BANCA if r == JUGADOR else JUGADOR

def elegir_patron(historial, ultimo_resultado):
    validos = [r for r in historial if r != EMPATE]
    patron_base = None
    if len(validos) >= 3:
        ultimos3 = validos[-3:]
        if all(r == ultimos3[0] for r in ultimos3):
            patron_base = PATRONES[5] if ultimos3[0] == JUGADOR else PATRONES[4]
        else:
            ultimos4 = validos[-4:] if len(validos) >= 4 else validos
            if all(ultimos4[i] != ultimos4[i+1] for i in range(len(ultimos4)-1)):
                patron_base = PATRONES[3] if ultimo_resultado == JUGADOR else PATRONES[2]
    if patron_base is None:
        patron_base = random.choice(PATRONES)
    if ultimo_resultado == BANCA and patron_base[0] == JUGADOR:
        return [opuesto(p) for p in patron_base]
    if ultimo_resultado == JUGADOR and patron_base[0] == BANCA:
        return [opuesto(p) for p in patron_base]
    return patron_base[:]

def capturar(region):
    left, top, w, h = region
    with mss.mss() as sct:
        shot = sct.grab({"left": left, "top": top, "width": w, "height": h})
        return cv2.cvtColor(np.array(shot), cv2.COLOR_BGRA2BGR)

def capturar_bytes(region):
    _, buf = cv2.imencode('.png', capturar(region))
    return buf.tobytes()

def contar_banner(img, banner_roi):
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
    px_azul, px_rojo, px_verde = contar_banner(img, banner_roi)
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
    resultados = []
    for _ in range(intentos):
        r = detectar_banner(capturar(region), banner_roi)
        if r:
            resultados.append(r)
        time.sleep(espera)
    if not resultados:
        return None
    return max(set(resultados), key=resultados.count)

def _recortar_inferior(img):
    w, h = img.size
    if h > RECORTE_INFERIOR:
        img = img.crop((0, 0, w, h - RECORTE_INFERIOR))
    return img

def crear_img_senal(cap_bytes, nombre, patron):
    img = _recortar_inferior(Image.open(io.BytesIO(cap_bytes)).convert("RGB"))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def crear_img_stats(cap_bytes, nombre, patron, paso_acierto):
    img = _recortar_inferior(Image.open(io.BytesIO(cap_bytes)).convert("RGB"))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

async def enviar_foto(bot, chat_id, img_bytes, caption):
    if MODO_PRUEBA:
        os.makedirs("prueba_envios", exist_ok=True)
        nombre_arch = "prueba_envios/" + str(chat_id) + "_" + time.strftime("%H%M%S") + ".png"
        with open(nombre_arch, "wb") as f:
            f.write(img_bytes)
        log.info("[PRUEBA] (NO enviado) imagen -> " + nombre_arch)
        log.info("[PRUEBA] caption: " + caption.replace(NL, " | "))
        return True
    try:
        await bot.send_photo(chat_id=chat_id, photo=io.BytesIO(img_bytes), caption=caption, parse_mode="Markdown")
        return True
    except TelegramError as e:
        log.error("Error Telegram foto: " + str(e))
        return False

async def enviar_texto(bot, chat_id, texto):
    if MODO_PRUEBA:
        log.info("[PRUEBA] (NO enviado) texto: " + texto)
        return True
    try:
        await bot.send_message(chat_id=chat_id, text=texto, parse_mode="Markdown")
        return True
    except TelegramError as e:
        log.error("Error Telegram texto: " + str(e))
        return False

def caption_senal(nombre, patron):
    seq = "  ".join(str(i+1)+"."+ec(p) for i, p in enumerate(patron))
    return "🃏 *" + nombre + "*" + NL + NL + seq

def caption_ganada(nombre, patron, paso):
    partes = [str(i+1)+"."+ec(p)+("✓" if i+1 == paso else "") for i, p in enumerate(patron)]
    return "🃏 *" + nombre + "*" + NL + NL + "  ".join(partes) + NL + NL + "✓ *GANADA* - Acierto en el intento " + str(paso)

def caption_perdida(nombre, patron):
    seq = "  ".join(str(i+1)+"."+ec(p)+"✗" for i, p in enumerate(patron))
    return "🃏 *" + nombre + "*" + NL + NL + seq + NL + NL + "✗ *PERDIDA* - Sin aciertos en 6 intentos"

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

async def loop_mesa(mesa_cfg, bot, estado, detector):
    nombre = mesa_cfg["nombre"]
    region = mesa_cfg["region"]
    banner_roi = mesa_cfg["banner_roi"]
    log.info("Iniciando mesa: " + nombre)
    historial = estado["historial"]
    patron = estado["patron"]
    paso = estado["paso"]
    en_secuencia = estado["en_secuencia"]

    while True:
        try:
            await asyncio.sleep(INTERVALO_CAPTURA)
            if en_pausa_global():
                restante = int(pausa_global_hasta - time.time())
                if restante % 60 == 0:
                    log.info("[" + nombre + "] En pausa global - " + str(restante//60) + " min restantes")
                continue

            img_bgr = capturar(region)
            if MODO_PRUEBA:
                _pa, _pr, _pv = contar_banner(img_bgr, banner_roi)
                log.info("[%s] azul=%d rojo=%d verde=%d" % (nombre, _pa, _pr, _pv))
            resultado_raw = detectar_banner(img_bgr, banner_roi)

            if not detector.es_nuevo(resultado_raw):
                continue

            log.info("[" + nombre + "] Banner detectado: " + str(resultado_raw) + " - confirmando...")
            resultado = await asyncio.get_event_loop().run_in_executor(
                None, lambda: confirmar_resultado(region, banner_roi, intentos=3, espera=0.4))

            if resultado is None:
                log.info("[" + nombre + "] No confirmado - ignorando")
                continue

            if resultado == EMPATE:
                log.info("[%s] EMPATE - push: no gana ni pierde, se mantiene el movimiento %d" % (nombre, paso))
                historial.append(EMPATE)
                continue

            log.info("[" + nombre + "] Resultado confirmado: " + resultado)
            historial.append(resultado)
            _ok, _buf = cv2.imencode('.png', img_bgr)
            cap = _buf.tobytes() if _ok else capturar_bytes(region)

            if en_secuencia and patron and paso <= PASOS:
                if patron[paso - 1] == resultado:
                    log.info("[" + nombre + "] GANADA en intento " + str(paso))
                    await enviar_foto(bot, CANAL_ESTADISTICAS_ID, crear_img_stats(cap, nombre, patron, paso),
                                      caption_ganada(nombre, patron, paso))
                    en_secuencia = False
                    paso = 1
                    iniciar_lapso_mesa(nombre)
                elif paso >= PASOS:
                    log.info("[" + nombre + "] PERDIDA - activando pausa global 30 min")
                    await enviar_foto(bot, CANAL_ESTADISTICAS_ID, crear_img_stats(cap, nombre, patron, paso),
                                      caption_perdida(nombre, patron))
                    activar_pausa_global()
                    en_secuencia = False
                    paso = 1
                    iniciar_lapso_mesa(nombre)
                    estado.update({"historial": historial, "patron": patron, "paso": paso, "en_secuencia": en_secuencia})
                    continue
                else:
                    paso += 1
                    log.info("[" + nombre + "] Fallo - ahora en paso " + str(paso))
                    estado["paso"] = paso
                    continue

            if not senal_permitida(nombre):
                objetivo = max(proxima_senal_por_mesa.get(nombre, 0.0), proxima_senal_global)
                log.info("[" + nombre + "] Oportunidad de senal, pero en espaciado - faltan " + str(int(objetivo - time.time())) + "s")
                continue

            patron = elegir_patron(historial, resultado)
            paso = 1
            en_secuencia = True
            log.info("[" + nombre + "] Nueva senal - patron: " + " ".join(ec(p) for p in patron))
            await enviar_foto(bot, CANAL_SENALES_ID, crear_img_senal(cap, nombre, patron), caption_senal(nombre, patron))
            marcar_antirrafaga()
            log.info("[" + nombre + "] Senal enviada")
            estado.update({"historial": historial, "patron": patron, "paso": paso, "en_secuencia": en_secuencia})

        except Exception as e:
            log.error("Error en " + nombre + ": " + str(e), exc_info=True)
            await asyncio.sleep(5)

async def main():
    print("=" * 55)
    print("  BACCARAT BOT v2 - Rushbet Pragmatic Play")
    print("=" * 55)
    bot = Bot(token=TELEGRAM_TOKEN)
    if MODO_PRUEBA:
        print("MODO PRUEBA ACTIVO - NO se enviara nada a Telegram.")
        try:
            me = await bot.get_me(); print("Token valido: @" + me.username)
        except TelegramError as e:
            print("No se pudo verificar el token: " + str(e))
    else:
        try:
            me = await bot.get_me(); print("Bot conectado: @" + me.username)
        except TelegramError as e:
            print("Error conectando: " + str(e)); return

    mesas_activas = [m for m in MESAS if m.get("activa", True)]
    print("Mesas: " + ", ".join(m["nombre"] for m in mesas_activas))
    print("Intervalo: " + str(INTERVALO_CAPTURA) + "s")
    if ANTIINACTIVIDAD_ACTIVO:
        print("Anti-inactividad: cada " + str(ANTIINACTIVIDAD_CADA) + "s en " + str(ANTIINACTIVIDAD_POS))
    print(NL + "Monitoreando - minimiza esta ventana y deja Rushbet al frente" + NL)

    estados, detectores = {}, {}
    for m in mesas_activas:
        estados[m["nombre"]] = {"historial": [], "patron": [], "paso": 1, "en_secuencia": False}
        detectores[m["nombre"]] = DetectorCambio()

    tasks = [loop_mesa(m, bot, estados[m["nombre"]], detectores[m["nombre"]]) for m in mesas_activas]
    if ANTIINACTIVIDAD_ACTIVO:
        tasks.append(loop_antiinactividad())
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(NL + "Bot detenido")

