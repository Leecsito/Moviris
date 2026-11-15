# MOVIRIS · Monitoreo de focos de calor

Bienvenida, Inicio, Mapa, Calendario y componente ETL para los datos de **NASA
FIRMS** (MODIS y VIIRS, archivo y NRT). El proyecto puede trabajar en **modo
local** con SQLite o publicar en **Turso**.

- `/` → bienvenida animada (`index.html`, `styles.css`, `script.js` en la raíz).
- `/inicio/` → componente Inicio: contexto del proyecto, problema, solución y públicos.
- `/mapa/` → mapa de celdas por área y fechas, con fondo OpenStreetMap. En móvil, el mapa va arriba y el panel debajo.
- `/calendario/` → calendario de actividad por año, mes y día; usa el área del mapa.
- `/dashboard/` → placeholder del Dashboard: solo evita el `404` mientras se implementa.
- `/etl/` → subida de CSV, ejecución del ETL y resumen.

La pestaña `/etl/` es deliberadamente simple: **subir archivos → ejecutar → ver el
resultado**. Los mapas, estadísticas y consultas pertenecen a la aplicación
principal, no a esta pestaña.

## 1. Arranque rápido

Requisitos: **Python 3.10+** (probado con 3.12).

```bash
pip install -r requirements.txt
python run.py
```

Abre la bienvenida en **http://127.0.0.1:5000/**. El ETL está en
**http://127.0.0.1:5000/etl/**. El mapa y el calendario están en
**http://127.0.0.1:5000/mapa/** y **http://127.0.0.1:5000/calendario/**.
El placeholder del Dashboard está en **http://127.0.0.1:5000/dashboard/**.

Si el puerto está ocupado:

```bash
python run.py --port 8080 --open
```

`--open` abre la bienvenida. Detén cualquier instancia anterior antes de arrancar.

### Bienvenida

- Página completa con tema oscuro editorial, red de puntos, satélite SVG orbitando, CTA con esquinas cortadas y franja de datos.
- **Sin header ni footer:** la portada no monta `#site-header` ni carga `/header/*`.
- Respeta `prefers-reduced-motion`.
- El botón **Explorar el fuego** lleva a `/inicio/`, el componente Inicio.
- `/inicio/` es una landing con hero, problema, solución, públicos y CTA a mapa/calendario.
- La bienvenida no consulta la API ni Turso.
- No volver al patrón de landing genérico anterior (ver `DOCUMENTACION.md`, sección 13).

### Header compartido

El header vive en `header/` y se integra **sin copiar su HTML** dentro de cada página:

- Cada página que lo usa incluye `<div id="site-header"></div>`, `/header/style.css` y `/header/script.js`.
- El script descarga `/header/index.html` y marca la pestaña activa.
- Lo usan `/etl/`, `/inicio/`, `/mapa/`, `/calendario/` y `/dashboard/`; la bienvenida `/` no.
- Todas las pestañas del header tienen página. `/dashboard/` es un placeholder temporal sin API.

## 2. Modo local por defecto

El archivo `.env` trae:

```env
TURSO_ENABLED=false
```

Con `false`:

- ninguna ruta consulta ni escribe en Turso;
- las lecturas (`health`, `stats`, `map`, `cells`, `mask`) usan
  `data/moviris_staging.db`;
- el ETL guarda el resultado solo en ese staging;
- el mapa y el calendario leen ese staging en modo solo lectura;
- `/api/etl/sync` responde con un error claro;
- la cabecera de la pestaña muestra **“Modo local”**.

El staging se regenera ejecutando el ETL desde la pestaña o con:

```bash
python etl/etl.py --source hackathon
```

### Volver a conectar Turso

Cambia una sola línea en `.env`:

```env
TURSO_ENABLED=true
```

Guarda el archivo. La siguiente petición ya usa Turso; no hay botón ni estado
persistido aparte. No se escribe nada en Turso hasta que ejecutes un ETL con
push o llames al endpoint de sincronización.

Los datos que ya están en Turso no se tocan con `TURSO_ENABLED=false`. Cuando
vuelvas a conectar y ejecutes un ETL, el resultado se publicará según la opción
de reemplazo del proceso.

> El CLI `python etl/etl.py` también respeta `TURSO_ENABLED`. Con `false` no
> sincroniza; con `true` sincroniza salvo que uses `--no-push`.

### ¿Dónde están los datos?

- `data/moviris_staging.db` es la base SQLite local con los datos limpios.
  Es lo que usa el panel cuando `TURSO_ENABLED=false`.
- `backend/schema.sql` contiene **solo las definiciones de las tablas**; no
  guarda datos.
- Turso guarda la copia publicada. En modo local no se consulta ni se modifica.
- Los CSV crudos son solo la entrada del ETL. No es necesario conservarlos en el
  proyecto si ya tienes el staging generado.

## 3. Qué hace la pestaña ETL

1. **Archivos de entrada**
   - Zona para arrastrar o seleccionar `.csv` y `.zip` (máx. 512 MB por archivo).
   - Lista de archivos subidos con nombre, tamaño, tipo y estado.
   - Botón **Quitar** por archivo; también borra el archivo del servidor.
   - Los CSV deben incluir `latitude`, `longitude` y `acq_date`.
2. **Proceso ETL**
   - Un único botón **Ejecutar ETL**.
   - Usa los valores por defecto de `etl.py`: incluye NRT, excluye el año más
     reciente de la línea base y reemplaza el staging local.
   - Barra de progreso con cinco pasos: **Extract, Transform, Baseline, Estado y
     Load**. En modo local, Load aparece como omitido.
   - Resumen final: filas leídas, celda-días cargados, filas de línea base y
     celdas en la máscara.
   - Errores claros para CSV inválidos, fallos de Turso y problemas de
     conexión.

## 4. Estructura

```
.
├── run.py                     # arranca Flask
├── requirements.txt
├── .env / .env.example        # TURSO_ENABLED y credenciales
├── index.html                 # bienvenida (se sirve en /)
├── styles.css                 # estilos de la bienvenida
├── script.js                  # animaciones de la bienvenida
├── ico.svg                    # logo raíz (fill #637545)
├── backend/
│   ├── app.py                 # rutas HTTP, subida y borrado de archivos
│   ├── db.py                  # lecturas locales o Turso según el flag
│   ├── jobs.py                # ETL en segundo plano
│   ├── settings.py            # interruptor TURSO_ENABLED
│   └── schema.sql             # esquema de referencia
├── etl/
│   ├── index.html             # pestaña simplificada
│   ├── style.css              # tema claro
│   ├── script.js              # subida, progreso y resumen
│   └── etl.py                 # motor ETL + CLI
├── header/
│   ├── index.html             # fragmento compartido de navegación
│   ├── style.css              # estilos del header
│   └── script.js              # inyección y pestaña activa
├── inicio/
│   ├── index.html             # componente Inicio (landing)
│   ├── style.css              # estilos del componente
│   └── script.js              # revelado al hacer scroll
├── mapa/
│   ├── index.html             # mapa por área y fechas
│   ├── style.css              # estilos del mapa
│   ├── script.js              # Leaflet, filtros y CSV
│   └── mapa.py                # blueprint Flask del mapa
├── calendario/
│   ├── index.html             # calendario por año, mes y día
│   ├── style.css              # estilos de la matriz y el detalle
│   ├── script.js              # matriz, detalle diario y CSV
│   └── calendario.py          # blueprint Flask del calendario
├── dashboard/
│   ├── index.html             # placeholder del Dashboard
│   └── style.css              # estilos del placeholder
├── data/moviris_staging.db    # staging local (datos limpios)
└── uploads/                   # archivos temporales subidos desde la pestaña
```

`data/` y `uploads/` se crean automáticamente y están en `.gitignore`. El logo
(`ico.svg`, con `fill="#637545"`) vive en la raíz y se sirve como `/ico.svg`; no
hay copia en `etl/`.

La bienvenida no consulta la API ni Turso: es un frontend estático. El botón
**Explorar el fuego** navega a `/inicio/`, el componente Inicio.

No es necesario guardar los CSV crudos dentro del proyecto: la pestaña los
recibe por subida. Si quieres usar el CLI con una carpeta local, pásala con
`--source`.

## 5. Uso por línea de comandos

```bash
# Respeta TURSO_ENABLED; con false solo escribe el staging local
python etl/etl.py --source "C:\ruta\a\mis_csv"

# Forzar solo staging local aunque Turso esté activo
python etl/etl.py --source "C:\ruta\a\mis_csv" --no-push

# Reintentar la sincronización del staging (falla si TURSO_ENABLED=false)
python etl/etl.py --push-only

# Otras opciones
python etl/etl.py --source "C:\ruta\a\mis_csv" --no-nrt
python etl/etl.py --source "C:\ruta\a\mis_csv" --include-current-year
```

`--source` acepta una carpeta o un archivo CSV. Si no se indica, el CLI busca
`hackathon/` en la raíz; esa carpeta es opcional y no es necesaria para la
pestaña.

El resumen JSON incluye `mode` (`local`/`turso`), `pushed` y `pushed_rows`.

## 6. API

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/api/health` | Modo activo (`local`/`turso`), estado y staging. |
| `POST` | `/api/upload` | Subida multipart (`files`) de CSV/ZIP. |
| `DELETE` | `/api/uploads/<upload_id>` | Borra un lote subido y sus CSV. |
| `POST` | `/api/etl/run` | Lanza el ETL; en modo local fuerza `push=false`. |
| `GET` | `/api/etl/status` | Progreso del trabajo (`?job_id=...`). |
| `POST` | `/api/etl/sync` | Sincroniza el staging; bloqueado en modo local. |
| `GET` | `/api/stats` | Estadísticas (local o Turso según el flag). |
| `GET` | `/api/map` | Puntos críticos/inusuales (local o Turso). |
| `GET` | `/api/cells` | Celdas con filtros (local o Turso). |
| `GET` | `/api/mask` | Fuentes no vegetales (local o Turso). |
| `GET` | `/api/staging` | Información del SQLite local. |
| `GET` | `/api/mapa/meta` | Rango de fechas del staging para el mapa. |
| `GET` | `/api/mapa/cells` | Celdas agregadas del área y fechas. |
| `GET` | `/api/mapa/csv` | CSV en streaming de celdas-día. |
| `GET` | `/api/calendario/matrix` | Matriz año × mes y semanas críticas del área. |
| `GET` | `/api/calendario/month` | Detalle diario de un mes (`year`, `month`). |

En modo local, `stats`, `map`, `cells` y `mask` leen `data/moviris_staging.db`.
No hay conexión con Turso en esas rutas. `/api/mapa/*` y `/api/calendario/*`
leen el mismo staging; con `TURSO_ENABLED=true` responden `501`.

## 7. Metodología ETL

- **Malla**: celdas de 0,01°; se guarda el centro con 3 decimales.- **Sensores**: Terra/Aqua se unifican como `MODIS`; SNPP, N20 y N21 se conservan.
- **Confianza**: MODIS 0–100 → 0/1/2 con cortes 30/80; VIIRS `l/n/h` → 0/1/2.
- **FRP normalizado**: cada FRP se divide por la mediana de su sensor y se suma
  por celda-día.
- **NRT**: una celda-día es NRT solo si todas sus detecciones vienen de NRT.
- **Línea base**: por celda y semana ISO, con las detecciones diarias de los años
  históricos; se excluye el año más reciente del dataset.
- **Estado**: `critical` si supera el p75 histórico y el z-score es ≥ 1 (o si el
  z-score es ≥ 2); `unusual` si supera la media; `normal` en el resto.
- **Máscara no vegetal**: celdas persistentes (≥ 40 detecciones, ≥ 4 años,
  ≥ 15 semanas) clasificadas como volcán, fuente fija o mar. La máscara de tierra
  está incluida en `etl.py` (Natural Earth 1:10m, 0,01°).

## 8. Rendimiento

Con los 8 CSV de ejemplo (~560.000 detecciones, 43 MB):

- cálculo local + staging: **~55 s**;
- sincronización completa con Turso: **~8 min** (solo si `TURSO_ENABLED=true`).

En modo local no hay espera de sincronización.

## 9. Problemas frecuentes

| Síntoma | Solución |
|---|---|
| La raíz muestra la bienvenida | Es lo esperado; el ETL está en `/etl/`. |
| El botón **Explorar el fuego** lleva a `/inicio/` | Es el componente Inicio, con su propia landing. |
| Veo la versión anterior de la interfaz | Detén el `run.py` viejo y vuelve a arrancar; el navegador puede requerir recarga forzada. |
| La cabecera dice “Modo local” | Es lo esperado con `TURSO_ENABLED=false`. |
| Quiero publicar en Turso | Cambia `TURSO_ENABLED=true` en `.env` y ejecuta el ETL. |
| Turso sin conexión | Revisa `TURSO_DATABASE_URL` y `TURSO_AUTH_TOKEN`. |
| `Turso está desactivado` al sincronizar | Activa `TURSO_ENABLED=true` en `.env`. |
| El CSV no se acepta | Debe tener `latitude`, `longitude` y `acq_date`. |
| La subida supera 512 MB | Divide el archivo o usa un ZIP más pequeño. |
| No existe el staging local | Ejecuta el ETL desde la pestaña o el CLI. |
| El mapa no carga o no muestra teselas | Verifica Internet (Leaflet/OpenStreetMap) y que exista staging; usa `TURSO_ENABLED=false`. |
| El fondo del mapa tiene otro estilo | Es OpenStreetMap, el fondo gratuito sin key; CARTO ahora requiere una key gratuita. Las celdas y la API siguen igual. |
| `/api/mapa/*` responde `501` | El mapa todavía no lee de Turso; usa `TURSO_ENABLED=false`. |
| El calendario no muestra datos | Verifica que exista staging y que `TURSO_ENABLED=false`; ejecuta el ETL si está vacío. |
| La matriz del calendario se corta en móvil | Es el scroll interno de `.matrix-wrap`; desliza la tabla horizontalmente. |
| `/api/calendario/*` responde `501` | El calendario hereda `_connect()` del mapa y todavía no lee de Turso; usa `TURSO_ENABLED=false`. |
| Dashboard muestra “Módulo en preparación” | Es el placeholder temporal; el Dashboard real aún no está implementado. |
| El puerto 5000 está ocupado | Detén la instancia anterior o `python run.py --port 8080`. |

## 10. Seguridad

- El token de Turso vive en `.env` y solo lo usa el backend.
- `.env` está en `.gitignore`.
- En modo local no se lee ni se escribe en Turso.
- Los archivos subidos se guardan bajo `uploads/`; el endpoint de borrado valida
  el identificador y la ruta.
