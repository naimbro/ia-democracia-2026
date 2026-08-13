"""Lista, semana por semana, las lecturas con paywall del syllabus.

Recorre index.html, detecta los enlaces a The Economist y The New York Times, y
arma el manifiesto que consume el extractor. Marca cuáles ya tienen PDF en Drive
para no volver a bajarlas.

Uso:
    python tools/articulos/manifiesto.py                # resumen de todo el curso
    python tools/articulos/manifiesto.py --semana 5     # manifiesto de una semana
    python tools/articulos/manifiesto.py --semana 5 --js  # llamada lista para pegar
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from syllabus import lecturas, semanas


def slug(texto, largo=28):
    texto = re.sub(r"<[^>]+>", "", texto).lower()
    texto = re.sub(r"[^a-z0-9]+", "-", texto).strip("-")
    return texto[:largo].rstrip("-")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--syllabus", default="index.html")
    p.add_argument("--semana", type=int, help="genera el manifiesto de una semana")
    p.add_argument("--todas", action="store_true",
                   help="junta las semanas pendientes en un lote por medio")
    p.add_argument("--js", action="store_true",
                   help="imprime la llamada a __extraerLote lista para pegar en la consola")
    p.add_argument("--incluir-hechas", action="store_true",
                   help="incluye lecturas que ya tienen PDF en Drive")
    args = p.parse_args()

    html = Path(args.syllabus).read_text(encoding="utf-8")
    todas = semanas(html)

    if args.todas:
        entradas = []
        for s in todas:
            arts = [a for a in lecturas(s["html"]) if not a["tiene_pdf"]]
            for i, a in enumerate(arts, start=1):
                entradas.append({
                    "url": a["url"],
                    "archivo": "s%d-%02d-%s-%s.json" % (s["semana"], i, a["medio"], slug(a["titulo"])),
                    "semana": s["semana"],
                    "medio": a["medio"],
                })
        if not entradas:
            print("Nada pendiente.")
            return 0
        # Un lote por medio: cada dominio necesita su propia pestaña autenticada.
        for corto, nombre in [("nyt", "The New York Times"), ("eco", "The Economist")]:
            lote = [e for e in entradas if e["medio"] == corto]
            if not lote:
                continue
            print("// %s  (%d artículos)" % (nombre, len(lote)))
            print("await __extraerLote([")
            print(",\n".join(
                "  { url: '%s', archivo: '%s', semana: %d }" % (e["url"], e["archivo"], e["semana"])
                for e in lote))
            print("], { bundle: 'pendientes-%s.json' })\n" % corto)
        return 0

    if not args.semana:
        total = pendientes = 0
        for s in todas:
            arts = lecturas(s["html"])
            if not arts:
                continue
            falta = [a for a in arts if not a["tiene_pdf"]]
            total += len(arts)
            pendientes += len(falta)
            print("Semana %-2d  %d con paywall, %d sin PDF   %s"
                  % (s["semana"], len(arts), len(falta), s["titulo"][:46]))
        print("\n%d lecturas con paywall en total, %d sin PDF." % (total, pendientes))
        return 0

    s = next((x for x in todas if x["semana"] == args.semana), None)
    if not s:
        raise SystemExit("No existe la semana %d (el syllabus tiene %d)." % (args.semana, len(todas)))

    arts = lecturas(s["html"])
    if not args.incluir_hechas:
        arts = [a for a in arts if not a["tiene_pdf"]]
    if not arts:
        print("Semana %d: nada pendiente." % args.semana)
        return 0

    entradas = []
    for i, a in enumerate(arts, start=1):
        entradas.append({
            "url": a["url"],
            "archivo": "s%d-%02d-%s-%s.json" % (args.semana, i, a["medio"], slug(a["titulo"])),
            "medio": a["medio"],
        })

    if not args.js:
        print(json.dumps({"semana": args.semana, "titulo": s["titulo"], "articulos": entradas},
                         ensure_ascii=False, indent=2))
        return 0

    # Una llamada por medio: cada dominio necesita su propia pestaña autenticada.
    for corto, nombre in [("nyt", "The New York Times"), ("eco", "The Economist")]:
        lote = [e for e in entradas if e["medio"] == corto]
        if not lote:
            continue
        print("// %s  (%d)" % (nombre, len(lote)))
        print("await __extraerLote([")
        print(",\n".join("  { url: '%s', archivo: '%s' }" % (e["url"], e["archivo"]) for e in lote))
        print("], { semana: %d, bundle: 's%d-%s.json' })\n" % (args.semana, args.semana, corto))
    return 0


if __name__ == "__main__":
    sys.exit(main())
