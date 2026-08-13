"""Separa el bundle que baja el extractor en un JSON por artículo.

El extractor entrega todos los artículos de un medio en un solo archivo, porque
Chrome bloquea las descargas automáticas múltiples de un mismo sitio.

Uso:
    python tools/articulos/repartir.py ~/Downloads/s3-nyt.json lecturas/semana3/raw
"""

import argparse
import json
import re
import sys
from pathlib import Path


def seguro(nombre):
    nombre = Path(str(nombre)).name
    nombre = re.sub(r"[^A-Za-z0-9._-]+", "-", nombre).strip("-")
    if not nombre.endswith(".json"):
        nombre += ".json"
    return nombre or "articulo.json"


def palabras(art):
    total = 0
    for b in art.get("cuerpo", []):
        texto = b.get("html") or " ".join(b.get("items", []))
        total += len(re.sub(r"<[^>]+>", " ", texto).split())
    return total


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("bundle", help="JSON descargado por el extractor")
    p.add_argument("destino", help="carpeta donde dejar un JSON por artículo")
    p.add_argument("--borrar", action="store_true", help="elimina el bundle al terminar")
    args = p.parse_args()

    bundle = Path(args.bundle).expanduser()
    destino = Path(args.destino)
    destino.mkdir(parents=True, exist_ok=True)

    datos = json.loads(bundle.read_text(encoding="utf-8"))
    articulos = datos if isinstance(datos, list) else [datos]

    fallos = 0
    for art in articulos:
        if "error" in art:
            print("  !! %s -> %s" % (art.get("url", "?"), art["error"]))
            fallos += 1
            continue
        nombre = seguro(art.get("archivo") or art.get("titulo", "articulo"))
        (destino / nombre).write_text(
            json.dumps(art, ensure_ascii=False, indent=2), encoding="utf-8")
        print("  ok %-34s %5d palabras  %s" % (nombre, palabras(art), art.get("titulo", "")[:44]))

    if args.borrar and not fallos:
        bundle.unlink()
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
