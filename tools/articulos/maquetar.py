"""Convierte los JSON extraídos en PDF limpios, listos para imprimir y repartir.

Formato "tipo lectura": una columna, serif, sin publicidad ni navegación, con
encabezado del curso y márgenes amplios para anotar a mano.

Uso:
    python tools/articulos/maquetar.py lecturas/semana3/raw --salida lecturas/semana3/pdf
    python tools/articulos/maquetar.py lecturas/semana3/raw/s3-01-nyt-mass-hysteria.json
"""

import argparse
import html as htmlmod
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CHROME = [
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
]

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
         "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

# Promos y pies de página que los medios incrustan en el cuerpo del artículo.
RUIDO = [
    r"^Follow the New York Times Opinion section",
    r"^The Times is committed to publishing a diversity of letters",
    r"^Here are some tips\.",
    r"^For subscribers only: to see how we design",
    r"^Sign up to .{0,60}newsletter",
    r"^Explore more of .{0,40}coverage",
    r"^Listen to this story\.",
    r"^Your browser does not support",
    r"^Editor.s note:? ?$",
]
RUIDO_RE = [re.compile(p, re.I) for p in RUIDO]


def sin_etiquetas(s):
    return re.sub(r"<[^>]+>", "", s or "").strip()


def es_ruido(bloque):
    if bloque.get("tipo") != "p":
        return False
    texto = sin_etiquetas(bloque.get("html", ""))
    return any(r.search(texto) for r in RUIDO_RE)


def fecha_larga(iso):
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", str(iso or ""))
    if not m:
        return ""
    anio, mes, dia = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return "%d de %s de %d" % (dia, MESES[mes - 1], anio)


def normaliza_pie(pie):
    """El Economist entrega el pie de foto como objeto {textHtml|text}; el NYT
    como texto plano. Devuelve HTML listo para insertar, o '' si viene vacío."""
    if isinstance(pie, dict):
        return (pie.get("textHtml") or htmlmod.escape(pie.get("text") or "")).strip()
    return htmlmod.escape(pie).strip() if pie else ""


def cuerpo_html(bloques, con_imagenes):
    partes = []
    for b in bloques:
        t = b.get("tipo")
        if t == "h2":
            partes.append("<h2>%s</h2>" % b["html"])
        elif t == "quote":
            partes.append("<blockquote>%s</blockquote>" % b["html"])
        elif t == "box":
            partes.append('<aside class="recuadro">%s</aside>' % b["html"])
        elif t in ("ul", "ol"):
            items = "".join("<li>%s</li>" % i for i in b.get("items", []))
            partes.append("<%s>%s</%s>" % (t, items, t))
        elif t == "img":
            if not con_imagenes:
                continue
            pie = normaliza_pie(b.get("pie"))
            partes.append(
                '<figure><img src="%s" alt="" onerror="this.closest(\'figure\').remove()">%s</figure>'
                % (htmlmod.escape(b["src"], quote=True),
                   ("<figcaption>%s</figcaption>" % pie) if pie else "")
            )
        else:
            partes.append("<p>%s</p>" % b["html"])
    return "\n".join(partes)


def construir_html(art, con_imagenes=True):
    bloques = [b for b in art.get("cuerpo", []) if not es_ruido(b)]
    e = htmlmod.escape

    cabecera = " · ".join(x for x in [
        "IA y Democracia 2026",
        ("Semana %s" % art["semana"]) if art.get("semana") else "",
        art.get("fuente", ""),
        art.get("seccion", ""),
    ] if x)
    firma = " · ".join(x for x in [
        art.get("autor", ""), art.get("lugar", ""), fecha_larga(art.get("fecha")),
    ] if x)
    lectura = ("%s min de lectura" % art["lectura"]) if art.get("lectura") else ""

    trozos = [
        "<!doctype html>", '<html lang="en">', "<head>", '<meta charset="utf-8">',
        "<title>%s</title>" % e(art.get("titulo", "")),
        "<style>%s</style>" % CSS, "</head>", "<body>",
        '<header class="curso"><span>%s</span>%s</header>' % (
            e(cabecera), ('<span class="lectura">%s</span>' % e(lectura)) if lectura else ""),
        "<article>",
    ]
    if art.get("antetitulo"):
        trozos.append('<p class="antetitulo">%s</p>' % e(art["antetitulo"]))
    trozos.append("<h1>%s</h1>" % e(art.get("titulo", "")))
    if art.get("bajada"):
        trozos.append('<p class="bajada">%s</p>' % e(art["bajada"]))
    if firma:
        trozos.append('<p class="firma">%s</p>' % e(firma))
    trozos += ["<hr>", cuerpo_html(bloques, con_imagenes), "</article>"]
    trozos += [
        "<footer>",
        '<p class="fuente">%s%s. <span class="url">%s</span></p>' % (
            e(art.get("fuente", "")),
            (", " + fecha_larga(art.get("fecha"))) if art.get("fecha") else "",
            e(art.get("url", ""))),
        '<p class="aviso">Material de lectura del curso Inteligencia Artificial y Democracia 2026. '
        'Los derechos del texto pertenecen a %s.</p>' % e(art.get("fuente", "")),
        "</footer>", "</body>", "</html>",
    ]
    return "\n".join(trozos)


CSS = """
@page { size: A4; margin: 22mm 20mm 20mm 20mm; }
html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body { margin: 0; font-family: Charter, Georgia, "Times New Roman", serif;
  font-size: 11.5pt; line-height: 1.55; color: #14171a; hyphens: auto; }
header.curso { display: flex; justify-content: space-between; gap: 1em;
  font-family: "Segoe UI", system-ui, Arial, sans-serif; font-size: 8pt;
  letter-spacing: .09em; text-transform: uppercase; color: #6b7280;
  border-bottom: .5pt solid #c7ccd1; padding-bottom: 5pt; margin-bottom: 20pt; }
header.curso .lectura { white-space: nowrap; }
article { max-width: 34em; }
.antetitulo { font-family: "Segoe UI", system-ui, Arial, sans-serif; font-size: 9pt;
  font-weight: 700; letter-spacing: .06em; text-transform: uppercase;
  color: #b3261e; margin: 0 0 4pt; }
h1 { font-size: 21pt; line-height: 1.18; font-weight: 700; margin: 0 0 8pt;
  hyphens: none; text-wrap: balance; }
.bajada { font-size: 12.5pt; line-height: 1.4; font-style: italic; color: #4b5563;
  margin: 0 0 10pt; hyphens: none; }
.firma { font-family: "Segoe UI", system-ui, Arial, sans-serif; font-size: 8.5pt;
  letter-spacing: .04em; text-transform: uppercase; color: #6b7280; margin: 0; }
hr { border: 0; border-top: .5pt solid #c7ccd1; margin: 14pt 0 16pt; }
p { margin: 0 0 10pt; text-align: justify; orphans: 3; widows: 3; }
h2 { font-size: 12pt; font-weight: 700; margin: 16pt 0 7pt; hyphens: none;
  break-after: avoid; page-break-after: avoid; }
blockquote { margin: 12pt 0 12pt 1.4em; padding-left: 1em;
  border-left: 2pt solid #d0d5da; font-style: italic; color: #374151; }
ul, ol { margin: 0 0 10pt; padding-left: 1.4em; }
li { margin-bottom: 4pt; text-align: justify; }
aside.recuadro { break-inside: avoid; page-break-inside: avoid; margin: 14pt 0;
  padding: 10pt 12pt; background: #f4f6f7; border-left: 2.5pt solid #b3261e; }
aside.recuadro p { font-size: 10.5pt; }
aside.recuadro p:last-child { margin-bottom: 0; }
figure { break-inside: avoid; page-break-inside: avoid; margin: 14pt 0; }
figure img { max-width: 100%; height: auto; }
figcaption { font-family: "Segoe UI", system-ui, Arial, sans-serif; font-size: 8.5pt;
  line-height: 1.4; color: #6b7280; margin-top: 4pt; text-align: left; }
a { color: inherit; text-decoration: none; border-bottom: .5pt solid #b9bfc5; }
footer { max-width: 34em; margin-top: 20pt; padding-top: 8pt;
  border-top: .5pt solid #c7ccd1; break-inside: avoid;
  font-family: "Segoe UI", system-ui, Arial, sans-serif; font-size: 8pt;
  line-height: 1.45; color: #6b7280; }
footer p { margin: 0 0 3pt; text-align: left; }
footer .url { word-break: break-all; }
footer .aviso { color: #9aa1a8; }
"""


def buscar_chrome():
    for c in CHROME:
        if Path(c).exists():
            return c
    hallado = shutil.which("chrome") or shutil.which("msedge")
    if hallado:
        return hallado
    raise SystemExit("No encontré Chrome ni Edge para renderizar el PDF.")


def a_pdf(ruta_html, ruta_pdf, navegador):
    """Chrome headless: el perfil real está en uso, así que va uno temporal."""
    with tempfile.TemporaryDirectory() as perfil:
        cmd = [
            navegador, "--headless", "--disable-gpu", "--no-first-run",
            "--user-data-dir=" + perfil,
            "--no-pdf-header-footer",
            "--print-to-pdf=" + str(ruta_pdf),
            "--virtual-time-budget=10000",
            ruta_html.as_uri(),
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if not Path(ruta_pdf).exists():
        raise RuntimeError("Chrome no generó el PDF:\n%s" % (r.stderr or r.stdout)[-800:])


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("entrada", help="carpeta con los JSON, o un JSON suelto")
    p.add_argument("--salida", help="carpeta de los PDF (por defecto: ../pdf)")
    p.add_argument("--sin-imagenes", action="store_true",
                   help="omite fotos y gráficos (ahorra tinta al imprimir)")
    p.add_argument("--solo-html", action="store_true",
                   help="deja el HTML intermedio y no genera PDF")
    args = p.parse_args()

    entrada = Path(args.entrada)
    archivos = sorted(entrada.glob("*.json")) if entrada.is_dir() else [entrada]
    if not archivos:
        raise SystemExit("No hay JSON en %s" % entrada)

    base = entrada if entrada.is_dir() else entrada.parent
    salida = Path(args.salida) if args.salida else base.parent / "pdf"
    salida.mkdir(parents=True, exist_ok=True)
    navegador = None if args.solo_html else buscar_chrome()

    for ruta in archivos:
        art = json.loads(ruta.read_text(encoding="utf-8"))
        doc = construir_html(art, con_imagenes=not args.sin_imagenes)
        ruta_html = (salida / (ruta.stem + ".html")).resolve()
        ruta_html.write_text(doc, encoding="utf-8")

        if args.solo_html:
            print("html  %s" % ruta_html.name)
            continue

        ruta_pdf = (salida / (ruta.stem + ".pdf")).resolve()
        a_pdf(ruta_html, ruta_pdf, navegador)
        ruta_html.unlink()
        kb = ruta_pdf.stat().st_size // 1024
        print("pdf   %-34s %4d kB   %s" % (ruta_pdf.name, kb, art.get("titulo", "")[:48]))

    print("\n-> %s" % salida.resolve())


if __name__ == "__main__":
    sys.exit(main())
