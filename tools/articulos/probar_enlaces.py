"""Prueba cada enlace de Drive del syllabus como lo vería un alumno sin sesión.

Pide cada archivo sin cookies ni credenciales. Un 401, o una redirección a la
pantalla de acceso, significa que la carpeta sigue restringida: en Drive el
permiso se hereda de la carpeta, así que basta con abrir la carpeta, pero hay
que cerrar el diálogo con "Listo" para que el cambio se guarde.

Revisar los permisos desde el conector de Drive no basta: esto comprueba lo que
realmente ve alguien que abre el enlace del syllabus.

Uso:
    python tools/articulos/probar_enlaces.py
"""
import io
import re
import sys
import urllib.error
import urllib.request

html = io.open("index.html", encoding="utf-8").read()

# id -> texto del enlace, en orden de aparición
enlaces = []
for m in re.finditer(r'<a href="https://drive\.google\.com/file/d/([\w-]+)[^"]*"[^>]*>(.*?)</a>', html, re.S):
    enlaces.append((m.group(1), re.sub(r"<[^>]+>", "", m.group(2)).strip()))

vistos, unicos = set(), []
for i, t in enlaces:
    if i not in vistos:
        vistos.add(i)
        unicos.append((i, t))

print("%d enlaces de Drive en el syllabus\n" % len(unicos))

abiertos, cerrados, errores = [], [], []
for fid, etiqueta in unicos:
    url = "https://drive.google.com/file/d/%s/view" % fid
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            cuerpo = r.read(120000).decode("utf-8", "replace")
            final = r.geturl()
        if "accounts.google.com" in final or "ServiceLogin" in final:
            cerrados.append((fid, etiqueta, "redirige a inicio de sesión"))
        elif re.search(r"Solicitar acceso|Request access|Necesitas acceso|You need access", cuerpo):
            cerrados.append((fid, etiqueta, "pide solicitar acceso"))
        else:
            titulo = re.search(r"<title>(.*?)</title>", cuerpo, re.S)
            abiertos.append((fid, titulo.group(1).strip() if titulo else "?"))
    except urllib.error.HTTPError as e:
        (cerrados if e.code in (401, 403, 404) else errores).append((fid, etiqueta, "HTTP %d" % e.code))
    except Exception as e:
        errores.append((fid, etiqueta, type(e).__name__))

for fid, titulo in abiertos:
    print("  OK      %s" % titulo[:70])
for fid, etiqueta, motivo in cerrados:
    print("  CERRADO %-46s %s  [%s]" % (etiqueta[:46], motivo, fid))
for fid, etiqueta, motivo in errores:
    print("  ERROR   %-46s %s" % (etiqueta[:46], motivo))

print("\n%d accesibles, %d cerrados, %d con error" % (len(abiertos), len(cerrados), len(errores)))
sys.exit(1 if cerrados or errores else 0)
