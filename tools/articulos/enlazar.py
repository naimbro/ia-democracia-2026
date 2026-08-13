"""Agrega a index.html el enlace al PDF de Drive de cada lectura con paywall.

Cruza tres cosas: los JSON extraídos (que traen la URL original y el nombre de
archivo), un mapa de nombre de PDF a id de Drive, y el syllabus. Inserta el
enlace justo después del <a> del medio, sin tocar el enlace original.

Es idempotente: una lectura que ya tiene su PDF se salta.

El mapa se arma con los ids que devuelve el conector de Drive:

    { "s5-02-nyt-musk-zucman.pdf": "1hh1nvZ...", ... }

Uso:
    python tools/articulos/enlazar.py mapa.json
    python tools/articulos/enlazar.py mapa.json --simular
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from syllabus import lecturas

PLANTILLA = ' · <a href="https://drive.google.com/file/d/%s/view?usp=sharing" target="_blank">%s</a>'


def extraidos(raiz):
    """URL original -> nombre del PDF, para todo lo que se haya extraído.

    Recorre lecturas/*/raw, no solo semanaN: la sección de recursos generales
    del syllabus también tiene lecturas con paywall."""
    mapa = {}
    for ruta in Path(raiz).glob("*/raw/*.json"):
        art = json.loads(ruta.read_text(encoding="utf-8"))
        mapa[art["url"].split("?")[0]] = ruta.stem + ".pdf"
    return mapa


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("mapa", help="JSON con {nombre_pdf: id_de_drive}")
    p.add_argument("--syllabus", default="index.html")
    p.add_argument("--lecturas", default="lecturas")
    p.add_argument("--simular", action="store_true", help="no escribe, solo informa")
    args = p.parse_args()

    ids = json.loads(Path(args.mapa).read_text(encoding="utf-8"))
    pdfs = extraidos(args.lecturas)
    syllabus = Path(args.syllabus)
    html = syllabus.read_text(encoding="utf-8")

    puestos, ya, sin_id, sin_articulo = [], [], [], []
    parches = []  # (posicion_de_insercion, texto)

    for a in lecturas(html):
        pdf = pdfs.get(a["url"])
        if not pdf:
            sin_articulo.append(a["url"])
            continue
        if a["tiene_pdf"]:
            ya.append(pdf)
            continue
        if pdf not in ids:
            sin_id.append(pdf)
            continue
        # Los podcasts se etiquetan como transcripción: no son lectura obligatoria.
        etiqueta = "transcripción (PDF)" if a["es_podcast"] else "PDF"
        # Justo antes de cerrar el <li> de la lectura. Usa el límite real del
        # elemento: buscar el próximo </li> caería dentro de una lista anidada.
        parches.append((html.rindex("</li>", a["ini"], a["fin"]), PLANTILLA % (ids[pdf], etiqueta)))
        puestos.append(pdf)

    # De atrás hacia adelante, para que las posiciones no se corran.
    for pos, texto in sorted(parches, reverse=True):
        html = html[:pos] + texto + html[pos:]

    for nom in puestos:
        print("  +  %s" % nom)
    for nom in ya:
        print("  =  %s (ya tenía)" % nom)
    for nom in sin_id:
        print("  ?  %s: falta id de Drive" % nom)
    for url in sin_articulo:
        print("  !  %s: sin JSON extraído" % url)

    print("\n%d agregados, %d ya estaban, %d sin id, %d sin extraer."
          % (len(puestos), len(ya), len(sin_id), len(sin_articulo)))

    if args.simular:
        print("(simulación: no se escribió nada)")
    elif puestos:
        syllabus.write_text(html, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
