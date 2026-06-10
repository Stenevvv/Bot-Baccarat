"""
DIAGNÓSTICO DE DETECCIÓN
========================
Herramienta para calibrar la zona de detección (banner_roi) SIN enviar
nada a Telegram.

Qué hace:
  - Captura cada mesa definida en config/settings.py
  - Dibuja una REGLA (números de posición en píxeles) en X (arriba) e Y
    (izquierda), para medir exactamente dónde aparece el banner
  - Dibuja en VERDE el rectángulo banner_roi actual
  - Cuenta los píxeles azules (Jugador) y rojos (Banca) dentro de esa zona
  - Aprende el "nivel normal" (baseline) de cada mesa y, cuando hay un SALTO
    fuerte de color (un resultado real), guarda una copia con la hora en el
    nombre: <Mesa>_RESULTADO_<hora>.png  ← esas imágenes son las importantes
  - Imprime en consola los conteos en tiempo real

Uso:
    python diagnostico.py

Deja el casino al frente 1-2 minutos. Cuando termine alguna mano, se guardará
la imagen del resultado automáticamente. Luego Ctrl+C y compárteme las
imágenes de la carpeta ./diagnostico/ (sobre todo las que dicen RESULTADO).
"""
import os
import time
import datetime
import mss
import cv2
import numpy as np

from config.settings import MESAS

CARPETA = "diagnostico"
INTERVALO = 1.5
UMBRAL = 600
SALTO_MINIMO = 2200   # cuánto debe subir un color sobre su nivel normal para considerarlo resultado


def capturar(region):
    left, top, w, h = region
    with mss.mss() as sct:
        mon = {"left": left, "top": top, "width": w, "height": h}
        shot = sct.grab(mon)
        img = np.array(shot)
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)


def contar_colores(recorte):
    hsv = cv2.cvtColor(recorte, cv2.COLOR_BGR2HSV)
    mask_azul = cv2.inRange(hsv, np.array([100, 100, 80]), np.array([135, 255, 255]))
    mask_rojo1 = cv2.inRange(hsv, np.array([0, 100, 80]), np.array([12, 255, 255]))
    mask_rojo2 = cv2.inRange(hsv, np.array([168, 100, 80]), np.array([180, 255, 255]))
    mask_rojo = cv2.bitwise_or(mask_rojo1, mask_rojo2)
    return int(cv2.countNonZero(mask_azul)), int(cv2.countNonZero(mask_rojo))


def dibujar_reglas(img):
    """Regla vertical (Y, izquierda) y horizontal (X, arriba) cada 20 px."""
    h, w = img.shape[:2]
    for yy in range(0, h, 20):
        cv2.line(img, (0, yy), (16, yy), (0, 255, 255), 1)
        cv2.putText(img, str(yy), (18, yy + 4), cv2.FONT_HERSHEY_SIMPLEX,
                    0.32, (0, 255, 255), 1, cv2.LINE_AA)
    for xx in range(0, w, 40):
        cv2.line(img, (xx, 0), (xx, 12), (0, 255, 255), 1)
        cv2.putText(img, str(xx), (xx + 2, 24), cv2.FONT_HERSHEY_SIMPLEX,
                    0.32, (0, 255, 255), 1, cv2.LINE_AA)


def main():
    os.makedirs(CARPETA, exist_ok=True)
    print("=" * 55)
    print("  DIAGNÓSTICO DE DETECCIÓN — no envía nada a Telegram")
    print("=" * 55)
    print("Mesas:", ", ".join(m["nombre"] for m in MESAS))
    print("Carpeta:", CARPETA + "/   |   Reglas amarillas = posiciones en px")
    print("Se guardará <Mesa>_RESULTADO_<hora>.png cuando haya un resultado.")
    print("Ctrl+C para detener.\n")

    base_azul = {}   # nivel normal de azul por mesa
    base_rojo = {}   # nivel normal de rojo por mesa

    try:
        while True:
            ts = datetime.datetime.now().strftime("%H:%M:%S")
            for m in MESAS:
                nombre = m["nombre"]
                region = m["region"]
                bx, by, bw, bh = m["banner_roi"]

                img = capturar(region)
                recorte = img[by:by + bh, bx:bx + bw]
                px_azul, px_rojo = contar_colores(recorte)

                # Actualizar baseline como el mínimo visto (nivel "en reposo")
                base_azul[nombre] = min(base_azul.get(nombre, px_azul), px_azul)
                base_rojo[nombre] = min(base_rojo.get(nombre, px_rojo), px_rojo)
                salto_azul = px_azul - base_azul[nombre]
                salto_rojo = px_rojo - base_rojo[nombre]

                es_resultado = salto_azul > SALTO_MINIMO or salto_rojo > SALTO_MINIMO
                if es_resultado:
                    quien = "JUGADOR" if salto_azul > salto_rojo else "BANCA"
                else:
                    quien = "sin resultado"

                anotada = img.copy()
                dibujar_reglas(anotada)
                cv2.rectangle(anotada, (bx, by), (bx + bw, by + bh), (0, 255, 0), 2)
                texto = (nombre + " azul=" + str(px_azul) + "(+%d)" % salto_azul +
                         " rojo=" + str(px_rojo) + "(+%d)" % salto_rojo + " -> " + quien)
                cv2.putText(anotada, texto, (5, 38), cv2.FONT_HERSHEY_SIMPLEX,
                            0.4, (255, 255, 255), 1, cv2.LINE_AA)

                base = nombre.replace(" ", "_")
                cv2.imwrite(os.path.join(CARPETA, base + ".png"), anotada)

                if es_resultado:
                    hora = datetime.datetime.now().strftime("%H%M%S")
                    cv2.imwrite(os.path.join(CARPETA, base + "_RESULTADO_" + hora + ".png"), anotada)

                print("[" + ts + "] " + texto)

            print("-" * 40)
            time.sleep(INTERVALO)

    except KeyboardInterrupt:
        print("\nDetenido. Comparte las imágenes de la carpeta:", CARPETA + "/")


if __name__ == "__main__":
    main()
