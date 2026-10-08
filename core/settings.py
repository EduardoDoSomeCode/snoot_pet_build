import json
import os

from core.paths import get_settings_path

# Valores por defecto de la app
DEFAULTS = {
    "always_on_top": True,   # pet por encima de otros programas
    "capture_mode": False,   # ventana capturable por OBS (sin override-redirect)
}


class Settings:
    # ---------------------------------
    # Ajustes persistidos en JSON
    # ---------------------------------
    def __init__(self, path=None):
        self.path = path or get_settings_path()
        self.data = dict(DEFAULTS)
        self.load()

    def load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                stored = json.load(f)

            if isinstance(stored, dict):
                for key, default in DEFAULTS.items():
                    if key in stored:
                        self.data[key] = bool(stored[key])
        except (OSError, ValueError):
            # Sin archivo / corrupto → usamos los defaults
            pass

    def save(self):
        try:
            directory = os.path.dirname(self.path)
            if directory:
                os.makedirs(directory, exist_ok=True)

            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=4)
        except OSError as e:
            print(f"Could not save settings: {e}")

    def get(self, key, default=None):
        if key in self.data:
            return self.data[key]
        return DEFAULTS.get(key, default)

    def set(self, key, value):
        self.data[key] = bool(value)
        self.save()
        return self.data[key]