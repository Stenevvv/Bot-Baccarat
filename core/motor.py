"""
Motor de predicción + Martingala
Genera la secuencia de 6 pasos y rastrea aciertos por mesa
"""
from collections import deque
from config.settings import (
    PASOS_SECUENCIA, ESTRATEGIA,
    VENTANA_FRECUENCIA
)

JUGADOR = "JUGADOR"
BANCA   = "BANCA"
EMPATE  = "EMPATE"


class MesaEstado:
    """
    Mantiene el estado completo de UNA mesa:
    - historial de resultados reales
    - secuencia actual de predicciones (6 pasos)
    - en qué paso vamos y si ya acertó
    """

    def __init__(self, nombre: str):
        self.nombre = nombre
        self.historial: deque[str] = deque(maxlen=50)   # últimas 50 manos reales
        self.secuencia: list[str] = []                  # predicciones 1-6
        self.paso_actual: int = 0                       # 0 = esperando nueva secuencia
        self.acertado: bool = False
        self.ultimo_resultado: str | None = None
        self.mano_numero: int = 0                       # contador global de manos

    # ── Estado legible ────────────────────────────────────────

    def secuencia_texto(self) -> str:
        """'1.🔵 2.🔴 3.🔵 4.🔴 5.🔵 6.🔴'"""
        emojis = {JUGADOR: "🔵", BANCA: "🔴"}
        partes = []
        for i, pred in enumerate(self.secuencia, start=1):
            marca = "✅" if (self.acertado and i == self.intento_acierto) else ""
            partes.append(f"{i}.{emojis.get(pred,'❓')}{marca}")
        return "  ".join(partes)

    @property
    def intento_acierto(self) -> int | None:
        """Número del intento donde acertó (1-6) o None"""
        if not self.acertado:
            return None
        return self.paso_actual   # se fija en verificar_resultado

    def necesita_nueva_secuencia(self) -> bool:
        return self.paso_actual == 0 or self.acertado or self.paso_actual > PASOS_SECUENCIA

    # ── Generación de secuencia ───────────────────────────────

    def generar_secuencia(self) -> list[str]:
        """Genera los 6 pasos según la estrategia configurada"""
        if len(self.historial) == 0:
            # Sin historial: alternar empezando por JUGADOR
            base = JUGADOR
        elif ESTRATEGIA == "ultimo":
            base = self._ultimo_valido()
        elif ESTRATEGIA == "frecuencia":
            base = self._mas_frecuente()
        elif ESTRATEGIA == "alternado":
            base = self._opuesto(self._ultimo_valido())
        else:
            base = self._mas_frecuente()

        return self._construir_secuencia(base)

    def _ultimo_valido(self) -> str:
        """Último resultado que no sea EMPATE"""
        for r in reversed(self.historial):
            if r != EMPATE:
                return r
        return JUGADOR

    def _mas_frecuente(self) -> str:
        ventana = [r for r in list(self.historial)[-VENTANA_FRECUENCIA:]
                   if r != EMPATE]
        if not ventana:
            return JUGADOR
        return max(set(ventana), key=ventana.count)

    def _opuesto(self, resultado: str) -> str:
        return BANCA if resultado == JUGADOR else JUGADOR

    def _construir_secuencia(self, base: str) -> list[str]:
        """
        Construye 6 pasos: comienza con 'base' y alterna
        según el patrón Martingala clásico
        Paso:  1     2     3     4     5     6
        Tipo:  base  base  opp   base  opp   opp
        """
        opp = self._opuesto(base)
        patron = [base, base, opp, base, opp, opp]
        return patron

    # ── Verificación de resultado ─────────────────────────────

    def registrar_resultado(self, resultado: str) -> dict:
        """
        Recibe el resultado real de una mano y:
        1. Lo agrega al historial
        2. Verifica contra la secuencia actual
        3. Retorna un dict con el evento a publicar

        Returns:
            {
                "tipo":   "nueva_secuencia" | "acierto" | "siguiente" | "perdida",
                "mesa":   str,
                "resultado_real": str,
                "secuencia": list[str],
                "paso":   int,
                "mano":   int,
            }
        """
        if resultado == EMPATE:
            # Los empates no avanzan la secuencia
            self.historial.append(resultado)
            self.mano_numero += 1
            return {"tipo": "empate", "mesa": self.nombre,
                    "resultado_real": resultado, "mano": self.mano_numero}

        self.historial.append(resultado)
        self.ultimo_resultado = resultado
        self.mano_numero += 1

        # ¿Necesitamos nueva secuencia?
        if self.necesita_nueva_secuencia():
            self.secuencia = self.generar_secuencia()
            self.paso_actual = 1
            self.acertado = False

        # Verificar paso actual
        prediccion = self.secuencia[self.paso_actual - 1]
        acerto = (prediccion == resultado)

        if acerto:
            self.acertado = True
            evento = {
                "tipo": "acierto",
                "mesa": self.nombre,
                "resultado_real": resultado,
                "prediccion": prediccion,
                "secuencia": self.secuencia.copy(),
                "paso": self.paso_actual,
                "mano": self.mano_numero,
            }
            # Después de acierto, la siguiente mano inicia nueva secuencia
            # (paso_actual queda fijo para el texto)
        else:
            if self.paso_actual >= PASOS_SECUENCIA:
                evento = {
                    "tipo": "perdida",
                    "mesa": self.nombre,
                    "resultado_real": resultado,
                    "prediccion": prediccion,
                    "secuencia": self.secuencia.copy(),
                    "paso": self.paso_actual,
                    "mano": self.mano_numero,
                }
                self.paso_actual = 0   # fuerza nueva secuencia en la próxima mano
            else:
                self.paso_actual += 1
                evento = {
                    "tipo": "siguiente",
                    "mesa": self.nombre,
                    "resultado_real": resultado,
                    "prediccion": prediccion,
                    "secuencia": self.secuencia.copy(),
                    "paso": self.paso_actual - 1,    # paso que falló
                    "mano": self.mano_numero,
                }

        return evento


class GestorMesas:
    """Mantiene el estado de todas las mesas activas"""

    def __init__(self, nombres: list[str]):
        self.mesas: dict[str, MesaEstado] = {
            nombre: MesaEstado(nombre) for nombre in nombres
        }

    def registrar(self, nombre: str, resultado: str) -> dict:
        if nombre not in self.mesas:
            raise KeyError(f"Mesa '{nombre}' no registrada")
        return self.mesas[nombre].registrar_resultado(resultado)

    def estado(self, nombre: str) -> MesaEstado:
        return self.mesas[nombre]
