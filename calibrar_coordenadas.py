"""
CALIBRADOR DE COORDENADAS
Corre este script ANTES de usar el bot para encontrar las
coordenadas exactas de cada mesa en tu pantalla.

Uso:
    python calibrar_coordenadas.py

Instrucciones:
    1. Abre Rushbet en el navegador con las 3 mesas visibles
    2. Corre este script
    3. Mueve el ratón a las esquinas de cada región
    4. El script va imprimiendo las coordenadas en tiempo real
    5. Copia los valores a config/settings.py
"""
import time
import sys

try:
    import pyautogui
    TIENE_PYAUTOGUI = True
except ImportError:
    TIENE_PYAUTOGUI = False

try:
    import mss
    import cv2
    import numpy as np
    TIENE_MSS = True
except ImportError:
    TIENE_MSS = False


def mostrar_posicion_raton():
    """Muestra la posición del ratón en tiempo real"""
    if not TIENE_PYAUTOGUI:
        print("❌ pyautogui no instalado. Corre: pip install pyautogui")
        return

    print("\n🖱️  MODO POSICIÓN DEL RATÓN")
    print("   Mueve el ratón a cada esquina de la mesa y anota las coordenadas")
    print("   Presiona Ctrl+C para salir\n")
    try:
        while True:
            x, y = pyautogui.position()
            print(f"\r   Posición: X={x:4d}  Y={y:4d}", end="", flush=True)
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n")


def captura_interactiva():
    """Toma capturas de regiones para verificar el recorte"""
    if not TIENE_MSS:
        print("❌ mss no instalado. Corre: pip install mss")
        return

    print("\n📸 CAPTURA INTERACTIVA")
    print("   Ingresa las coordenadas de la región a capturar")
    print("   Formato: left top width height (ej: 0 0 640 400)\n")

    with mss.mss() as sct:
        while True:
            entrada = input("   Coordenadas (o 'q' para salir): ").strip()
            if entrada.lower() == 'q':
                break
            try:
                left, top, width, height = map(int, entrada.split())
                monitor = {"left": left, "top": top, "width": width, "height": height}
                screenshot = sct.grab(monitor)
                img = np.array(screenshot)
                img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                cv2.imwrite(f"calibracion_{left}_{top}.png", img_bgr)
                print(f"   ✅ Guardado: calibracion_{left}_{top}.png")
            except ValueError:
                print("   ❌ Formato inválido. Usa: left top width height")
            except Exception as e:
                print(f"   ❌ Error: {e}")


def guia_coordenadas():
    """Imprime una guía para encontrar coordenadas manualmente"""
    print("""
╔══════════════════════════════════════════════════════╗
║        GUÍA PARA CALIBRAR COORDENADAS                ║
╠══════════════════════════════════════════════════════╣
║                                                      ║
║  1. Abre las 3 mesas en Rushbet                      ║
║     Sugerencia: usa 3 pestañas o ventanas            ║
║                                                      ║
║  2. Para cada mesa necesitas 2 regiones:             ║
║                                                      ║
║     ▸ region: toda el área de la mesa                ║
║       (left, top, width, height) en píxeles          ║
║                                                      ║
║     ▸ banner_roi: zona donde aparece                 ║
║       "BANCA" / "JUGADOR"                            ║
║       RELATIVO a la region (empieza en 0,0)          ║
║                                                      ║
║  3. Cómo encontrar las coordenadas:                  ║
║     • Windows: usa la herramienta Recortes,          ║
║       luego hovea con el cursor                      ║
║     • O corre: python calibrar_coordenadas.py        ║
║       y selecciona opción 1                          ║
║                                                      ║
║  4. Ejemplo de configuración:                        ║
║                                                      ║
║     MESAS = [                                        ║
║       {                                              ║
║         "nombre": "Super 8 Baccarat",                ║
║         "region": (10, 120, 620, 380),  ← mesa       ║
║         "banner_roi": (140, 45, 340, 55),← banner    ║
║       },                                             ║
║     ]                                                ║
║                                                      ║
╚══════════════════════════════════════════════════════╝
""")


def menu():
    print("""
╔══════════════════════════════════════════════════════╗
║         🎯  CALIBRADOR DE COORDENADAS                ║
╚══════════════════════════════════════════════════════╝

  1. Mostrar posición del ratón en tiempo real
  2. Capturar región y guardar imagen
  3. Ver guía de coordenadas
  4. Salir
""")
    return input("  Elige opción: ").strip()


if __name__ == "__main__":
    guia_coordenadas()
    while True:
        opcion = menu()
        if opcion == "1":
            mostrar_posicion_raton()
        elif opcion == "2":
            captura_interactiva()
        elif opcion == "3":
            guia_coordenadas()
        elif opcion == "4":
            print("\n👋 Hasta luego\n")
            break
        else:
            print("  Opción inválida")
