# MOVIRIS — Documentación Técnica

**Tipo:** Bienvenida animada + componente ETL para focos de calor (subida de CSV, limpieza, línea base y publicación opcional en Turso)  
**Backend:** Flask (Python)  
**Frontend:** HTML, CSS y JavaScript vanilla (bienvenida animada + pestaña ETL)  
**Idiomas:** Interfaz bilingüe EN/ES con diccionario estático (`i18n.js`); inglés por defecto  
**Explain:** Botón por gráfico en Dashboard y Calendario; una llamada a Groq por clic (`backend/explain.py`)  
**Motor ETL:** Python estándar (`csv`, `sqlite3`, `statistics`, `zlib`)  
**Base de datos:** Turso (libSQL) para publicación remota y SQLite local para staging  
**Fuente de datos:** NASA FIRMS (MODIS y VIIRS, archivo y NRT)  
**Entorno de ejecución:** Python 3.10+ (Windows / Linux)  
**Estado actual:** Modo local por defecto (`TURSO_ENABLED=false`), con lectura Turso disponible al activar `true`; bienvenida en `/`, componente Inicio en `/inicio/`, mapa en `/mapa/`, calendario en `/calendario/`, Dashboard con API en `/dashboard/`, ETL en `/etl/` e interfaz EN/ES con Explain (Groq) en Dashboard y Calendario

> [!IMPORTANT]
> **Modo local activo.** El proyecto arranca con `TURSO_ENABLED=false`. En este modo la pestaña ETL, los endpoints de lectura y el CLI trabajan únicamente contra `data/moviris_staging.db`; no se consulta ni se escribe en Turso. Para reconectar, cambia `TURSO_ENABLED=true` en `.env`. No hay botón de conexión en la interfaz.
>
> **Los CSV crudos no son datos de runtime.** El resultado limpio vive en el staging SQLite y, cuando se publica, en Turso. `backend/schema.sql` contiene solo el DDL, no datos.

---

## 1. Stack Tecnológico

| Capa | Tecnología | Propósito |
|------|------------|-----------|
| **Lenguaje base** | Python 3.10+ | Backend, ETL, validaciones y acceso a datos |
| **Framework web** | Flask 3.1+ | Rutas HTTP, subida de archivos y servidor de desarrollo |
| **Cliente de Turso** | `libsql-client` 0.3.1+ | Conexión HTTP a Turso y ejecución de lotes |
| **Staging local** | SQLite 3 (`sqlite3` de la stdlib) | Persistencia intermedia de los datos limpios |
| **Procesamiento CSV** | `csv` de la stdlib | Lectura de FIRMS sin pandas ni numpy |
| **Cálculo estadístico** | `statistics`, `math` | Media, desviación, percentiles y z-score |
| **Máscara geográfica** | Natural Earth 1:10 m rasterizado a 0,01° | Distinguir tierra y mar sin dependencias externas |
| **Frontend** | HTML5 + CSS3 + JavaScript vanilla | Bienvenida animada, Inicio, Mapa, Calendario y pestaña ETL |
| **Idioma** | Diccionario estático `i18n.js` + `Intl` | Interfaz EN/ES, números y fechas por locale; sin API de traducción |
| **Explain** | Groq Chat Completions (`urllib` de la stdlib) | Explicación breve por gráfico, solo con los datos enviados |
| **Mapa** | Leaflet 1.9.4 (CDN) + teselas OpenStreetMap | Visualización de celdas y áreas de interés |
| **Servidor de producción** | No incluido | El servidor Flask es de desarrollo; usar un WSGI para producción |
| **Control de versiones** | Git / GitHub | Repositorio del proyecto |

> [!NOTE]
> No se utilizan frameworks de frontend, ORM, pandas ni librerías de mapas en el backend. La bienvenida, Inicio y ETL usan JavaScript vanilla; el componente Mapa usa Leaflet 1.9.4 desde CDN con teselas de OpenStreetMap, el Dashboard usa Chart.js 4.4.1 desde CDN y toda la interfaz comparte el diccionario estático de `i18n.js`. El backend consulta SQL parametrizado. El ETL usa únicamente la biblioteca estándar de Python más `libsql-client`; Explain usa `urllib` de la stdlib.

---

## 2. Estructura de Directorios

```text
MOVIRIS/
│
├── run.py                     # Punto de entrada: arranca Flask
├── requirements.txt           # Flask + libsql-client
├── .env                       # Credenciales de Turso y TURSO_ENABLED (IGNORADO)
├── .env.example               # Plantilla de configuración
├── .gitignore                 # Excluye .env, data/, uploads/, caché y entornos
├── ico.svg                    # Logo oficial (fill #637545, servido en /ico.svg)
├── index.html                 # Bienvenida (se sirve en /)
├── styles.css                 # Estilos de la bienvenida
├── script.js                  # Animaciones de la bienvenida
├── i18n.js                    # Diccionario EN/ES, selector y formatos regionales
├── explain.js                 # Ventana Explain compartida (Dashboard y Calendario)
├── explain.css                # Estilos del botón y de la ventana Explain
├── README.md                  # Inicio rápido
├── DOCUMENTACION.md           # Este documento
│
├── backend/
│   ├── __init__.py
│   ├── app.py                 # Rutas, subida/borrado de archivos y frontend
│   ├── explain.py             # POST /api/explain: una llamada a Groq por clic
│   ├── db.py                  # Lecturas locales o Turso según TURSO_ENABLED
│   ├── jobs.py                # Gestor de trabajos ETL en segundo plano
│   ├── settings.py            # Interruptor TURSO_ENABLED
│   └── schema.sql             # DDL de referencia (sin datos)
│
├── tests/
│   └── test_explain.py        # Pruebas de /api/explain con Groq simulado
│
├── etl/
│   ├── index.html             # Pestaña simplificada de ETL
│   ├── style.css              # Tema claro y sobrio
│   ├── script.js              # Subida, progreso, resumen y errores
│   └── etl.py                 # Motor ETL + CLI
│
├── header/
│   ├── index.html             # Fragmento compartido de navegación
│   ├── style.css              # Estilos con alcance #site-header
│   └── script.js              # Inyección del fragmento y pestaña activa
│
├── inicio/
│   ├── index.html             # Componente Inicio (landing)
│   ├── style.css              # Estilos del componente Inicio
│   └── script.js              # Revelado al hacer scroll
│
├── mapa/
│   ├── index.html             # Página del mapa
│   ├── style.css              # Estilos del mapa
│   ├── script.js              # Leaflet, área, fechas y celdas
│   └── mapa.py                # Blueprint Flask del mapa y su API
│
├── calendario/
│   ├── index.html             # Página del calendario
│   ├── style.css              # Estilos del calendario
│   ├── script.js              # Matriz año × mes, detalle diario y CSV
│   └── calendario.py          # Blueprint Flask del calendario y su API
│
├── dashboard/
│   ├── index.html             # Dashboard de patrones históricos
│   ├── style.css              # Estilos del Dashboard
│   ├── script.js              # Gráficos, filtros y descargas CSV
│   └── dashboard.py           # Blueprint Flask y API del Dashboard
│
├── data/                      # IGNORADO
│   └── moviris_staging.db     # Datos limpios locales (~96 MB con el dataset actual)
│
└── uploads/                   # IGNORADO, temporal
    └── <upload_id>/           # CSV/ZIP subidos desde la pestaña
```

### Convención de archivos

| Archivo / carpeta | Rol | Se versiona |
|-------------------|-----|-------------|
| `run.py` | Arranque del servidor | Sí |
| `index.html` | Bienvenida servida en `/` | Sí |
| `styles.css` | Estilos de la bienvenida | Sí |
| `script.js` | Animaciones de la bienvenida | Sí |
| `i18n.js` | Diccionario EN/ES, selector de idioma y helpers de formato | Sí |
| `explain.js`, `explain.css` | Botón y ventana Explain compartidos | Sí |
| `backend/` | Backend Flask, ETL jobs y acceso a datos | Sí |
| `tests/` | Pruebas automatizadas (`test_explain.py`) | Sí |
| `etl/` | Pestaña ETL y motor de transformación | Sí |
| `header/` | Componente compartido de header; no se duplica en las páginas | Sí |
| `inicio/` | Componente Inicio (landing) | Sí |
| `mapa/` | Componente Mapa + blueprint Flask | Sí |
| `calendario/` | Componente Calendario + blueprint Flask | Sí |
| `dashboard/` | Dashboard de patrones históricos + blueprint Flask | Sí |
| `ico.svg` | Logo servido en `/ico.svg`; `fill="#637545"` | Sí |
| `requirements.txt` | Dependencias Python | Sí |
| `.env` | Token de Turso, `TURSO_ENABLED` y credenciales de Groq | **No** (ignorado) |
| `data/` | Staging SQLite generado | **No** (ignorado) |
| `uploads/` | Archivos temporales de subida | **No** (ignorado) |
| `__pycache__/`, `*.pyc` | Caché de Python | **No** (ignorado) |
| `hackathon/` | CSV crudos opcionales para el CLI | No es necesario; no forma parte del runtime |

> [!NOTE]
> El logo **no se duplica** en `etl/`. `backend/app.py` sirve el archivo de la raíz mediante `GET /ico.svg`. La ruta antigua `/etl/ico.svg` ya no existe.

---

## 3. Arquitectura del Sistema

### A. Diagrama global

```text
┌─────────────────────────────────────────────────────────────────────┐
│                    Navegador · etl/index.html                       │
│  - Lista de archivos subidos en memoria                             │
│  - Botón Ejecutar ETL                                               │
│  - Barra de progreso, pasos y resumen                               │
│  - Indicador Modo local / Turso conectado                           │
└───────────────┬─────────────────────────────────────────────────────┘
                │ POST /api/upload  (un archivo por petición)
                │ DELETE /api/uploads/<id>
                │ POST /api/etl/run
                │ GET  /api/etl/status
                │ GET  /api/health
                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     Flask · backend/app.py                          │
│                                                                     │
│  1. Guarda CSV/ZIP en uploads/<upload_id>/                          │
│  2. Valida columnas latitude, longitude y acq_date                  │
│  3. Crea un JobManager (un trabajo activo)                          │
│  4. Lanza etl/etl.py en un hilo                                     │
│  5. Expone progreso, logs y resumen por polling                     │
└───────────────┬─────────────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     ETL · etl/etl.py                                │
│                                                                     │
│  Extract  → analiza archivos y sensores                             │
│  Transform→ agrega celdas-día (malla 0,01°)                         │
│  Baseline → línea base por celda y semana ISO                       │
│  Estado   → z-score, normal/inusual/crítico y máscara no vegetal    │
│  Load     → escribe staging SQLite; push a Turso si está activo     │
└───────────────┬───────────────────────────────┬─────────────────────┘
                │                               │
                ▼                               ▼
┌──────────────────────────────┐   ┌──────────────────────────────────┐
│ data/moviris_staging.db      │   │ Turso (libSQL)                   │
│ SQLite local                 │   │ fire_cells_daily                 │
│ 3 tablas analíticas          │   │ fire_baseline                    │
│                              │   │ non_vegetation_mask              │
└──────────────────────────────┘   └──────────────────────────────────┘
                ▲
                │ lectura local si TURSO_ENABLED=false
                │ lectura remota si TURSO_ENABLED=true
┌───────────────┴─────────────────────────────────────────────────────┐
│ backend/db.py · health, stats, map, cells, mask                     │
└─────────────────────────────────────────────────────────────────────┘
```

### B. Flujo de la pestaña ETL

1. **Subida:** el usuario arrastra o selecciona archivos `.csv` o `.zip`. El frontend sube **cada archivo en una petición independiente** a `POST /api/upload`.
2. **Validación:** el backend valida el nombre, la extensión, el tamaño, el ZIP y que el CSV tenga `latitude`, `longitude` y `acq_date`.
3. **Almacenamiento temporal:** cada archivo se guarda en `uploads/<upload_id>/`. Un ZIP se descomprime en una subcarpeta y se valida cada CSV extraído.
4. **Lista:** la respuesta devuelve un lote (`batch`) con id, tamaño, archivos y tipo (`archive` / `nrt`). El frontend muestra la lista y permite **Quitar** cada lote.
5. **Borrado:** `DELETE /api/uploads/<upload_id>` elimina la carpeta. Se rechaza con `409` si hay un ETL en ejecución.
6. **Ejecución:** el botón **Ejecutar ETL** envía `POST /api/etl/run` con los `upload_ids` y los valores por defecto (`include_nrt`, `exclude_current_year`, `replace`, `push`).
7. **Job en segundo plano:** el backend resuelve las rutas, crea un trabajo y arranca `run_etl()` en un hilo. La UI consulta `GET /api/etl/status` cada segundo.
8. **Resultado local:** el ETL escribe `data/moviris_staging.db` con las tres tablas.
9. **Publicación opcional:** si `TURSO_ENABLED=true` y `push=true`, se ejecuta `push_staging()` contra Turso. En modo local el backend fuerza `push=false` y la etapa **Load** aparece como **omitida**.
10. **Resumen:** la UI muestra filas leídas, celda-días, filas de línea base y celdas en la máscara.

### C. Modos de ejecución

| Aspecto | `TURSO_ENABLED=false` (actual) | `TURSO_ENABLED=true` |
|---|---|---|
| Fuente de lecturas (`health`, `stats`, `map`, `cells`, `mask`) | `data/moviris_staging.db` | Turso |
| ETL | Fuerza `push=false`; solo staging | `push` según la petición |
| `POST /api/etl/sync` | Responde `409` sin conectar | Sincroniza el staging |
| Indicador de cabecera | **Modo local** | **Turso conectado** o **Turso sin conexión** |
| Resumen del ETL | `mode: "local"`, `pushed: false` | `mode: "turso"`, `pushed: true` si se publicó |
| Consumo de Turso | Ninguno | Lecturas y escrituras explícitas |

El interruptor se lee desde `.env` en cada comprobación mediante `backend/settings.py`. No hay estado persistido aparte ni botón de conexión. Cambiar la línea y guardar el archivo es suficiente; la siguiente petición usa el nuevo modo.

> [!IMPORTANT]
> En modo local **no se ejecuta** `push_staging()`, que es la única función que hace `CREATE TABLE`, `DELETE` o `INSERT` en Turso. Los datos existentes en Turso permanecen intactos hasta que se cambie el flag y se ejecute un ETL con push o un sync explícito.

### D. Flujo interno del ETL

1. **Descubrimiento:** expande archivos y carpetas; deduplica rutas.
2. **Extract:** lee cada CSV, valida columnas, normaliza sensores/confianza/fechas y calcula medianas de FRP por sensor.
3. **Transform:** agrega detecciones por celda y fecha (malla 0,01°): conteo, FRP máximo, FRP normalizado, confianza máxima, sensores e `is_nrt`.
4. **Baseline:** construye la línea base por celda y semana ISO con las detecciones diarias históricas; excluye el año más reciente si hay más de un año.
5. **Estado:** calcula z-score y clasifica `normal`, `unusual` o `critical`.
6. **Máscara:** detecta fuentes persistentes y las clasifica como volcán, fuente fija o mar.
7. **Staging:** escribe un SQLite temporal y lo reemplaza atómicamente sobre `data/moviris_staging.db`.
8. **Load:** si Turso está activo y se pidió push, crea el esquema si falta, vacía las tablas si `replace=true`, inserta por lotes y verifica conteos.

Rangos de progreso del ETL: `1–20` Extract, `20–45` Transform, `45–65` Baseline/Estado, `65–74` máscara, `74–82` staging y `82–100` Turso. En modo local el proceso termina en `100` sin ejecutar la etapa remota.

### E. Estado de los trabajos

```text
POST /api/etl/run
        │
        ▼
   running ──► done
      │
      └────► error
```

- Solo existe **un trabajo activo** a la vez; un segundo intento recibe `409`.
- El estado vive en memoria (`JobManager`), no en la base.
- Se conservan los últimos **20** trabajos y hasta **500** líneas de log por trabajo.
- No hay endpoint de cancelación.
- `can_sync` se activa si un trabajo falla y el staging local existe; permite reintentar la subida cuando Turso está habilitado.

### F. Flujo de la bienvenida

1. `GET /` sirve `index.html` desde la raíz.
2. El HTML carga `/styles.css` y `/script.js`; no llama a la API ni a Turso.
3. Al cargar, JS activa `is-loaded`, que revela el titular, el subtítulo, el CTA, el satélite y la franja de datos.
4. El canvas `#network` dibuja una red de puntos que se conectan por proximidad y se mueven lentamente.
5. El SVG `.sat` muestra el anillo de marcas, la órbita y la Tierra; el grupo `.orb` gira 48 s con una animación CSS.
6. El CTA añade `is-leaving`, desvanece la página y navega a `/inicio/` después de 300 ms. Con `prefers-reduced-motion`, la navegación es inmediata.
7. `/inicio/` es el componente Inicio: hero, problema, solución, públicos y CTA a `/mapa/` y `/calendario/`.

> [!NOTE]
> Esta es la dirección visual vigente de la bienvenida. El patrón de landing genérico que se rechazó está documentado en la sección 13 y **no debe reintroducirse**. La bienvenida **no monta el header compartido**; ese componente se usa en `/etl/` y `/inicio/`.

---

## 4. Módulos y Componentes en Detalle

### [Entrada] `run.py`

| Elemento | Detalle |
|---|---|
| Argumentos | `--host` (default `127.0.0.1`), `--port` (default `5000`), `--debug`, `--reload`, `--open` |
| Arranque | Importa `backend.app.app` y ejecuta Flask con `threaded=True` |
| Consola | En Windows reconfigura `stdout`/`stderr` a UTF-8 |
| Banner | Muestra la bienvenida, el ETL, la API y el modo de Turso |
| `--open` | Abre la bienvenida (`/`), no el ETL |
| Limitación | Servidor de desarrollo; no usar tal cual en producción |

### [Bienvenida] `index.html`, `styles.css`, `script.js`

La bienvenida se sirve en `/` y es completamente estática: **no llama a la API ni a Turso**.

| Archivo | Rol |
|---|---|
| `index.html` | Canvas `#network`, titular, subtítulo, CTA, SVG `.sat` y franja `.facts`; **sin header ni footer** |
| `styles.css` | Tema oscuro, red de puntos, órbita, CTA con esquinas cortadas, revelado y responsive; **sin header/footer** |
| `script.js` | Red de puntos, revelado y transición `is-leaving`; sin llamadas a la API |

- **Copy:** “Lee el fuego antes de que avance.” / “Más de una década de focos de calor en Ecuador, en un solo calendario.” / **Explorar el fuego**.
- **Sin header ni footer:** la portada no monta `#site-header` ni carga `/header/*`; el header compartido se usa solo en `/etl/` y `/inicio/` (y futuras páginas).
- **Red de puntos:** canvas fijo con nodos que se conectan por proximidad y se mueven lentamente; se detiene con movimiento reducido.
- **Satélite:** SVG `.sat` con anillo de marcas, órbita y Tierra; el grupo `.orb` gira 48 s con animación CSS. En pantallas bajas se oculta para no forzar scroll.
- **CTA:** botón crema con esquinas cortadas; al pulsar añade `is-leaving`, desvanece la página y navega a `/inicio/`.
- **Revelado:** JS añade `is-loaded`; titular, subtítulo, CTA, satélite y datos aparecen escalonados. El titular usa opacidad + desplazamiento, **sin `overflow: hidden`**, para no cortar descendentes como la “g”.
- **Accesibilidad:** `prefers-reduced-motion` detiene la órbita y la red; sin JS, el contenido sigue visible y el enlace funciona.
- **Navegación:** el CTA lleva a `/inicio/`, el componente Inicio.
- **Selector de idioma:** la portada no monta el header, así que incluye su propio `#lang-select` (EN/ES) en la esquina superior derecha, con la misma clave `localStorage['moviris.lang']`.
- **Responsive:** dos columnas en escritorio; en móvil, una columna con CTA y datos compactos; el satélite se adapta al espacio restante.

### [Header compartido] `header/`

El header es un componente separado; **no se copia su HTML dentro de las páginas**.

| Archivo | Rol |
|---|---|
| `index.html` | Fragmento: marca, navegación (Inicio, Calendario, Mapa, Dashboard, ETL), rango 2012–2026 y selector `EN/ES` |
| `style.css` | Estilos con alcance `#site-header`, pestaña activa, selector de idioma y responsive |
| `script.js` | Descarga el fragmento, lo inyecta en `#site-header`, marca `aria-current="page"` y aplica el idioma al fragmento |

- **Páginas que lo usan:** `/etl/`, `/inicio/`, `/mapa/`, `/calendario/` y `/dashboard/`. La bienvenida `/` **no** lo monta.
- **Integración:** cada página solo incluye `<div id="site-header"></div>`, `/header/style.css` y `/header/script.js`; el resto lo resuelve el componente.
- **Sin duplicación:** las páginas no contienen las clases `hd-*` ni el HTML del header.
- **Enlaces:** todas las pestañas del header tienen página. El Dashboard consume `/api/dashboard/summary`.
- **Sin API/Turso:** el header solo descarga su propio fragmento estático.
- **Idioma:** el selector `EN/ES` es parte del fragmento. Al cambiarlo, `i18n.js` guarda la preferencia, añade `?lang=` a la URL y recarga para que números, fechas y gráficos se rendericen en el idioma elegido.
- **Rutas:** `/header/index.html`, `/header/style.css` y `/header/script.js`.

### [Mapa] `mapa/`

El mapa es un componente separado con su propio blueprint de Flask.

| Archivo | Rol |
|---|---|
| `index.html` | Página: controles de área/fechas, mapa Leaflet, KPIs y leyenda |
| `style.css` | Estilos del panel lateral, mapa y responsive |
| `script.js` | Leaflet, dibujo de área, consultas a la API y descarga CSV |
| `mapa.py` | Blueprint `mapa`: página, assets y API de consulta |

#### Registro del blueprint

El docstring de `mapa.py` indica la integración exacta; `backend/app.py` ya la aplica:

```python
from mapa.mapa import bp as mapa_bp
app.register_blueprint(mapa_bp)
```

#### Rutas del blueprint

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/mapa`, `/mapa/`, `/mapa/index.html` | Página del mapa |
| `GET` | `/mapa/style.css`, `/mapa/script.js` | Assets permitidos; `mapa.py` y otros archivos responden `404` |
| `GET` | `/api/mapa/meta` | Rango de fechas disponible (`min_date`, `max_date`) |
| `GET` | `/api/mapa/cells` | Celdas agregadas del área para dibujar y KPIs |
| `GET` | `/api/mapa/csv` | CSV en streaming de celdas-día del área y fechas |

#### Fuente de datos y modo

- Con `TURSO_ENABLED=false` lee `data/moviris_staging.db` en modo **solo lectura**.
- Con `TURSO_ENABLED=true` lee directamente de Turso mediante `TursoConnection` (`backend/db.py`).
- Si no hay datos en el modo activo o Turso no responde, responde `503`.
- El mapa no usa el header como HTML copiado: monta `#site-header` y carga `/header/*`, igual que las demás páginas.
- **Vista inicial mundial:** el mapa arranca en el mundo (`[-85, 85, -180, 180]`), no en Ecuador. La clave compartida es `localStorage['moviris.aoi.v2']`; las zonas rápidas son Mundo, América del Norte, América Central y Caribe, América del Sur, Europa, África, Asia y Oceanía.
- **Responsive:** a partir de 900 px el mapa pasa arriba y el panel debajo; a partir de 600 px los controles ocupan el ancho completo y el mapa mide 55dvh (mínimo 300 px). `script.js` usa `ResizeObserver` + `orientationchange` para llamar a `map.invalidateSize()`, de modo que Leaflet se adapta al cambiar el layout.
- Leaflet 1.9.4 se carga desde CDN y las teselas base son de **OpenStreetMap**, sin API key. OpenStreetMap es gratuito y financiado por donaciones; su política pide tráfico moderado y mantener la atribución visible. Para una demo local es suficiente; si el tráfico crece, conviene una key gratuita de CARTO, otro proveedor o teselas propias.
- **Cambio temporal de fondo:** antes se usaban teselas de CARTO, que desde el 25/09/2026 muestran “API KEY REQUIRED” si no se configura una key gratuita. Se cambió a OpenStreetMap para poder probar el mapa sin registro; el resto del diseño y del texto no cambió. Para volver a CARTO basta añadir `?key=TU_KEY` a la URL de teselas.

### [Calendario] `calendario/`

El calendario es un componente separado con su propio blueprint de Flask. Reutiliza el área de interés y la confianza del mapa.

| Archivo | Rol |
|---|---|
| `index.html` | Página: cabecera, controles, KPIs, matriz año × mes, períodos críticos y detalle diario |
| `style.css` | Estilos de la matriz, panel lateral y responsive |
| `script.js` | Carga matriz/mes, lee y guarda `localStorage['moviris.aoi.v2']`, descarga CSV |
| `calendario.py` | Blueprint `calendario`: página, assets y API de consulta |

#### Registro del blueprint

El docstring de `calendario.py` indica que se registre **después** del blueprint del mapa; `backend/app.py` ya lo aplica:

```python
from calendario.calendario import bp as calendario_bp
app.register_blueprint(calendario_bp)
```

#### Rutas del blueprint

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/calendario`, `/calendario/`, `/calendario/index.html` | Página del calendario |
| `GET` | `/calendario/style.css`, `/calendario/script.js` | Assets permitidos; `calendario.py` y otros archivos responden `404` |
| `GET` | `/api/calendario/matrix` | Matriz año × mes, mes actual vs. mediana y semanas con más celdas críticas |
| `GET` | `/api/calendario/month` | Detalle diario de un mes (`year`, `month`) |

#### Fuente de datos y modo

- Reutiliza `_connect()`, `ApiError` y `_number()` de `mapa/mapa.py`; hereda el modo local o Turso.
- Con `TURSO_ENABLED=false` lee `data/moviris_staging.db` en modo **solo lectura**.
- Con `TURSO_ENABLED=true` lee directamente de Turso.
- Si no hay datos en el modo activo o Turso no responde, responde `503`.
- El calendario monta `#site-header` y carga `/header/*`; no copia el HTML del header.
- **Área de interés:** la lee de la URL o de `localStorage['moviris.aoi.v2']` (la misma clave que usa el mapa) y la guarda al cambiar `conf`. Si el usuario viene del mapa, conserva la zona; sin área guardada usa la vista mundial.
- **CSV:** el botón **Descargar CSV** llama a `/api/mapa/csv` con el área y el rango visible; no hay endpoint CSV propio en el calendario.
- **Responsive:** por debajo de 960 px la matriz y el panel lateral pasan a una columna; por debajo de 600 px los controles ocupan el ancho completo. La matriz se desplaza horizontalmente dentro de `.matrix-wrap` (`min-width: 0` en las columnas) sin desbordar la página.

### [Dashboard] `dashboard/`

El Dashboard muestra la actividad histórica del área de interés: indicadores,
actividad por año, anomalías, estacionalidad, cobertura MODIS/VIIRS y descargas
CSV. Usa la misma área que el mapa (`localStorage['moviris.aoi.v2']`).

| Archivo | Rol |
|---|---|
| `index.html` | Página con el header compartido, controles, KPIs y cinco gráficos |
| `style.css` | Estilos del Dashboard con la paleta del proyecto |
| `script.js` | Chart.js, filtros, cálculo de anomalías/medianas y descargas |
| `dashboard.py` | Blueprint Flask: página, assets y `/api/dashboard/summary` |

#### Rutas

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/dashboard`, `/dashboard/`, `/dashboard/index.html` | Página del Dashboard |
| `GET` | `/dashboard/style.css` | Estilos del Dashboard |
| `GET` | `/dashboard/script.js` | Lógica y gráficos del Dashboard |
| `GET` | `/api/dashboard/summary` | Totales, matriz año × mes, celdas por año y cobertura de sensores |

#### API del Dashboard

- **Parámetros:** `south`, `north`, `west`, `east` y `conf` (`0`, `1` o `2`).
- **Respuesta:** `min_date`, `max_date`, `totals`, `months`, `year_cells` y `coverage`.
- Reutiliza `_area_params()` del calendario y `_connect()` del mapa.
- Con `TURSO_ENABLED=false` lee el staging local; con `true` lee Turso.
- Si no hay datos en el modo activo o Turso no responde, responde `503`.
- El CSV de celdas-día se descarga desde `/api/mapa/csv`, no desde un endpoint propio.
- Chart.js se carga desde CDN; si no hay Internet, la página avisa y no dibuja los gráficos.
- Monta `#site-header` y carga `/header/*`; el header marca **Dashboard**.

### [Idioma] `i18n.js`

El idioma es un componente transversal: se carga antes de los scripts de cada página y traduce el DOM sin tocar el HTML estático.

| Archivo | Rol |
|---|---|
| `i18n.js` | Diccionario EN/ES, lectura/guardado del idioma, traducción de texto y atributos, formatos `Intl` |
| selector `#lang-select` | En el header compartido y en la portada (que no monta header) |

- **Idioma por defecto:** inglés (`en`); español (`es`) como segunda opción.
- **Persistencia:** `localStorage['moviris.lang']`. También acepta `?lang=en` o `?lang=es`; el parámetro tiene prioridad y actualiza la preferencia.
- **Diccionario estático:** las cadenas en español del HTML/JS son las claves; `EN` contiene la traducción inglesa. No se usa ninguna API de traducción.
- **Traducción automática:** un `TreeWalker` recorre nodos de texto (excluye `script`, `style`, `noscript`, `code`, `pre`, `textarea`) y traduce `placeholder`, `title`, `aria-label` y `alt`. Los textos generados después por JS se traducen llamando a `MovirisI18n.apply(...)` o usando `t(...)`.
- **Anti-destello:** al arrancar añade `html.moviris-i18n-loading` para ocultar el cuerpo hasta aplicar el idioma; un temporizador de 2.5 s lo revela si una CDN retrasa `DOMContentLoaded`.
- **Cambio de idioma:** guarda la preferencia, escribe `?lang=` en la URL y recarga la página para que gráficos, números y fechas se recalculen.
- **Formatos:** `number`, `decimal`, `coordinate`, `percent`, `monthName`, `weekdayName` y `date` usan `Intl` con `en-US` / `es-EC`. Ejemplo: `560,264` en inglés y `560.264` en español.
- **API pública:** `window.MovirisI18n` expone `t`, `apply`, `setLang`, `number`, `decimal`, `coordinate`, `percent`, `monthName`, `weekdayName`, `date`, `locale`, `lang` y `dictionary`.
- **Alcance:** navegación, títulos, etiquetas, botones, tooltips, leyendas, ejes, textos de gráficos, errores de interfaz, Inicio, Calendario, Mapa, Dashboard y ETL. Los mensajes internos del ETL generados por el backend conservan su idioma original.

### [Explain] `explain.js`, `explain.css` y `backend/explain.py`

Botón **Explain / Explicar** en los cinco gráficos del Dashboard y en los tres bloques del Calendario (matriz año × mes, este mes frente a la mediana y períodos críticos).

| Archivo | Rol |
|---|---|
| `explain.js` | Ventana modal compartida: apertura, `Loading…`, error, cierre con X/Esc y una única petición |
| `explain.css` | Estilo del botón, overlay y diálogo; `position: relative` en las tarjetas |
| `backend/explain.py` | Blueprint `explain`: validación, límite de peticiones, prompt y llamada a Groq |

- **Una llamada por clic:** no hay chat ni historial. Cada clic envía `POST /api/explain` y muestra la respuesta; cerrar la ventana aborta la petición en curso.
- **Contenido enviado:** `chart` (lista blanca), `title`, `filters` (área, confianza, métrica, período y selección), `lang` y un resumen compacto (`top_years`, `top_months`, medianas, índices o semanas; nunca la matriz completa).
- **Respuesta:** texto plano de unas 100 palabras en el idioma activo; explica qué muestra el gráfico, qué dicen los datos y qué significan. El prompt prohíbe inventar cifras y usar Markdown.
- **Backend:** usa `urllib.request` de la stdlib (sin dependencia nueva), `temperature: 0.2`, `max_tokens: 400`, timeout de 25 s y un máximo de 20 peticiones/minuto por IP.
- **User-Agent propio:** envía `MOVIRIS/1.0 (+https://moviris.onrender.com)`. Sin esa cabecera, Cloudflare puede bloquear `urllib` con `403` aunque el token sea válido.
- **Configuración:** `GROQ_LLM_TOKEN` y `GROQ_MODEL` viven solo en `.env`/entorno del servidor. Sin ambos, el endpoint responde `503` con un mensaje localizado; la clave nunca se envía al navegador.
- **Calendario:** la columna de la matriz usa `align-self: start` para que el botón Explain quede junto a la matriz y no al fondo de la fila estirada por la lista de períodos.
- **Errores:** `400` solicitud inválida, `413` resumen demasiado grande, `429` demasiadas peticiones, `502` fallo de Groq y `503` sin configurar. Los mensajes se devuelven en `en` o `es` según `lang`.
- **Privacidad:** no se registra el token ni el cuerpo de la petición en los logs.

### [Backend] `backend/app.py`

#### Constantes

| Constante | Valor | Descripción |
|---|---|---|
| `ETL_DIR` | `ROOT / "etl"` | Archivos de la pestaña ETL |
| `INICIO_DIR` | `ROOT / "inicio"` | Componente Inicio |
| `HEADER_DIR` | `ROOT / "header"` | Componente de header compartido |
| `HACKATHON_DIR` | `ROOT / "hackathon"` | Carpeta opcional de CSV para el CLI y `/api/files` |
| `UPLOADS_DIR` | `ROOT / "uploads"` | Almacenamiento temporal de subidas |
| `MAX_UPLOAD_BYTES` | `512 MB` | Límite por petición de subida |
| `MAX_UPLOAD_FILES` | `80` | Máximo de archivos por petición |
| `ALLOWED_EXTENSIONS` | `.csv`, `.zip` | Extensiones aceptadas |
| `REQUIRED_CSV_COLUMNS` | `latitude`, `longitude`, `acq_date` | Columnas mínimas del CSV |
| `UPLOAD_ID_RE` | `^[0-9a-f]{8,32}$` | Validación del id de subida |

#### Funciones principales

| Función | Propósito |
|---|---|
| `csv_header_ok(path)` | Comprueba la cabecera mínima del CSV |
| `_resolve_server_file(value)` | Resuelve y valida rutas dentro de `hackathon/` |
| `_resolve_upload(value)` | Resuelve un lote de `uploads/<id>/` y devuelve sus CSV |
| `_resolve_run_files(payload)` | Combina `server_files` y `upload_ids`, deduplica y valida |
| `_cleanup_uploads(keep=50, current=...)` | Conserva los 50 lotes más recientes |
| `staging_info()` | Conteos y metadatos del SQLite local |
| `_batch_entry(folder)` | Metadatos de un lote subido |
| `list_upload_batches(limit=10)` | Lotes recientes para `GET /api/files` |

#### Rutas

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/` | Bienvenida (`index.html` raíz) |
| `GET` | `/styles.css` | Estilos de la bienvenida |
| `GET` | `/script.js` | Animaciones de la bienvenida |
| `GET` | `/i18n.js` | Diccionario EN/ES y helpers de formato |
| `GET` | `/explain.js` | Ventana Explain compartida |
| `GET` | `/explain.css` | Estilos del botón y la ventana Explain |
| `GET` | `/header/index.html` | Fragmento del header compartido |
| `GET` | `/header/style.css` | Estilos del header compartido |
| `GET` | `/header/script.js` | Inyección y navegación activa del header |
| `GET` | `/etl`, `/etl/`, `/etl/index.html` | Pestaña ETL |
| `GET` | `/style.css`, `/etl/style.css` | Hoja de estilos del ETL |
| `GET` | `/etl/script.js` | Lógica de la pestaña ETL |
| `GET` | `/inicio`, `/inicio/`, `/inicio/index.html` | Componente Inicio |
| `GET` | `/inicio/style.css` | Estilos del componente Inicio |
| `GET` | `/inicio/script.js` | Revelado al hacer scroll del componente Inicio |
| `GET` | `/mapa`, `/mapa/`, `/mapa/index.html` | Página del mapa (blueprint `mapa`) |
| `GET` | `/mapa/style.css`, `/mapa/script.js` | Assets del mapa; `mapa.py` no se expone |
| `GET` | `/api/mapa/meta` | Rango de fechas del staging (blueprint `mapa`) |
| `GET` | `/api/mapa/cells` | Celdas agregadas del área (blueprint `mapa`) |
| `GET` | `/api/mapa/csv` | CSV en streaming (blueprint `mapa`) |
| `GET` | `/calendario`, `/calendario/`, `/calendario/index.html` | Página del calendario (blueprint `calendario`) |
| `GET` | `/calendario/style.css`, `/calendario/script.js` | Assets del calendario; `calendario.py` no se expone |
| `GET` | `/api/calendario/matrix` | Matriz anual/mensual y períodos críticos (blueprint `calendario`) |
| `GET` | `/api/calendario/month` | Detalle diario de un mes (blueprint `calendario`) |
| `GET` | `/dashboard`, `/dashboard/`, `/dashboard/index.html` | Página del Dashboard (blueprint `dashboard`) |
| `GET` | `/dashboard/style.css`, `/dashboard/script.js` | Assets del Dashboard; `dashboard.py` no se expone |
| `GET` | `/api/dashboard/summary` | Totales, matriz año × mes y cobertura de sensores (blueprint `dashboard`) |
| `POST` | `/api/explain` | Explicación breve de un gráfico con Groq (blueprint `explain`) |
| `GET` | `/ico.svg` | Logo de la raíz (sin copia en `etl/`) |
| `GET` | `/api/health` | Modo, estado de Turso/staging y tablas |
| `GET` | `/api/files` | CSV del proyecto (si existe `hackathon/`) y lotes subidos |
| `POST` | `/api/upload` | Subida multipart de CSV/ZIP |
| `DELETE` | `/api/uploads/<upload_id>` | Borra un lote y sus archivos |
| `POST` | `/api/etl/run` | Lanza el ETL |
| `POST` | `/api/etl/sync` | Sincroniza el staging; bloqueado en modo local |
| `GET` | `/api/etl/status` | Estado del último trabajo o de `?job_id=...` |
| `GET` | `/api/etl/runs` | Historial corto de trabajos |
| `GET` | `/api/staging` | Información del staging local |
| `GET` | `/api/stats` | Estadísticas (local o Turso) |
| `GET` | `/api/map` | Puntos críticos/inusuales (local o Turso) |
| `GET` | `/api/cells` | Celdas con filtros (local o Turso) |
| `GET` | `/api/mask` | Fuentes no vegetales (local o Turso) |

> `/api/map`, `/api/cells` y `/api/mask` son los endpoints heredados de `backend/db.py`. `/api/mapa/*` pertenece al blueprint del componente Mapa, `/api/calendario/*` al Calendario, `/api/dashboard/*` al Dashboard y `/api/explain` al blueprint `explain`; los de lectura respetan `TURSO_ENABLED` y no son el mismo endpoint.

#### Detalle de `POST /api/upload`

- Acepta el campo multipart `files` (o `file`).
- Guarda cada archivo con `secure_filename` y nombres únicos.
- Un ZIP se abre de forma segura: se ignoran directorios y `__MACOSX`, se usan solo los `.csv`, se sanea cada nombre y se evita path traversal.
- Límite: 512 MB por petición; 80 archivos por petición; 60 CSV por ZIP (se truncan y se informan).
- Si ningún archivo es válido, elimina la carpeta temporal y responde `400` con `rejected`.
- Si hay al menos un CSV válido, responde `201` con `{upload_id, batch, rejected}`.

#### Detalle de `POST /api/etl/run`

```json
{
  "upload_ids": ["a1b2c3d4e5f6"],
  "include_nrt": true,
  "exclude_current_year": true,
  "replace": true,
  "push": true
}
```

- En modo local, el backend cambia `push` a `false` aunque el cliente envíe `true`.
- `replace` solo afecta a Turso; el staging local siempre se reemplaza.
- Responde `202` con `{ "job": { ... } }`; si ya hay un trabajo, `409`; si las rutas no existen, `400`.

### [Datos] `backend/db.py`

- `_data_source()` es el punto único de conmutación:
  - `TURSO_ENABLED=false` → `sqlite3` contra `data/moviris_staging.db`.
  - `TURSO_ENABLED=true` → cliente `libsql_client` contra Turso.
- `health()` comprueba las tablas requeridas y devuelve `mode: "local"` o `"turso"`.
- `stats()` cachea el resultado durante **12 s** y separa la caché por modo.
- `map_points()`, `list_cells()`, `list_mask_sources()` y `top_cells_by_status()` usan el mismo conmutador.
- `top_cells_by_status()` existe como helper interno, pero no está expuesto por ninguna ruta.

### [Trabajos] `backend/jobs.py`

| Elemento | Detalle |
|---|---|
| `JobManager` | Un trabajo activo, historial de 20, logs de 500 líneas |
| `start_etl(files, options)` | Crea el job; fuerza `push=false` si Turso está desactivado |
| `_run_etl()` | Llama a `run_etl()` con el callback de progreso y el log |
| `start_sync(replace)` | Rechaza si Turso está desactivado o no hay staging |
| `_run_sync()` | Llama a `push_staging()`; vuelve a comprobar el flag |
| `snapshot()` | Copia serializable del job, con `elapsed_seconds` en vivo |
| `staging_ready()` | Comprueba que el staging local tenga celdas-día |

Estados de un job: `running`, `done`, `error`. Campos principales: `id`, `kind`, `status`, `stage`, `percent`, `message`, `files`, `options`, `logs`, `metrics`, `summary`, `error`, `can_sync`.

### [Configuración] `backend/settings.py`

```python
def turso_enabled(env=None) -> bool:
    values = env if env is not None else load_env()
    raw = str(values.get("TURSO_ENABLED", "true")).strip().lower()
    return raw not in {"0", "false", "no", "off", "disabled", "local"}

def mode(env=None) -> str:
    return "turso" if turso_enabled(env) else "local"
```

No hay archivo de estado aparte. El único interruptor es `TURSO_ENABLED` en `.env` (o en el entorno del proceso).

### [ETL] `etl/etl.py`

#### Constantes principales

| Constante | Valor | Descripción |
|---|---|---|
| `DEFAULT_SOURCE` | `hackathon/` | Fuente por defecto del CLI (opcional) |
| `DEFAULT_STAGING` | `data/moviris_staging.db` | SQLite local |
| `DEFAULT_BATCH_SIZE` | `4000` | Filas por lote al subir a Turso |
| `GRID` | `0.01` | Resolución de la malla |
| `MASK_MIN_HITS` | `40` | Detecciones mínimas para una fuente persistente |
| `MASK_MIN_YEARS` | `4` | Años distintos mínimos |
| `MASK_MIN_WEEKS` | `15` | Semanas distintas mínimas |
| `MASK_VOLCANO_RADIUS` | `0.05°` | Radio de asociación a un volcán |
| `MASK_VOLCANO_MIN_HITS` | `5` | Detecciones mínimas para marcar un volcán |

#### Funciones

| Función | Propósito |
|---|---|
| `load_env()` | Carga `.env` sin dependencias externas y sin pisar el entorno |
| `turso_enabled(env)` | Lee `TURSO_ENABLED` |
| `turso_config(env)` | Devuelve URL HTTP y token; valida que existan |
| `discover_files(sources)` | Expande archivos/carpetas y deduplica |
| `scan_sources(...)` | Primera pasada: valida, cuenta, calcula FRP mediano |
| `aggregate_rows(...)` | Segunda pasada: celdas-día y normalización |
| `build_baseline(...)` | Línea base por celda y semana ISO |
| `score_daily(...)` | z-score y estado |
| `build_mask(...)` | Fuentes persistentes no vegetales |
| `write_staging(...)` | Escribe el SQLite local de forma atómica |
| `push_staging(...)` | Publica en Turso; **se niega si `TURSO_ENABLED=false`** |
| `run_etl(...)` | Orquesta todo y devuelve el resumen |
| `main(...)` | CLI |

#### CLI

| Flag | Efecto |
|---|---|
| `--source PATH` | Archivo o carpeta de CSV (repetible); si se omite usa `hackathon/` |
| `--no-nrt` | Excluye archivos NRT |
| `--include-current-year` | No excluye el año más reciente de la línea base |
| `--no-push` | Fuerza solo staging local |
| `--no-replace` | No vacía las tablas de Turso antes de insertar |
| `--push-only` | Sincroniza el staging existente; falla si Turso está desactivado |
| `--staging PATH` | Ruta alternativa del SQLite local |
| `--batch-size N` | Filas por lote de subida |
| `--quiet` | Silencia el progreso detallado |

---

## 5. API

### A. `GET /api/health`

Ejemplo en modo local:

```json
{
  "ok": true,
  "service": "moviris-etl",
  "mode": "local",
  "turso_enabled": false,
  "database": {
    "ok": true,
    "mode": "local",
    "storage": "staging",
    "path": "D:\\PROYECTOS\\MOVIRIS\\data\\moviris_staging.db",
    "tables": ["fire_baseline", "fire_cells_daily", "non_vegetation_mask"],
    "missing": [],
    "latency_ms": 1.2
  },
  "staging": { "exists": true, "ready": true, "rows": { "...": 0 } }
}
```

### B. `POST /api/upload`

```bash
curl -X POST http://127.0.0.1:5000/api/upload \
  -F "files=@fire_archive_M-C61_848345.csv"
```

Respuesta `201`:

```json
{
  "upload_id": "a1b2c3d4e5f6",
  "batch": {
    "id": "a1b2c3d4e5f6",
    "file_count": 1,
    "size": 4642299,
    "size_label": "4.4 MB",
    "files": [
      {
        "name": "fire_archive_M-C61_848345.csv",
        "kind": "archive",
        "size_label": "4.4 MB"
      }
    ]
  },
  "rejected": []
}
```

> [!IMPORTANT]
> El backend acepta hasta **512 MB** por petición, pero Render rechaza cuerpos mayores con un `413` antes de llegar a Flask. Los archivos de Brasil de 344–897 MB no se pueden subir desde `/etl/`: hay que usar el CLI (`python etl/etl.py --source ... --push`) o dividir el CSV en partes más pequeñas.

### C. `POST /api/etl/run`

```json
{
  "upload_ids": ["a1b2c3d4e5f6"],
  "include_nrt": true,
  "exclude_current_year": true,
  "replace": true,
  "push": true
}
```

Respuesta `202`:

```json
{
  "job": {
    "id": "68a0ab2e73",
    "kind": "etl",
    "status": "running",
    "stage": "Iniciando",
    "percent": 0,
    "message": "Preparando el proceso...",
    "file_count": 1,
    "options": {
      "include_nrt": true,
      "exclude_current_year": true,
      "replace": true,
      "push": false
    },
    "logs": [],
    "metrics": {},
    "summary": null,
    "error": null,
    "can_sync": false
  }
}
```

> [!NOTE]
> En modo local, `options.push` aparece en `false` aunque el cliente haya enviado `true`. Es una defensa del backend, no un error.

### D. `GET /api/etl/status`

```json
{
  "job": {
    "id": "68a0ab2e73",
    "status": "done",
    "stage": "Completado",
    "percent": 100,
    "elapsed_seconds": 74.0,
    "summary": {
      "files": 8,
      "detections": 560264,
      "daily_rows": 339729,
      "cells": 65583,
      "baseline_rows": 218660,
      "mask_rows": 459,
      "pushed": false,
      "pushed_rows": 0,
      "mode": "local",
      "turso_enabled": false
    }
  }
}
```

### E. `DELETE /api/uploads/<upload_id>`

- `200`: `{ "deleted": true, "upload_id": "..." }`
- `400`: id inválido.
- `404`: lote inexistente.
- `409`: hay un ETL en ejecución.

### F. `POST /api/etl/sync`

- En modo local: `409` con `error` explicando que `TURSO_ENABLED=false`.
- En modo Turso: `202` y un trabajo de tipo `sync`.
- Si no hay staging: `400`.

### G. Endpoints de consulta

| Ruta | Local | Turso | Uso |
|---|---|---|---|
| `/api/stats` | `data/moviris_staging.db` | Turso | Estadísticas del panel principal |
| `/api/map` | staging | Turso | Puntos críticos/inusuales de 90 días |
| `/api/cells` | staging | Turso | Celdas con filtros |
| `/api/mask` | staging | Turso | Fuentes no vegetales |

Estos endpoints **no los usa la pestaña ETL**; pertenecen a la aplicación principal. En modo local no tocan Turso.

### H. API del mapa (blueprint `mapa`)

El componente `/mapa/` registra su propio blueprint; sus rutas **no** son las mismas que `/api/map` de `backend/db.py`.

**Parámetros de `/api/mapa/cells` y `/api/mapa/csv`:**

| Parámetro | Tipo | Obligatorio | Detalle |
|---|---|---|---|
| `south` | REAL | Sí | Límite sur; `south < north` |
| `north` | REAL | Sí | Límite norte |
| `west` | REAL | Sí | Límite oeste; `west < east` |
| `east` | REAL | Sí | Límite este |
| `start` | DATE | Sí | `YYYY-MM-DD`; `start <= end` |
| `end` | DATE | Sí | `YYYY-MM-DD` |
| `conf` | INT | No | `0` todas, `1` nominal+alta, `2` solo alta; default `0` |
| `limit` | INT | No | Solo en `/cells`; default `20000`, máximo `30000` |

**`GET /api/mapa/meta`:**

```json
{ "min_date": "2012-01-11", "max_date": "2026-11-14" }
```

**`GET /api/mapa/cells`:** devuelve `columns`, `cells`, `summary`, `shown` y `truncated`. Las columnas son:

```text
lat, lon, days, detections, frp_max, critical_days, unusual_days, last_date, conf_max
```

**`GET /api/mapa/csv`:** descarga en streaming las columnas:

```text
acq_date, cell_lat, cell_lon, detections, frp_max, frp_sum_norm,
confidence_max, sensors, status, z_score, is_nrt
```

- Lee `data/moviris_staging.db` en modo solo lectura.
- `TURSO_ENABLED=true` lee de Turso; si la conexión falla → `503`.
- Sin datos en el modo activo → `503`.
- Parámetros inválidos → `400` con `{ "error": "..." }`.
- El CSV de un área amplia puede ser grande (el ejemplo de Ecuador completo superó los 19 MB); se transmite por bloques de 5.000 filas.

### I. API del calendario (blueprint `calendario`)

El calendario comparte los parámetros de área y confianza del mapa, pero usa todo el período disponible y no recibe fechas.

**Parámetros de `/api/calendario/matrix`:**

| Parámetro | Tipo | Obligatorio | Detalle |
|---|---|---|---|
| `south` | REAL | Sí | Límite sur; `south < north` |
| `north` | REAL | Sí | Límite norte |
| `west` | REAL | Sí | Límite oeste; `west < east` |
| `east` | REAL | Sí | Límite este |
| `conf` | INT | No | `0` todas, `1` nominal+alta, `2` solo alta; default `0` |

**Parámetros de `/api/calendario/month`:** los mismos de área y `conf`, más:

| Parámetro | Tipo | Obligatorio | Detalle |
|---|---|---|---|
| `year` | INT | Sí | Año del mes a detallar |
| `month` | INT | Sí | Mes `1`–`12` |

**`GET /api/calendario/matrix`:** devuelve `current`, `min_date`, `max_date`, `metrics`, `months` y `weeks`.

- `current`: año, mes, día, valores del período actual (`values`), mediana (`median`) y lista de `years`.
- `months`: actividad agregada por año y mes (179 meses en el staging actual).
- `weeks`: las 10 semanas con más celdas críticas, con detalle de celdas críticas e inusuales.
- `metrics`: definiciones de las métricas mostradas en la interfaz.

**`GET /api/calendario/month`:** devuelve `year`, `month` y `days`; cada día incluye su estado y sus valores. Octubre de 2026 devolvió 30 días.

- Reutiliza `_connect()`, `ApiError` y `_number()` de `mapa/mapa.py`.
- `TURSO_ENABLED=true` lee de Turso; si la conexión falla → `503`.
- Sin datos en el modo activo → `503`.
- Sin área o sin `year`/`month` → `400` con `{ "error": "..." }`.

### J. API de Explain (blueprint `explain`)

**`POST /api/explain`:** recibe un resumen ya calculado por el navegador y devuelve una explicación breve generada por Groq.

**Cuerpo JSON:**

| Campo | Tipo | Obligatorio | Detalle |
|---|---|---|---|
| `chart` | STRING | Sí | Uno de `years`, `anomaly`, `season`, `index`, `coverage`, `calendar_matrix`, `calendar_compare`, `calendar_weeks` |
| `title` | STRING | No | Título visible del gráfico; se recorta a 120 caracteres |
| `filters` | OBJECT | Sí | Área, confianza, métrica, período y selección actual |
| `data` | OBJECT/ARRAY | Sí | Resumen compacto; el JSON completo no puede superar 14.000 caracteres |
| `lang` | STRING | No | `en` (default) o `es`; define el idioma del prompt y de los errores |

**Respuesta correcta (`200`):**

```json
{ "text": "Explicación breve...", "lang": "en" }
```

- Usa `GROQ_LLM_TOKEN` y `GROQ_MODEL`; si falta cualquiera, responde `503` con `code: "not_configured"`.
- El modelo no se fija en el código: `.env.example` sugiere `openai/gpt-oss-20b`, el modelo de producción más rápido y barato de la lista oficial de Groq.
- Una sola llamada a `https://api.groq.com/openai/v1/chat/completions`, sin historial, con `max_tokens: 400` y timeout de 25 s.
- Límite de 20 peticiones por minuto e IP (`429` con `code: "rate_limited"`).
- Errores localizados: `400` inválido, `413` resumen demasiado grande, `502` fallo de Groq, `503` sin configurar.
- No registra el token ni el cuerpo enviado; solo el tipo de error.

### K. Errores HTTP

| Código | Condición |
|---|---|
| `400` | Faltan archivos, columnas, rutas inválidas o el staging no existe |
| `404` | Ruta, job o subida inexistente |
| `409` | Ya hay un ETL en ejecución o se intenta sincronizar en modo local |
| `413` | La subida supera 512 MB o el resumen de Explain supera 14.000 caracteres |
| `429` | Se superaron 20 peticiones de Explain por minuto e IP |
| `500` | Error interno no controlado |
| `502` | Groq no respondió o devolvió una respuesta vacía |
| `503` | No se pudieron consultar los datos (staging ausente o Turso caído) o falta configurar Groq |

### L. Caché de consultas

- `backend/cache.py` implementa `TTLCache` (LRU con vencimiento).
- Usan caché: `/api/mapa/meta`, `/api/mapa/cells`, `/api/dashboard/summary`, `/api/calendario/matrix` y `/api/calendario/month`.
- TTL por defecto: **300 s**. El tamaño máximo varía por endpoint (el mapa conserva 12 respuestas; el calendario, 32/64).
- La clave incluye el modo (`local` o `turso`) y los parámetros normalizados, para no mezclar áreas ni respuestas.
- Las respuestas incluyen `X-Cache: HIT|MISS` y `Cache-Control: private, max-age=60`.
- `JobManager._finish()` llama a `clear_all_caches()` al terminar un ETL o sync (`done`/`error`), de modo que los datos nuevos se vean sin esperar el TTL.
- La caché es por proceso: con varios workers de Gunicorn cada uno tendría la suya. El despliegue recomendado usa **un solo worker**.
- Si Turso se actualiza desde fuera de la app, el cambio se refleja al vencer el TTL (5 min) o al reiniciar/redeployar.

---

## 6. Esquema de Datos

### 6.1 Tablas

#### `fire_cells_daily` — eventos armonizados por celda y día

| Campo | Tipo | Restricción | Descripción |
|---|---|---|---|
| `cell_lat` | `REAL` | NOT NULL, PK | Centro de la celda (malla 0,01°) |
| `cell_lon` | `REAL` | NOT NULL, PK | Centro de la celda |
| `acq_date` | `TEXT` | NOT NULL, PK | Fecha UTC `YYYY-MM-DD` |
| `year` | `INTEGER` | NOT NULL | Año calendario |
| `month` | `INTEGER` | NOT NULL | Mes |
| `week_of_year` | `INTEGER` | NOT NULL | Semana ISO |
| `detections` | `INTEGER` | NOT NULL | Detecciones agrupadas |
| `frp_max` | `REAL` | NULL | FRP máximo (MW) |
| `frp_sum_norm` | `REAL` | NULL | FRP normalizado por sensor |
| `confidence_max` | `INTEGER` | NOT NULL, CHECK 0/1/2 | Confianza máxima |
| `sensors` | `TEXT` | NOT NULL | Ej. `MODIS,SNPP,N20` |
| `is_nrt` | `INTEGER` | NOT NULL, CHECK 0/1 | 1 si todas las detecciones son NRT |
| `status` | `TEXT` | CHECK `normal`, `critical`, `unusual` | Estado |
| `z_score` | `REAL` | NULL | z-score de detecciones |

Clave primaria: `(cell_lat, cell_lon, acq_date)`. Índices: fecha, bbox, año/semana y estado/fecha.

#### `fire_baseline` — línea base por celda y semana

| Campo | Tipo | Restricción | Descripción |
|---|---|---|---|
| `cell_lat` | `REAL` | NOT NULL, PK | Celda |
| `cell_lon` | `REAL` | NOT NULL, PK | Celda |
| `week_of_year` | `INTEGER` | NOT NULL, PK, CHECK 1–53 | Semana ISO |
| `years_count` | `INTEGER` | NOT NULL | Años con detecciones |
| `mean_detections` | `REAL` | NOT NULL | Media diaria |
| `std_detections` | `REAL` | NOT NULL | Desviación diaria |
| `mean_frp` | `REAL` | NULL | FRP medio |
| `p75_detections` | `REAL` | NULL | Percentil 75 |

#### `non_vegetation_mask` — fuentes persistentes no vegetales

| Campo | Tipo | Restricción | Descripción |
|---|---|---|---|
| `cell_lat` | `REAL` | NOT NULL, PK | Celda |
| `cell_lon` | `REAL` | NOT NULL, PK | Celda |
| `source_type` | `INTEGER` | NOT NULL, PK, CHECK 1/2/3 | 1 volcán, 2 fija, 3 mar |
| `hits` | `INTEGER` | NOT NULL | Detecciones históricas |

### 6.2 DDL de referencia

```sql
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS fire_cells_daily (
    cell_lat        REAL    NOT NULL,
    cell_lon        REAL    NOT NULL,
    acq_date        TEXT    NOT NULL,
    year            INTEGER NOT NULL,
    month           INTEGER NOT NULL,
    week_of_year    INTEGER NOT NULL,
    detections      INTEGER NOT NULL,
    frp_max         REAL,
    frp_sum_norm    REAL,
    confidence_max  INTEGER NOT NULL CHECK (confidence_max IN (0,1,2)),
    sensors         TEXT    NOT NULL,
    is_nrt          INTEGER NOT NULL DEFAULT 0 CHECK (is_nrt IN (0,1)),
    status          TEXT    CHECK (status IN ('normal','critical','unusual')),
    z_score         REAL,
    PRIMARY KEY (cell_lat, cell_lon, acq_date)
) WITHOUT ROWID;

CREATE INDEX IF NOT EXISTS idx_daily_date   ON fire_cells_daily (acq_date);
CREATE INDEX IF NOT EXISTS idx_daily_bbox   ON fire_cells_daily (cell_lat, cell_lon, acq_date);
CREATE INDEX IF NOT EXISTS idx_daily_week   ON fire_cells_daily (year, week_of_year);
CREATE INDEX IF NOT EXISTS idx_daily_status ON fire_cells_daily (status, acq_date);

CREATE TABLE IF NOT EXISTS fire_baseline (
    cell_lat        REAL    NOT NULL,
    cell_lon        REAL    NOT NULL,
    week_of_year    INTEGER NOT NULL CHECK (week_of_year BETWEEN 1 AND 53),
    years_count     INTEGER NOT NULL,
    mean_detections REAL    NOT NULL,
    std_detections  REAL    NOT NULL,
    mean_frp        REAL,
    p75_detections  REAL,
    PRIMARY KEY (cell_lat, cell_lon, week_of_year)
) WITHOUT ROWID;

CREATE INDEX IF NOT EXISTS idx_baseline_bbox ON fire_baseline (cell_lat, cell_lon);

CREATE TABLE IF NOT EXISTS non_vegetation_mask (
    cell_lat    REAL    NOT NULL,
    cell_lon    REAL    NOT NULL,
    source_type INTEGER NOT NULL CHECK (source_type IN (1,2,3)),
    hits        INTEGER NOT NULL,
    PRIMARY KEY (cell_lat, cell_lon, source_type)
) WITHOUT ROWID;
```

### 6.3 Dónde viven los datos

| Ubicación | Contenido | Persistencia |
|---|---|---|
| `data/moviris_staging.db` | Datos limpios locales (3 tablas) | Local; ignorado por git |
| `backend/schema.sql` | Solo DDL, sin filas | Versionado |
| Turso | Copia publicada de las 3 tablas | Remota; intacta en modo local |
| `uploads/` | CSV/ZIP temporales subidos | Temporal; ignorado |
| CSV crudos | Entrada del ETL | Opcionales; no son runtime |

> [!WARNING]
> `backend/schema.sql` **no contiene datos**. Si se elimina `data/moviris_staging.db`, la única copia de los datos limpios será Turso. Para respaldar el staging se puede copiar el `.db` o generar un dump SQL con `sqlite3 data/moviris_staging.db .dump > respaldo.sql`.

### 6.4 Dataset actual

Última ejecución completa en modo local:

| Métrica | Valor |
|---|---|
| Detecciones leídas | 560.264 |
| Celdas-día | 339.729 |
| Filas de línea base | 218.660 |
| Filas de máscara | 459 |
| Filas totales del staging | 558.848 |
| Celdas activas | 65.583 |
| Rango | 2012-01-11 → 2026-11-14 |
| Estados | 30.091 críticos / 13.108 inusuales / 296.530 normales |
| Máscara | 208 volcanes / 251 fuentes fijas / 0 mar |
| Tamaño del staging | ~96 MB |

---

## 7. Frontend ETL (`etl/`)

> La bienvenida se documenta en la sección 4. Esta sección cubre únicamente la pestaña ETL.
>
> La pestaña **monta el header compartido** (`<div id="site-header"></div>` + `/header/style.css` + `/header/script.js`) y conserva su barra de estado “Modo local”. No duplica el HTML del header.
>
> La interfaz y los estados se traducen EN/ES con `i18n.js`; los mensajes internos que genera el backend del ETL conservan su idioma original y solo se traducen las etiquetas y los errores de interfaz.

### A. Composición

La pestaña utiliza una sola columna centrada de **720 px máximo** y dos tarjetas:

1. **Archivos de entrada**: zona de arrastre/selección, contador, lista de archivos y botón **Quitar**.
2. **Proceso ETL**: botón **Ejecutar ETL**, progreso, cinco pasos, errores y resumen.

No incluye portada, estadísticas, mapa, tabla de celdas ni parámetros. Esos elementos pertenecen a la aplicación principal.

### B. Tema visual

| Token | Color | Uso |
|---|---|---|
| Fondo | `#EBEBD8` | Página |
| Tarjetas | `#F7F7EC` | Superficies |
| Primario | `#637545` | Botón, barra, enlaces |
| Texto principal | `#455230` | Títulos y textos |
| Secundario | `#6B7557` | Ayudas y metadatos |
| Bordes | `#9BA685` | Separadores y contornos |
| Error | `#A94438` | Errores |

Sin degradados, sin sombras, sin neones y sin emojis. Tipografía `Inter` con fallback al sistema.

### C. Estado en memoria (`script.js`)

| Variable | Tipo | Descripción |
|---|---|---|
| `files` | ARRAY | Archivos subidos: nombre, tamaño, tipo, estado, `uploadId`, CSV internos y error |
| `uploading` | BOOLEAN | Bloquea el botón mientras hay subidas |
| `deleting` | BOOLEAN | Bloquea mientras se borra un lote |
| `running` | BOOLEAN | ETL en ejecución |
| `jobId` | STRING | Trabajo consultado por polling |
| `pollTimer` | TIMER | Intervalo de 1 s |
| `pollFailures` | INTEGER | Corta tras 5 fallos consecutivos |
| `mode` | STRING | `local` o `turso` según `/api/health` |

### D. Comportamiento

1. **Subida:** se sube un archivo por petición para poder eliminarlo individualmente. Se ignoran duplicados con el mismo nombre y tamaño.
2. **Lista:** muestra tipo (`CSV`/`ZIP`), tamaño, `NRT`/`Archivo`, estado (`Listo`, `Subiendo…`, `Error`) y **Quitar**.
3. **ZIP:** se muestra como un lote; debajo se listan hasta tres CSV internos y `+N más`. Quitar elimina el lote completo.
4. **Borrado:** llama a `DELETE /api/uploads/<id>`. Si no hay `uploadId` (subida fallida), se quita solo de la lista.
5. **Ejecución:** envía `upload_ids` y los valores por defecto. En modo local el backend fuerza `push=false`.
6. **Progreso:** polling cada 1 s; la etapa actual se deduce del `stage` del backend y del porcentaje.
7. **Pasos:** `Extract → Transform → Baseline → Estado → Load`. En modo local, `Load (omitido)`.
8. **Resumen:** `detections`, `daily_rows`, `baseline_rows` y `mask_rows`; tiempo total del job.
9. **Errores:** caja roja con `job.error`; en inglés se muestra un mensaje genérico traducido y el detalle original queda en la consola. Pistas para Turso, columnas faltantes o staging ausente. Un `413` muestra un aviso específico: el archivo supera el límite del servidor y debe subirse por CLI o dividirse.
10. **Recarga:** la lista empieza vacía; si hay un trabajo en ejecución, se recupera y continúa el polling. Un trabajo terminado no se restaura.

### E. Accesibilidad y responsive

- `aria-live` en mensajes, `role="progressbar"` con `aria-valuenow`, foco visible y `aria-label` en el botón de quitar.
- Dropzone accesible por teclado (`Enter`/`Espacio`).
- En móvil: una columna, botón a ancho completo, pasos con salto de línea y resumen en una columna.
- El logo se sirve desde `/ico.svg`; el SVG usa `fill="#637545"` y no hay copia en `etl/`.

---

## 8. Reglas de Negocio y Heurísticas del ETL

1. **Malla de 0,01°:** cada detección se asigna a `floor(valor / 0,01)` y se guarda el centro de la celda con 3 decimales.
2. **Sensores:** Terra y Aqua se unifican como `MODIS`; SNPP, N20 y N21 se conservan. La columna `sensors` se ordena como `MODIS,SNPP,N20,N21`.
3. **Confianza:** MODIS 0–100 → `0` (<30), `1` (30–79) y `2` (≥80); VIIRS `l/n/h` → `0/1/2`. Valores NRT como `2.0NRT` se normalizan.
4. **FRP normalizado:** cada FRP se divide por la mediana histórica de su sensor y se suma por celda-día. Esto hace comparables MODIS y VIIRS.
5. **NRT:** una celda-día es NRT solo si **todas** sus detecciones vienen de archivos NRT. Si hay mezcla, gana el archivo definitivo (`is_nrt = 0`).
6. **Línea base:** por celda y semana ISO se usan las detecciones **diarias** históricas; `years_count` cuenta años distintos con al menos una detección. Se excluye el año más reciente del dataset si hay más de un año.
7. **Estado:** `critical` si supera el p75 y el z-score es ≥ 1, o si el z-score es ≥ 2 y supera la media; `unusual` si supera la media; `normal` en el resto. Sin línea base, `unusual` a partir de 3 detecciones.
8. **Máscara:** fuentes con ≥ 40 detecciones, ≥ 4 años y ≥ 15 semanas distintas. Se clasifican como volcán si están a ≤ 0,05° de un volcán conocido, como mar si caen sobre agua y como fuente fija en el resto.
9. **Máscara de tierra:** Natural Earth 1:10 m rasterizado a 0,01° y embebido como blob comprimido. Fuera de cobertura se asume tierra para no marcar por error una fuente como mar.
10. **Volcanes:** lista integrada de Ecuador, sur de Colombia y Galápagos. Es específica del recorte actual.
11. **Reemplazo:** el staging local siempre se reemplaza de forma atómica. En Turso, `replace=true` hace `DELETE` de las tres tablas antes de insertar.
12. **Local vs. remoto:** con `TURSO_ENABLED=false` no se ejecuta `push_staging()`; con `true`, el push es explícito (ETL con `push=true` o sync).

> [!WARNING]
> La máscara de tierra y la lista de volcanes están pensadas para el recorte Ecuador / Galápagos / sur de Colombia. Para Brasil u otra región, la máscara de mar no será fiable fuera de la cobertura y los volcanes no aplicarán. La malla y el proceso de agregación sí funcionan para cualquier CSV de FIRMS.

---

## 9. Instalación y Guía de Uso

### A. Requisitos

| Requisito | Versión / Nota |
|---|---|
| Python | 3.10 o superior |
| pip | Para instalar Flask y libsql-client |
| Turso | Opcional en modo local; necesario para publicar |
| Navegador | Chrome, Edge, Firefox o Safari actuales |
| Internet | Necesario para Leaflet/CDN y teselas OpenStreetMap del mapa |

### B. Instalación

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

### C. Configuración

Copia `.env.example` a `.env`:

```env
TURSO_DATABASE_URL=libsql://tu-base.turso.io
TURSO_AUTH_TOKEN=tu-token-de-turso
TURSO_ENABLED=false
GROQ_LLM_TOKEN=tu-token-de-groq
GROQ_MODEL=openai/gpt-oss-20b
```

- `TURSO_ENABLED=false` → modo local (recomendado para desarrollo).
- `TURSO_ENABLED=true` → lecturas y publicaciones en Turso.
- `GROQ_MODEL` debe ser un modelo de la lista oficial de Groq; `.env.example` usa `openai/gpt-oss-20b`. Sin token o sin modelo, Explain responde `503`.
- `.env` está ignorado por git.

### D. Arranque

```bash
python run.py
```

Abre la bienvenida:

```text
http://127.0.0.1:5000/
```

El ETL está en `http://127.0.0.1:5000/etl/`, el componente Inicio en
`http://127.0.0.1:5000/inicio/`, el mapa en `http://127.0.0.1:5000/mapa/`, el
calendario en `http://127.0.0.1:5000/calendario/` y el Dashboard en
`http://127.0.0.1:5000/dashboard/`.

Si el puerto está ocupado:

```bash
python run.py --port 8080 --open
```

`--open` abre la bienvenida. Si tienes una instancia anterior corriendo en el
puerto 5000, deténla antes de arrancar; el proceso viejo mantiene el código y el
modo anteriores en memoria.

### E. Uso de la bienvenida y la pestaña

1. Abre `/`: verás la animación de bienvenida y el botón **Explorar el fuego**.
2. El botón lleva a `/inicio/`, el componente Inicio con su hero y secciones.
3. En `/etl/`, arrastra los CSV o un ZIP, o pulsa **selecciónalos**.
4. Espera a que todos aparezcan como **Listo**.
5. Usa **Quitar** para descartar un archivo antes de procesar.
6. Pulsa **Ejecutar ETL**.
7. Observa los pasos y el resumen.
8. En modo local, el resultado queda en `data/moviris_staging.db` y verás **Load (omitido)**.

### F. Uso del mapa

1. Abre `/mapa/`; el header marca **Mapa**.
2. Define el área con **Dibujar área**, una **Zona rápida** o los campos norte/sur/oeste/este.
3. Elige fechas (o usa 90 días / 1 año / Todo) y la confianza mínima.
4. Pulsa **Aplicar** para consultar celdas y ver los KPIs en el panel.
5. Usa **Descargar CSV** para exportar las celdas-día del área y fechas.
6. El mapa lee el staging local o Turso según `TURSO_ENABLED`. Si no hay datos o Turso falla, `503`.
7. Leaflet y las teselas de OpenStreetMap se cargan desde CDN; el mapa necesita conexión a Internet. OpenStreetMap no requiere key, pero su política pide tráfico moderado y atribución visible. Si el fondo no carga, revisa la conexión; para producción con alto tráfico, usa una key gratuita de CARTO o teselas propias.

### G. Uso del calendario

1. Abre `/calendario/`; el header marca **Calendario**.
2. La página usa el área de interés guardada por el mapa (`localStorage['moviris.aoi.v2']`); si no existe, usa la vista mundial por defecto.
3. Cambia **Medir** y **Confianza mínima** para recalcular la matriz y el detalle.
4. Revisa los KPIs: año activo, mes del año activo, mes más intenso y la comparación del período actual con la mediana.
5. Pulsa una celda de la matriz para abrir el detalle diario de ese mes.
6. Usa **Descargar CSV** para exportar el área y el rango visible con el endpoint del mapa (`/api/mapa/csv`).
7. El enlace **Cambiar en el mapa** abre `/mapa/` conservando el área de interés.
8. El calendario lee el staging local o Turso según `TURSO_ENABLED`. Si no hay datos o Turso falla, `503`.

### H. Idioma y Explain

1. El selector **EN/ES** está en el header y en la portada; la preferencia se guarda en `localStorage['moviris.lang']` y también se puede forzar con `?lang=en` o `?lang=es`.
2. Al cambiar de idioma, la página se recarga y vuelve a calcular números, meses, fechas y gráficos con el locale correspondiente (`en-US` o `es-EC`).
3. En `/dashboard/`, cada uno de los cinco gráficos tiene un botón **Explain / Explicar** en su esquina inferior derecha.
4. En `/calendario/`, los tres bloques (matriz año × mes, este mes frente a la mediana y períodos críticos) tienen su propio botón.
5. El botón abre una ventana con **Loading… / Cargando…** y luego un texto breve. Se cierra con la **X**, con **Esc** o haciendo clic fuera.
6. Si falta configurar Groq, la ventana muestra un aviso localizado; el resto de la aplicación sigue funcionando.

### I. Uso del CLI

```bash
# Modo local (respeta TURSO_ENABLED=false)
python etl/etl.py --source "C:\ruta\a\mis_csv"

# Forzar solo staging
python etl/etl.py --source "C:\ruta\a\mis_csv" --no-push

# Sincronizar el staging (falla si TURSO_ENABLED=false)
python etl/etl.py --push-only
```

`--source` acepta una carpeta o un archivo. Si no se indica, busca `hackathon/`; esa carpeta es opcional.

### J. Reconectar Turso

1. Cambia `TURSO_ENABLED=true` en `.env`.
2. Guarda el archivo.
3. La siguiente petición ya consulta Turso.
4. Ejecuta un ETL con push o `POST /api/etl/sync` para publicar el staging.
5. Los datos actuales de Turso no se modifican hasta ese paso explícito.

### K. Prueba rápida

```bash
curl http://127.0.0.1:5000/api/health
curl -X POST http://127.0.0.1:5000/api/upload \
  -F "files=@fire_archive_M-C61_848345.csv"
curl -X POST http://127.0.0.1:5000/api/etl/run \
  -H "Content-Type: application/json" \
  -d "{\"upload_ids\":[\"TU_UPLOAD_ID\"],\"push\":true}"
```

---

## 10. Configuración y Variables

| Variable / constante | Ubicación | Valor por defecto | Descripción |
|---|---|---|---|
| `TURSO_DATABASE_URL` | `.env` | — | URL `libsql://...` de Turso |
| `TURSO_AUTH_TOKEN` | `.env` | — | Token de escritura/lectura |
| `TURSO_ENABLED` | `.env` | `false` en el proyecto | Interruptor local/Turso |
| `GROQ_LLM_TOKEN` | `.env` | — | Token de Groq; solo backend |
| `GROQ_MODEL` | `.env` | `openai/gpt-oss-20b` en `.env.example` | Modelo de Groq para Explain |
| `MAX_BODY_CHARS` | `backend/explain.py` | `14_000` | Tamaño máximo del resumen de Explain |
| `MAX_REQUESTS_PER_MINUTE` | `backend/explain.py` | `20` | Límite de Explain por IP |
| `DEFAULT_STAGING` | `etl/etl.py` | `data/moviris_staging.db` | SQLite local |
| `DEFAULT_SOURCE` | `etl/etl.py` | `hackathon/` | Fuente por defecto del CLI (opcional) |
| `GRID` | `etl/etl.py` | `0.01` | Resolución de la malla |
| `DEFAULT_BATCH_SIZE` | `etl/etl.py` | `4000` | Filas por lote al subir a Turso |
| `MASK_MIN_HITS` | `etl/etl.py` | `40` | Umbral de persistencia |
| `MASK_MIN_YEARS` | `etl/etl.py` | `4` | Años mínimos |
| `MASK_MIN_WEEKS` | `etl/etl.py` | `15` | Semanas mínimas |
| `MAX_UPLOAD_BYTES` | `backend/app.py` | `512 MB` | Límite por petición |
| `MAX_UPLOAD_FILES` | `backend/app.py` | `80` | Archivos por petición |
| `_cleanup_uploads(keep=50)` | `backend/app.py` | `50` | Lotes locales conservados |
| `MAX_LOGS` | `backend/jobs.py` | `500` | Líneas de log por job |
| `MAX_JOBS` | `backend/jobs.py` | `20` | Historial de jobs |
| `STATS_TTL_SECONDS` | `backend/db.py` | `12` | Caché de estadísticas |
| TTL mapa/dashboard/calendario | `backend/cache.py` y módulos | `300 s` | Caché de consultas pesadas |
| Host / puerto | `run.py` | `127.0.0.1:5000` | Servidor de desarrollo |

---

## 11. Pruebas y Validación

### A. Modo local sin Turso

Se arrancó el backend con credenciales de Turso inválidas y `TURSO_ENABLED=false` para demostrar que no existe conexión remota:

| Prueba | Resultado |
|---|---|
| `GET /api/health` | `mode: local`, `turso_enabled: false`, `database.ok: true` |
| `GET /api/stats` | Leyó 339.729 celdas-día del staging |
| `GET /api/map` | Leyó puntos del staging |
| `GET /api/cells` | Leyó celdas del staging |
| `GET /api/mask` | Leyó fuentes del staging |
| `POST /api/etl/sync` | `409` bloqueado sin conectar |
| `POST /api/etl/run` con `push: true` | Terminó con `pushed: false` y `mode: local` |
| `push_staging()` directo con flag false | Lanzó `EtlError` antes de importar el cliente |
| CLI `--push-only` con flag false | Error controlado, sin conexión |

### B. Prueba de la pestaña

| Prueba | Resultado |
|---|---|
| Carga inicial | “Modo local”, sin hero, estadísticas, mapa ni parámetros |
| CSV inválido | Fila con estado **Error** y detalle de columnas faltantes |
| Subida de 8 CSV | 8 filas “Listo”, botón habilitado |
| Ejecución | 5 pasos; 4 completados y **Load (omitido)** |
| Resumen | 560.264 / 339.729 / 218.660 / 459 |
| Quitar un archivo | `DELETE /api/uploads/<id>` correcto; quedan 7 |
| Vista móvil 390 px | Sin desbordamiento horizontal |
| Logo | `GET /ico.svg` → 200; `/etl/ico.svg` → 404 |

### C. Prueba de la bienvenida

| Prueba | Resultado |
|---|---|
| `GET /` | Título, subtítulo y CTA correctos |
| Canvas `#network` | Red de puntos presente |
| Órbita | `animationName: orbit` definida en CSS |
| Satélite SVG | Visible y escalado; se adapta al espacio en móvil |
| Titular | La “g” de “fuego” queda completa; líneas sin `overflow: hidden` |
| Escritorio 1440 px | Sin desbordamiento horizontal |
| Móvil 390 px | Sin desbordamiento; CTA y datos legibles |
| Botón **Explorar el fuego** | Añade `is-leaving` y navega a `/inicio/` |
| `prefers-reduced-motion` | Contenido visible; sin órbita ni red animada |
| `/inicio/` | Componente Inicio con CSS, JS y header activo |
| API/Turso | La bienvenida no llama a ninguna ruta `/api` |
| Header compartido | `/etl/` marca ETL, `/inicio/` marca Inicio, `/mapa/` marca Mapa, `/calendario/` marca Calendario y `/dashboard/` marca Dashboard; la bienvenida `/` no monta `#site-header` |

### D. Prueba del mapa

| Prueba | Resultado |
|---|---|
| `/mapa/`, `/mapa/style.css`, `/mapa/script.js` | `200` |
| `/mapa/mapa.py` | `404` (solo se sirven los assets permitidos) |
| Header en `/mapa/` | Pestaña **Mapa** activa |
| `/api/mapa/meta` | `2012-01-11` → `2026-11-14` |
| `/api/mapa/cells` (bbox `-5..2`, `-82..-75`, 2012–2026) | 64.614 celdas, 327.694 celdas-día, 488.375 detecciones; 27.523 días críticos y 11.267 inusuales; `truncated: true` al limitar a 10 |
| `/api/mapa/csv` con el mismo rango | `200`, `text/csv`, streaming; ~19,6 MB en el área amplia |
| `/api/mapa/cells` sin parámetros | `400` con `error` |
| Página del mapa | KPIs cargados, celdas dibujadas y header activo |
| Consola | Sin errores propios del componente |
| Mapa base | Teselas OpenStreetMap sin key; atribución visible en el mapa |
| Responsive 1440 px | Panel a la izquierda, mapa a la derecha (1068×931 en la prueba) |
| Responsive 820 px | Mapa arriba y panel debajo; sin overflow horizontal |
| Responsive 390 px | Mapa de 390×464, panel debajo, controles a ancho completo; `scrollWidth = innerWidth` |

### E. Prueba del calendario

| Prueba | Resultado |
|---|---|
| `/calendario/`, `/calendario/style.css`, `/calendario/script.js` | `200` |
| `/calendario/calendario.py` | `404` (solo se sirven los assets permitidos) |
| Header en `/calendario/` | Pestaña **Calendario** activa |
| `/api/calendario/matrix` (área por defecto) | `200`; `2012-01-11` → `2026-11-14`; 179 meses y 10 semanas |
| `current` de la matriz | `2026-11`, día 14; valores `[183, 256, 5, 12]`; mediana `[2351.0, 3467.0, 221.5, 60.0]` |
| `/api/calendario/month?year=2026&month=10` | `200`, 30 días |
| `/api/calendario/month` sin `year`/`month` | `400` con `error` |
| `/api/calendario/matrix` sin área | `400` con `error` |
| Página del calendario | KPIs cargados (`2024`, `Noviembre`, `Noviembre 2020`), 180 celdas de matriz y detalle diario |
| Consola | Sin errores propios del componente |
| Área de interés | Se lee y guarda en `localStorage['moviris.aoi.v2']`, la misma clave del mapa |
| CSV | El botón descarga desde `/api/mapa/csv`, no desde un endpoint propio |
| Responsive 960 px | Matriz y panel lateral en una columna |
| Responsive 390 px | Matriz con scroll interno; `scrollWidth = innerWidth`, sin overflow de página |

### F. Prueba del Dashboard

| Prueba | Resultado |
|---|---|
| `/dashboard`, `/dashboard/`, `/dashboard/index.html` | `200` |
| `/dashboard/style.css`, `/dashboard/script.js` | `200` |
| `/dashboard/dashboard.py` | `404` |
| Header en `/dashboard/` | Pestaña **Dashboard** activa |
| Contenido | Título “Dashboard · MOVIRIS”, KPIs y cinco gráficos |
| API local | `/api/dashboard/summary` → `200` con `min_date`, `max_date`, `totals`, `months`, `year_cells` y `coverage` |
| Modo Turso | `/api/dashboard/summary` → `200` con los datos de Turso |
| Consola | Sin errores propios; Chart.js requiere Internet |
| Responsive | Sin overflow horizontal en 1440 px y 390 px |

### G. Consumo de Turso

No se consultó ni modificó Turso durante la implementación del modo local ni durante las pruebas de la pestaña. La última sincronización conocida sigue intacta con 558.848 filas (339.729 + 218.660 + 459).

### H. Prueba de idioma y Explain

| Prueba | Resultado |
|---|---|
| `GET /i18n.js`, `/explain.js`, `/explain.css` | `200` |
| Diccionario estático | 198 textos de HTML extraídos; solo 16 son neutros (números, siglas, `MOVIRIS`, `—`, `PNG`, `0%`) y no requieren traducción |
| jsdom EN | Portada “Read the fire before it spreads.”, Dashboard “Historical fire patterns”, 5 botones **Explain**, Calendario “When your area burns”, 3 botones |
| jsdom ES | Portada y Dashboard en español, botones **Explicar**, `html lang="es"` |
| Selector | `#lang-select` en header y portada; valor `en`/`es` según `localStorage` o `?lang=` |
| Formatos | `560,264` en EN y `560.264` en ES; meses y fechas con `Intl` (`Jan 2026` / `ene 2026`) |
| `POST /api/explain` sin `GROQ_MODEL` | `503` con `code: not_configured` y mensaje en el idioma pedido |
| `POST /api/explain` con `chart` inválido | `400` con `code: invalid` |
| `POST /api/explain` con resumen > 14.000 caracteres | `413` |
| `POST /api/explain` con Groq simulado | `200` con `text` y `lang` |
| Groq real con `openai/gpt-oss-20b` | `200` en EN y ES; respuesta completa de ~90 palabras |
| Groq con `urllib` sin User-Agent propio | `403` de Cloudflare; se añadió `MOVIRIS/1.0` y volvió a `200` |
| `python -m unittest discover -s tests -v` | 4 pruebas OK |
| `node --check` en `i18n.js`, `explain.js` y scripts de página | Sin errores de sintaxis |

---

## 12. Deuda Técnica y Buenas Prácticas

1. **Sin autenticación ni autorización:** cualquier cliente con acceso local puede subir archivos o lanzar el ETL. Es aceptable para uso local, no para exposición pública.
2. **Sin CSRF ni rate limiting general:** el backend no está pensado para Internet. Solo `/api/explain` tiene un límite básico de 20 peticiones/minuto por IP; el resto de endpoints no lo tiene.
3. **Jobs en memoria:** reiniciar el servidor pierde el historial y el progreso de un job en curso. El staging y Turso sí persisten.
4. **Un solo job activo y sin cancelación:** no se puede pausar ni abortar un ETL desde la UI.
5. **Sincronización secuencial:** 558.848 filas tardan ~8 minutos con lotes HTTP de 4.000. Paralelizar o usar importación masiva reduciría el tiempo.
6. **Reemplazo completo:** cada push con `replace=true` vuelve a escribir todas las filas; no hay cargas incrementales.
7. **Sin migraciones:** el esquema se crea con `CREATE TABLE IF NOT EXISTS`; no hay versionado de cambios.
8. **Tests parciales:** `tests/test_explain.py` cubre el endpoint Explain con Groq simulado, pero el ETL, las consultas y el resto de endpoints siguen sin suite automatizada.
9. **Memoria del ETL:** la agregación y la línea base se mantienen en diccionarios de Python. Con millones de filas (por ejemplo, todo Brasil a 0,01°) el consumo de RAM puede ser alto. Para escalar: malla de 0,05°, filtro de fechas/región o agregación respaldada por SQLite.
10. **Máscara regional:** la máscara de tierra y la lista de volcanes son específicas de Ecuador / Galápagos / sur de Colombia. Fuera de esa cobertura se asume tierra.
11. **Archivos temporales:** `uploads/` conserva hasta 50 lotes; los más antiguos se eliminan automáticamente. No es un backup.
12. **Lista de archivos volátil:** la pestaña no persiste la lista de subidas en el navegador; al recargar empieza vacía. Los lotes siguen en el servidor hasta que se quiten o se limpien.
13. **Progreso de subida:** no hay barra por archivo; se muestra el avance secuencial “Subiendo X de N”.
14. **Dependencias de Turso:** el modo local evita el consumo, pero la reconexión requiere credenciales válidas y el flag en `true`.
15. **Datos y `.sql`:** `backend/schema.sql` no es un respaldo de datos. El respaldo local es `data/moviris_staging.db`; para un dump, usar `sqlite3 ... .dump`.
16. **Servidor de desarrollo:** `run.py` usa Flask sin WSGI de producción.
17. **Enlaces de Inicio:** los CTA a `/mapa/` y `/calendario/` ya funcionan; todas las pestañas del header tienen página.
18. **Animación de bienvenida:** la red de puntos usa `requestAnimationFrame` y la órbita es CSS; en equipos de bajas prestaciones puede consumir CPU. Se puede reducir el número de nodos o desactivar con `prefers-reduced-motion`.
19. **Dashboard implementado:** `/dashboard/` tiene KPIs, gráficos y `/api/dashboard/summary`; reutiliza `_connect()` del mapa y lee el staging local o Turso. El CSV de celdas se sigue descargando desde `/api/mapa/csv`.
20. **Mapa, calendario y dashboard leen Turso:** `_connect()` devuelve `TursoConnection` cuando `TURSO_ENABLED=true`, con un adaptador de cursor compatible con `sqlite3`. Las consultas son de solo lectura; si Turso falla, la API responde `503`. El staging local sigue siendo necesario para ejecutar el ETL.
21. **Dependencia de CDN y teselas:** Leaflet y OpenStreetMap se cargan desde Internet. OpenStreetMap no requiere key, pero su infraestructura es financiada por donaciones y pide tráfico moderado; para producción con alto tráfico conviene una key gratuita de CARTO, otro proveedor o teselas propias. Las celdas y la API siguen funcionando sin cambiar el blueprint.
22. **Límites del mapa:** `/api/mapa/cells` envía hasta 20.000 celdas por defecto (máximo 30.000) y el CSV puede ser grande; para áreas continentales conviene filtrar fechas o confianza.
23. **Responsive del mapa:** el breakpoint de 900 px apila mapa y panel, y el de 600 px ajusta controles y altura. El mapa depende de `map.invalidateSize()` (ResizeObserver/orientationchange); si se agrega otro contenedor o un cambio de layout, hay que conservar esa llamada.
24. **Responsive del calendario:** la matriz año × mes no cabe en 390 px por diseño. Se resuelve con scroll interno en `.matrix-wrap` y `min-width: 0` en las columnas; si se cambia la estructura de `.cols`, hay que conservar ambas reglas para no desbordar la página.
25. **CSV del calendario:** el botón de descarga usa `/api/mapa/csv`; si el mapa cambia de endpoint o de parámetros, hay que actualizar el calendario. El calendario no tiene exportación propia.
26. **Diccionario manual:** `i18n.js` usa las cadenas en español como claves. Al añadir texto nuevo en HTML o JS hay que añadir su entrada en `EN`; si falta, la interfaz muestra el español también en inglés. Los textos neutros (siglas, números, `MOVIRIS`) se dejan sin entrada a propósito.
27. **Recarga al cambiar idioma:** el selector guarda la preferencia y recarga la página. Es intencional para que Chart.js, la matriz y los formatos `Intl` se recalculen; no hay traducción en caliente.
28. **Explain depende de Groq:** sin `GROQ_LLM_TOKEN` y `GROQ_MODEL` el botón muestra un `503` localizado. El modelo se configura por entorno y no está fijado en el código. El resumen que se envía es compacto (top N, medianas, índices), no los datos completos. El límite por IP vive en memoria del proceso y se reinicia con el servidor.
29. **Logs del ETL en español:** los mensajes internos del backend se conservan en su idioma original; en inglés la interfaz muestra un mensaje genérico y el detalle queda en la consola del navegador.

---

## 13. Dirección de diseño

> [!IMPORTANT]
> **Regla permanente del usuario:** el diseño anterior de la bienvenida —tema oscuro editorial, hero de dos columnas, visual a la derecha, franja de tres métricas y satélite orbitando— fue rechazado por ser **demasiado típico, estandarizado y poco original**. No repetir ese enfoque ni usarlo como plantilla para futuras pantallas.

### Autoevaluación del diseño rechazado

- **Composición predecible:** titular a la izquierda, elemento visual a la derecha y tres métricas al pie. Es un patrón de landing muy visto.
- **Cliché visual:** el satélite orbitando comunica “tecnología/espacio” de forma genérica; no nace de una idea propia de MOVIRIS.
- **Jerarquía estándar:** eyebrow + titular grande + subtítulo + CTA + métricas; correcta, pero intercambiable con cualquier producto.
- **Resultado:** técnicamente funcional y visualmente limpio, pero sin una identidad que lo haga reconocible como MOVIRIS.

### Reglas para la próxima dirección

1. Evitar layouts de landing genéricos: hero texto+visual, tres tarjetas/métricas, secciones predecibles.
2. Evitar clichés visuales (órbitas, glassmorphism, neones, degradados llamativos) si no responden a una idea propia del proyecto.
3. Buscar una composición distintiva con una idea visual específica: fuego, territorio, calendario, datos satelitales o memoria histórica.
4. Cada propuesta debe explicar **qué la hace diferente** y **qué patrón genérico evita**.
5. Mantener la paleta del proyecto y la legibilidad; la originalidad no justifica romper la accesibilidad.
6. No avanzar con un rediseño hasta contar con una referencia o definición del usuario.
7. Revisar el resultado antes de darlo por bueno: si se siente como una plantilla, rehacerlo.

> [!NOTE]
> La versión actual del código (red de puntos, CTA con esquinas cortadas, satélite SVG y franja de datos; **sin header ni footer** en la portada) es la dirección visual vigente. No reintroducir el patrón genérico anterior. Cualquier cambio futuro debe respetar las reglas de esta sección.

## ⚠️ DIRECTIVA OBLIGATORIA DE MANTENIMIENTO DE DOCUMENTACIÓN

> [!IMPORTANT]
> **REGLA PERMANENTE DEL PROYECTO:**
>
> **Actualización obligatoria por cambios:** cada vez que se realice cualquier modificación, refactorización o ampliación en el proyecto (por ejemplo: cambios en `etl.py`, endpoints, esquema, frontend, configuración de Turso, estructura de archivos o dependencias), es **estrictamente obligatorio actualizar este archivo `DOCUMENTACION.md`**. Ningún cambio se considerará finalizado sin reflejar sus nuevos conceptos, funciones, esquemas o parámetros.
>
> **Corrección oportunista de inconsistencias:** si durante la implementación de un cambio encuentras explicaciones confusas, desactualizadas o incorrectas en la documentación directamente relacionada, corrígelas en ese mismo momento. No realices auditorías completas de todo el archivo para evitar consumo innecesario de tokens; subsana solo los errores puntuales que encuentres al paso.
>
> *"Con la idea de que la IA no tenga que revisar todo el proyecto, sino solo la documentación."*
