from PIL import Image
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPixmap


class AnimationPlayer:
    # ---------------------------------
    # Reproduccion de GIF sobre un QLabel
    #
    # Pillow solo se usa para decodificar el GIF y recortarle el margen
    # transparente, una sola vez. Todo el reescalado va por Qt:_smooth_
    # transformation_ de Qt es ~25x mas rapido que LANCZOS de Pillow
    # (212ms -> 9ms para los 16 frames de fang al 1.8), y eso es lo que hace
    # que cambiar de tamano con la rueda no se congele.
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

        self.base_pixmaps = []      # frames ya recortados, a tamano natural
        self.scaled_cache = {}      # cache por escala

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

        # Los GIF vienen con margenes transparentes alrededor del dibujo (en
        # fang son 127px arriba). Si la ventana conserva ese margen, al pegarla
        # al borde superior el dibujo queda ese hueco por debajo y parece que la
        # pet no llega. Recortamos para que la ventana abrace el dibujo.
        if self.trim_margins:
            frames = self._trim(frames)

        self.base_pixmaps = [self._to_pixmap(frame) for frame in frames]

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

        return [frame.crop(box) for frame in frames]

    # ---------------------------------
    # Factor total de escalado: base_size (config) x escala del usuario
    # ---------------------------------
    def _factor(self):
        if not self.base_pixmaps:
            return 1.0

        natural = self.base_pixmaps[0].height()
        base_factor = (self.base_size / natural) if self.base_size else 1.0

        return self.scaling_manager.scale * base_factor

    # ---------------------------------
    # Generar frames escalados SOLO si necesario
    # ---------------------------------
    def get_scaled_frames(self):
        scale = round(self.scaling_manager.scale, 2)

        if scale in self.scaled_cache:
            # Marcarlo como usado para que el LRU no lo expulse
            frames = self.scaled_cache.pop(scale)
            self.scaled_cache[scale] = frames
            return frames

        factor = self._factor()

        scaled = []
        for pixmap in self.base_pixmaps:
            if abs(factor - 1.0) < 0.001:
                scaled.append(pixmap)
                continue

            width = max(1, int(round(pixmap.width() * factor)))
            height = max(1, int(round(pixmap.height() * factor)))

            scaled.append(
                pixmap.scaled(
                    width,
                    height,
                    Qt.IgnoreAspectRatio,
                    Qt.SmoothTransformation,
                )
            )

        self.scaled_cache[scale] = scaled
        self._evict_cache(scale)

        return scaled

    # ---------------------------------
    # ---------------------------------
    # El cache no puede crecer sin limite: cada escala guarda los frames ya
    # reescalados, y con la rueda recorriendo todo el rango se acumulaba mas de
    # 400 MB de pixmaps (16 frames de 1239x1080 a 4 bytes por pixel). Se queda
    # con las ultimas escalas usadas, que es justo lo que hace falta para ir
    # arriba y abajo con la rueda sin volver a reescalar.
    # ---------------------------------
    CACHE_MAX_ENTRIES = 3
    CACHE_MAX_MB = 80

    @staticmethod
    def _frames_mb(frames):
        return sum(p.width() * p.height() * 4 for p in frames) / (1024 * 1024)

    def _evict_cache(self, keep_scale):
        cache = self.scaled_cache

        # Las claves se ordenan por antiguedad de uso (la que se acaba de
        # insertar es la ultima)
        while len(cache) > 1:
            total = sum(self._frames_mb(f) for f in cache.values())

            if len(cache) <= self.CACHE_MAX_ENTRIES and total <= self.CACHE_MAX_MB:
                break

            # Evitar siempre la escala en uso
            oldest = next((k for k in cache if k != keep_scale), None)
            if oldest is None:
                break

            cache.pop(oldest, None)

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