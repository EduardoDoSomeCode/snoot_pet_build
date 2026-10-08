import random

from PySide6.QtCore import QTimer


class BehaviorScheduler:
    # ---------------------------------
    # Cambio de estado autónomo, con QTimer
    #
    # Nota: se mantiene el criterio original (estados marcados con "auto" y su
    # "weight"). Los config.json que trae la app usan "behavior_weight", que
    # este scheduler todavía no lee, igual que antes del port.
    # ---------------------------------
    def __init__(self, parent, character, change_state_callback):
        self.parent = parent
        self.character = character
        self.change_state = change_state_callback

        self.enabled = character.config.get("behavior", {}).get("enabled", False)

        self.timer = QTimer(self.parent)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.execute_behavior)

        if not self.enabled:
            return

        behavior_cfg = character.config["behavior"]

        self.interval_min = behavior_cfg.get("interval_min", 5)
        self.interval_max = behavior_cfg.get("interval_max", 10)

        self.schedule_next()

    # -----------------------------------
    # Programar siguiente acción
    # -----------------------------------
    def schedule_next(self):
        delay = random.randint(self.interval_min, self.interval_max) * 1000
        self.timer.start(delay)

    # -----------------------------------
    # Elegir estado aleatorio
    # -----------------------------------
    def execute_behavior(self):
        auto_states = []

        for state_name, state_data in self.character.config["states"].items():
            if state_data.get("auto"):
                weight = state_data.get("weight", 1)
                auto_states.extend([state_name] * weight)

        if auto_states:
            chosen_state = random.choice(auto_states)

            if chosen_state in self.character.config["states"]:
                self.change_state(chosen_state)

        self.schedule_next()

    # -----------------------------------
    # Detener scheduler
    # -----------------------------------
    def stop(self):
        self.timer.stop()