# Artículos con paywall → PDF para clase

Pipeline para convertir lecturas de The Economist y The New York Times en PDF
limpios, listos para imprimir y repartir en clase.

Usa **tu propia suscripción**: el extractor corre dentro de una pestaña ya
autenticada del navegador. No hay credenciales, cookies ni tokens en este
repositorio, y nada de eso debe guardarse aquí.

## Los tres pasos

```
extractor.js   navegador   artículo  → JSON estructurado
repartir.py    local       bundle    → un JSON por artículo
maquetar.py    local       JSON      → PDF tipo lectura
```

La separación importa: rediseñar el PDF solo toca `maquetar.py`, sin volver a
descargar nada. Los JSON en `lecturas/semanaN/raw/` son la fuente de verdad.

## 1. Extraer

Requiere una pestaña abierta en el medio, con la sesión iniciada. Se inyecta
`extractor.js` completo en esa pestaña y luego:

```js
await __extraerLote([
  { url: 'https://www.nytimes.com/...', archivo: 's3-01-nyt-algo.json' },
  { url: 'https://www.nytimes.com/...', archivo: 's3-02-nyt-otro.json' }
], { semana: 3, bundle: 's3-nyt.json' })
```

Desde una pestaña ya abierta en el dominio, `fetch()` es *same-origin* y viaja
con las cookies de la sesión: se bajan todos los artículos de un medio sin
navegar a cada uno. Hay que correrlo **una vez por medio** (economist y nytimes
son orígenes distintos).

Todo llega en **un solo archivo**. Chrome bloquea las descargas automáticas
múltiples de un mismo sitio: deja pasar la primera y descarta el resto salvo que
se conceda el permiso. Por eso un bundle único, y por eso la primera vez que se
usa un medio nuevo Chrome pide autorización de descarga en la barra de
direcciones — hay que concederla una vez por sitio.

`receptor.py` es una alternativa que escribe directo en el repositorio sin pasar
por la carpeta de Descargas, pero exige el permiso de *acceso a red local* del
sitio, que es más engorroso de conceder. Queda como respaldo.

## 2. Repartir

```bash
python tools/articulos/repartir.py ~/Downloads/s3-nyt.json lecturas/semana3/raw --borrar
```

## 3. Maquetar

```bash
python tools/articulos/maquetar.py lecturas/semana3/raw --salida lecturas/semana3/pdf
```

Opciones útiles:

- `--sin-imagenes` omite fotos y gráficos (ahorra tinta al imprimir).
- `--solo-html` deja el HTML intermedio para revisar el diseño sin generar PDF.

Renderiza con Chrome en modo headless y un perfil temporal, porque el perfil
real está en uso por el navegador abierto.

## Formato del PDF

Una columna, serif, A4 con márgenes de 20–22 mm para anotar a mano. Encabezado
con curso, semana, medio y sección; pie con la fuente, la fecha y la URL. Se
descartan las promos que los medios incrustan en el cuerpo del artículo
("Follow the New York Times Opinion section…", "For subscribers only…"); la
lista está en `RUIDO`, dentro de `maquetar.py`.

## Cuando un medio cambia de maquetación

- **The Economist**: se lee `__NEXT_DATA__`, el JSON de Next.js con el cuerpo ya
  segmentado en `PARAGRAPH` / `CROSSHEAD` / `INFOBOX`. Es estable; las clases CSS
  de la página están ofuscadas y no sirven.
- **The New York Times**: metadatos desde el `ld+json` de tipo `NewsArticle`, y
  el cuerpo desde `section[name="articleBody"]`.

Si `__extraerLote` devuelve `cuerpo vacío`, el medio cambió de estructura o la
sesión perdió la suscripción. Conviene revisar primero que el artículo se vea
completo en la pestaña.
