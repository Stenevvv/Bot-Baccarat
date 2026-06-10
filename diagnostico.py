"""
DIAGNÓSTICO (modo tira de fotos)
================================
Calibra la zona de detección SIN enviar nada a Telegram.

IMPORTANTE: esta versión guarda UNA FOTO EN CADA CICLO (no depende de
detectar nada). Así capturamos sí o sí el momento en que aparece el banner
"JUGADOR"/"BANCA". Tú luego miras las miniaturas y eliges las que muestren
un banner azul o rojo.

Cada foto trae:
  - Reglas amarillas (posición en píxeles) en X (arriba) e Y (izquierda)
  - VERDE   = la banner_roi configurada en config/settings.py
  - MAGENTA = zona de prueba al centro (sobre el EMPATE)
  - Los conteos de azul/rojo de cada zona

Las fotos se guardan en ./diagnostico/frames/ con la hora en el nombre:
    Baccarat_1_152233.png

Uso:
    python diagnostico.py

Deja correr ~1 minuto con el casino al frente (sin mover ni cambiar el zoom).
Ctrl+C para detener. Luego abre la carpeta (explorer diagnostico\\frames),
mira las miniaturas y mándame 2-3 que muestren un banner de resultado.
"""
import os
import time
import datetime
import mss
import cv2
import numpy as np

from config.settings import MESAS

CARPETA = os.path.join("diagnostico", "frames")
INTERVALO = 2.0


def capturar(region):
    left, top, w, h = region
    with mss.mss() as sct:
        mon = {"left": left, "top": top, "width": w, "height": h}
        shot = sct.grab(mon)
        img = np.array(shot)
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)


def contar_colores(recorte):
    if recorte.size == 0:
        return 0, 0
    hsv = cv2.cvtColor(recorte, cv2.COLOR_BGR2HSV)
    mask_azul = cv2.inRange(hsv, np.array([100, 100, 80]), np.array([135, 255, 255]))
    mask_rojo1 = cv2.inRange(hsv, np.array([0, 100, 80]), np.array([12, 255, 255]))
    mask_rojo2 = cv2.inRange(hsv, np.array([168, 100, 80]), np.array([180, 255, 255]))
    mask_rojo = cv2.bitwise_or(mask_rojo1, mask_rojo2)
    return int(cv2.countNonZero(mask_azul)), int(cv2.countNonZero(mask_rojo))


def zona_central(region):
    _, _, w, _ = region
    return (int(w * 0.36), 140, int(w * 0.28), 52)


def dibujar_reglas(img):
    h, w = img.shape[:2]
    for yy in range(0, h, 20):
        cv2.line(img, (0, yy), (16, yy), (0, 255, 255), 1)
        cv2.putText(img, str(yy), (18, yy + 4), cv2.FONT_HERSHEY_SIMPLEX,
                    0.32, (0, 255, 255), 1, cv2.LINE_AA)
    for xx in range(0, w, 40):
        cv2.line(img, (xx, 0), (xx, 12), (0, 255, 255), 1)
        cv2.putText(img, str(xx), (xx + 2, 24), cv2.FONT_HERSHEY_SIMPLEX,
                    0.32, (0, 255, 255), 1, cv2.LINE_AA)


def caja(img, roi, color, etiqueta):
    x, y, w, h = roi
    cv2.rectangle(img, (x, y), (x + w, y + h), color, 2)
    cv2.putText(img, etiqueta, (x, y - 3), cv2.FONT_HERSHEY_SIMPLEX,
                0.35, color, 1, cv2.LINE_AA)


def main():
    os.makedirs(CARPETA, exist_ok=True)
    print("=" * 58)
    print("  DIAGNÓSTICO (tira de fotos) — no envía nada a Telegram")
    print("=" * 58)
    print("Mesas:", ", ".join(m["nombre"] for m in MESAS))
    print("Guarda UNA foto por ciclo en:", CARPETA)
    print("Deja correr ~1 min y Ctrl+C. Luego mira las miniaturas.")
    print()

    n = 0
    try:
        while True:
            hora = datetime.datetime.now().strftime("%H%M%S")
            ts = datetime.datetime.now().strftime("%H:%M:%S")
            for m in MESAS:
                nombre = m["nombre"]
                region = m["region"]
                roi_v = m["banner_roi"]
                roi_m = zona_central(region)

                img = capturar(region)
                va, vr = contar_colores(img[roi_v[1]:roi_v[1] + roi_v[3], roi_v[0]:roi_v[0] + roi_v[2]])
                ma, mr = contar_colores(img[roi_m[1]:roi_m[1] + roi_m[3], roi_m[0]:roi_m[0] + roi_m[2]])

                dibujar_reglas(img)
                caja(img, roi_v, (0, 255, 0), "VERDE a=%d r=%d" % (va, vr))
                caja(img, roi_m, (255, 0, 255), "MAGENTA a=%d r=%d" % (ma, mr))

                base = nombre.replace(" ", "_")
                cv2.imwrite(os.path.join(CARPETA, base + "_" + hora + ".png"), img)
                print("[" + ts + "] " + nombre +
                      " | VERDE a=%d r=%d | MAGENTA a=%d r=%d" % (va, vr, ma, mr))
            n += 1
            print("-" * 45 + "  (fotos guardadas: %d)" % (n * len(MESAS)))
            time.sleep(INTERVALO)

    except KeyboardInterrupt:
        print("\nDetenido. Abre la carpeta y mira las miniaturas:")
        print("   explorer diagnostico\\frames")
        print("Mándame 2-3 fotos que muestren un banner azul o rojo.")


if __name__ == "__main__":
    main()
