\# Baccarat Bot — Rushbet Pragmatic Play



Bot que monitorea 3 mesas de baccarat en vivo, detecta el resultado por el color

del banner (Jugador / Banca / Empate) y envía señales y estadísticas a dos

canales de Telegram.



> Proyecto experimental/educativo. Automatizar un casino puede violar sus

> términos de servicio. Úsalo bajo tu responsabilidad.



\## Instalación

&#x20;   pip install -r requirements.txt



\## Configuración

1\. Crea un archivo `.env` con: `TELEGRAM\_TOKEN=tu\_token` (no se sube a GitHub).

2\. Ajusta canales, mesas y tiempos en `config/settings.py`.

3\. `MODO\_PRUEBA = True` para probar sin enviar a Telegram; `False` para operar.



\## Uso

&#x20;   python main.py



Herramientas:

\- `calibrar\_coordenadas.py` — hallar coordenadas de pantalla.

\- `diagnostico.py` — ver qué detecta el bot sin enviar a Telegram.



\## Notas

\- El empate es un \*push\*: no avanza el movimiento.

\- Tras perder los 6 intentos hay una pausa global de 30 min.

\- Seguridad: el token solo se lee del `.env`. Un commit muy antiguo tuvo un token

&#x20; escrito en el código; ese token fue \*\*revocado\*\* y ya no es válido.



