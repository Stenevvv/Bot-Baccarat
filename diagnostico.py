"""
DIAGNÓSTICO DE DETECCIÓN
========================
Herramienta para calibrar la zona de detección (banner_roi) SIN enviar
nada a Telegram.

Qué hace:
  - Captura cada mesa definida en config/settings.py
  - Dibuja en VERDE el rectángulo banner_roi (la zona donde el bot busca
    el banner "JUGADOR"/"BANCA")
  - Cuenta los píxeles azules (Jugador) y rojos (Banca) dentro de esa zona
  - Escribe el veredicto sobre la imagen y la guarda en la carpeta ./diagnostico/
  - Imprime en consola los conteos en tiempo real

Uso:
    python diagnostico.py

Mientras corre, deja el casino al frente y espera a que alguna mesa muestre
un resultado (banner azul/rojo). Luego revisa las imágenes guardadas en la
carpeta ./diagnostico/ y compárte las que muestren un resultado.

Presiona Ctrl+C para detener.
"""
import os
import time
import datetime
import mss
import cv2
import numpy as np

from config.settings import MESAS

CARPETA = "diagnostico"
INTERVALO = 2.0          # segundos entre capturas
UMBRAL = 600             # mismo umbral que usa el bot en main.py


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


def main():
    os.makedirs(CARPETA, exist_ok=True)
    print("=" * 55)
    print("  DIAGNÓSTICO DE DETECCIÓN — no envía nada a Telegram")
    print("=" * 55)
    print("Mesas:", ", ".join(m["nombre"] for m in MESAS))
    print("Guardando imágenes en la carpeta:", CARPETA + "/")
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

                # Dibujar la zona banner_roi en verde
                anotada = img.copy()
                cv2.rectangle(anotada, (bx, by), (bx + bw, by + bh), (0, 255, 0), 2)
                texto = nombre + " | azul=" + str(px_azul) + " rojo=" + str(px_rojo) + " -> " + verd
                cv2.putText(anotada, texto, (5, 18), cv2.FONT_HERSHEY_SIMPLEX,
                            0.45, (0, 255, 0), 1, cv2.LINE_AA)

                nombre_archivo = nombre.replace(" ", "_") + ".png"
                cv2.imwrite(os.path.join(CARPETA, nombre_archivo), anotada)

                print("[" + ts + "] " + texto)

            print("-" * 40)
            time.sleep(INTERVALO)

    except KeyboardInterrupt:
        print("\nDetenido. Revisa las imágenes en la carpeta:", CARPETA + "/")


if __name__ == "__main__":
    main()
