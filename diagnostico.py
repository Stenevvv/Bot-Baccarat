"""
DIAGNÓSTICO DE DETECCIÓN (doble zona)
=====================================
Calibra la zona de detección SIN enviar nada a Telegram.

Vigila DOS zonas en cada mesa:
  - VERDE   = la banner_roi configurada en config/settings.py (zona actual)
  - MAGENTA = una zona de prueba más abajo y al centro (sobre el EMPATE),
              donde suele aparecer el banner "JUGADOR"/"BANCA"

Dibuja reglas (números de posición en px) en X (arriba) e Y (izquierda).
Aprende el nivel normal de cada zona y, cuando un color SALTA (resultado real),
guarda <Mesa>_RESULTADO_<hora>.png con ambas zonas dibujadas.

Uso:
    python diagnostico.py

IMPORTANTE: deja el navegador del casino EXACTAMENTE igual (misma posición,
mismo zoom, pantalla completa) que cuando calibraste. Si lo mueves o cambias
el zoom, las coordenadas se desajustan.

Deja correr 2-3 min, Ctrl+C, y comparte las imágenes RESULTADO de ./diagnostico/
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
SALTO_MINIMO = 1500   # cuánto debe subir un color sobre su nivel normal


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
    """Zona de prueba: centro de la mesa, a la altura del banner."""
    _, _, w, _ = region
    cx = int(w * 0.36)
    cw = int(w * 0.28)
    return (cx, 140, cw, 52)


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


def evaluar(img, roi, base_a, base_r, clave):
    x, y, w, h = roi
    rec = img[y:y + h, x:x + w]
    pa, pr = contar_colores(rec)
    base_a[clave] = min(base_a.get(clave, pa), pa)
    base_r[clave] = min(base_r.get(clave, pr), pr)
    sa = pa - base_a[clave]
    sr = pr - base_r[clave]
    return pa, pr, sa, sr


def main():
    os.makedirs(CARPETA, exist_ok=True)
    print("=" * 58)
    print("  DIAGNÓSTICO DOBLE ZONA — no envía nada a Telegram")
    print("=" * 58)
    print("Mesas:", ", ".join(m["nombre"] for m in MESAS))
    print("VERDE = zona actual | MAGENTA = zona de prueba (centro/abajo)")
    print("Se guarda <Mesa>_RESULTADO_<hora>.png cuando una zona salta.")
    print("Ctrl+C para detener.\n")

    ba, br = {}, {}   # baselines por clave "mesa|zona"

    try:
        while True:
            ts = datetime.datetime.now().strftime("%H:%M:%S")
            for m in MESAS:
                nombre = m["nombre"]
                region = m["region"]
                roi_v = m["banner_roi"]
                roi_m = zona_central(region)

                img = capturar(region)
                va, vr, vsa, vsr = evaluar(img, roi_v, ba, br, nombre + "|V")
                ma, mr, msa, msr = evaluar(img, roi_m, ba, br, nombre + "|M")

                salto_v = max(vsa, vsr)
                salto_m = max(msa, msr)
                es_res = salto_v > SALTO_MINIMO or salto_m > SALTO_MINIMO

                def color_de(sa, sr):
                    if max(sa, sr) <= SALTO_MINIMO:
                        return "-"
                    return "JUGADOR" if sa > sr else "BANCA"

                anotada = img.copy()
                dibujar_reglas(anotada)
                cv2.rectangle(anotada, (roi_v[0], roi_v[1]),
                              (roi_v[0] + roi_v[2], roi_v[1] + roi_v[3]), (0, 255, 0), 2)
                cv2.rectangle(anotada, (roi_m[0], roi_m[1]),
                              (roi_m[0] + roi_m[2], roi_m[1] + roi_m[3]), (255, 0, 255), 2)
                linea1 = nombre + " V[verde] a=%d(+%d) r=%d(+%d) %s" % (va, vsa, vr, vsr, color_de(vsa, vsr))
                linea2 = "  M[magenta] a=%d(+%d) r=%d(+%d) %s" % (ma, msa, mr, msr, color_de(msa, msr))
                cv2.putText(anotada, linea1, (5, 38), cv2.FONT_HERSHEY_SIMPLEX,
                            0.4, (0, 255, 0), 1, cv2.LINE_AA)
                cv2.putText(anotada, linea2, (5, 54), cv2.FONT_HERSHEY_SIMPLEX,
                            0.4, (255, 0, 255), 1, cv2.LINE_AA)

                base = nombre.replace(" ", "_")
                cv2.imwrite(os.path.join(CARPETA, base + ".png"), anotada)
                if es_res:
                    hora = datetime.datetime.now().strftime("%H%M%S")
                    cv2.imwrite(os.path.join(CARPETA, base + "_RESULTADO_" + hora + ".png"), anotada)

                print("[" + ts + "] " + linea1)
                print("           " + linea2)
            print("-" * 45)
            time.sleep(INTERVALO)

    except KeyboardInterrupt:
        print("\nDetenido. Comparte las imágenes RESULTADO de:", CARPETA + "/")


if __name__ == "__main__":
    main()
