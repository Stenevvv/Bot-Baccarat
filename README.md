# 🃏 Baccarat Bot — Rushbet Pragmatic Play

Bot que monitorea 3 mesas de baccarat virtual en Rushbet en tiempo real,
genera predicciones con método Martingala (secuencia de 6 pasos) y envía
capturas + resultados a dos canales de Telegram.

---

## Estructura del proyecto

```
baccarat_bot/
├── main.py                    ← Punto de entrada, corre el bot
├── calibrar_coordenadas.py    ← Herramienta para calibrar la pantalla
├── requirements.txt
├── config/
│   └── settings.py            ← ⚠️  EDITAR ANTES DE CORRER
├── core/
│   ├── motor.py               ← Lógica Martingala + secuencia 6 pasos
│   └── detector.py            ← Captura + OCR + detección de color
└── telegram/
    └── cliente.py             ← Envío a los dos canales
```

---

## Instalación

### Requisitos
- Python 3.10 o superior
- Windows / Linux / macOS
- Rushbet abierto en el navegador con las 3 mesas visibles

### Paso 1 — Instalar dependencias

```bash
pip install -r requirements.txt
```

> La primera vez que corra EasyOCR descargará modelos (~500 MB).
> Solo ocurre una vez.

---

## Configuración

### Paso 2 — Crear el bot de Telegram

1. Abre Telegram y busca **@BotFather**
2. Escribe `/newbot` y sigue las instrucciones
3. Copia el **token** que te da (formato: `123456:ABC-DEF...`)

### Paso 3 — Obtener los Chat IDs de tus canales

1. Añade tu bot como **administrador** a ambos canales
2. Envía un mensaje en cada canal
3. Abre en el navegador:
   ```
   https://api.telegram.org/bot<TU_TOKEN>/getUpdates
   ```
4. Busca el campo `"chat": {"id": -100XXXXXXXXX}` — ese es el Chat ID

### Paso 4 — Editar `config/settings.py`

```python
TELEGRAM_TOKEN        = "123456:ABC-DEF-tu-token-aqui"
CANAL_SENALES_ID      = -1001234567890   # canal de señales
CANAL_ESTADISTICAS_ID = -1009876543210   # canal de estadísticas
```

### Paso 5 — Calibrar coordenadas de pantalla

Este paso es **obligatorio**. Las coordenadas varían según tu resolución
y cómo tengas dispuestas las mesas en el navegador.

```bash
python calibrar_coordenadas.py
```

1. Selecciona opción **1** para ver la posición del ratón en tiempo real
2. Mueve el ratón a la esquina superior-izquierda de cada mesa → anota X, Y
3. Mueve a la esquina inferior-derecha → calcula width y height
4. Repite para el banner "BANCA / JUGADOR" dentro de cada mesa

Luego actualiza `MESAS` en `config/settings.py`:

```python
MESAS = [
    {
        "nombre": "Super 8 Baccarat",
        "region":     (10, 120, 620, 380),   # ← tus coordenadas
        "banner_roi": (140, 45, 340, 55),    # ← relativo a region
        "activa": True,
    },
    # ... Baccarat 2, Baccarat 5
]
```

---

## Uso

```bash
python main.py
```

El bot:
1. Verifica la conexión con Telegram
2. Genera la primera secuencia de 6 pasos para cada mesa
3. Publica la señal inicial en el **canal de señales**
4. Monitorea en tiempo real (cada 3 segundos por defecto)
5. Cuando detecta un resultado nuevo:
   - Si **acertó** → publica en **canal de estadísticas**: `GANADA ✅ Acierto en el intento N`
   - Si **falló 6 veces** → publica: `PERDIDA ❌ Sin aciertos`
   - En ambos casos publica la nueva señal en el **canal de señales**

---

## Solución de problemas

| Problema | Causa probable | Solución |
|---|---|---|
| OCR no detecta BANCA/JUGADOR | Banner muy pequeño o colores distintos | Calibrar `banner_roi` con más área |
| Detecta el mismo resultado varias veces | Cooldown muy bajo | Aumentar `COOLDOWN` en `detector.py` (default 8s) |
| Error de Telegram 401 | Token inválido | Verificar `TELEGRAM_TOKEN` |
| Error de Telegram 400 | Chat ID incorrecto | Verificar que el bot sea admin del canal |
| EasyOCR no funciona | Falla la instalación | Probar solo con detección por color comentando la línea OCR |

---

## Ajuste fino del OCR

Si el OCR falla, puedes forzar solo detección por color en `detector.py`:

```python
def detectar_resultado(img_bgr, banner_roi):
    # Comenta la línea de OCR y usa solo color:
    # resultado = detectar_resultado_ocr(img_bgr, banner_roi)
    return detectar_resultado_color(img_bgr, banner_roi)
```

Los colores HSV se ajustan en `config/settings.py`:
```python
COLOR_JUGADOR_HSV_BAJO = (100, 120, 100)   # azul oscuro
COLOR_JUGADOR_HSV_ALTO = (130, 255, 255)
```

---

## Notas

- El bot **no hace apuestas automáticas**, solo sugiere y reporta
- Los empates no avanzan la secuencia Martingala
- La estrategia de predicción se configura con `ESTRATEGIA` en settings.py
- Los logs se guardan en `baccarat_bot.log`
