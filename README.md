# Snoot pet

Desktop pet en **PySide6 (Qt)**. Click = cambia de estado, doble click = boop,
scroll = tamaño, botón derecho = menú.

> La versión anterior estaba en Tkinter y se respaldó en
> `../snoot-pet.tkinter-backup/`. El cambio a Qt no es cosmético: Tk en X11 no
> tiene colorkey, así que la pet era un rectángulo con `-alpha 0.5` y en OBS
> salía como una caja gris. Ver "Por qué Qt" más abajo.

## Opciones de ventana

Click derecho sobre la pet → menú contextual:

| Opción | Qué hace |
| --- | --- |
| **Always on Top** | La pet se queda por encima de los demás programas. Se guarda entre ejecuciones y se re-afirma cada 1,5 s, porque los juegos en pantalla completa y otras apps le quitan la prioridad a la ventana. |
| **Capture Mode (OBS)** | Cambia la ventana de `Qt.Tool` a ventana normal, para que OBS pueda listarla y capturarla. |

Ambos ajustes se guardan en `settings.json`:

- Linux: `~/.local/share/Snoot_pet/settings.json`
- Windows: `%APPDATA%\Snoot_pet\settings.json`
- macOS: `~/Library/Application Support/Snoot_pet/settings.json`
- Modo portable: junto al ejecutable, en `user_data/`

También se pueden forzar al arrancar:

```bash
python desktop_pet.py --capture                 # arranca en modo captura
python desktop_pet.py --no-always-on-top        # arranca sin always on top
python desktop_pet.py --character liz           # otro personaje
```

### Siempre encima, sí o sí

El flag `Qt.WindowStaysOnTopHint` por sí solo no aguanta: cualquier app que se abra
maximizada, o un juego en fullscreen, se queda por delante. `core/window.py` tiene un
watchdog que lo re-afirma cada 1,5 s con `raise_()`.

En X11 hay un detalle extra: Qt aplica el hint al mapear la ventana, pero si cambias
los flags con la ventana ya visible (por ejemplo al activar el modo captura) el WM se
queda sin `_NET_WM_STATE_ABOVE` y la pet vuelve a ser una ventana normal. Por eso, solo
bajo X11, el watchdog manda además el `_ClientMessage` de `_NET_WM_STATE_ABOVE` a mano
(vía ctypes). En Wayland no hace falta: el compositor mantiene el hint.

Ojo: en fullscreen **exclusivo** (no el fullscreen de ventana) ningún compositor
puede dibujar encima, así que la pet no se verá hasta salir de ese modo.

### Por qué la pet "no llegaba" al borde superior

No era el arrastre: los GIF vienen con **mucho margen transparente** alrededor del
dibujo. En `fang_neutral.gif` el frame es de 600×600 pero el dibujo solo ocupa
492×429, con **127px de aire arriba**:

```
fang  frame=600x600  arte=492x429  MARGEN: arriba=127px abajo=44px izq=60px der=48px
```

Al pegarla al borde superior, la ventana sí llegaba a y=0, pero la cabeza de la pet
quedaba 127px más abajo y parecía un hueco. Ahora `core/animation.py` recorta el
margen (con la unión de todos los frames, para que la pet no vibre entre fotogramas),
de modo que la ventana abraza justo el dibujo. El tamaño en pantalla no cambia, solo
desaparece el aire invisible.

Se puede desactivar por personaje con `"trim_margins": false` en su `config.json`.

### La ventana no se encoge al reducir la escala

El layout usa `SetFixedSize` para que la ventana abrace siempre el dibujo. Sin eso,
al bajar el tamaño con la rueda el QLabel encogía pero **la ventana se quedaba con
el tamaño anterior** y el pixmap quedaba centrado dentro, dejando un hueco alrededor
de la pet (muy visible arriba, porque el label centra verticalmente). Por eso las
versiones grandes llegaban al borde y las pequeñas no: crecer sí funcionaba, encoger
no. Con `SetFixedSize` ventana y pixmap coinciden en los 20 pasos de la escala.

Los tamaños de ventana tras el recorte:

```
anon    330x400     fang   492x429     liz    311x858
olivia  495x456     rosa   518x498     stella 409x498
```

### Por qué Qt

En Tk sobre X11, `wm attributes` solo admite `-alpha`, `-topmost`, `-zoomed`,
`-fullscreen` y `-type`. No hay `-transparentcolor` ni colorkey, y `-alpha` se aplica
a **toda** la ventana: el fondo negro de la pet se volvía una caja translúcida y en
OBS era un rectángulo gris.

Con Qt, `WA_TranslucentBackground` + `FramelessWindowHint` da alfa real por píxel en
Windows, Linux (X11 y Wayland) y macOS. Verificado: 56,6 % de los píxeles de la
ventana con alfa 0 y las esquinas a `(0, 0, 0, 0)` en lugar de negro.

De paso, la app pasa a ser **cliente nativo de Wayland** (antes iba por XWayland),
que es lo que hacía que OBS la capturara como una caja negra.

## Ver la pet en OBS

Activa **Capture Mode** y en OBS añade una fuente de captura:

- **Windows**: *Window Capture*. Si sale negro, marca *Use Windows Graphics Capture*;
  con `PrintWindow` las ventanas *layered* a veces no se capturan bien.
- **macOS**: *Window Capture* funciona con ventanas sin bordes.
- **Linux/X11** (launch both under X11):

  ```bash
  QT_QPA_PLATFORM=xcb obs-studio     # OBS con backend X11
  QT_QPA_PLATFORM=xcb ./snoot-pet   # la pet tambien como cliente X11
  ```

  En modo captura la ventana se declara `_NET_WM_WINDOW_TYPE_NORMAL` (OBS ignora las
  de tipo `UTILITY`, que es lo que Qt usa normalmente para una pet).

- **Linux/Wayland**: OBS no puede capturar ventanas concretas, solo la pantalla.
  Usa *Display Capture* (o PipeWire) y recorta en OBS. La pet ya sale con transparencia
  correcta, pero el fondo será el que tengas detrás; si necesitas recorte limpio,
  Chroma Key sobre una escena de color conocido.

Alternativa que funciona en cualquier caso: *Display Capture* + *Crop/Filter* alrededor
de la zona donde tienes la pet.

## Estructura

```
desktop_pet.py            ventana principal (QWidget), menú, eventos, import de personajes
core/engine.py            arranque de QApplication
core/window.py            transparencia, always on top, modo captura, watchdog
core/animation.py         reproducción de GIF (Pillow -> QPixmap) con cache por escala
core/behavior.py          cambio de estado autónomo
core/character_loader.py  config.json de cada personaje
core/scaling.py           escala con límites
core/settings.py          persistencia de los toggles
core/paths.py             rutas de datos (portable / APPDATA / XDG)
packaging/                AppRun, .desktop y script de build del AppImage
```

## Empaquetar como AppImage

```bash
./packaging/build_appimage.sh
```

Genera `Snoot_pet-x86_64.AppImage` (~90 MB) en la raíz del proyecto. El script crea
un venv en `/tmp/snoot-appimage`, lanza PyInstaller con `desktop_pet_appimage.spec`
(one-dir), monta el `AppDir` y lo empaqueta con `appimagetool`.

Notas:

- Se distribuye un `AppRun` propio porque algunas versiones de `appimagetool` no lo
  generan y el AppImage queda sin él (no arranca).
- El AppImage lleva Qt completo: pesa más que la versión Tk (que eran 65 MB), pero
  funciona igual en sistemas sin Qt instalado.
- `desktop_pet.spec` sigue siendo el build one-file (útil para Windows).

## Desarrollo

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
python desktop_pet.py
```

---

The MIT License (MIT)