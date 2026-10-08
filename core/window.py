import ctypes

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication

# Cada cuánto re-afirmamos que la pet está por encima. Otras apps (sobre todo
# los juegos en fullscreen) le roban la prioridad a la ventana.
WATCHDOG_INTERVAL = 1500  # ms


class X11Topmost:
    # ---------------------------------
    # Re-afirma _NET_WM_STATE_ABOVE por X11.
    #
    # Qt aplica WindowStaysOnTopHint al mapear la ventana, pero si cambiamos
    # los flags con la ventana ya visible (por ejemplo al activar el modo
    # captura) el WM se queda sin el estado y la pet vuelve a ser una ventana
    # normal. En Wayland esto no hace falta: va por xdg-foreign.
    # ---------------------------------
    XA_ATOM = 4
    ClientMessage = 33
    SubstructureNotifyMask = 1 << 19
    SubstructureRedirectMask = 1 << 20

    def __init__(self):
        self.lib = None
        self.display = None

        try:
            lib = ctypes.CDLL("libX11.so.6")

            lib.XOpenDisplay.restype = ctypes.c_void_p
            lib.XOpenDisplay.argtypes = [ctypes.c_char_p]

            lib.XInternAtom.restype = ctypes.c_ulong
            lib.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]

            lib.XSendEvent.restype = ctypes.c_int
            lib.XSendEvent.argtypes = [
                ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_long,
                ctypes.c_void_p,
            ]

            lib.XFlush.argtypes = [ctypes.c_void_p]

            lib.XDefaultRootWindow.restype = ctypes.c_ulong
            lib.XDefaultRootWindow.argtypes = [ctypes.c_void_p]

            display = lib.XOpenDisplay(None)
            if not display:
                raise OSError("Could not open X display")

            self.lib = lib
            self.display = display
            self._atoms = {}

        except Exception:
            self.lib = None
            self.display = None

    @property
    def available(self):
        return self.lib is not None and self.display is not None

    def _atom(self, name):
        if name not in self._atoms:
            self._atoms[name] = self.lib.XInternAtom(
                self.display, name.encode("utf-8"), False
            )
        return self._atoms[name]

    def send_above(self, window_id):
        if not self.available or not window_id:
            return False

        class XClientMessageEvent(ctypes.Structure):
            _fields_ = [
                ("type", ctypes.c_int),
                ("serial", ctypes.c_ulong),
                ("send_event", ctypes.c_int),
                ("display", ctypes.c_void_p),
                ("window", ctypes.c_ulong),
                ("message_type", ctypes.c_ulong),
                ("format", ctypes.c_int),
                ("data", ctypes.c_long * 5),
            ]

        try:
            event = XClientMessageEvent()
            event.type = self.ClientMessage
            event.serial = 0
            event.send_event = 1
            event.display = self.display
            event.window = window_id
            event.message_type = self._atom("_NET_WM_STATE")
            event.format = 32
            # 1 = source indication "pag", 2 = "app"
            event.data[0] = self._atom("_NET_WM_STATE_ABOVE")
            event.data[1] = 2
            event.data[2] = 0

            mask = self.SubstructureNotifyMask | self.SubstructureRedirectMask

            self.lib.XSendEvent(
                self.display,
                self.lib.XDefaultRootWindow(self.display),
                0,
                mask,
                ctypes.byref(event),
            )
            self.lib.XFlush(self.display)
            return True

        except Exception:
            return False


class WindowController:
    # ---------------------------------
    # Transparencia + siempre encima + modo capturable (OBS)
    #
    # Con Qt esto es native y sin trucos: WA_TranslucentBackground da alfa
    # real por pixel en Windows, Linux (X11 y Wayland) y macOS. En Tk/X11 solo
    # existía -alpha, que aplicaba transparencia a toda la ventana.
    # ---------------------------------
    def __init__(self, window, always_on_top=True, capture_mode=False):
        self.window = window
        self.always_on_top = bool(always_on_top)
        self.capture_mode = bool(capture_mode)

        # Solo hace falta en X11: en Wayland el compositor ya mantiene el hint.
        self._x11 = X11Topmost() if QGuiApplication.platformName() == "xcb" else None

        self._watchdog = QTimer(window)
        self._watchdog.setInterval(WATCHDOG_INTERVAL)
        self._watchdog.timeout.connect(self._watchdog_tick)

        self.apply()
        self._watchdog.start()

    # ---------------------------------
    def apply(self):
        window = self.window

        # Alfa real por pixel: sin esto la ventana es un rectángulo opaco.
        window.setAttribute(Qt.WA_TranslucentBackground, True)

        # Sin bordes en ambos modos; solo cambia el tipo de ventana.
        #   Qt.Tool -> ventana utilitaria, no aparece en el taskbar
        #   Qt.Window -> ventana normal, la que OBS puede listar
        window.setWindowFlag(Qt.FramelessWindowHint, True)
        window.setWindowFlag(Qt.Tool, not self.capture_mode)
        window.setWindowFlag(Qt.WindowStaysOnTopHint, self.always_on_top)

        # Cambiar flags oculta la ventana: hay que volver a mostrarla.
        window.show()

        self.reassert_topmost()

    # ---------------------------------
    def reassert_topmost(self):
        if not self.always_on_top:
            return

        self.window.raise_()

        if self._x11 is not None:
            handle = self.window.windowHandle()
            window_id = int(handle.winId()) if handle else 0
            self._x11.send_above(window_id)

    # ---------------------------------
    def set_always_on_top(self, enabled):
        self.always_on_top = bool(enabled)
        self.apply()

    def set_capture_mode(self, enabled):
        self.capture_mode = bool(enabled)
        self.apply()

    # ---------------------------------
    def _watchdog_tick(self):
        self.reassert_topmost()

    def stop(self):
        self._watchdog.stop()