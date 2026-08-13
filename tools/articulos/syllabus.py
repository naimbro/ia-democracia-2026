"""Lectura del syllabus (index.html): semanas y sus lecturas con paywall.

Lo comparten manifiesto.py y enlazar.py.

El syllabus anida listas varios niveles (semana > bloque temático > lectura), así
que una expresión regular tipo `<li>(.*?)</li>` corta en el primer cierre y
pierde el contenido del <li> externo. Acá los <li> se emparejan con una pila,
y cada enlace se atribuye a su <li> más interno, que es el de la lectura.
"""

import re

MEDIOS = [
    (re.compile(r"nytimes\.com"), "nyt", "The New York Times"),
    (re.compile(r"economist\.com"), "eco", "The Economist"),
    (re.compile(r"theatlantic\.com"), "atl", "The Atlantic"),
]

RE_LI = re.compile(r"<li\b[^>]*>|</li\s*>", re.I)
RE_ENLACE = re.compile(
    r'<a\s[^>]*href="(https://www\.(?:nytimes|economist|theatlantic)\.com/[^"]+)"[^>]*>(.*?)</a>',
    re.S | re.I)
RE_ETIQUETAS = re.compile(r"<[^>]+>")


def medio(url):
    for patron, corto, nombre in MEDIOS:
        if patron.search(url):
            return corto, nombre
    return None, None


def texto_plano(html):
    return re.sub(r"\s+", " ", RE_ETIQUETAS.sub("", html)).strip()


def items(html):
    """(inicio, fin) de cada <li>, emparejados con una pila."""
    pila, encontrados = [], []
    for m in RE_LI.finditer(html):
        if m.group(0).startswith("</"):
            if pila:
                encontrados.append((pila.pop(), m.end()))
        else:
            pila.append(m.start())
    return encontrados


def item_de(pares, pos):
    """El <li> más interno que contiene pos, o None."""
    dentro = [(a, b) for a, b in pares if a < pos < b]
    return max(dentro, key=lambda t: t[0]) if dentro else None


def semanas(html):
    """Cada .class-block es una semana, en el orden del contador CSS."""
    trozos = html.split('<div class="class-block">')[1:]
    salida = []
    for i, trozo in enumerate(trozos, start=1):
        titulo = re.search(r"<h2>(.*?)</h2>", trozo, re.S)
        salida.append({
            "semana": i,
            "titulo": texto_plano(titulo.group(1)) if titulo else "",
            "html": trozo,
        })
    return salida


def lecturas(trozo_html):
    """Lecturas con paywall de una semana, sin duplicados, en orden de aparición."""
    pares = items(trozo_html)
    vistas, salida = set(), []
    for m in RE_ENLACE.finditer(trozo_html):
        url = m.group(1).split("?")[0]
        if url in vistas:
            continue
        vistas.add(url)
        corto, nombre = medio(url)
        li = item_de(pares, m.start())
        ini, fin = li if li else (m.start(), m.end())
        item = trozo_html[ini:fin]
        salida.append({
            "url": url,
            "titulo": texto_plano(m.group(2)),
            "medio": corto,
            "fuente": nombre,
            "item": item,
            "pos": m.start(),
            # Límites del <li> de la lectura: sin ellos, insertar "antes del
            # próximo </li>" cae dentro de una lista anidada de preguntas.
            "ini": ini,
            "fin": fin,
            "tiene_pdf": "drive.google.com/file/d/" in item,
            "es_podcast": bool(re.search(r"\(podcast\)", item, re.I)),
        })
    return salida
