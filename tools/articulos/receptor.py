"""Receptor local para el extractor de artículos.

Chrome bloquea las descargas automáticas múltiples de un mismo sitio, así que en
vez de usar la carpeta de Descargas el extractor envía el JSON por POST a este
servidor, que lo escribe directo en el repositorio.

http://localhost es un origen "potencialmente confiable" para Chrome, de modo
que un fetch desde una página https:// hacia acá no cuenta como contenido mixto.

Uso:
    python tools/articulos/receptor.py lecturas/semana3/raw [--puerto 8765]
"""

import argparse
import json
import re
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from socketserver import ThreadingMixIn

DESTINO = None


class ServidorHilos(ThreadingMixIn, HTTPServer):
    """Preflight y POST llegan por conexiones distintas: sin hilos se traban."""

    daemon_threads = True


class Receptor(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        # Private Network Access: una página pública (https://www.economist.com)
        # que llama a localhost necesita este permiso explícito, y Chrome fuerza
        # un preflight aunque el POST sea una "simple request".
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Private-Network-Access-Id", "00:00:00:00:00:00")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_POST(self):
        cuerpo = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        try:
            datos = json.loads(cuerpo.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            return self._responder(400, {"error": "JSON inválido: %s" % e})

        articulos = datos if isinstance(datos, list) else [datos]
        escritos = []
        for art in articulos:
            if "error" in art:
                print("  !! %s -> %s" % (art.get("url", "?"), art["error"]), flush=True)
                continue
            nombre = seguro(art.get("archivo") or (art.get("titulo", "articulo") + ".json"))
            ruta = DESTINO / nombre
            ruta.write_text(json.dumps(art, ensure_ascii=False, indent=2), encoding="utf-8")
            escritos.append(nombre)
            print("  ok %s (%s bloques)" % (nombre, len(art.get("cuerpo", []))), flush=True)

        self._responder(200, {"escritos": escritos})

    def _responder(self, codigo, payload):
        cuerpo = json.dumps(payload).encode("utf-8")
        self.send_response(codigo)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def log_message(self, *args):
        pass  # el detalle útil ya se imprime en do_POST


def seguro(nombre):
    """Evita que un nombre venido del navegador escriba fuera de DESTINO."""
    nombre = Path(str(nombre)).name
    nombre = re.sub(r"[^A-Za-z0-9._-]+", "-", nombre).strip("-")
    if not nombre.endswith(".json"):
        nombre += ".json"
    return nombre or "articulo.json"


def main():
    global DESTINO
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("destino", help="carpeta donde escribir los JSON")
    p.add_argument("--puerto", type=int, default=8765)
    args = p.parse_args()

    DESTINO = Path(args.destino).resolve()
    DESTINO.mkdir(parents=True, exist_ok=True)

    servidor = ServidorHilos(("127.0.0.1", args.puerto), Receptor)
    print("receptor escuchando en http://localhost:%d -> %s" % (args.puerto, DESTINO), flush=True)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("receptor detenido", flush=True)
        return 0


if __name__ == "__main__":
    sys.exit(main())
