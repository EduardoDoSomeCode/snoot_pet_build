"""Genera los iconos que necesitan los empaquetados.

    python packaging/make_icons.py <salida-dir>

Sale:
  snoot-pet.png    para Linux (.desktop, .DirIcon) y Windows
  snoot-pet.ico    para Windows (el instalador lo quiere en .ico)
  snoot-pet.icns   para macOS

Pillow no sabe escribir .icns, asi que se escribe a mano: el formato es un
contenedor muy simple, "icns" + longitud total, y luego trozos de tipo, con la
longitud incluida en los 8 bytes de cabecera del trozo.
"""
import io
import os
import struct
import sys

from PIL import Image

ORIGEN = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fangneutral.ico"
)

# tipo de .icns -> lado en pixeles
Trozos_ICNS = (
    (b"icp4", 16),
    (b"icp5", 32),
    (b"ic07", 128),
    (b"ic08", 256),
    (b"ic09", 512),
)


def png_bytes(lado):
    imagen = Image.open(ORIGEN).convert("RGBA").resize((lado, lado), Image.LANCZOS)
    buf = io.BytesIO()
    imagen.save(buf, format="PNG")
    return buf.getvalue()


def escribir_icns(destino, imagenes):
    """imagenes: lista de (tipo, lado) en píxeles."""
    cuerpo = b""

    for tipo, lado in imagenes:
        datos = png_bytes(lado)
        # cada trozo lleva su longitud, y esos 8 bytes cuentan dentro
        cuerpo += tipo + struct.pack(">I", 8 + len(datos)) + datos

    with open(destino, "wb") as f:
        f.write(b"icns" + struct.pack(">I", 8 + len(cuerpo)) + cuerpo)


def main():
    salida = sys.argv[1] if len(sys.argv) > 1 else "."
    os.makedirs(salida, exist_ok=True)

    if not os.path.exists(ORIGEN):
        sys.exit(f"no encuentro el icono de origen: {ORIGEN}")

    base = Image.open(ORIGEN).convert("RGBA")
    print(f"origen: {ORIGEN}  {base.size}")

    png = os.path.join(salida, "snoot-pet.png")
    base.resize((256, 256), Image.LANCZOS).save(png)
    print(f"  {png} (256x256)")

    ico = os.path.join(salida, "snoot-pet.ico")
    base.save(ico, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(f"  {ico}")

    icns = os.path.join(salida, "snoot-pet.icns")
    escribir_icns(icns, Trozos_ICNS)
    print(f"  {icns} ({os.path.getsize(icns) // 1024} KB, "
          f"{len(Trozos_ICNS)} tamaños)")


if __name__ == "__main__":
    main()