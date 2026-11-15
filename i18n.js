/* ==========================================================================
   MOVIRIS · i18n
   Diccionario estático EN/ES, selector de idioma y formatos regionales.
   El castellano es el idioma fuente del HTML; el inglés es el idioma por
   defecto. No se usa ninguna API para traducir la interfaz.
   ========================================================================== */

(() => {
  'use strict';

  const STORAGE_KEY = 'moviris.lang';
  const DEFAULT_LANG = 'en';
  const SUPPORTED = ['en', 'es'];

  const EN = {
    /* Portada */
    "MOVIRIS · Lee el fuego antes de que avance": "MOVIRIS · Read the fire before it spreads",
    "Focos de calor · NASA FIRMS": "Fire hotspots · NASA FIRMS",
    "Lee el fuego": "Read the fire",
    "antes de que": "before it",
    "avance.": "spreads.",
    "Focos de calor de NASA FIRMS, en un solo calendario.": "NASA FIRMS fire hotspots, in a single calendar.",
    "Explorar el fuego": "Explore the fire",
    "Datos satelitales · NASA FIRMS": "Satellite data · NASA FIRMS",
    "Fuente": "Source",
    "Sensores": "Sensors",
    "Malla común": "Common grid",
    "Satélite orbitando la Tierra": "Satellite orbiting Earth",
    "Datos del proyecto": "Project data",

    /* Header */
    "Inicio": "Home",
    "Calendario": "Calendar",
    "Mapa": "Map",
    "Dashboard": "Dashboard",
    "ETL": "ETL",
    "MOVIRIS, bienvenida": "MOVIRIS, home",
    "Principal": "Main",
    "Idioma": "Language",
    "Language": "Language",

    /* Inicio */
    "Inicio · MOVIRIS": "Home · MOVIRIS",
    "Cinco satélites.": "Five satellites.",
    "Dos sensores.": "Two sensors.",
    "Una sola historia del fuego.": "One single story of fire.",
    "MODIS y VIIRS llevan años vigilando el planeta, pero no se pueden comparar. MOVIRIS los une para que veas cuándo y dónde arde, y cuándo algo se sale de lo normal.": "MODIS and VIIRS have monitored the planet for years, but they cannot be compared. MOVIRIS brings them together so you can see when and where fires burn, and when something is out of the ordinary.",
    "Elige tu zona en el mapa": "Choose your area on the map",
    "Ver el calendario": "View the calendar",
    "El problema": "The problem",
    "Los satélites llevan más de dos décadas rastreando el fuego, pero cada sensor lo cuenta a su manera. Hay": "Satellites have been tracking fires for more than two decades, but each sensor tells it its own way. There are",
    "de": "from",
    "varios satélites": "several satellites",
    "que no se pueden sumar sin más.": "that cannot simply be added together.",
    "Sin una imagen consistente, nadie sabe con certeza cuándo y dónde se quema.": "Without a consistent picture, no one knows for sure when and where fires burn.",
    "La solución": "The solution",
    "Ponerlos a hablar el mismo idioma.": "Make them speak the same language.",
    "Una sola malla": "One common grid",
    "Cada foco cae en una celda de ~1 km, sin importar qué satélite lo vio.": "Each hotspot falls into a ~1 km cell, regardless of which satellite saw it.",
    "Una sola confianza": "One common confidence scale",
    "Una escala común de tres niveles para los dos sensores.": "A common three-level scale for both sensors.",
    "Normal": "Normal",
    "Crítica": "Critical",
    "Inusual": "Unusual",
    "Una sola vara": "One common yardstick",
    "Cada semana se compara con la historia de esa misma celda y se marca como Normal, Crítica o Inusual.": "Each week is compared with that cell's history and marked Normal, Critical, or Unusual.",
    "Para quién": "Who it is for",
    "Para quien necesita decidir antes de que el fuego avance.": "For those who need to decide before the fire spreads.",
    "Alerta temprana": "Early warning",
    "Descubre en qué semanas una zona suele encenderse.": "Find out which weeks an area usually ignites.",
    "Respuesta a emergencias": "Emergency response",
    "Detecta al instante lo que se sale de lo habitual.": "Spot what is out of the ordinary instantly.",
    "Científicos": "Scientists",
    "Patrones históricos comparables.": "Comparable historical patterns.",
    "Administradores de tierras": "Land managers",
    "Incendios forestales y quemas agrícolas en un mismo calendario.": "Wildfires and agricultural burns in one calendar.",
    "¿Dónde quieres mirar?": "Where do you want to look?",
    "Fuente: NASA FIRMS. Un foco de calor no siempre es un incendio, y los datos recientes (NRT) son preliminares.": "Source: NASA FIRMS. A fire hotspot is not always a fire, and recent (NRT) data are preliminary.",
    "Un foco visto por MODIS y por VIIRS cae en una misma celda de la malla": "A hotspot seen by MODIS and VIIRS falls into the same grid cell",
    "Baja · Nominal · Alta": "Low · Nominal · High",
    "MALLA · 0,01°": "GRID · 0.01°",
    "0,01°": "0.01°",

    /* Mapa */
    "Mapa · MOVIRIS": "Map · MOVIRIS",
    "Área de interés": "Area of interest",
    "Dibujar área": "Draw area",
    "Cancelar dibujo": "Cancel drawing",
    "Vista mundial": "World view",
    "Haz clic en dos esquinas opuestas del mapa. Esc cancela.": "Click two opposite corners on the map. Esc cancels.",
    "Zona rápida": "Quick zone",
    "Elegir…": "Choose…",
    "Mundo": "World",
    "América del Norte": "North America",
    "América Central y Caribe": "Central America and Caribbean",
    "América del Sur": "South America",
    "Europa": "Europe",
    "África": "Africa",
    "Asia": "Asia",
    "Oceanía": "Oceania",
    "Norte": "North",
    "Sur": "South",
    "Oeste": "West",
    "Este": "East",
    "Fechas": "Dates",
    "Desde": "From",
    "Hasta": "To",
    "90 días": "90 days",
    "1 año": "1 year",
    "Todo": "All",
    "Vista": "View",
    "Confianza mínima": "Minimum confidence",
    "Todas (incluye baja)": "All (includes low)",
    "Nominal y alta": "Nominal and high",
    "Solo alta": "High only",
    "Colorear por": "Color by",
    "Estado (crítico / inusual)": "Status (critical / unusual)",
    "Intensidad (días con focos)": "Intensity (days with hotspots)",
    "Aplicar": "Apply",
    "Descargar CSV": "Download CSV",
    "Resultado": "Result",
    "Celdas con focos": "Cells with hotspots",
    "Celdas-día activas": "Active cell-days",
    "Detecciones": "Detections",
    "Días críticos": "Critical days",
    "Días inusuales": "Unusual days",
    "Cada celda mide ~1 km (0,01°). El CSV contiene una fila por celda y día, no las detecciones originales. Un foco de calor no siempre es un incendio; los datos NRT son preliminares.": "Each cell is ~1 km (0.01°). The CSV contains one row per cell-day, not the original detections. A fire hotspot is not always a fire; NRT data are preliminary.",
    "Cargando…": "Loading…",
    "Controles del mapa": "Map controls",
    "Rangos rápidos": "Quick ranges",
    "Leyenda": "Legend",
    "Mapa de focos de calor": "Fire hotspot map",
    "Rango de fechas disponible": "Available date range",
    "Área de interés del mapa": "Map area of interest",
    "día": "day",
    "días": "days",
    "Con días críticos": "With critical days",
    "Con días inusuales (sin críticos)": "With unusual days (no critical)",
    "Solo días normales": "Normal days only",
    "Días con focos": "Days with hotspots",
    "FRP máximo": "Maximum FRP",
    "Días inusuales (sin críticos)": "Unusual days (no critical)",
    "más de {n} días": "more than {n} days",
    "Preparando el CSV…": "Preparing CSV…",
    "El área es demasiado pequeña. Dibuja un rectángulo más grande.": "The area is too small. Draw a larger rectangle.",
    "Elige las dos fechas.": "Choose both dates.",
    "La fecha inicial debe ser anterior a la final.": "The start date must be before the end date.",
    "No se pudieron consultar los datos.": "Could not load the data.",
    "No hay datos locales. Ejecuta primero el ETL.": "No local data. Run the ETL first.",
    "La base no tiene datos.": "The database has no data.",

    /* Calendario */
    "Calendario · MOVIRIS": "Calendar · MOVIRIS",
    "Calendario de actividad de quema": "Burning activity calendar",
    "Cuándo arde tu zona": "When your area burns",
    "Cargando área…": "Loading area…",
    "Cambiar en el mapa": "Change on the map",
    "Medir": "Measure",
    "Celdas-día críticas": "Critical cell-days",
    "Celdas-día inusuales": "Unusual cell-days",
    "Año más activo": "Most active year",
    "Mes del año más activo": "Most active month of the year",
    "Mes más intenso": "Most intense month",
    "Año × mes": "Year × month",
    "Los meses con borde punteado están incompletos. Elige un mes para ver sus días.": "Months with a dashed border are incomplete. Choose a month to see its days.",
    "Este mes frente a la mediana": "This month vs. the median",
    "Períodos críticos": "Critical periods",
    "Detalle del mes": "Month detail",
    "Ver este mes en el mapa →": "View this month on the map →",
    "Cada celda mide ~1 km (0,01°). «Críticas» e «inusuales» vienen del ETL: comparan cada semana con el historial de su celda. El CSV contiene una fila por celda y día. Un foco de calor no siempre es un incendio; los datos NRT son preliminares.": "Each cell is ~1 km (0.01°). “Critical” and “unusual” come from the ETL: each week is compared with its cell's history. The CSV contains one row per cell-day. A fire hotspot is not always a fire; NRT data are preliminary.",
    "Resumen": "Summary",
    "Calendario de años por mes": "Calendar of years by month",
    "Año": "Year",
    "Total": "Total",
    "Sin actividad en esta área": "No activity in this area",
    "Este año": "This year",
    "semana": "week",
    "Sin datos": "No data",
    "Celdas-día": "Cell-days",
    "Promedio": "Average",
    "Mediana": "Median",
    "Día": "Day",
    "Días": "Days",

    /* Dashboard */
    "Dashboard · MOVIRIS": "Dashboard · MOVIRIS",
    "Patrones históricos del fuego": "Historical fire patterns",
    "CSV de celdas-día": "Cell-days CSV",
    "CSV del resumen anual": "Annual summary CSV",
    "Actividad por año": "Activity by year",
    "Anomalía anual": "Annual anomaly",
    "Estacionalidad": "Seasonality",
    "Comparar con el año": "Compare with year",
    "Detecciones frente a celdas-día": "Detections vs. cell-days",
    "Quién vio cada celda-día": "Who saw each cell-day",
    "Indicadores del área": "Area indicators",
    "Barras de actividad por año": "Activity bars by year",
    "Desviación de cada año frente a la media": "Deviation of each year from the mean",
    "Mediana mensual y año elegido": "Monthly median and selected year",
    "Índice de detecciones y de celdas-día activas": "Detections and active cell-days index",
    "Celdas-día por familia de sensores": "Cell-days by sensor family",
    "Media de años completos": "Average of complete years",
    "Las barras claras son años incompletos.": "Light bars are incomplete years.",
    "Anomalía (%)": "Anomaly (%)",
    "años quedaron por encima de la media. Mayor desviación:": "years were above the mean. Largest deviation:",
    "Mes más activo según la mediana": "Most active month by median",
    "La mediana usa": "The median uses",
    "años completos": "complete years",
    "todos los años disponibles": "all available years",
    "Sin actividad en esta área.": "No activity in this area.",
    "Se necesitan al menos 3 años completos con actividad.": "At least 3 complete years with activity are needed.",
    "Se necesitan al menos 2 años completos con actividad.": "At least 2 complete years with activity are needed.",
    "Sin datos de sensores en esta área.": "No sensor data in this area.",
    "Solo MODIS": "MODIS only",
    "MODIS y VIIRS": "MODIS and VIIRS",
    "Solo VIIRS": "VIIRS only",
    "No se pudo cargar la librería de gráficos (Chart.js). Revisa tu conexión a internet.": "Could not load the chart library (Chart.js). Check your internet connection.",
    "Este gráfico no tiene datos para descargar.": "This chart has no data to download.",
    "Índice 100 = media de los años completos. Las detecciones aumentan cuando entran más satélites; las celdas-día cuentan cada celda una sola vez por día. Si las líneas se separan, el cambio viene de los sensores y no del fuego.": "Index 100 = average of complete years. Detections rise as more satellites come in; cell-days count each cell only once per day. If the lines diverge, the change comes from sensors, not fire.",
    "Celdas-día activas del área según qué familia de sensores las detectó. Muestra el paso de MODIS a VIIRS y el período en que ambos observan.": "Cell-days in the area by sensor family. Shows the transition from MODIS to VIIRS and the period when both observe.",
    "Cada celda mide ~1 km (0,01°). Media, mediana y anomalías usan solo años completos. «Críticas» e «inusuales» vienen del ETL: comparan cada semana con el historial de su celda. Un foco de calor no siempre es un incendio; los datos NRT son preliminares.": "Each cell is ~1 km (0.01°). Mean, median, and anomalies use complete years only. “Critical” and “unusual” come from the ETL: each week is compared with its cell's history. A fire hotspot is not always a fire; NRT data are preliminary.",

    /* ETL */
    "MOVIRIS · ETL de focos de calor": "MOVIRIS · Fire hotspot ETL",
    "ETL de focos de calor": "Fire hotspot ETL",
    "Verificando…": "Checking…",
    "Archivos de entrada": "Input files",
    "Sube los CSV de FIRMS (MODIS o VIIRS). También puedes subir un ZIP.": "Upload FIRMS CSV files (MODIS or VIIRS). You can also upload a ZIP.",
    "0 archivos": "0 files",
    "Arrastra los archivos aquí": "Drag files here",
    "o": "or",
    "selecciónalos": "select them",
    "CSV o ZIP · hasta 512 MB por archivo": "CSV or ZIP · up to 512 MB per file",
    "Todavía no hay archivos.": "There are no files yet.",
    "Proceso ETL": "ETL process",
    "Procesa los archivos y guarda el resultado limpio.": "Process the files and store the clean result.",
    "Ejecutar ETL": "Run ETL",
    "En espera": "Waiting",
    "Estado": "Status",
    "No se pudo completar el proceso": "The process could not be completed",
    "Resumen del proceso": "Process summary",
    "Filas leídas": "Rows read",
    "Celda-días cargados": "Cell-days loaded",
    "Filas de línea base": "Baseline rows",
    "Celdas en la máscara": "Cells in the mask",
    "MOVIRIS · ETL": "MOVIRIS · ETL",
    "Modo local": "Local mode",
    "Estado de la fuente de datos": "Data source status",
    "Seleccionar archivos CSV o ZIP": "Select CSV or ZIP files",
    "Archivos subidos": "Uploaded files",
    "Turso conectado": "Turso connected",
    "Turso sin conexión": "Turso offline",
    "Sin conexión": "Offline",
    "Turso desactivado (TURSO_ENABLED=false). El resultado queda en el staging local.": "Turso disabled (TURSO_ENABLED=false). The result stays in local staging.",
    "Modo local. Aún no hay un staging disponible; ejecuta el ETL.": "Local mode. No staging is available yet; run the ETL.",
    "No se pudo consultar el estado del servidor.": "Could not check the server status.",
    "Ejecutando…": "Running…",
    "Subiendo…": "Uploading…",
    "Listo": "Ready",
    "Archivo": "File",
    "Quitar": "Remove",
    "Solo se aceptan archivos .csv o .zip.": "Only .csv or .zip files are accepted.",
    "{n} archivo": "{n} file",
    "{n} archivos": "{n} files",
    "{n} más": "{n} more",
    "{name} ya está en la lista.": "{name} is already in the list.",
    "{n} archivo(s) descartado(s): {detail}": "{n} file(s) discarded: {detail}",
    "Subiendo {index} de {total}: {name}": "Uploading {index} of {total}: {name}",
    "{ready} listo(s), {failed} con error. Revisa el detalle en la lista.": "{ready} ready, {failed} failed. Check the details in the list.",
    "{ready} listo(s). {note}": "{ready} ready. {note}",
    "{ready} archivo(s) listos para procesar.": "{ready} file(s) ready to process.",
    "Archivo quitado de la lista.": "File removed from the list.",
    "Archivo eliminado.": "File deleted.",
    "El archivo ya no estaba en el servidor; se quitó de la lista.": "The file was no longer on the server; it was removed from the list.",
    "Sube al menos un archivo válido antes de ejecutar el ETL.": "Upload at least one valid file before running the ETL.",
    "El servidor no devolvió el trabajo.": "The server did not return the job.",
    "El servidor no devolvió el lote de archivos.": "The server did not return the file batch.",
    "El archivo supera el límite de subida del servidor. Usa el CLI del ETL o divide el CSV en partes más pequeñas.": "The file exceeds the server upload limit. Use the ETL CLI or split the CSV into smaller parts.",
    "El proceso terminó con un error.": "The process ended with an error.",
    "Error desconocido.": "Unknown error.",
    "Se perdió la conexión con el servidor. Recarga la página.": "The connection to the server was lost. Reload the page.",
    "Iniciando": "Starting",
    "Procesando…": "Processing…",
    "Datos cargados en Turso.": "Data loaded into Turso.",
    "Datos guardados en el staging local. Turso está desactivado (TURSO_ENABLED=false).": "Data saved to local staging. Turso is disabled (TURSO_ENABLED=false).",
    "Datos guardados en el staging local. No se sincronizó con Turso.": "Data saved to local staging. It was not synced to Turso.",
    "No se pudo completar la operación.": "The operation could not be completed.",
    "Revisa TURSO_DATABASE_URL y TURSO_AUTH_TOKEN en .env. Para trabajar sin Turso, deja TURSO_ENABLED=false.": "Check TURSO_DATABASE_URL and TURSO_AUTH_TOKEN in .env. To work without Turso, keep TURSO_ENABLED=false.",
    "Cada CSV debe incluir las columnas latitude, longitude y acq_date.": "Each CSV must include the latitude, longitude, and acq_date columns.",
    "No se encontró el staging local. Vuelve a ejecutar el ETL.": "Local staging was not found. Run the ETL again.",
    "Turso está desactivado: el resultado quedó en el staging local.": "Turso is disabled: the result stayed in local staging.",
    "Load (omitido)": "Load (skipped)",
    "Descubriendo archivos": "Discovering files",
    "Analizando fuentes": "Analyzing sources",
    "Fuentes analizadas": "Sources analyzed",
    "Agregando celdas-día": "Aggregating cell-days",
    "Agregación completa": "Aggregation complete",
    "Construyendo línea base": "Building baseline",
    "Evaluando anomalías": "Evaluating anomalies",
    "Anomalías evaluadas": "Anomalies evaluated",
    "Detectando fuentes no vegetales": "Detecting non-vegetation sources",
    "Escribiendo staging": "Writing staging",
    "Staging listo": "Staging ready",
    "Sincronizando Turso": "Syncing Turso",
    "Sincronizado": "Synced",
    "Completado": "Completed",
    "Extract": "Extract",
    "Transform": "Transform",
    "Baseline": "Baseline",
    "Load": "Load",
    "No hay archivos seleccionados": "No files selected",
    "Subir y procesar": "Upload and process",
    "Reintentar sincronización": "Retry sync",
    "Sincronizar Turso": "Sync Turso",
    "Cancelar": "Cancel",
    "Cerrar": "Close",
    "Descargar": "Download",
    "Eliminar": "Delete",
    "Error": "Error",
    "Aviso": "Notice",
    "Correcto": "Success",
    "Tamaño": "Size",
    "Estado del trabajo": "Job status",
    "Progreso": "Progress",
    "Registro": "Log",
    "Nuevo ETL": "New ETL",
    "Solo staging local": "Local staging only",
    "Publicar en Turso": "Publish to Turso",
    "Sincronizar": "Sync",
    "Seleccionar archivos": "Select files",
    "Arrastra o selecciona archivos": "Drag or select files",
    "No hay trabajos": "No jobs",
    "Volver": "Back",
    "Iniciar": "Start",
    "Detener": "Stop",
    "Subiendo": "Uploading",
    "Procesando": "Processing",
    "Fallido": "Failed",

    /* Plantillas dinámicas */
    "Vista mundial (por defecto)": "World view (default)",
    "año": "year",
    "años": "years",
    "en": "in",
    "Aún no hay años completos para calcular la media. Las barras claras son años incompletos.": "There are not enough complete years to calculate the mean. Light bars are incomplete years.",
    "Media de {n} años completos: {avg}. Año más activo: {year} ({value}). Las barras claras son años incompletos.": "Average of {n} complete years: {avg}. Most active year: {year} ({value}). Light bars are incomplete years.",
    "{value} % frente a la media": "{value} % vs. the mean",
    "{above} de {total} años quedaron por encima de la media. Mayor desviación: {year} ({sign}{value} %).": "{above} of {total} years were above the mean. Largest deviation: {year} ({sign}{value} %).",
    "Mediana ({n} {years})": "Median ({n} {years})",
    "Mes más activo según la mediana: {month} ({value}). La mediana usa {scope}.": "Most active month by median: {month} ({value}). The median uses {scope}.",
    "No se pudo generar el CSV.": "Could not generate the CSV.",
    "más de {value}": "more than {value}",
    "(mes incompleto)": "(incomplete month)",
    "Sin focos": "No hotspots",
    "día 1": "day 1",
    "días 1–{day}": "days 1–{day}",
    "Aún no hay años anteriores para comparar.": "There are not enough previous years to compare yet.",
    "Mediana del mismo tramo en {n} {years} ({first}–{last}). Medida: {metric}.": "Median for the same span over {n} {years} ({first}–{last}). Metric: {metric}.",
    "Igual que la mediana.": "Same as the median.",
    "{sign}{pct} % frente a la mediana.": "{sign}{pct} % vs. the median.",
    "La mediana es 0: no hay referencia para comparar.": "The median is 0: there is no reference to compare.",
    "Sin actividad, igual que la mediana.": "No activity, same as the median.",
    "No hay semanas críticas en esta área.": "There are no critical weeks in this area.",
    "{year} · semana {week}": "{year} · week {week}",
    "{critical} celdas-día críticas · {unusual} inusuales · {active} activas": "{critical} critical cell-days · {unusual} unusual · {active} active",
    "celdas-día activas": "active cell-days",
    "celdas-día críticas": "critical cell-days",
    "celdas-día inusuales": "unusual cell-days",
    "detecciones": "detections",
    "críticas": "critical",
    "inusuales": "unusual",
    "Completa los cuatro límites del área.": "Complete all four area bounds.",
    "Área no válida: el sur debe ser menor que el norte y el oeste menor que el este.": "Invalid area: south must be less than north and west less than east.",
    "con focos": "with hotspots",
    "Se dibujan las {shown} celdas más activas de {total}. Acerca el mapa para ver más detalle o reduce el área y las fechas.": "Showing the {shown} most active cells of {total}. Zoom in for more detail or reduce the area and dates.",
    "Vista agregada a {grid}° para mostrar toda el área. Acerca el mapa para ver más detalle.": "Aggregated view at {grid}° to show the entire area. Zoom in for more detail.",
    "No hay focos en esta área y rango de fechas.": "There are no hotspots in this area and date range.",
    "Celda": "Cell",
    "Último foco": "Last hotspot",

    /* Explain */
    "Explain": "Explain",
    "Explicar": "Explain",
    "Explain this chart": "Explain this chart",
    "Explicar este gráfico": "Explain this chart",
    "Loading...": "Loading...",
    "Cargando...": "Loading...",
    "Could not generate an explanation. Please try again.": "Could not generate an explanation. Please try again.",
    "No se pudo generar la explicación. Inténtalo de nuevo.": "Could not generate an explanation. Please try again.",
    "Too many requests. Try again later.": "Too many requests. Try again later.",
    "Demasiadas solicitudes. Inténtalo más tarde.": "Too many requests. Try again later.",
    "Explain is not configured.": "Explain is not configured.",
    "Explain no está configurado.": "Explain is not configured.",
    "Request failed.": "Request failed.",
    "La solicitud falló.": "Request failed.",

    /* Mensajes generales */
    "El mapa todavía no lee de Turso. Usa TURSO_ENABLED=false.": "The map does not read from Turso yet. Use TURSO_ENABLED=false.",
    "No se pudieron cargar los datos.": "Could not load the data.",
    "No hay datos en el modo activo.": "There is no data in the active mode.",
    "No se pudo conectar con Turso.": "Could not connect to Turso.",
    "Solicitud no válida.": "Invalid request.",
    "Demasiadas solicitudes.": "Too many requests."
  };

  const STORAGE_LOCALE = { en: 'en-US', es: 'es-EC' };
  let lang = readLang();

  function readLang() {
    try {
      const queryLang = new URLSearchParams(window.location.search || '').get('lang');
      if (SUPPORTED.includes(queryLang)) {
        window.localStorage.setItem(STORAGE_KEY, queryLang);
        return queryLang;
      }
    } catch (e) { /* sin URL o almacenamiento */ }
    try {
      const saved = window.localStorage.getItem(STORAGE_KEY);
      if (SUPPORTED.includes(saved)) return saved;
    } catch (e) { /* almacenamiento no disponible */ }
    return DEFAULT_LANG;
  }

  function locale() {
    return STORAGE_LOCALE[lang] || STORAGE_LOCALE[DEFAULT_LANG];
  }

  function t(text, vars) {
    const base = lang === 'en' ? (Object.prototype.hasOwnProperty.call(EN, text) ? EN[text] : text) : text;
    if (!vars) return base;
    return base.replace(/\{(\w+)\}/g, (match, key) => (
      Object.prototype.hasOwnProperty.call(vars, key) ? String(vars[key]) : match
    ));
  }

  function number(value, options) {
    const n = Number(value);
    if (!Number.isFinite(n)) return '—';
    return new Intl.NumberFormat(locale(), options || {}).format(n);
  }

  function decimal(value) {
    return number(value, { maximumFractionDigits: 1 });
  }

  function coordinate(value) {
    return number(value, { maximumFractionDigits: 3 });
  }

  function percent(value) {
    return number(value, { maximumFractionDigits: 1 }) + ' %';
  }

  function monthName(index, short = false) {
    const date = new Date(Date.UTC(2020, index, 1));
    const text = new Intl.DateTimeFormat(locale(), {
      month: short ? 'short' : 'long',
      timeZone: 'UTC',
    }).format(date);
    return text.charAt(0).toUpperCase() + text.slice(1);
  }

  function weekdayName(index, short = true) {
    const date = new Date(Date.UTC(2021, 0, 4 + index));
    const text = new Intl.DateTimeFormat(locale(), {
      weekday: short ? 'short' : 'long',
      timeZone: 'UTC',
    }).format(date);
    return text.charAt(0).toUpperCase() + text.slice(1);
  }

  function date(value, options) {
    if (!value) return '';
    const parsed = value instanceof Date ? value : new Date(value);
    if (Number.isNaN(parsed.getTime())) return String(value);
    return new Intl.DateTimeFormat(locale(), {
      timeZone: 'UTC',
      ...(options || { dateStyle: 'medium' }),
    }).format(parsed);
  }

  const originals = new WeakMap();
  const attrOriginals = new WeakMap();
  const ATTRS = ['placeholder', 'title', 'aria-label', 'alt'];
  let selectorBound = false;

  function translateTextNode(node) {
    const raw = node.nodeValue;
    if (!raw || !raw.trim()) return;
    const trimmed = raw.trim();
    const record = originals.get(node);
    let source;
    if (record && (raw === record.source || raw === record.translated)) {
      source = record.source;
    } else {
      source = trimmed;
    }
    const target = lang === 'en' && Object.prototype.hasOwnProperty.call(EN, source.replace(/\s+/g, ' '))
      ? EN[source.replace(/\s+/g, ' ')]
      : source;
    const start = raw.indexOf(trimmed);
    const output = raw.slice(0, start) + target + raw.slice(start + trimmed.length);
    if (output !== raw) node.nodeValue = output;
    originals.set(node, { source, translated: output });
  }

  function translateAttr(element, attr) {
    const raw = element.getAttribute(attr);
    if (!raw || !raw.trim()) return;
    const trimmed = raw.trim();
    let record = attrOriginals.get(element);
    if (!record) {
      record = {};
      attrOriginals.set(element, record);
    }
    let source = record[attr] || trimmed;
    if (raw !== trimmed && record[attr] && raw !== record[attr]) {
      source = trimmed;
    }
    const target = lang === 'en' && Object.prototype.hasOwnProperty.call(EN, source.replace(/\s+/g, ' '))
      ? EN[source.replace(/\s+/g, ' ')]
      : source;
    const start = raw.indexOf(trimmed);
    const output = raw.slice(0, start) + target + raw.slice(start + trimmed.length);
    if (output !== raw) element.setAttribute(attr, output);
    record[attr] = source;
  }

  function bindSelectors(root) {
    const scope = root && root.querySelectorAll ? root : document;
    scope.querySelectorAll('#lang-select').forEach((select) => {
      select.value = lang;
      if (select.dataset.i18nBound === '1') return;
      select.dataset.i18nBound = '1';
      select.addEventListener('change', (event) => {
        setLang(event.target.value);
      });
    });
    selectorBound = true;
  }

  function apply(root) {
    const scope = root || document.documentElement;
    if (!scope) return;
    const walker = document.createTreeWalker(scope, NodeFilter.SHOW_TEXT, {
      acceptNode(node) {
        const parent = node.parentElement;
        if (!parent) return NodeFilter.FILTER_REJECT;
        if (['SCRIPT', 'STYLE', 'NOSCRIPT', 'CODE', 'PRE', 'TEXTAREA'].includes(parent.tagName)) {
          return NodeFilter.FILTER_REJECT;
        }
        return NodeFilter.FILTER_ACCEPT;
      },
    });
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    nodes.forEach(translateTextNode);
    if (scope.querySelectorAll) {
      scope.querySelectorAll('*').forEach((element) => {
        ATTRS.forEach((attr) => translateAttr(element, attr));
      });
    }
    bindSelectors(scope);
  }

  function setLang(value) {
    if (!SUPPORTED.includes(value) || value === lang) return;
    try {
      window.localStorage.setItem(STORAGE_KEY, value);
    } catch (e) { /* almacenamiento no disponible */ }
    try {
      const url = new URL(window.location.href);
      url.searchParams.set('lang', value);
      window.location.replace(url.toString());
    } catch (e) {
      window.location.reload();
    }
  }

  // Evita el destello de español mientras se aplica el idioma guardado.
  try {
    const style = document.createElement('style');
    style.textContent = 'html.moviris-i18n-loading body{visibility:hidden!important}';
    document.head.appendChild(style);
    document.documentElement.classList.add('moviris-i18n-loading');
    document.documentElement.lang = lang;
  } catch (e) { /* sin DOM todavía */ }

  function finishApply() {
    try {
      apply(document.documentElement);
    } finally {
      document.documentElement.classList.remove('moviris-i18n-loading');
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', finishApply, { once: true });
    // Si una CDN externa retrasa DOMContentLoaded, no dejamos la página oculta.
    window.setTimeout(() => {
      if (document.documentElement.classList.contains('moviris-i18n-loading')) {
        finishApply();
      }
    }, 2500);
  } else {
    finishApply();
  }

  window.MovirisI18n = {
    t,
    apply,
    refresh: apply,
    setLang,
    number,
    decimal,
    coordinate,
    percent,
    monthName,
    weekdayName,
    date,
    locale,
    get lang() { return lang; },
    get supported() { return SUPPORTED.slice(); },
    dictionary: EN,
  };
})();
