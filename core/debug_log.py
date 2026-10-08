"""Log de diagnóstico de los gestos del ratón.

Sin Qt a propósito, para que las pruebas puedan comprobarlo sin montar una
QApplication: desktop_pet.py lo importa, pero este módulo no importa nada de
PySide6.
"""
import os
import time

from core.paths import get_user_data_path

# Por encima de esto se reinicia el archivo, para que una sesión de depuración
# larga no deje un log de cientos de megas.
MAX_LOG_BYTES = 65536

FLAG = "SNOOT_LOG"


def _log_path():
    return os.path.join(os.path.dirname(get_user_data_path()), "pet.log")


def debug(message):
    """Registra un gesto del ratón, solo con SNOOT_LOG=1.

    Anota cada press/move/release con la distancia y la decisión que se ha
    tomado: es lo que deja ver que llega de verdad desde el ratón en vez de
    adivinarlo.

    Antes escribía en stdout siempre, no solo con SNOOT_LOG=1. Cada movimiento
    del ratón sobre la pet pasaba por un print en el hilo de la interfaz, así
    que al arrastrar salía una línea por evento (ruidoso al lanzarla desde una
    terminal) sin coste para nadie. Ahora el print va detrás del mismo flag que
    el archivo, que es lo que se quiere: depurar o no depurar, pero no por
    defecto.
    """
    if os.environ.get(FLAG) != "1":
        return

    print(f"[pet] {message}")

    try:
        log_path = _log_path()

        # El corte mira el tamaño ANTES de escribir: el reinicio se ve en la
        # escritura siguiente, no en la que se pasa de 64 KB.
        if os.path.exists(log_path) and os.path.getsize(log_path) > MAX_LOG_BYTES:
            os.remove(log_path)

        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%H:%M:%S')} {message}\n")
    except OSError:
        pass


# Alias corto: en desktop_pet.py las llamadas son "_debug(...)" y quedaban
# legibles como están. Se mantiene el nombre para no tocar 8 llamadas.
_debug = debug