from PIL import Image
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPixmap


class AnimationPlayer:
    # ---------------------------------
    # Reproduccion de GIF sobre un QLabel
    #
    # El GIF se decodifica una sola vez con PIL (y se reescala con LANCZOS
    # como antes); los frames ya reescalados se cachean por escala.
    # ---------------------------------
    def __init__(
        self,
        label,
        gif_path,
        fps,
        loop=True,
        next_state=None,
        scaling_manager=None,
        base_size=None,
        on_finished=None,
        trim_margins=True,
    ):
        self.label = label
        self.gif_path = gif_path
        self.fps = fps
        self.loop = loop
        self.next_state = next_state
        self.scaling_manager = scaling_manager
        self.base_size = base_size
        self.on_finished = on_finished
        self.trim_margins = trim_margins

        self.original_frames = []
        self.scaled_cache = {}  # cache por escala

        self.current_frame = 0
        self.running = False

        self.timer = QTimer(self.label)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.play)

        self.load_gif()

    # ---------------------------------
    # Cargar GIF original una sola vez
    # ---------------------------------
    def load_gif(self):
        frames = []

        gif = Image.open(self.gif_path)

        try:
            while True:
                frames.append(gif.copy().convert("RGBA"))
                gif.seek(len(frames))
        except EOFError:
            pass

        if not frames:
            return

        if self.trim_margins:
            frames = self._trim(frames)
        elif self.base_size:
            frames = self._apply_base_size(frames)

        self.original_frames = frames

    # ---------------------------------
    # Escalar por base_size (comportamiento original)
    # ---------------------------------
    @staticmethod
    def _apply_base_size(frames, base_size):
        scale = base_size / frames[0].height
        out = []
        for frame in frames:
            out.append(frame.resize(
                (max(1, int(frame.width * scale)), base_size), Image.LANCZOS))
        return out

    # ---------------------------------
    # Recortar el margen transparente (union de todos los frames, para que la
    # pet no "vibra" entre fotogramas)
    # ---------------------------------
    @staticmethod
    def _union_bbox(frames):
        box = None

        for frame in frames:
            other = frame.getchannel("A").getbbox()
            if other is None:
                continue
            if box is None:
                box = list(other)
            else:
                box = [
                    min(box[0], other[0]),
                    min(box[1], other[1]),
                    max(box[2], other[2]),
                    max(box[3], other[3]),
                ]

        return tuple(box) if box else None

    def _trim(self, frames):
        box = self._union_bbox(frames)
        if box is None:
            return frames

        # Proporción que se tenía antes de recortar, para no cambiar el tamaño
        # en pantalla de la pet (solo quitar el aire que nunca se ve).
        scale = self.base_size / frames[0].height if self.base_size else 1.0

        out = []
        for frame in frames:
            cropped = frame.crop(box)
            if scale != 1.0:
                cropped = cropped.resize(
                    (max(1, int(cropped.width * scale)),
                     max(1, int(cropped.height * scale))),
                    Image.LANCZOS,
                )
            out.append(cropped)

        return out

    # ---------------------------------
    # PIL frame -> QPixmap (con alfa)
    # ---------------------------------
    @staticmethod
    def _to_pixmap(frame):
        raw = frame.tobytes("raw", "RGBA")
        image = QImage(
            raw,
            frame.width,
            frame.height,
            frame.width * 4,
            QImage.Format_RGBA8888,
        )
        # copy(): QImage no copia el buffer, y el de Pillow es temporal.
        return QPixmap.fromImage(image.copy())

    # ---------------------------------
    # Generar frames escalados SOLO si necesario
    # ---------------------------------
    def get_scaled_frames(self):
        scale = round(self.scaling_manager.scale, 2)

        if scale not in self.scaled_cache:
            scaled_frames = []

            for frame in self.original_frames:
                if scale == 1.0:
                    resized = frame
                else:
                    width = max(1, int(frame.width * scale))
                    height = max(1, int(frame.height * scale))
                    resized = frame.resize((width, height), Image.LANCZOS)

                scaled_frames.append(self._to_pixmap(resized))

            self.scaled_cache[scale] = scaled_frames

        return self.scaled_cache[scale]

    # ---------------------------------
    def start(self):
        self.running = True
        self.play()

    def stop(self):
        self.running = False
        self.timer.stop()

    # ---------------------------------
    # Animación optimizada
    # ---------------------------------
    def play(self):
        if not self.running:
            return

        frames = self.get_scaled_frames()

        if not frames:
            self.stop()
            return

        self.label.setPixmap(frames[self.current_frame])

        self.current_frame += 1

        if self.current_frame >= len(frames):
            if self.loop:
                self.current_frame = 0
            else:
                self.stop()
                if self.next_state and self.on_finished:
                    self.on_finished(self.next_state)
                return

        self.timer.start(max(1, int(1000 / self.fps)))