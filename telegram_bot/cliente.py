"""
Cliente Telegram
Envía señales y estadísticas a los dos canales configurados
"""
import asyncio
import io
import logging
from telegram import Bot
from telegram.error import TelegramError

from config.settings import (
    TELEGRAM_TOKEN,
    CANAL_SENALES_ID,
    CANAL_ESTADISTICAS_ID,
)

logger = logging.getLogger(__name__)

JUGADOR = "JUGADOR"
BANCA   = "BANCA"
EMPATE  = "EMPATE"

_bot: Bot | None = None


def get_bot() -> Bot:
    global _bot
    if _bot is None:
        _bot = Bot(token=TELEGRAM_TOKEN)
    return _bot


# ── Formateo de mensajes ──────────────────────────────────────

def _emoji_resultado(resultado: str) -> str:
    return {"JUGADOR": "🔵 JUGADOR", "BANCA": "🔴 BANCA", "EMPATE": "⚪ EMPATE"}.get(resultado, resultado)


def _texto_secuencia(secuencia: list[str], paso_actual: int = 0, paso_acierto: int = 0) -> str:
    emojis = {JUGADOR: "🔵", BANCA: "🔴"}
    partes = []
    for i, pred in enumerate(secuencia, start=1):
        emoji = emojis.get(pred, "❓")
        if paso_acierto and i == paso_acierto:
            partes.append(f"{i}.{emoji}✅")
        elif i == paso_actual:
            partes.append(f"{i}.{emoji}◀")   # flecha al paso actual
        else:
            partes.append(f"{i}.{emoji}")
    return "  ".join(partes)


def _caption_senal(nombre_mesa: str, secuencia: list[str], paso: int) -> str:
    seq_texto = _texto_secuencia(secuencia, paso_actual=paso)
    return (
        f"🃏 *{nombre_mesa}*\n\n"
        f"{seq_texto}\n\n"
        f"_Intento {paso} de 6_"
    )


def _caption_acierto(nombre_mesa: str, secuencia: list[str], paso: int, resultado_real: str) -> str:
    seq_texto = _texto_secuencia(secuencia, paso_acierto=paso)
    return (
        f"🃏 *{nombre_mesa}*\n\n"
        f"{seq_texto}\n\n"
        f"✅ *GANADA* — Acierto en el intento {paso}\n"
        f"Resultado real: {_emoji_resultado(resultado_real)}"
    )


def _caption_perdida(nombre_mesa: str, secuencia: list[str], resultado_real: str) -> str:
    emojis = {JUGADOR: "🔵", BANCA: "🔴"}
    seq_texto = "  ".join(
        f"{i}.{emojis.get(p,'?')}❌" for i, p in enumerate(secuencia, 1)
    )
    return (
        f"🃏 *{nombre_mesa}*\n\n"
        f"{seq_texto}\n\n"
        f"❌ *PERDIDA* — Sin aciertos en 6 intentos\n"
        f"Último resultado: {_emoji_resultado(resultado_real)}"
    )


def _texto_estadisticas_header() -> str:
    return "📊 *Estadísticas WIN 365*"


# ── Envíos principales ────────────────────────────────────────

async def enviar_senal(
    imagen_bytes: bytes,
    nombre_mesa: str,
    secuencia: list[str],
    paso: int,
) -> bool:
    """Publica la señal (predicción) en el canal de señales"""
    caption = _caption_senal(nombre_mesa, secuencia, paso)
    return await _enviar_foto(CANAL_SENALES_ID, imagen_bytes, caption)


async def enviar_resultado_acierto(
    imagen_bytes: bytes,
    nombre_mesa: str,
    secuencia: list[str],
    paso: int,
    resultado_real: str,
) -> bool:
    """Publica resultado GANADA en el canal de estadísticas"""
    # Primero el header de estadísticas
    await _enviar_texto(CANAL_ESTADISTICAS_ID, _texto_estadisticas_header())
    caption = _caption_acierto(nombre_mesa, secuencia, paso, resultado_real)
    return await _enviar_foto(CANAL_ESTADISTICAS_ID, imagen_bytes, caption)


async def enviar_resultado_perdida(
    imagen_bytes: bytes,
    nombre_mesa: str,
    secuencia: list[str],
    resultado_real: str,
) -> bool:
    """Publica resultado PERDIDA en el canal de estadísticas"""
    await _enviar_texto(CANAL_ESTADISTICAS_ID, _texto_estadisticas_header())
    caption = _caption_perdida(nombre_mesa, secuencia, resultado_real)
    return await _enviar_foto(CANAL_ESTADISTICAS_ID, imagen_bytes, caption)


# ── Helpers internos ──────────────────────────────────────────

async def _enviar_foto(chat_id: int, imagen_bytes: bytes, caption: str) -> bool:
    try:
        bot = get_bot()
        await bot.send_photo(
            chat_id=chat_id,
            photo=io.BytesIO(imagen_bytes),
            caption=caption,
            parse_mode="Markdown",
        )
        return True
    except TelegramError as e:
        logger.error(f"Error enviando foto a {chat_id}: {e}")
        return False


async def _enviar_texto(chat_id: int, texto: str) -> bool:
    try:
        bot = get_bot()
        await bot.send_message(
            chat_id=chat_id,
            text=texto,
            parse_mode="Markdown",
        )
        return True
    except TelegramError as e:
        logger.error(f"Error enviando texto a {chat_id}: {e}")
        return False


async def verificar_conexion() -> bool:
    """Verifica que el token sea válido"""
    try:
        bot = get_bot()
        me = await bot.get_me()
        print(f"✅ Bot conectado: @{me.username}")
        return True
    except TelegramError as e:
        print(f"❌ Error de conexión Telegram: {e}")
        return False
