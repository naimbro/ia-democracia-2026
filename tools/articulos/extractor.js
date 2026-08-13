/* ---------------------------------------------------------------------------
   Extractor de artículos con paywall -> JSON estructurado.
   Curso: Inteligencia Artificial y Democracia 2026.

   Se inyecta en la pestaña del artículo y reutiliza la sesión autenticada del
   navegador. El texto se arma y se descarga dentro del navegador, sin pasar por
   ningún intermediario: no hay pérdida ni error de transcripción.

   La maquetación del PDF vive aparte, en maquetar.py, para poder rediseñar el
   impreso sin volver a descargar nada.

   Uso:  await __extraerLote([{url, archivo}, ...], { semana: 3, bundle: 's3-eco.json' })

   __extraerLote baja varios artículos de una sola inyección: desde una pestaña
   ya abierta en el dominio, fetch() es same-origin y viaja con las cookies de
   la sesión, así que no hace falta navegar a cada artículo.

   El resultado NO baja por la carpeta de Descargas: Chrome bloquea las descargas
   automáticas múltiples de un mismo sitio. En su lugar se envía por POST a
   receptor.py, que escribe cada artículo directo en el repositorio. Hay que
   tenerlo corriendo antes:

       python tools/articulos/receptor.py lecturas/semana3/raw
   --------------------------------------------------------------------------- */

var RECEPTOR = 'http://localhost:8765/';

window.__extraerLote = function (entradas, opts) {
  opts = opts || {};
  return entradas.reduce(function (cadena, e) {
    return cadena.then(function (acc) {
      return fetch(e.url, { credentials: 'include' })
        .then(function (r) {
          if (!r.ok) throw new Error('HTTP ' + r.status);
          return r.text();
        })
        .then(function (html) {
          var doc = new DOMParser().parseFromString(html, 'text/html');
          var art = extraerDe(doc, e.url, new URL(e.url).hostname);
          art.url = e.url.split('?')[0];
          art.archivo = e.archivo || (slug(art.titulo) + '.json');
          art.bloque = e.bloque || '';
          art.semana = opts.semana || '';
          art.capturado = new Date().toISOString();
          if (!art.cuerpo.length) throw new Error('cuerpo vacío: paywall o cambio de maquetación');
          acc.push(art);
          // Pausa breve: descargar en ráfaga se ve como scraping y no aporta nada.
          return new Promise(function (res) { setTimeout(function () { res(acc); }, 900); });
        })
        .catch(function (err) {
          acc.push({ error: String((err && err.message) || err), url: e.url, archivo: e.archivo });
          return acc;
        });
    });
  }, Promise.resolve([])).then(function (arts) {
    var resumen = arts.map(function (a) {
      return a.error
        ? { ok: false, archivo: a.archivo, error: a.error }
        : { ok: true, archivo: a.archivo, fuente: a.fuente, titulo: a.titulo,
            autor: a.autor, fecha: a.fecha, bloques: a.cuerpo.length, palabras: palabras(a.cuerpo) };
    });
    return enviar(arts).then(
      function (r) { return { guardados: r.escritos, articulos: resumen }; },
      function (e) { return { error: 'receptor no responde (' + e.message + '): ¿está corriendo receptor.py?', articulos: resumen }; }
    );
  });
};

/* text/plain evita el preflight CORS: es una "simple request". */
function enviar(datos) {
  return fetch(RECEPTOR, {
    method: 'POST',
    headers: { 'Content-Type': 'text/plain;charset=utf-8' },
    body: JSON.stringify(datos)
  }).then(function (r) {
    if (!r.ok) throw new Error('HTTP ' + r.status);
    return r.json();
  });
}

function extraerDe(doc, url, hostname) {
  var host = hostname.replace(/^www\./, '');
  if (host.indexOf('economist') !== -1) return extraerEconomist(doc, url);
  if (host.indexOf('nytimes') !== -1) return extraerNYT(doc, url);
  throw new Error('Sitio no soportado: ' + host);
}

/* ----------------------------- The Economist -----------------------------
   Next.js expone el artículo completo en __NEXT_DATA__, con el cuerpo ya
   segmentado en PARAGRAPH / CROSSHEAD / INFOBOX. Es más fiable que el DOM,
   cuyas clases CSS están ofuscadas y cambian cada pocas semanas.            */

function extraerEconomist(doc, url) {
  var nd = doc.getElementById('__NEXT_DATA__');
  if (!nd) throw new Error('Falta __NEXT_DATA__ en ' + url + ': la página quizá no terminó de cargar');
  var c = JSON.parse(nd.textContent).props.pageProps.content;
  if (!c) throw new Error('Sin content en __NEXT_DATA__ de ' + url);

  var cuerpo = [];
  (c.body || []).forEach(function (n) {
    if (n.type === 'PARAGRAPH') {
      cuerpo.push({ tipo: 'p', html: n.textHtml || esc(n.text) });
    } else if (n.type === 'CROSSHEAD') {
      cuerpo.push({ tipo: 'h2', html: esc(n.text) });
    } else if (n.type === 'UNORDERED_LIST' || n.type === 'ORDERED_LIST') {
      cuerpo.push({ tipo: n.type === 'ORDERED_LIST' ? 'ol' : 'ul', items: listaItems(n) });
    } else if (n.type === 'BLOCK_QUOTE') {
      cuerpo.push({ tipo: 'quote', html: n.textHtml || esc(n.text) });
    } else if ((n.type === 'IMAGE' || n.type === 'CHART') && n.url) {
      // caption puede venir como objeto {textHtml|text} o como texto plano.
      var cap = n.caption;
      if (cap && typeof cap === 'object') cap = cap.textHtml || esc(cap.text || '');
      cuerpo.push({ tipo: 'img', src: n.url, pie: cap || esc(n.altText || '') });
    } else if (n.type === 'INFOBOX') {
      var sub = [];
      (n.components || n.body || []).forEach(function (b) {
        if (b.type === 'UNORDERED_LIST' || b.type === 'ORDERED_LIST') {
          sub.push('<ul>' + listaItems(b).map(function (i) { return '<li>' + i + '</li>'; }).join('') + '</ul>');
        } else {
          sub.push('<p>' + (b.textHtml || esc(b.text)) + '</p>');
        }
      });
      if (sub.length) cuerpo.push({ tipo: 'box', html: sub.join('') });
    }
  });

  return {
    fuente: 'The Economist',
    seccion: (c.section && c.section.name) || '',
    antetitulo: c.flyTitle || '',
    titulo: c.headline || doc.title,
    bajada: c.rubric || '',
    autor: c.byline || '',
    lugar: c.dateline || '',
    fecha: c.datePublished || c.dateFirstPublished || '',
    lectura: c.estimatedReadTime ? Math.round(c.estimatedReadTime) : null,
    cuerpo: cuerpo
  };
}

function listaItems(n) {
  return (n.items || []).map(function (i) {
    return typeof i === 'string' ? esc(i) : (i.textHtml || esc(i.text));
  });
}

/* ------------------------- The New York Times ----------------------------
   El NYT no publica un JSON de cuerpo estable, pero sí un ld+json NewsArticle
   con los metadatos, y delimita el cuerpo con section[name="articleBody"].  */

function extraerNYT(doc, url) {
  var meta = ldNewsArticle(doc);
  var sec = doc.querySelector('section[name="articleBody"]');
  if (!sec) throw new Error('Sin section[name="articleBody"] en ' + url);

  var cuerpo = [];
  sec.querySelectorAll('p, h2, h3, ul, ol, blockquote, figure').forEach(function (el) {
    // aside = "lecturas relacionadas" y promos, no forman parte del artículo.
    if (el.closest('aside')) return;
    // Evita duplicar los <p> que ya se recogen al recorrer su contenedor.
    if (el.tagName === 'P' && el.parentElement && el.parentElement.closest('figure, blockquote, ul, ol')) return;

    if (el.tagName === 'FIGURE') {
      var img = el.querySelector('img');
      var pie = el.querySelector('figcaption');
      if (img) {
        var src = img.getAttribute('src') || primeraDeSrcset(img.getAttribute('srcset'));
        if (src) cuerpo.push({ tipo: 'img', src: new URL(src, url).href, pie: pie ? texto(pie) : '' });
      }
      return;
    }
    if (!texto(el)) return;
    if (el.tagName === 'H2' || el.tagName === 'H3') {
      cuerpo.push({ tipo: 'h2', html: esc(texto(el)) });
    } else if (el.tagName === 'UL' || el.tagName === 'OL') {
      cuerpo.push({
        tipo: el.tagName.toLowerCase(),
        items: [].slice.call(el.querySelectorAll(':scope > li')).map(function (li) { return limpiar(li.innerHTML, url); })
      });
    } else if (el.tagName === 'BLOCKQUOTE') {
      cuerpo.push({ tipo: 'quote', html: limpiar(el.innerHTML, url) });
    } else {
      cuerpo.push({ tipo: 'p', html: limpiar(el.innerHTML, url) });
    }
  });

  var h1 = doc.querySelector('h1');
  return {
    fuente: 'The New York Times',
    seccion: (meta.articleSection || new URL(url).pathname.split('/')[4] || '').toString(),
    antetitulo: '',
    titulo: (h1 && texto(h1)) || meta.headline || doc.title.replace(/ - The New York Times$/, ''),
    bajada: meta.description || '',
    autor: autoresLd(meta.author),
    lugar: '',
    fecha: meta.datePublished || fechaTime(doc),
    lectura: null,
    cuerpo: cuerpo
  };
}

// innerText exige layout, que un documento de DOMParser no tiene: usar textContent.
function texto(el) {
  return (el.textContent || '').replace(/\s+/g, ' ').trim();
}

function primeraDeSrcset(srcset) {
  if (!srcset) return '';
  return srcset.split(',')[0].trim().split(/\s+/)[0] || '';
}

function ldNewsArticle(doc) {
  var nodos = [].slice.call(doc.querySelectorAll('script[type="application/ld+json"]'));
  for (var i = 0; i < nodos.length; i++) {
    try {
      var j = JSON.parse(nodos[i].textContent);
      if (/^(NewsArticle|Article|OpinionNewsArticle|ReportageNewsArticle)$/.test(j['@type'])) return j;
    } catch (e) { /* fragmento no parseable, seguir */ }
  }
  return {};
}

function autoresLd(a) {
  if (!a) return '';
  return (Array.isArray(a) ? a : [a])
    .map(function (x) { return typeof x === 'string' ? x : (x.name || ''); })
    .filter(Boolean).join(', ');
}

function fechaTime(doc) {
  var t = doc.querySelector('time[datetime]');
  return t ? t.getAttribute('datetime') : '';
}

/* ------------------------------ utilidades ------------------------------- */

function esc(s) {
  var d = document.createElement('div');
  d.textContent = s == null ? '' : String(s);
  return d.innerHTML;
}

/* Conserva énfasis y enlaces; descarta scripts, botones y atributos de tracking. */
function limpiar(html, base) {
  var d = document.createElement('div');
  d.innerHTML = html || '';
  d.querySelectorAll('script, style, button, svg, noscript').forEach(function (e) { e.remove(); });
  d.querySelectorAll('*').forEach(function (e) {
    if (!/^(EM|I|STRONG|B|A|SUP|SUB|SPAN|BR|CODE|Q)$/.test(e.tagName)) {
      e.replaceWith.apply(e, [].slice.call(e.childNodes));
      return;
    }
    [].slice.call(e.attributes).forEach(function (at) {
      if (!(e.tagName === 'A' && at.name === 'href')) e.removeAttribute(at.name);
    });
    if (e.tagName === 'A' && e.getAttribute('href')) {
      try { e.setAttribute('href', new URL(e.getAttribute('href'), base || location.href).href); } catch (err) { /* href inválido */ }
    }
  });
  return d.innerHTML.trim();
}

function palabras(cuerpo) {
  return cuerpo.reduce(function (n, b) {
    var t = b.html || (b.items || []).join(' ') || '';
    return n + t.replace(/<[^>]+>/g, ' ').trim().split(/\s+/).filter(Boolean).length;
  }, 0);
}

function slug(s) {
  return (s || 'articulo').toLowerCase().normalize('NFD').replace(/\p{M}/gu, '')
    .replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 70);
}

