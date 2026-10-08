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
python desktop_pet.py --platform wayland        # fuerza Wayland nativo
```

### Siempre encima: por qué en Linux usa XWayland

En Linux la pet usa por defecto el backend **XWayland (xcb)**, no el nativo de Wayland.
No es una preferencia estética: **el protocolo xdg-shell no tiene ningún request de
"keep above"**, así que con el backend nativo `Qt.WindowStaysOnTopHint` no hace nada y
la pet se va detrás en cuanto se abre otra ventana (pestaña, diálogo, maximized…).

KWin sí honra `_NET_WM_STATE_ABOVE`, que es lo que usa el backend X11. Con el, la pet se
mantiene encima de verdad:

```
_NET_WM_STATE(ATOM) = _NET_WM_STATE_ABOVE, _NET_WM_STATE_STAYS_ON_TOP
```

Y no se pierde nada por el cambio:

- **Transparencia**: sigue siendo alfa real por pixel (23,9 % de píxeles transparentes,
  esquinas a `(0,0,0,0)`), también sobre X11.
- **Arrastre**: en X11 `move()` sí funciona, así que el arrastre manual es válido.
- **OBS**: *Window Capture (X11)* es justo la vía que se recomienda más abajo.

`core/window.py` tiene además un watchdog que re-afirma el estado cada 1,5 s, porque al
cambiar los flags con la ventana ya visible (por ejemplo al activar el modo captura) el
WM se queda sin el estado.

Si prefieres nativo, menú → *Native Wayland (restart)*. Asumes que la pet puede quedar
detrás de las ventanas nuevas.

Ojo: en fullscreen **exclusivo** (no el fullscreen de ventana) ningún compositor puede
dibujar encima, así que la pet no se verá hasta salir de ese modo.

### Solo una pet a la vez

La app reclama un socket local al arrancar: si ya hay otra instancia, esta sale con un
aviso. Sin eso se acumulan varias pets, todas "always on top" compitiendo por el
stacking de KWin, y la que estabas mirando acaba tapada por otra.

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

### Cambiar de tamaño va rápido porque reescala Qt, no Pillow

Pillow solo decodifica el GIF y le recorta el margen, una sola vez. Todo el
reescalado pasa por `QPixmap.scaled()`, que es unas **25 veces más rápido** que
`Image.LANCZOS`:

```
escala   tamaño     Pillow LANCZOS   Qt smooth    ganancia
  0.50   246x214           63.9ms        2.5ms       25.9x
  1.30   639x557          132.1ms        4.6ms       28.7x
  1.80   885x772          212.2ms        9.2ms       23.2x
```

Como el trabajo ocurre en el hilo de la interfaz, esa diferencia era justo lo que
hacía que la rueda pareciera congelarse. Medido en la app: el peor paso de escala pasó
de 185ms a 59ms en fang y de 140ms a 25ms en liz.

### Cache de frames, y por qué está acotado

Hay dos niveles: los frames ya recortados (`base_pixmaps`, se decodifican una vez) y
los pixmaps de cada escala (`scaled_cache`). Volver a una escala ya visitada cuesta
0.01ms en vez de 15–35ms, así que ir arriba y abajo con la rueda va fluido.

El cache **no puede crecer sin límite**: cada escala guarda los 16 frames ya
reescalados, y recorrer todo el rango con la rueda acumulaba más de 400 MB de pixmaps
(RSS de 537 MB). Ahora se queda con las últimas escalas usadas, hasta 3 o 80 MB:

```
antes:  9 escalas en cache -> 460 MB de pixmaps, RSS 537 MB
ahora:  1-3 escalas       ->  57 MB de pixmaps, RSS 237 MB
```

Volver a una escala antigua que se ha evicted cuesta ~30ms de reescalado, imperceptible.

### Sin tope de tamaño

Antes había un `limit_scale_to_screen()` que impedía que la pet creciera más que la
altura de la pantalla. Se basaba en una teoría equivocada (que el compositor limitaba
la ventana), se ha eliminado, y con él el efecto colateral de que liz se quedaba
atascada en 1.21 aunque su `config.json` permite 2.0. Ahora el tope es solo el
`scale_limits` de cada personaje, así que una pet muy grande puede sobresalir de la
pantura; bájale el tamaño con la rueda si te molesta.

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
- **Linux**: la pet ya corre como cliente XWayland por defecto (ver "Siempre encima"),
  así que basta con arrancar OBS también con backend X11 para que vea la ventana:

  ```bash
  QT_QPA_PLATFORM=xcb obs-studio
  ```

  En modo captura la ventana se declara `_NET_WM_WINDOW_TYPE_NORMAL` (OBS ignora las
  de tipo `UTILITY`, que es lo que Qt usa normalmente para una pet).

- **Linux con la pet en Wayland nativo** (`--platform wayland`): OBS no puede capturar
  ventanas concretas, solo la pantalla. Usa *Display Capture* (o PipeWire) y recorta en
  OBS. La pet sale con transparencia correcta, pero el fondo será el que tengas detrás;
  si necesitas recorte limpio, Chroma Key sobre una escena de color conocido.

Alternativa que funciona en cualquier caso: *Display Capture* + *Crop/Filter* alrededor
de la zona donde tienes la pet.

### Click: uno solo, inmediato

**Un único gesto.** El click cambia de animación al instante, igual que en la versión de
Tk. No hay doble click ni temporizadores: antes el click se retrasaba 250 ms para poder
distinguírselo de un doble click, y cualquier evento que se perdiera dejaba el click
sin hacer nada — un fallo indistinguible de "la pet no responde".

El click avanza por los estados que se reproducen en bucle (`neutral`, `guitar`…). Los
de un solo uso (`boop`, `blushy_*`…) quedan fuera a propósito: en fang son 7 de 16 y
estaban al principio de la lista, así que los primeros clicks caían en un boop de 0,2 s
que luego volvía solo a `neutral` y desde fuera parecía que no pasaba nada. Se pueden
volver a incluir con `"cycle_one_shots": true` en el `config.json` del personaje.

La decisión de gestos vive en `core/interaction.py`, sin Qt ni ventanas: recibe
posiciones y devuelve `CLICK`, `DRAG` o `NONE`. Se prueba sin montar la GUI:

```bash
python tests/test_interaction.py     # 16 pruebas
```

El umbral es `max(12px, QApplication.startDragDistance())` y la distancia es real, no
manhattan (en diagonal esta duplica el valor). Con 4 px, el temblor normal de la mano
al hacer click contaba como arrastre y el click se perdía:

```
temblor    0px   2px   4px   6px      40px
resultado  click click click click   arrastre
```

### Depurar los gestos

Con `SNOOT_LOG=1` se registra cada gesto del ratón con su distancia y la decisión
tomada, en `~/.local/share/Snoot_pet/pet.log`:

```bash
SNOOT_LOG=1 ./Snoot_pet-x86_64.AppImage
# ... haz un click ...
cat ~/.local/share/Snoot_pet/pet.log
```

```
00:19:45 press  pos=(816, 367) ventana=(616, 217) umbral=12
00:19:45 move   pos=(820, 367) dist=(816, 367) -> none
00:19:45 move   pos=(824, 367) dist=(816, 367) -> none
00:19:45 release ventana=(616, 217) -> click
```

Si haces click, no ocurre nada y **no** aparece una línea `release ... -> click`, el
problema ya no está en la app: los eventos no están llegando a la ventana.

---

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