-- Esquema de referencia de MOVIRIS (Turso / libSQL).
-- El ETL crea estas tablas automáticamente si no existen.

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
