import os
import json


class Character:
    def __init__(self, base_path):
        # 🔥 Convertir siempre a ruta absoluta
        self.base_path = os.path.abspath(base_path)
        self.config = self.load_config()

    # ---------------------------------
    # Cargar config.json
    # ---------------------------------
    def load_config(self):
        config_path = os.path.join(self.base_path, "config.json")

        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Config not found: {config_path}")

        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)

    # ---------------------------------
    # Obtener estado + ruta absoluta del GIF
    # ---------------------------------
    def get_state(self, state):
        if state not in self.config["states"]:
            raise ValueError(f"State '{state}' not found in character config.")

        state_info = self.config["states"][state]

        file_name = state_info["file"]

        # 🔥 Ruta absoluta real del gif
        file_path = os.path.abspath(os.path.join(self.base_path, file_name))

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Animation file not found: {file_path}")

        return state_info, file_path
