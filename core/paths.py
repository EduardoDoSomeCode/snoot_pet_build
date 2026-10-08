import os
import platform
import sys

APP_NAME = "Snoot_pet"


def is_portable_mode():
    # Si existe carpeta "portable" junto al ejecutable → modo portable
    return os.path.exists(os.path.join(get_base_dir(), "portable"))


def get_base_dir():
    # Carpeta del ejecutable, o de la app si se ejecuta desde el codigo
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)

    return get_app_dir()


def get_app_dir():
    # Carpeta de la app (…/snoot-pet), independiente del directorio actual
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_user_data_dir():
    # Carpeta raiz de datos del usuario (personajes + ajustes)
    if is_portable_mode():
        base_path = os.path.join(get_base_dir(), "user_data")
    elif platform.system() == "Windows":
        base_path = os.path.join(os.getenv("APPDATA") or get_base_dir(), APP_NAME)
    elif platform.system() == "Darwin":
        base_path = os.path.join(
            os.path.expanduser("~/Library/Application Support"), APP_NAME
        )
    else:
        base_path = os.path.join(os.path.expanduser("~/.local/share"), APP_NAME)

    try:
        os.makedirs(base_path, exist_ok=True)
    except OSError:
        pass

    return base_path


def get_user_data_path():
    characters_path = os.path.join(get_user_data_dir(), "characters")

    # "Import Character" hace makedirs de la subcarpeta del personaje, que
    # fallaría si el padre no existe
    try:
        os.makedirs(characters_path, exist_ok=True)
    except OSError:
        pass

    return characters_path


def get_settings_path():
    return os.path.join(get_user_data_dir(), "settings.json")


def get_internal_characters_path():
    return resource_path(os.path.join("art_assets", "characters"))


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS  # PyInstaller temp folder
    except Exception:
        base_path = get_app_dir()

    return os.path.join(base_path, relative_path)