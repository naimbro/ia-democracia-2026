# Artículos con paywall → PDF para clase

Pipeline para convertir lecturas de The Economist, The New York Times y The
Atlantic en PDF limpios, listos para imprimir y repartir en clase.

Usa **tu propia suscripción**: el extractor corre dentro de una pestaña ya
autenticada del navegador. No hay credenciales, cookies ni tokens en este
repositorio, y nada de eso debe guardarse aquí.

## Los pasos

```
manifiesto.py  local       syllabus  → qué falta bajar
extractor.js   navegador   artículo  → JSON estructurado
repartir.py    local       bundle    → un JSON por artículo
maquetar.py    local       JSON      → PDF tipo lectura
enlazar.py     local       ids Drive → enlaces en el syllabus
```

La separación importa: rediseñar el PDF solo toca `maquetar.py`, sin volver a
descargar nada. Los JSON en `lecturas/semanaN/raw/` son la fuente de verdad.

`syllabus.py` es el módulo compartido que lee `index.html`. El syllabus anida
listas varios niveles (semana › bloque temático › lectura › preguntas), así que
empareja los `<li>` con una pila y atribuye cada enlace a su `<li>` más interno.
Con una expresión regular tipo `<li>(.*?)</li>` se pierden lecturas y los
enlaces terminan insertados dentro de las listas de preguntas.

## 0. Ver qué falta

```bash
python tools/articulos/manifiesto.py              # resumen del curso
python tools/articulos/manifiesto.py --todas      # llamadas listas para pegar
```

`--todas` junta las semanas pendientes en un lote por medio: como el nombre de
archivo lleva la semana, no hace falta repetir el proceso semana por semana.

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

## 4. Enlazar en el syllabus

Los PDF se copian a Drive (`G:\Mi unidad\Lecturas Semana N — IA y Democracia
2026`) y se enlazan desde `index.html`. Hace falta un mapa de nombre de PDF a id
de Drive, que se arma con los ids del conector de Drive:

```json
{ "s5-02-nyt-musk-zucman.pdf": "1hh1nvZ...", "...": "..." }
```

```bash
python tools/articulos/enlazar.py mapa.json --simular   # revisar
python tools/articulos/enlazar.py mapa.json             # aplicar
```

Es idempotente: no duplica enlaces ya puestos. Mantiene el enlace original al
medio y agrega el PDF al lado. Las entradas marcadas `(podcast)` se etiquetan
"transcripción (PDF)", porque son para escuchar y su transcripción ocupa decenas
de páginas.

Las carpetas de Drive nacen privadas. Para que los alumnos accedan hay que
abrirlas a mano; no hay herramienta que cambie permisos de Drive desde acá.

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

## Lo que no se puede convertir

Las URL bajo `economist.com/insider/` son episodios de video de The Economist
Insider, no artículos: la página solo trae un resumen de un par de párrafos y un
reproductor. Devuelven `Falta __NEXT_DATA__` y quedan en el syllabus como
enlace, sin PDF. No es un error del extractor.

## The Atlantic y los gift links

`extractor.js` también soporta The Atlantic: metadatos desde el `ld+json`
`NewsArticle` y cuerpo desde `section[class*="ArticleBody_root"]`. Dos trampas
propias de ese sitio:

- El bloque `ArticleRelatedContent` ("Recommended Reading") va incrustado en
  medio del cuerpo y aporta encabezados e imágenes que no son del artículo.
- `alternativeHeadline` repite el titular; la bajada real está en el elemento
  `dek` del DOM.

Cuando la lectura llega por un **gift link** del suscriptor, ese enlace abre el
artículo completo sin paywall. Conviene usarlo como enlace al medio en el
syllabus: es el mecanismo que el propio medio ofrece para compartir, así que el
alumno puede leer en la fuente y el PDF queda solo como respaldo para imprimir.
