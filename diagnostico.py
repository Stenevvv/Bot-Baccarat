"""
DIAGNÓSTICO DE DETECCIÓN
========================
Herramienta para calibrar la zona de detección (banner_roi) SIN enviar
nada a Telegram.

Qué hace:
  - Captura cada mesa definida en config/settings.py
  - Dibuja una REGLA vertical (números de posición Y en píxeles) en el
    borde izquierdo, para medir exactamente dónde aparece el banner
  - Dibuja en VERDE el rectángulo banner_roi (zona donde el bot busca
    el banner "JUGADOR"/"BANCA")
  - Cuenta los píxeles azules (Jugador) y rojos (Banca) dentro de esa zona
  - Guarda la última imagen de cada mesa (se sobrescribe)
  - Si detecta un posible RESULTADO, guarda además una copia con la hora
    en el nombre (para que no se pierda el momento)
  - Imprime en consola los conteos en tiempo real

Uso:
    python diagnostico.py

Deja el casino al frente. Cuando veas en alguna mesa el banner rojo (BANCA)
o azul (JUGADOR), ya quedará guardado automáticamente. Presiona Ctrl+C para
detener y luego compárteme las imágenes de la carpeta ./diagnostico/
"""
import os
import time
import datetime
import mss
import cv2
import numpy as np

from config.settings import MESAS

CARPETA = "diagnostico"
INTERVALO = 1.5          # segundos entre capturas
UMBRAL = 600             # mismo umbral base que usa el bot
GUARDExtra = 2500        # si un color supera esto y domina, se guarda copia con hora


def capturar(region):
    left, top, w, h = region
    with mss.mss() as sct:
        mon = {"left": left, "top": top, "width": w, "height": h}
        shot = sct.grab(mon)
        img = np.array(shot)
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)


def contar_colores(recorte):
    """Devuelve (px_azul, px_rojo) dentro del recorte."""
    hsv = cv2.cvtColor(recorte, cv2.COLOR_BGR2HSV)
    mask_azul = cv2.inRange(hsv, np.array([100, 100, 80]), np.array([135, 255, 255]))
    mask_rojo1 = cv2.inRange(hsv, np.array([0, 100, 80]), np.array([12, 255, 255]))
    mask_rojo2 = cv2.inRange(hsv, np.array([168, 100, 80]), np.array([180, 255, 255]))
    mask_rojo = cv2.bitwise_or(mask_rojo1, mask_rojo2)
    return int(cv2.countNonZero(mask_azul)), int(cv2.countNonZero(mask_rojo))


def veredicto(px_azul, px_rojo):
    if px_azul < UMBRAL and px_rojo < UMBRAL:
        return "SIN RESULTADO"
    return "JUGADOR (azul)" if px_azul > px_rojo else "BANCA (rojo)"


def dibujar_regla(img):
    """Dibuja una regla vertical con números de posición Y cada 20 px."""
    h, w = img.shape[:2]
    for yy in range(0, h, 20):
        cv2.line(img, (0, yy), (18, yy), (0, 255, 255), 1)
        cv2.putText(img, str(yy), (20, yy + 4), cv2.FONT_HERSHEY_SIMPLEX,
                    0.35, (0, 255, 255), 1, cv2.LINE_AA)


def main():
    os.makedirs(CARPETA, exist_ok=True)
    print("=" * 55)
    print("  DIAGNÓSTICO DE DETECCIÓN — no envía nada a Telegram")
    print("=" * 55)
    print("Mesas:", ", ".join(m["nombre"] for m in MESAS))
    print("Guardando imágenes en la carpeta:", CARPETA + "/")
    print("La REGLA amarilla (números) sirve para medir el banner.")
    print("Presiona Ctrl+C para detener.\n")

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
                verd = veredicto(px_azul, px_rojo)

                anotada = img.copy()
                dibujar_regla(anotada)
                # Zona banner_roi en verde
                cv2.rectangle(anotada, (bx, by), (bx + bw, by + bh), (0, 255, 0), 2)
                texto = nombre + " | azul=" + str(px_azul) + " rojo=" + str(px_rojo) + " -> " + verd
                cv2.putText(anotada, texto, (5, 12), cv2.FONT_HERSHEY_SIMPLEX,
                            0.4, (255, 255, 255), 1, cv2.LINE_AA)

                base = nombre.replace(" ", "_")
                cv2.imwrite(os.path.join(CARPETA, base + ".png"), anotada)

                # Guardar copia con hora si parece un resultado real
                dom = max(px_azul, px_rojo)
                otro = min(px_azul, px_rojo)
                if dom > GUARDExtra and dom > 2 * max(otro, 1):
                    hora = datetime.datetime.now().strftime("%H%M%S")
                    cv2.imwrite(os.path.join(CARPETA, base + "_RESULTADO_" + hora + ".png"), anotada)

                print("[" + ts + "] " + texto)

            print("-" * 40)
            time.sleep(INTERVALO)

    except KeyboardInterrupt:
        print("\nDetenido. Revisa las imágenes en la carpeta:", CARPETA + "/")


if __name__ == "__main__":
    main()
