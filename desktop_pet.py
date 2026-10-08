import argparse
import os
import platform
import shutil
import json

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QGuiApplication
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QInputDialog,
    QLabel,
    QLayout,
    QMenu,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from core.engine import create_app, configure_platform, claim_single_instance
from core.scaling import ScalingManager
from core.character_loader import Character
from core.animation import AnimationPlayer
from core.behavior import BehaviorScheduler
from core.settings import Settings
from core.window import WindowController
from core.paths import get_internal_characters_path, get_user_data_path


class DesktopPet(QWidget):
    # ---------------------------------
    # La pet: ventana translucida sin bordes
    # ---------------------------------
    DOUBLE_CLICK_MS = 250

    def __init__(self, character_path):
        super().__init__()

        # Titulo de la ventana: es lo que OBS muestra en su lista de ventanas
        self.setWindowTitle("Snoot pet")

        self.settings = Settings()

        self.character = Character(character_path)

        scale_min = self.character.config["scale_limits"]["min"]
        scale_max = self.character.config["scale_limits"]["max"]

        self.scaling = ScalingManager(scale_min, scale_max)

        self.drag_offset = None
        self._double_clicked = False
        self._press_pos = None
        self._drag_offset = None
        self._press_window_pos = None
        self._moved = False
        self._compositor_move = False

        # El click simple se retrasa para no comerse el doble click
        self._click_timer = QTimer(self)
        self._click_timer.setSingleShot(True)
        self._click_timer.timeout.connect(self.cycle_state)

        self.current_state = None
        self.animation = None
        self.state_list = list(self.character.config["states"].keys())
        self.cycle_list = self.build_cycle_list()
        self.cycle_index = 0

        # Layout sin margenes para que el alfa llegue hasta el borde
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # La ventana debe ajustarse SIEMPRE al dibujo. Sin esto, al reducir la
        # escala el QLabel encoge pero la ventana se queda con el tamaño
        # anterior y el pixmap queda centrado dentro: aparecia un hueco
        # alrededor de la pet (visible sobre todo arriba) que hacia pensar que
        # no llegaba al borde de la pantalla.
        layout.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)

        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet("background: transparent;")
        layout.addWidget(self.label)

        # Estado inicial
        default_state = self.character.config["default_state"]
        self.change_state(default_state)

        # Comportamiento autónomo
        self.behavior = BehaviorScheduler(
            parent=self,
            character=self.character,
            change_state_callback=self.change_state,
        )

        # Ventana: transparencia, "always on top" y modo capturable por OBS
        self.window_ctl = WindowController(
            self,
            always_on_top=self.settings.get("always_on_top"),
            capture_mode=self.settings.get("capture_mode"),
        )

        self.create_menu()

    # ---------------------------------
    # Cambio de estado
    # ---------------------------------
    def change_state(self, state_name):
        if state_name not in self.character.config["states"]:
            return  # estado inválido, ignorar

        if self.animation:
            self.animation.stop()

        state_info, file_path = self.character.get_state(state_name)

        self.current_state = state_name

        self.animation = AnimationPlayer(
            label=self.label,
            gif_path=file_path,
            fps=state_info["fps"],
            loop=state_info.get("loop", True),
            next_state=state_info.get("next_state", None),
            scaling_manager=self.scaling,
            base_size=self.character.config.get("base_size", None),
            on_finished=self.handle_next_state,
            trim_margins=self.character.config.get("trim_margins", True),
        )

        self.animation.start()

    # ---------------------------------
    # Transición automática
    # ---------------------------------
    def handle_next_state(self, state_name=None):
        state_name = state_name or self.current_state

        state_info = self.character.config["states"][state_name]
        next_state = state_info.get("next_state")

        if next_state:
            self.change_state(next_state)

    # ---------------------------------
    # Estados y escala
    # ---------------------------------
    def build_cycle_list(self):
        # Estados por los que pasa el click.
        #
        # Los de un solo uso (loop=false) se quedan fuera: en fang son 7 de 16
        # y estan al principio, asi que los primeros clicks caian en un boop de
        # 0,2s que luego volvia solo a neutral. Desde fuera parecia que el click
        # no hacia nada. Se pueden volver a incluir con "cycle_one_shots": true
        # en el config.json del personaje.
        states = self.character.config["states"]
        incluir = self.character.config.get("cycle_one_shots", False)

        lista = [
            nombre
            for nombre, datos in states.items()
            if incluir or datos.get("loop", True)
        ]

        return lista or list(states.keys())

    def cycle_state(self):
        if not self.cycle_list:
            return

        # 🔥 Pausar behavior mientras usuario interactúa
        if hasattr(self, "behavior") and self.behavior:
            self.behavior.stop()

        self.cycle_index = (self.cycle_index + 1) % len(self.cycle_list)
        next_state = self.cycle_list[self.cycle_index]

        self.change_state(next_state)

        # 🔥 Reiniciar behavior después de 5 segundos
        QTimer.singleShot(5000, self.restart_behavior)

    def restart_behavior(self):
        if hasattr(self, "behavior") and self.behavior:
            self.behavior.stop()
            self.behavior = BehaviorScheduler(
                parent=self,
                character=self.character,
                change_state_callback=self.change_state,
            )

    def scale_up(self):
        # No hace falta recrear la animación: el siguiente frame pide los
        # frames a la escala nueva y los cachea.
        self.scaling.increase()

    def scale_down(self):
        self.scaling.decrease()

    # ---------------------------------
    # Cambiar personaje dinámicamente
    # ---------------------------------
    def switch_character(self, character_name):
        internal_path = os.path.join(get_internal_characters_path(), character_name)
        user_path = os.path.join(get_user_data_path(), character_name)

        # 🔥 Prioridad a personajes del usuario
        if os.path.exists(user_path):
            new_path = user_path
        elif os.path.exists(internal_path):
            new_path = internal_path
        else:
            print(f"Character folder not found for: {character_name}")
            return

        # Detener animación actual
        if self.animation:
            self.animation.stop()

        # Detener scheduler
        if hasattr(self, "behavior") and self.behavior:
            self.behavior.stop()

        # Cargar nuevo personaje
        self.character = Character(new_path)

        # 🔥 Actualizar lista de estados
        self.state_list = list(self.character.config["states"].keys())
        self.cycle_list = self.build_cycle_list()
        self.cycle_index = 0

        # Estado inicial
        default_state = self.character.config["default_state"]
        self.change_state(default_state)

        # Reiniciar behavior
        self.behavior = BehaviorScheduler(
            parent=self,
            character=self.character,
            change_state_callback=self.change_state,
        )

        self.create_menu()

    # ---------------------------------
    # Menu contextual
    # ---------------------------------
    def create_menu(self):
        self.menu = QMenu(self)

        character_menu = self.menu.addMenu("Switch Character")

        for char_name in self.get_available_characters():
            action = character_menu.addAction(char_name.capitalize())
            action.triggered.connect(
                lambda _checked=False, name=char_name: self.switch_character(name)
            )

        self.menu.addSeparator()

        # Always on Top
        self.topmost_action = QAction("Always on Top", self, checkable=True)
        self.topmost_action.setChecked(self.settings.get("always_on_top"))
        self.topmost_action.triggered.connect(self.toggle_always_on_top)
        self.menu.addAction(self.topmost_action)

        # Capture Mode (OBS)
        self.capture_action = QAction("Capture Mode (OBS)", self, checkable=True)
        self.capture_action.setChecked(self.settings.get("capture_mode"))
        self.capture_action.triggered.connect(self.toggle_capture_mode)
        self.menu.addAction(self.capture_action)

        if platform.system() == "Linux":
            self.native_wayland_action = QAction(
                "Native Wayland (restart)", self, checkable=True
            )
            self.native_wayland_action.setChecked(
                self.settings.get("platform") != "xcb"
            )
            self.native_wayland_action.triggered.connect(self.toggle_native_wayland)
            self.menu.addAction(self.native_wayland_action)

        self.menu.addSeparator()
        self.menu.addAction("Import Character", self.import_character)
        self.menu.addSeparator()
        self.menu.addAction("Quit", QApplication.instance().quit)

    # ---------------------------------
    # Backend Wayland nativo vs XWayland
    # ---------------------------------
    def toggle_native_wayland(self):
        # Con xdg-shell no hay keep-above, asi que en nativo la pet acaba
        # detras de cualquier ventana nueva.
        native = self.native_wayland_action.isChecked()
        self.settings.set("platform", "wayland" if native else "xcb")

        QMessageBox.information(
            self,
            "Restart needed",
            "The change applies the next time the pet starts.\n\n"
            "On native Wayland the pet can go behind other windows: the "
            "Wayland protocol has no 'keep above' request, so the "
            "'Always on Top' option only works with the XWayland backend.",
        )

    # ---------------------------------
    # Listar personajes disponibles
    # ---------------------------------
    def get_available_characters(self):
        characters = []

        internal_path = get_internal_characters_path()
        user_path = get_user_data_path()

        for base_path in [internal_path, user_path]:
            if os.path.exists(base_path):
                for name in os.listdir(base_path):
                    full_path = os.path.join(base_path, name)
                    if os.path.isdir(full_path):
                        characters.append(name)

        return characters

    # ---------------------------------
    # Toggles persistidos
    # ---------------------------------
    def toggle_always_on_top(self, checked=None):
        enabled = self.topmost_action.isChecked()
        self.settings.set("always_on_top", enabled)
        self.window_ctl.set_always_on_top(enabled)

    def toggle_capture_mode(self, checked=None):
        enabled = self.capture_action.isChecked()
        self.settings.set("capture_mode", enabled)
        self.window_ctl.set_capture_mode(enabled)

    # ---------------------------------
    # Recolocar la ventana
    # ---------------------------------
    def center_window(self):
        screen = QApplication.primaryScreen()
        if screen is None:
            return

        geometry = screen.availableGeometry()

        self.adjustSize()
        size = self.size()

        self.move(
            geometry.center().x() - size.width() // 2,
            geometry.center().y() - size.height() // 2,
        )

    # ---------------------------------
    # Eventos de ratón
    # ---------------------------------
    DRAG_THRESHOLD = 4   # px de margen antes de considerar que es arrastre

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._press_pos = event.globalPosition().toPoint()
            self._drag_offset = self._press_pos - self.frameGeometry().topLeft()
            self._press_window_pos = self.pos()
            self._moved = False
            self._compositor_move = False
            self._double_clicked = False

            # Qt documenta llamar a startSystemMove() DESDE el press, no desde
            # el move: es cuando el puntero esta realmente agarrado. Si se
            # llama mas tarde devuelve False y, en Wayland, el fallback
            # (QWidget.move) es un no-op -> la pet se queda clavada.
            if self._start_system_move():
                self._compositor_move = True

        super().mousePressEvent(event)

    def _start_system_move(self):
        # En Wayland el cliente NO puede posicionar su propia ventana: QWidget.move()
        # solo cambia la posición interna de Qt y el compositor la ignora. La
        # única forma de arrastrar es pedirle el movimiento al compositor, que
        # internamente usa el request move de xdg-shell.
        #
        # Solo en Wayland: en X11/Windows el arrastre manual con move() funciona y
        # es más predecible.
        if QGuiApplication.platformName() != "wayland":
            return False

        handle = self.windowHandle()
        if handle is None:
            return False

        try:
            started = bool(handle.startSystemMove())
        except Exception:
            return False

        _debug(f"startSystemMove -> {started}")
        if not started:
            _debug("el compositor NO ha cogido el arrastre; en Wayland "
                   "QWidget.move() no hace nada, la ventana no se movra")

        return started

    def mouseMoveEvent(self, event):
        # Con arrastre gestionado por el compositor el puntero ya no es
        # nuestro: no hay que hacer nada aquí.
        if getattr(self, "_compositor_move", False):
            return

        if (event.buttons() & Qt.LeftButton) and self._press_pos is not None:
            if not self._moved:
                delta = (
                    event.globalPosition().toPoint() - self._press_pos
                ).manhattanLength()

                if delta > self.DRAG_THRESHOLD:
                    self._moved = True

            # Arrastre manual: solo funciona donde move() significa algo
            # (X11/Windows). En Wayland es un no-op.
            if self._moved and self._drag_offset is not None:
                self.move(event.globalPosition().toPoint() - self._drag_offset)

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            # "Se ha movido" se deduce comparando la posición de la ventana,
            # porque con arrastre del compositor no nos llegan los moves.
            moved = getattr(self, "_moved", False)
            press_pos = getattr(self, "_press_window_pos", None)
            if press_pos is not None and self.pos() != press_pos:
                moved = True

            # Qt entrega el doble click como press/release/dblclick/release:
            # el segundo release volvería a encolar un cambio de estado que
            # pisaría el boop del doble click medio segundo después.
            double_clicked = getattr(self, "_double_clicked", False)

            self._press_pos = None
            self._drag_offset = None
            self._press_window_pos = None
            self._moved = False
            self._compositor_move = False
            self._double_clicked = False

            # Un click simple cambia de estado. Se retrasa un poco porque Qt
            # avisa del doble click después del primer release, y sin esta
            # espera el boop se comía dos cambios de estado.
            if not moved and not double_clicked:
                self._click_timer.start(self.DOUBLE_CLICK_MS)

        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._click_timer.stop()
            self._double_clicked = True
            self.change_state("boop")
        super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event):
        delta = event.angleDelta().y()

        if delta > 0:
            self.scale_up()
        elif delta < 0:
            self.scale_down()

        event.accept()

    def contextMenuEvent(self, event):
        self.menu.exec(event.globalPos())
        event.accept()

    # ---------------------------------
    # Import Character System
    # ---------------------------------
    def import_character(self):
        # 🔥 Guardar posición actual
        pos = self.pos()

        # 🔥 Pausar behavior
        if hasattr(self, "behavior") and self.behavior:
            self.behavior.stop()

        # 🔥 Ocultar completamente el pet
        self.hide()

        try:
            file_paths, _ = QFileDialog.getOpenFileNames(
                self, "Select Character GIFs", "", "GIF files (*.gif)"
            )

            if not file_paths:
                return

            first_file = os.path.basename(file_paths[0])
            detected_name = first_file.split("_")[0]

            character_name, ok = QInputDialog.getText(
                self,
                "Character Name",
                f"Detected name: '{detected_name}'.\n"
                "Rename character or press OK to keep:",
                text=detected_name,
            )

            if not ok:
                return

            if not character_name.strip():
                QMessageBox.critical(self, "Error", "Character name cannot be empty.")
                return

            character_name = character_name.strip().lower()

            base_path = get_user_data_path()
            new_character_path = os.path.join(base_path, character_name)

            if os.path.exists(new_character_path):
                QMessageBox.information(
                    self,
                    "Attention",
                    "You already have a character with that name.",
                )
                return

            os.makedirs(new_character_path, exist_ok=True)

            states = {}

            for file_path in file_paths:
                filename = os.path.basename(file_path)
                shutil.copy(file_path, new_character_path)

                name_without_ext = os.path.splitext(filename)[0]
                parts = name_without_ext.split("_", 1)

                state_name = parts[1] if len(parts) == 2 else "neutral"

                states[state_name] = {
                    "file": filename,
                    "fps": 12,
                    "loop": True,
                }

            character_config = {
                "name": character_name.capitalize(),
                "default_state": (
                    "neutral" if "neutral" in states else list(states.keys())[0]
                ),
                "base_size": 600,
                "scale_limits": {
                    "min": 0.4,
                    "max": 2.0,
                },
                "states": states,
                "behavior": {
                    "enabled": True,
                    "interval_min": 6,
                    "interval_max": 14,
                },
            }

            json_path = os.path.join(new_character_path, "config.json")
            with open(json_path, "w") as f:
                json.dump(character_config, f, indent=4)

            QMessageBox.information(
                self, "Success", f"Character '{character_name}' imported successfully!"
            )

            self.create_menu()

        finally:
            # 🔥 Restaurar ventana en la posición original
            self.move(pos)
            self.show()

            # 🔥 Reiniciar behavior
            self.behavior = BehaviorScheduler(
                parent=self,
                character=self.character,
                change_state_callback=self.change_state,
            )


def _debug(message):
    """Log de diagnóstico. Con SNOOT_LOG=1 se guarda en el directorio de datos.

    Lo usa el arrastre en Wayland: como la app no puede posicionarse a si
    misma, si el compositor no acepta el arrastre la pet se queda clavada y no
    hay forma de saberlo sin ver el registro.
    """
    print(f"[pet] {message}")

    if os.environ.get("SNOOT_LOG") != "1":
        return

    try:
        log_path = os.path.join(os.path.dirname(get_user_data_path()),
                                "pet.log")

        # No dejar que crezca sin limite
        if os.path.exists(log_path) and os.path.getsize(log_path) > 65536:
            os.remove(log_path)

        with open(log_path, "a", encoding="utf-8") as f:
            f.write(message + "\n")
    except OSError:
        pass


def parse_args():
    parser = argparse.ArgumentParser(description="Snoot pet desktop companion")

    parser.add_argument(
        "--character",
        default="fang",
        help="Carpeta del personaje a cargar (por defecto: fang)",
    )
    parser.add_argument(
        "--capture",
        action="store_true",
        help="Inicia en modo captura (ventana visible para OBS)",
    )
    parser.add_argument(
        "--no-always-on-top",
        action="store_true",
        help="Inicia sin el always on top",
    )
    parser.add_argument(
        "--platform",
        choices=["xcb", "wayland"],
        default=None,
        help="Backend de Qt en Linux. xcb (XWayland) es el que soporta "
             "always on top de verdad; wayland es nativo pero se queda detras "
             "de las ventanas nuevas",
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    settings = Settings()
    configure_platform(args.platform or settings.get("platform"))

    app = create_app()

    # Solo una pet a la vez: varias instancias "always on top" compiten por el
    # stacking de KWin y la que estas mirando acaba tapada por otra.
    if claim_single_instance(app) is None:
        print("Ya hay una pet corriendo. Cierrala antes de abrir otra.")
        raise SystemExit(0)

    character_path = os.path.join(get_internal_characters_path(), args.character)
    if not os.path.isdir(character_path):
        character_path = os.path.join(get_user_data_path(), args.character)

    pet = DesktopPet(character_path)

    if args.capture:
        pet.capture_action.setChecked(True)
        pet.toggle_capture_mode()

    if args.no_always_on_top:
        pet.topmost_action.setChecked(False)
        pet.toggle_always_on_top()

    pet.center_window()
    pet.show()

    sys_exit = app.exec()
    raise SystemExit(sys_exit)