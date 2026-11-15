#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MOVIRIS · ETL de focos de calor (NASA FIRMS -> Turso / libSQL)
==============================================================

Este módulo convierte los CSV crudos de FIRMS (MODIS + VIIRS, archivo y NRT)
en las tres tablas analíticas del esquema MOVIRIS:

    · fire_cells_daily      -> eventos armonizados por celda y día (malla 0,01°)
    · fire_baseline        -> línea base histórica por celda y semana ISO
    · non_vegetation_mask  -> fuentes persistentes no vegetales (volcán, fija, mar)

El proceso se puede ejecutar de dos formas:

    # Desde la raíz del proyecto (escribe staging y sincroniza Turso)
    python etl/etl.py --source hackathon

    # Solo staging local, sin tocar Turso
    python etl/etl.py --source hackathon --no-push

    # Reintentar la sincronización con el staging ya generado
    python etl/etl.py --push-only

Decisiones metodológicas (resumen)
----------------------------------
1. Malla: cada detección se asigna a una celda de 0,01°. Se guarda el CENTRO de
   la celda con 3 decimales (p. ej. -0,735), tal como indica el esquema.
2. Sensores: Terra/Aqua se unifican como MODIS; SNPP, N20 y N21 se conservan.
3. Confianza: MODIS (0-100) -> 0/1/2 con cortes 30 y 80; VIIRS (l/n/h) -> 0/1/2.
4. FRP normalizado: cada FRP se divide por la mediana histórica de su sensor y
   se suman las detecciones de la celda-día. Así MODIS y VIIRS son comparables.
5. is_nrt: una celda-día es NRT solo si TODAS sus detecciones vienen de archivos
   NRT. Si hay mezcla, gana el archivo definitivo (is_nrt = 0).
6. Línea base: para cada celda y semana ISO se usan las detecciones DIARIAS de
   los años históricos (se excluye el año más reciente del dataset para no
   contaminar la línea base con el período que se quiere evaluar).
7. Estado: critical si supera el p75 histórico y el z-score es >= 1 (o si el
   z-score es >= 2); unusual si supera la media; normal en el resto.
8. Máscara: se marcan celdas persistentes (>= 40 detecciones, >= 4 años y
   >= 15 semanas distintas). Se clasifican como volcán si están a <= 0,05° de
   un volcán conocido, como mar si caen sobre agua y como fuente fija si no.
   La máscara de tierra usa Natural Earth 1:10m rasterizada a 0,01° (incluida
   en este archivo como un blob comprimido, sin dependencias externas).
"""

from __future__ import annotations

import argparse
import base64
import csv
import datetime as dt
import json
import math
import os
import sqlite3
import sys
import time
import traceback
import zlib
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median, pstdev
from typing import Callable, Iterable, Sequence

# ---------------------------------------------------------------------------
# Rutas y constantes
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
ETL_DIR = Path(__file__).resolve().parent
DEFAULT_SOURCE = ROOT / "hackathon"
DEFAULT_STAGING = ROOT / "data" / "moviris_staging.db"
DEFAULT_BATCH_SIZE = 4000
GRID = 0.01

TABLES = ("fire_cells_daily", "fire_baseline", "non_vegetation_mask")

# Índices de la lista que representa una fila diaria. Mantener el orden es
# importante: se reutiliza durante toda la tubería para ahorrar memoria.
(
    LAT,
    LON,
    DATE,
    YEAR,
    MONTH,
    WEEK,
    DET,
    FRP_MAX,
    FRP_NORM,
    CONF,
    SENSORS,
    NRT_COUNT,
    TOTAL,
    IS_NRT,
    STATUS,
    Z,
) = range(16)

REQUIRED_COLUMNS = {"latitude", "longitude", "acq_date"}

# Mediana aproximada de FRP por sensor, usada solo si un sensor no tiene
# muestras suficientes para calcularla (p. ej. un CSV recortado).
DEFAULT_FRP_MEDIANS = {"MODIS": 12.0, "SNPP": 2.2, "N20": 2.4, "N21": 2.8}

# Volcanes activos relevantes para el recorte Ecuador / sur de Colombia /
# Galápagos. Se usan para clasificar la máscara de fuentes no vegetales.
VOLCANOES = [
    ("Cayambe", 0.029, -77.986),
    ("Reventador", -0.077, -77.656),
    ("Pichincha", -0.171, -78.598),
    ("Antisana", -0.481, -78.141),
    ("Cotopaxi", -0.677, -78.436),
    ("Sumaco", -0.538, -77.626),
    ("Tungurahua", -1.467, -78.442),
    ("El Altar", -1.666, -78.408),
    ("Sangay", -2.005, -78.341),
    ("Chimborazo", -1.469, -78.817),
    ("Galeras", 1.220, -77.360),
    ("Cumbal", 0.950, -77.870),
    ("Chiles", 0.820, -77.940),
    ("Azufral", 1.080, -77.680),
    ("Doña Juana", 1.470, -76.930),
    ("Fernandina", -0.370, -91.550),
    ("Wolf", 0.020, -91.350),
    ("Darwin", -0.180, -91.280),
    ("Alcedo", -0.430, -91.120),
    ("Sierra Negra", -0.830, -91.170),
    ("Cerro Azul", -0.910, -91.400),
    ("Santiago", -0.220, -90.770),
    ("Marchena", 0.350, -90.470),
    ("Pinta", 0.580, -90.750),
    ("Genovesa", 0.320, -89.960),
    ("San Cristóbal", -0.880, -89.510),
    ("Floreana", -1.300, -90.450),
    ("Española", -1.370, -89.680),
]

# Umbrales de la máscara de fuentes persistentes.
MASK_MIN_HITS = 40
MASK_MIN_YEARS = 4
MASK_MIN_WEEKS = 15
MASK_VOLCANO_RADIUS = 0.05
MASK_VOLCANO_MIN_HITS = 5

# ---------------------------------------------------------------------------
# Esquema (idéntico al de Turso; IF NOT EXISTS para inicializar bases nuevas)
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
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
"""

SCHEMA_STATEMENTS = [
    stmt.strip()
    for stmt in SCHEMA_SQL.split(";")
    if stmt.strip() and not stmt.strip().upper().startswith("PRAGMA")
]

TABLE_SPECS = {
    "fire_cells_daily": {
        "columns": [
            "cell_lat", "cell_lon", "acq_date", "year", "month", "week_of_year",
            "detections", "frp_max", "frp_sum_norm", "confidence_max", "sensors",
            "is_nrt", "status", "z_score",
        ],
        "pk": "cell_lat, cell_lon, acq_date",
    },
    "fire_baseline": {
        "columns": [
            "cell_lat", "cell_lon", "week_of_year", "years_count",
            "mean_detections", "std_detections", "mean_frp", "p75_detections",
        ],
        "pk": "cell_lat, cell_lon, week_of_year",
    },
    "non_vegetation_mask": {
        "columns": ["cell_lat", "cell_lon", "source_type", "hits"],
        "pk": "cell_lat, cell_lon, source_type",
    },
}

# ---------------------------------------------------------------------------
# Máscara de tierra (Natural Earth 1:10m rasterizada a 0,01°, zlib + base64)
# ---------------------------------------------------------------------------
# Cobertura: lon [-92.0, -74.4], lat [-5.6, 2.5]. Bit 1 = tierra. El raster se
# generó con relleno por scanline sobre ne_10m_land.geojson y se comprimió para
# que el componente siga siendo autocontenido (sin descargas en tiempo de
# ejecución). Las coordenadas fuera de la cobertura se consideran tierra para
# no marcar por error una fuente como "mar".

_MASK_LON0 = -92.0
_MASK_LAT0 = -5.6
_MASK_RES = 0.01
_MASK_W = 1760
_MASK_H = 810
_LAND_MASK_B64 = (
    "eNrt3d1y2zYURlHi/V+6ceoklkRS/CfOp7Uu2qkTSu0McXYA0e4wAByrQQesREDf0DcAeUPfAH0DfQP0DfQNkDfQN0Df0DcAeUPf"
    "APQNfQPkDfQN0DfQN0DeQN8AfUPfAOQNfQP0DfQNkDfQN0DeQN8AeUPfAOQNfQOQN/QNkDfQN0DeQN8AeQN9A+QNfQOQN/QNUDfQ"
    "N0DfQN8AeQN9A65Lm7qhb4CdG+gbIG+gb4C8gb4B+oa+Acgb+gbIG+gbIG+gb4C8gb4B+oa+Acgb+gZgcqJvgL6BvgEKB/oG6Bvo"
    "GyBw6BuAvqFvgLyBvgH6BvoGCBzoG6BvoG+AvqFvAPqGvgHyBvoGlA2c0qFvQGDj7OTQN8BRJegboG+gb4C+gb4B+oa+Aegb+gbI"
    "G+gboG+gb4C8gb4B+gaWJyBv6BuAvKFvgLyBvgHyBvoGyBvoG6Bu6BuAvqFvgLyBvgHyBvoG6BvoGyBvoG+AvqFvAPKGvgHyBvoG"
    "6BvoGyBvoG+AvKFvAPKGvgHyBvoGyBvoGyBvoG+AvIG+AfKGvgHIG/oG6BvoGyBvoG+AvIG+AfIG+gbIG/oG6BvoG6BvoG+AwoG+"
    "AQIH+gboG/oGoG/oGyBvoG+AvoG+AfoG+gboG+gboG/oG4C+oW+AwIG+AfoG+gboG+gbIG/oG4C+oW+AvoG+AfIG+gboG+gboG+g"
    "b4C+oW8AAoe+AQIH+gYIHOgboG+gb4DAgb4B+oa+AQIH+gboG+gboG+gb4C8gb4B+oa+Aegb+gboG+gbIG+gb4C+gb4B+gb6Bggc"
    "+gagb+gbIHCgb4C+gb4BAgf6Bggc+gYgcOgbIHCgb4DCgb4BAgf6Bigc6BsgcOgbgMChb4DAgb4BAgf6Bggc6Bugb6BvgMChbwAC"
    "h74BAgf6Bkgc6BsgcKBvgMChbwD6hr4BCBz6Bugb6BsgcKBvgMCBvgH6hr4BCBz6Bggc6Bugb6BvgMCBvgECh74BCBz6BiBw6Bsg"
    "cKBvgMCBvgECB/oGKBz6BqBw6BuAwKFvgMCBvgECB/oG6BvoG6Bv6BuAwKFvgL6BvgH6BvoG6BvoGyBw6BuAvqFvAAKHvgECB/oG"
    "CBzoG6BvoG+AwKFvAAqHvgEIHPoGCBzoG6BwoG+AwoGlBwgc+gagcOgbgMKhb4DAgb4BCgf6Bigc+gYgcOgbgMChb4DAgb4BAgf6"
    "Bggc6BsgcOgbgL6hbwACh74BAgf6Bugb6BsgcOgbgL6hbwASh74BSB36Bigc6BsgcKBvgL6hbwD6hr4BCBz6BqBv6BsgcKBvgL6B"
    "vgH6hr4B6Bv6BqBv6BsgcKBvQGLgJA59AyI3cAKHvgGpGziHlegbEBi45y0d6BsQeWYJ+gYIHOgbIHDoG4C+oW8AAoe+Aegb+gZ8"
    "auB0Dn0D9A30DagROAeV6BuQ2TeFQ9+AvMD9PKsEfQMy+va4lwN9AxLPKkHfAIFD3wD0DX0D0Df0DUDg0DcAfUPfAH0DfQP0DX0D"
    "0Df0DUDg0DcAfUPfAAQOfQP0DX0DEDj0DUDf0DcAgUPfAAQOfQPS06Vv6BsQuzMTOPQNiDx51Df0DQjMW5M39A34nMAZ3ugbULxv"
    "Td/QN0DfQN+Aun0TOPQN0Df0DaC/vjmgRN+AyL6NTirjG30D9A19A+iwb03f0DdA30DfgBp9Ezj0DdA30DegSN+avqFvwEf0TeDQ"
    "NyCgbzZw6BsQ2bemb+gb8AmBM8DRN8AGDn0DsIFD3wBs4NA3ABs49A3QN4FD34CPCFzTN/QNSOzb49wyxNE3IDFwhjj6BuT0rekb"
    "+gbUC9uKvgkc+gaU2ba97daKnR76BtDLoeR8utadZKJvAJ3kbfb0ceYy0Deg47o9zqW3E8sYR9+Aenl7/KV3V4K+AVXy9u+XF1wL"
    "+gbUydvyi0HfgA7btmImvX/OEn0D6KVui2fSkm8kQN8Aeslb+/+L6/omcOgb0Hfd/v5srmXXDgKHvgE1+jb/nQD6hr4BlfPWJn9Q"
    "yfg/CRz6BtTIW5v8KcozuQN9A7rP2/Tu7OFr+oa+AbXyNr07ew2cYY6+AWXyNv0NbvqGvgGV+zYXuNHYgb4BBfI2e0I51jrQN6BA"
    "3mafMbF9Q9+Aqnmb3MH9+dKGV0TfAG7P21Tgvr+y7SXRN4C78/bct8djSXlD34CaeXsK3MPHbtqGvgFl8/Y4p56/aIqjb0DRvP38"
    "rO15eBni6BtQNW/j3+Gmb+gbUDxv+oa+AYl5+/FUydPwMsPRN6Bw3vQNfQMS8zYWOH1D34DicZvsmxGOvgGF4zb6hIm+oW9A5bJN"
    "beDkDX0Dqsdt4oDSBEffgNp1G+2bAY6+AdXzNnZAaYCjb0D5vL1+P4C+oW9A/by9Bk7f0Degft1GppcBjr4BYW3TN/QNCM2bvqFv"
    "gL6hbwD6hr4B6Bv6BsibvqFvgL7NDy8DHH0DArdv+oa+AYl50zf0DYjLm76hb8CVebvsh3PpG/oGXJm3i8Kjb+gbcOHZ5GUnlfqG"
    "vgHX9e2ld/KGvgHF8za+ofN0CfoGlO7b1ImlvqFvQOSZpb6hb4DCLR9dxjf6BuQFTt/QNyAxcA4o0TcgMXD6hr4BoYEzv9E3wAYO"
    "fQMo0jeFQ9+AuL75GV3oG5DZt68BZoajb0Bg4PQNfQMi+yZw6BsQeD6pcOgbkNk3gUPfgMS8+RAOfQNC+wb6Bugb+gagb+gbgLyh"
    "b4DAgb4BCgf6Bugb6Bugb+gbgL6hbwD6hr4B+gb6Bugb6Bugb+gbgLyhbwD6hr4B+gb6Bugb6Bsgb6BvgL6hbwD6hr4B6Bv6Bsgb"
    "6Bugb6BvgL6hbwDyhr4B6Bv6Bugb6Bsgb6BvgL6BvgHyhr4ByBv6BiBv6Bugb6BvgL6BvgHyBvoG6Bv6BiBv6Bugb6BvgLyBvgH6"
    "BvoGyBv6BqBv6BuAvqFvgMCBvgECB/oGCBzoGyBw6BuAvqFvAPKGvgH6BvoG6BvoGyBw6BuAwKFvABqHvgH6BvoG6BvoG6BvoG+A"
    "vqFvAPqGvgHoG/oG6Bvo29FrzLABfUPfIleYaQP6hr4lri/TBgQOfUtcXIYNCBz6Jm+AvqFvZyyKg9eWQQP6hr51siLMBpA3COqb"
    "TRfoGwT2zUdmIG+Q1zePhIC8QeT+TeBA3iD+fFLgQN8gs28CB/IGec9P6hvIG0T2zZAAeQN9A+QNKvTNkAB5g5y+DcoG+gaJfQPk"
    "DfQN0DfQN0De0DcAfUPfAOQNfQPkDfQN0DfQN0De0DcAfUPfAOQNfQP0DfQN0DfQN0DeQN8AfUPfAOQNfQPQN/QN0DfQN0DgQN8A"
    "gYMz+qaagMBRvm82hoDAEdg3Z5+AwBHYNx/vAfpGYN88wAIIHJ/dN4EDgYPIvn2/idKBwEFa3zrbykktCBz6duyd29GqM33gusip"
    "HUX6dnlNz/szpfEDFyy6P0vPto7O+3bDdvHM4xLTBy5agc4t6bxvO9/vxqA0gYPuDlEgpW+39kTgQODQt/PuzP6WlXkDAoe+le6b"
    "j+BA4NC3s27MHteVcQP6hr614oEb9A30DX1L7JvAgcChb4EHlKP/BcYN6Bv6lriBM25A39C3IbBvCgf6hr4FHFBKHOgb+hYaOKeU"
    "IHDo29G3ZrcLzNABfeOz+zaE9k3gQN/48L5dF7gzuyNwoG/o2y2FO7k7HjIBfUPfjr5BV76+DRwIHFz2Udipbzzy+9sVS8zcAX3j"
    "4/u24xbd+tLnrzFzB/QNfdt8j25+4QsWmcEDAoe+bbxJd7zq+YvM3AF9Q9+23aW7XvP0ZWbugL6hb5tu030vd/pCM3dA4NC3LXfp"
    "7hc7b639/puxA/qGvr3eqXs3YO22wAECh77NbIDe3rX6Bugblfq28LY94I43FyAscJJH+b4d9Cc6cwGS+qZu6Ju8QWDglI1CfRv0"
    "DVjcN5OY8n3btfXTN8gMnN0bpfo2bP6pIPoGHxY4faNa34aNbyRw8JGnlFC0b8fe6gYC6Bv0cT557L1uIIC8QQ99G/QNUDci+rbn"
    "bfQN9A267Nve99E30Dfor2/730jcQN+gu74d8kbiBvIGffXtqHf6vkbfQN+gh74d/kb6BvoG9/ftxDfSN5A3OK1v7y46N6TyBvoG"
    "p/Tt3WWeegT0jXJ9W3ClvgH6Rqm+Lbu26Rsgb1TqW9vdNwsZ0De669vCa698UBOQN9A3QN7Qt+U3oeNJQN8o3Le2v28WMqBvBPbN"
    "Ogbkje761vQN0Dc+uW/yBugbgX074BFNCx4kDjroW9tyiDn7FpY7CBzU6NvKF7bcQeGgo76tfPWvX/FRHSBw3Nm3BRevfe19vQX0"
    "Da7o2/qX1jdA4Oi5b9vq5udUAvrG/X07IW/6BggcHezfpm7B+dtS3gCBo+/nJyfuwWFr3w78FwL0DY7JydN1h+fNQgeBgzv6Njz+"
    "JC2nk4C+kdK3Bffk1hvZKgd9gw76tvE15Q0QOHru29aXlDdA3yjYt60XWuEgcaBvgL5Bhb5Z3CBw0Pfzk+svs66Buf9xFnTx/OTa"
    "6yxq4Hs02MVRvW+DuAGOKan2+duKSy1kQODI6huAwqFvgMCBvgECB8f3zboEBA59AxA49A3QNzi/bz5+AwQOfQMQOPQNQODQN0Dg"
    "YHuPnn+3vgECR0Dfnn9/0zdA36jft5cL9A0QOOr37fmaEz7PAxA47u1bUzdA4Eg7nxQ3QOAIfL5E3gB9I6pv7+4yqxDQN2r2bfY+"
    "swgBgaNs3zw3CQgcmX0b9A1QOBL75sdyAfqGvgEIHJX7ZvUB+kbxvg3yBugbkX17vdcsPkDgKN+3kbvN2gP0jZS+DSP/zxwAfSOo"
    "b5YeoG8k9W3QN0DfSOwbgMChbwD6hr4B6Bv6Bugb6Bugb+gbgL6hbwDyhr4B6Bv6Bugb6Bugb+gbgL6hbxfdyxY0oG+k9c3eEtA3"
    "8vrm9BTQN/L65uNBQN8I7Nuefz05BH2DGn1rKy80BUDfIGz/pm+gb1Clb6uvNAVA36D/50usaeDvZBA5Yr4/wIIG/s0FmzgC+jZ4"
    "EhJwSElm3wD0DX0D9A30DZA39A1A3tA3AHlD3wD0DX0D5A30DdA39A1A3tA3AH1D3wD0DX0D0Df0DdA30DdA39A3AIFD3wAEDn0D"
    "0Df0DUDgqNY3cQX0jby+2TwC+kZe35yOAvKGvgEY1xQ5n9Q3QN+wfwPkDQr1zZIF9A19A/QNSvTNigXkjby+WbCAupH3/CSAuKFv"
    "gL6BvgHyBhYPoG/oG4C+oW8A+oa+Aegb+gboG+gboG/oG4C+oW8A+oa+Aegb+gYgcOgboG+gb4DAoW8A+oa+AQgc+gYgcOgb8LGB"
    "Ezr0DbCVA30DBA59A9A49A1A4tA3gAMKJ3zoGxCYOHlD34DAwMkb+gYkBk7f0DcgsXD6hr4B+oa+AdQInL6hb0DmDg70DVA49A2g"
    "ROKkDn0DEhOnb+gbkFi4r784skTfgPwTS/QNQOHQNwCBQ98ABA59AxA49A1A4NA3QODQN4CcwkmdvgHk7+bUTt8AnF2ibwASh74B"
    "CBz6BiBw6BvAtsAJnr4B6Bv6BlAjcE4s9Q0gMXD6pm8AgYEb9E3fAPQNfQOoELhB3/QNIC9wg77pG0Bc4F5PK9E3gMDTSvQNICxw"
    "GqdvAJknlfqgbwDOJtE3gBp9Uzp9A7B9Q98AivRtsI3TN4DAwNnP6RtAZN8UQt8AAgOnb/oGkLmDQ98A8gondPoGkBg4Ozl9A0gM"
    "nKNKfQMIDNyPk0oy+iZ5AI8nlegbgL7hfBJA4NA3AH1D3wD0Td8AkDd9AxA49A1A4NA3AH1D3wDkDX0DkDd9A0Dd9A1A39A3AH1D"
    "3wD0DX0D0Df0DUDf9A1A39A3gIS06Zu+Adi4oW8A6oa+Acgb+gagbugbgLrpG4C8oW8A8oa+Aegb+gagbwgcgL7JG4DAoW8AEoe+"
    "AQgc+gYgcOgbgMChbwD6pm8AAoe+Aegb+gYgcOgbgMChbwACp28ACJy+AQjcr+GpH/oGkBc4+zt9A0gLnPNLfQPICtyK80v0DaBG"
    "4dYcX6JvAGnHl+gbgL6hbwACh74B6Ju+ASBv+gaAvukbgL6hbwDahr4B6Bv6BqBv+gaAvukbgL6hbwD6hr4B6Bv6BnB+2fRN3wAi"
    "N24Cp28A+oa+AdToW9M3fQMI7Zt66BtAXN+avOkbQGDe0DcAfUPfAPQNfQOQN/QNQN/0DQB90zcAfUPfAOQNfQPQN/QNQN/QNwB9"
    "0zcA5E3fAPQNfQPQN/QNQN/QNwB90zcA9E3fAAQOfQPQN/QNQODQNwB9Q98ABE7fANA3fQPQN/QNQOHQNwCBQ98A9A19AxA4fQNA"
    "3/QNQODQNwB9Q98ABA59A9A3fQNA4PQNQODQNwB9Q98ABA59A9A39A1gd980Tt8AEgOnb/oGoG/oG0CNwOmbvgGk7uHQNwB9Q98A"
    "9A19A9A39A3guMAtS5wQ3uE/XXZe2g=="
)
_land_bits: bytes | None = None


def is_land(lat: float, lon: float) -> bool:
    """Devuelve True si la celda cae sobre tierra (o fuera de cobertura)."""
    global _land_bits
    if _land_bits is None:
        _land_bits = zlib.decompress(base64.b64decode(_LAND_MASK_B64))
    col = int(math.floor((lon - _MASK_LON0) / _MASK_RES))
    row = int(math.floor((lat - _MASK_LAT0) / _MASK_RES))
    if 0 <= col < _MASK_W and 0 <= row < _MASK_H:
        return bool(_land_bits[row * _MASK_W + col])
    return True


# ---------------------------------------------------------------------------
# Utilidades generales
# ---------------------------------------------------------------------------


class EtlError(RuntimeError):
    """Error controlado del proceso ETL (se muestra limpio en la UI)."""


def load_env(path: str | Path | None = None) -> dict[str, str]:
    """Carga .env sin dependencias externas. No pisa variables ya definidas."""
    env = dict(os.environ)
    env_path = Path(path) if path else ROOT / ".env"
    if env_path.exists():
        try:
            for raw in env_path.read_text(encoding="utf-8-sig").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key:
                    env.setdefault(key, value)
        except OSError:
            pass
    return env


def turso_enabled(env: dict[str, str] | None = None) -> bool:
    """Lee TURSO_ENABLED del entorno/.env. false => modo local."""
    values = env if env is not None else load_env()
    raw = str(values.get("TURSO_ENABLED", "true")).strip().lower()
    return raw not in {"0", "false", "no", "off", "disabled", "local"}


def turso_config(env: dict[str, str] | None = None) -> tuple[str, str]:
    """Devuelve (url_http, token) a partir del entorno."""
    env = env or load_env()
    url = (
        env.get("TURSO_DATABASE_URL")
        or env.get("TURSO_URL")
        or env.get("LIBSQL_URL")
        or ""
    ).strip()
    token = (
        env.get("TURSO_AUTH_TOKEN")
        or env.get("TURSO_TOKEN")
        or env.get("LIBSQL_AUTH_TOKEN")
        or ""
    ).strip()
    if not url:
        raise EtlError("Falta TURSO_DATABASE_URL en el archivo .env")
    if not token:
        raise EtlError("Falta TURSO_AUTH_TOKEN en el archivo .env")
    if url.startswith("libsql://"):
        url = "https://" + url[len("libsql://"):]
    elif url.startswith("wss://"):
        url = "https://" + url[len("wss://"):]
    return url.rstrip("/"), token


def _emit(progress: Callable[[dict], None] | None, stage: str, percent: float,
          message: str, **extra) -> None:
    if progress is None:
        return
    payload = {
        "stage": stage,
        "percent": max(0.0, min(100.0, round(percent, 1))),
        "message": message,
    }
    payload.update(extra)
    try:
        progress(payload)
    except Exception:
        # Un callback defectuoso no debe romper el ETL.
        pass


def _say(log: Callable[[str], None] | None, message: str) -> None:
    if log is not None:
        try:
            log(message)
        except Exception:
            pass


def discover_files(sources: Sequence[str | Path]) -> list[Path]:
    """Expande directorios/archivos y devuelve CSV únicos y ordenados."""
    found: list[Path] = []
    for source in sources:
        path = Path(source)
        if not path.is_absolute():
            path = (ROOT / path).resolve()
        if path.is_dir():
            found.extend(sorted(p for p in path.rglob("*.csv") if p.is_file()))
        elif path.is_file() and path.suffix.lower() == ".csv":
            found.append(path)
    unique: dict[str, Path] = {}
    for path in found:
        try:
            key = str(path.resolve()).lower()
        except OSError:
            key = str(path).lower()
        unique.setdefault(key, path)
    return list(unique.values())


def _lookup_for(fieldnames: Iterable[str] | None) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for field in fieldnames or []:
        if field is None:
            continue
        normalized = field.strip().lower().lstrip("\ufeff")
        lookup[normalized] = field
    return lookup


def _get(row: dict, lookup: dict[str, str], name: str, default: str = "") -> str:
    key = lookup.get(name)
    if key is None:
        return default
    value = row.get(key, default)
    return default if value is None else value


def is_nrt_path(path: Path) -> bool:
    return "nrt" in path.stem.lower()


def sensor_key(satellite: str | None, instrument: str | None) -> str:
    sat = (satellite or "").strip().upper()
    inst = (instrument or "").strip().upper()
    if sat in {"TERRA", "AQUA", "MODIS"} or (not sat and inst == "MODIS"):
        return "MODIS"
    if sat in {"SNPP", "NPP", "S-NPP", "SUOMI NPP", "SUOMI-NPP"}:
        return "SNPP"
    if sat in {"N20", "NOAA-20", "NOAA20", "NOAA 20", "J1"}:
        return "N20"
    if sat in {"N21", "NOAA-21", "NOAA21", "NOAA 21", "J2"}:
        return "N21"
    if sat in {"N19", "NOAA-19", "NOAA19", "NOAA 19"}:
        return "N19"
    return sat or inst or "UNKNOWN"


def parse_confidence(raw: str | None, sensor: str) -> int:
    """Normaliza la confianza de FIRMS a 0 (baja), 1 (nominal) o 2 (alta)."""
    text = str(raw or "").strip().lower().replace("nrt", "").strip()
    if text in {"l", "low", "baja"}:
        return 0
    if text in {"n", "nominal", "media"}:
        return 1
    if text in {"h", "high", "alta"}:
        return 2
    try:
        value = float(text)
    except (TypeError, ValueError):
        return 0
    if not math.isfinite(value):
        return 0
    if sensor == "MODIS":
        if value >= 80:
            return 2
        if value >= 30:
            return 1
        return 0
    if value <= 2.001:
        return max(0, min(2, int(round(value))))
    if value >= 80:
        return 2
    if value >= 30:
        return 1
    return 0


def _parse_row(raw: dict, lookup: dict[str, str]) -> tuple | None:
    """Devuelve (lat, lon, fecha, frp, sensor, confianza) o None si es inválida."""
    try:
        lat = float(_get(raw, lookup, "latitude"))
        lon = float(_get(raw, lookup, "longitude"))
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(lat) and math.isfinite(lon)):
        return None
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return None
    date_text = str(_get(raw, lookup, "acq_date")).strip()[:10]
    try:
        date = dt.date.fromisoformat(date_text)
    except ValueError:
        return None
    frp: float | None = None
    frp_text = str(_get(raw, lookup, "frp")).strip()
    if frp_text:
        try:
            candidate = float(frp_text)
            if math.isfinite(candidate) and candidate >= 0:
                frp = candidate
        except ValueError:
            pass
    sensor = sensor_key(_get(raw, lookup, "satellite"), _get(raw, lookup, "instrument"))
    confidence = parse_confidence(_get(raw, lookup, "confidence"), sensor)
    return lat, lon, date, frp, sensor, confidence


def cell_center(value: float) -> float:
    """Centro de la celda de 0,01° que contiene la coordenada."""
    return round((math.floor(value / GRID) + 0.5) * GRID, 3)


def percentile(values: Sequence[float], fraction: float) -> float:
    """Percentil con interpolación lineal (equivalente al p75 de numpy)."""
    ordered = sorted(values)
    if not ordered:
        return 0.0
    if len(ordered) == 1:
        return float(ordered[0])
    position = (len(ordered) - 1) * fraction
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return float(ordered[lower])
    weight = position - lower
    return float(ordered[lower] + (ordered[upper] - ordered[lower]) * weight)


def _nearest_volcano(lat: float, lon: float) -> tuple[float, str] | None:
    best: tuple[float, str] | None = None
    cos_lat = math.cos(math.radians(lat))
    for name, vlat, vlon in VOLCANOES:
        dx = (lon - vlon) * cos_lat
        dy = lat - vlat
        distance = math.hypot(dx, dy)
        if best is None or distance < best[0]:
            best = (distance, name)
    return best


def _sorted_sensors(sensors: Iterable[str]) -> str:
    order = {"MODIS": 0, "SNPP": 1, "N20": 2, "N21": 3, "N19": 4}
    return ",".join(sorted(set(sensors), key=lambda s: (order.get(s, 99), s)))


# ---------------------------------------------------------------------------
# Fase 1: escaneo de sensores y FRP
# ---------------------------------------------------------------------------


def scan_sources(
    files: Sequence[Path],
    include_nrt: bool,
    progress: Callable[[dict], None] | None,
    log: Callable[[str], None] | None,
) -> tuple[list[Path], int, dict[str, float], str | None, str | None]:
    sensor_frp: dict[str, list[float]] = defaultdict(list)
    sensor_counts: Counter[str] = Counter()
    valid_files: list[Path] = []
    total_rows = 0
    invalid_rows = 0
    min_date: dt.date | None = None
    max_date: dt.date | None = None
    total_files = max(1, len(files))

    for index, path in enumerate(files):
        if is_nrt_path(path) and not include_nrt:
            _say(log, f"Omitido por NRT desactivado: {path.name}")
            continue
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                lookup = _lookup_for(reader.fieldnames)
                missing = REQUIRED_COLUMNS - set(lookup)
                if missing:
                    _say(log, f"Omitido {path.name}: faltan columnas {sorted(missing)}")
                    continue
                file_rows = 0
                for raw in reader:
                    parsed = _parse_row(raw, lookup)
                    if parsed is None:
                        invalid_rows += 1
                        continue
                    lat, lon, date, frp, sensor, _confidence = parsed
                    del lat, lon
                    sensor_counts[sensor] += 1
                    if frp is not None and frp > 0:
                        sensor_frp[sensor].append(frp)
                    if min_date is None or date < min_date:
                        min_date = date
                    if max_date is None or date > max_date:
                        max_date = date
                    file_rows += 1
        except (OSError, UnicodeDecodeError, csv.Error) as exc:
            _say(log, f"Error leyendo {path.name}: {exc}")
            continue
        if file_rows == 0:
            _say(log, f"Sin filas válidas: {path.name}")
            continue
        valid_files.append(path)
        total_rows += file_rows
        _say(log, f"Leído {path.name}: {file_rows:,} detecciones")
        _emit(
            progress,
            "Analizando fuentes",
            4 + 16 * (index + 1) / total_files,
            f"{index + 1}/{len(files)} archivos · {total_rows:,} detecciones",
        )

    if not valid_files or total_rows == 0:
        raise EtlError("No se encontraron detecciones válidas en los CSV seleccionados.")

    # Mediana de FRP por sensor para normalizar escalas MODIS/VIIRS.
    all_samples: list[float] = []
    for values in sensor_frp.values():
        all_samples.extend(values)
    fallback = median(all_samples) if all_samples else 1.0
    if fallback <= 0:
        fallback = 1.0
    factors: dict[str, float] = {}
    for sensor in sensor_counts:
        values = sensor_frp.get(sensor) or []
        if len(values) >= 100:
            factor = median(values)
        else:
            factor = DEFAULT_FRP_MEDIANS.get(sensor, fallback)
        if not factor or not math.isfinite(factor) or factor <= 0:
            factor = fallback
        factors[sensor] = round(float(factor), 4)
        _say(
            log,
            f"Sensor {sensor}: {sensor_counts[sensor]:,} detecciones · "
            f"FRP mediana {factors[sensor]:.2f} MW",
        )
    if invalid_rows:
        _say(log, f"Filas inválidas descartadas: {invalid_rows:,}")

    return (
        valid_files,
        total_rows,
        factors,
        min_date.isoformat() if min_date else None,
        max_date.isoformat() if max_date else None,
    )


# ---------------------------------------------------------------------------
# Fase 2: agregación celda-día
# ---------------------------------------------------------------------------


def aggregate_rows(
    files: Sequence[Path],
    include_nrt: bool,
    factors: dict[str, float],
    total_rows: int,
    progress: Callable[[dict], None] | None,
    log: Callable[[str], None] | None,
) -> dict[tuple[float, float, str], list]:
    daily: dict[tuple[float, float, str], list] = {}
    date_cache: dict[str, tuple[int, int, int]] = {}
    processed = 0
    invalid = 0
    last_emit = 0.0
    denominator = max(1, total_rows)

    for path in files:
        if is_nrt_path(path) and not include_nrt:
            continue
        nrt_file = is_nrt_path(path)
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                lookup = _lookup_for(reader.fieldnames)
                if REQUIRED_COLUMNS - set(lookup):
                    continue
                for raw in reader:
                    parsed = _parse_row(raw, lookup)
                    if parsed is None:
                        invalid += 1
                        continue
                    lat, lon, date, frp, sensor, confidence = parsed
                    iso = date.isoformat()
                    info = date_cache.get(iso)
                    if info is None:
                        info = (date.year, date.month, date.isocalendar()[1])
                        date_cache[iso] = info
                    key = (cell_center(lat), cell_center(lon), iso)
                    row = daily.get(key)
                    if row is None:
                        row = [
                            key[0], key[1], iso, info[0], info[1], info[2],
                            0, None, 0.0, 0, set(), 0, 0, 0, None, None,
                        ]
                        daily[key] = row
                    row[DET] += 1
                    row[TOTAL] += 1
                    if nrt_file:
                        row[NRT_COUNT] += 1
                    if frp is not None:
                        if row[FRP_MAX] is None or frp > row[FRP_MAX]:
                            row[FRP_MAX] = frp
                        row[FRP_NORM] += frp / factors.get(sensor, 1.0)
                    if confidence > row[CONF]:
                        row[CONF] = confidence
                    row[SENSORS].add(sensor)
                    processed += 1
                    now = time.monotonic()
                    if now - last_emit >= 0.6:
                        last_emit = now
                        _emit(
                            progress,
                            "Agregando celdas-día",
                            20 + 25 * processed / denominator,
                            f"{processed:,}/{total_rows:,} detecciones",
                        )
        except (OSError, UnicodeDecodeError, csv.Error) as exc:
            _say(log, f"Error agregando {path.name}: {exc}")

    if not daily:
        raise EtlError("La agregación no produjo ninguna celda-día.")

    # Cierre de la agregación: sensores, is_nrt y redondeos.
    for row in daily.values():
        row[IS_NRT] = 1 if (row[NRT_COUNT] and row[NRT_COUNT] == row[TOTAL]) else 0
        row[SENSORS] = _sorted_sensors(row[SENSORS])
        row[FRP_NORM] = round(row[FRP_NORM], 4)
        row[FRP_MAX] = round(row[FRP_MAX], 3) if row[FRP_MAX] is not None else None

    if invalid:
        _say(log, f"Filas inválidas durante la agregación: {invalid:,}")
    _say(log, f"Celdas-día generadas: {len(daily):,}")
    return daily


# ---------------------------------------------------------------------------
# Fase 3: línea base y scoring
# ---------------------------------------------------------------------------


def build_baseline(
    daily: dict[tuple[float, float, str], list],
    exclude_current_year: bool,
    progress: Callable[[dict], None] | None,
    log: Callable[[str], None] | None,
) -> tuple[dict[tuple[float, float, int], tuple], int | None]:
    years = {row[YEAR] for row in daily.values()}
    excluded_year: int | None = None
    if exclude_current_year and len(years) > 1:
        excluded_year = max(years)

    weekly: dict[tuple[float, float, int], list] = {}
    for row in daily.values():
        if excluded_year is not None and row[YEAR] == excluded_year:
            continue
        key = (row[LAT], row[LON], row[WEEK])
        bucket = weekly.get(key)
        if bucket is None:
            bucket = weekly[key] = [set(), [], []]
        bucket[0].add(row[YEAR])
        bucket[1].append(row[DET])
        if row[FRP_MAX] is not None:
            bucket[2].append(row[FRP_MAX])

    if not weekly:
        _say(log, "Sin datos históricos suficientes: línea base vacía.")
        return {}, excluded_year

    baseline: dict[tuple[float, float, int], tuple] = {}
    total = max(1, len(weekly))
    for index, (key, bucket) in enumerate(weekly.items()):
        detections = bucket[1]
        n = len(detections)
        if n == 0:
            continue
        mean = sum(detections) / n
        std = pstdev(detections) if n > 1 else 0.0
        p75 = percentile(detections, 0.75)
        mean_frp = (sum(bucket[2]) / len(bucket[2])) if bucket[2] else None
        baseline[key] = (
            len(bucket[0]),
            round(mean, 3),
            round(std, 3),
            round(mean_frp, 3) if mean_frp is not None else None,
            round(p75, 3),
        )
        if index % 20000 == 0:
            _emit(
                progress,
                "Construyendo línea base",
                45 + 15 * index / total,
                f"{index:,}/{total:,} celdas-semana",
            )

    if excluded_year is not None:
        _say(
            log,
            f"Línea base calculada sin {excluded_year} "
            f"({len(baseline):,} celdas-semana).",
        )
    else:
        _say(log, f"Línea base calculada con todos los años ({len(baseline):,} filas).")
    return baseline, excluded_year


def score_daily(
    daily: dict[tuple[float, float, str], list],
    baseline: dict[tuple[float, float, int], tuple],
    progress: Callable[[dict], None] | None,
    log: Callable[[str], None] | None,
) -> Counter[str]:
    counts: Counter[str] = Counter()
    total = max(1, len(daily))
    for index, row in enumerate(daily.values()):
        detections = row[DET]
        base = baseline.get((row[LAT], row[LON], row[WEEK]))
        if base is None:
            row[STATUS] = "unusual" if detections >= 3 else "normal"
            row[Z] = None
            counts[row[STATUS]] += 1
            continue
        n, mean, std, _mean_frp, p75 = base
        z_value: float | None = None
        if n >= 2 and std > 1e-9:
            raw_z = (detections - mean) / std
            z_value = round(max(-99.0, min(99.0, raw_z)), 2)
        row[Z] = z_value
        is_critical = detections > p75 and (z_value is None or z_value >= 1.0)
        if not is_critical and z_value is not None and z_value >= 2.0 and detections > mean:
            is_critical = True
        if is_critical:
            row[STATUS] = "critical"
        elif detections > mean:
            row[STATUS] = "unusual"
        else:
            row[STATUS] = "normal"
        counts[row[STATUS]] += 1
        if index % 40000 == 0:
            _emit(
                progress,
                "Evaluando anomalías",
                60 + 5 * index / total,
                f"{index:,}/{total:,} celdas-día",
            )
    _say(
        log,
        "Estados: "
        f"{counts.get('critical', 0):,} críticos · "
        f"{counts.get('unusual', 0):,} inusuales · "
        f"{counts.get('normal', 0):,} normales",
    )
    return counts


# ---------------------------------------------------------------------------
# Fase 4: máscara de fuentes no vegetales
# ---------------------------------------------------------------------------


def build_mask(
    daily: dict[tuple[float, float, str], list],
    progress: Callable[[dict], None] | None,
    log: Callable[[str], None] | None,
) -> list[tuple[float, float, int, int]]:
    cells: dict[tuple[float, float], list] = {}
    for row in daily.values():
        key = (row[LAT], row[LON])
        stats = cells.get(key)
        if stats is None:
            stats = cells[key] = [0, set(), set()]
        stats[0] += row[DET]
        stats[1].add(row[YEAR])
        stats[2].add(row[WEEK])

    mask: list[tuple[float, float, int, int]] = []
    type_counts: Counter[int] = Counter()
    total = max(1, len(cells))
    for index, ((lat, lon), (hits, years, weeks)) in enumerate(cells.items()):
        nearest = _nearest_volcano(lat, lon) if hits >= MASK_VOLCANO_MIN_HITS else None
        if nearest and nearest[0] <= MASK_VOLCANO_RADIUS:
            mask.append((lat, lon, 1, hits))
            type_counts[1] += 1
        elif (
            hits >= MASK_MIN_HITS
            and len(years) >= MASK_MIN_YEARS
            and len(weeks) >= MASK_MIN_WEEKS
        ):
            source_type = 2 if is_land(lat, lon) else 3
            mask.append((lat, lon, source_type, hits))
            type_counts[source_type] += 1
        if index % 20000 == 0:
            _emit(
                progress,
                "Detectando fuentes no vegetales",
                65 + 7 * index / total,
                f"{index:,}/{total:,} celdas evaluadas",
            )

    _say(
        log,
        "Máscara no vegetal: "
        f"{type_counts.get(1, 0):,} volcanes · "
        f"{type_counts.get(2, 0):,} fuentes fijas · "
        f"{type_counts.get(3, 0):,} mar",
    )
    return mask


# ---------------------------------------------------------------------------
# Fase 5: staging SQLite
# ---------------------------------------------------------------------------


def write_staging(
    staging_path: Path,
    daily: dict[tuple[float, float, str], list],
    baseline: dict[tuple[float, float, int], tuple],
    mask: list[tuple[float, float, int, int]],
    progress: Callable[[dict], None] | None,
    log: Callable[[str], None] | None,
) -> dict[str, int]:
    staging_path = Path(staging_path)
    staging_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = staging_path.with_name(staging_path.name + ".tmp")
    if temp_path.exists():
        try:
            temp_path.unlink()
        except OSError:
            pass

    counts = {
        "fire_cells_daily": len(daily),
        "fire_baseline": len(baseline),
        "non_vegetation_mask": len(mask),
    }

    connection = sqlite3.connect(str(temp_path))
    try:
        connection.execute("PRAGMA journal_mode = OFF")
        connection.execute("PRAGMA synchronous = OFF")
        connection.execute("PRAGMA temp_store = MEMORY")
        connection.executescript(SCHEMA_SQL)
        connection.execute("BEGIN")
        connection.executemany(
            "INSERT INTO fire_cells_daily (cell_lat, cell_lon, acq_date, year, month, "
            "week_of_year, detections, frp_max, frp_sum_norm, confidence_max, sensors, "
            "is_nrt, status, z_score) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                (
                    row[LAT], row[LON], row[DATE], row[YEAR], row[MONTH], row[WEEK],
                    row[DET], row[FRP_MAX], row[FRP_NORM], row[CONF], row[SENSORS],
                    row[IS_NRT], row[STATUS], row[Z],
                )
                for row in daily.values()
            ),
        )
        _emit(progress, "Escribiendo staging", 74, f"{counts['fire_cells_daily']:,} celdas-día")
        connection.executemany(
            "INSERT INTO fire_baseline (cell_lat, cell_lon, week_of_year, years_count, "
            "mean_detections, std_detections, mean_frp, p75_detections) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (
                (lat, lon, week, n, mean, std, mean_frp, p75)
                for (lat, lon, week), (n, mean, std, mean_frp, p75) in baseline.items()
            ),
        )
        _emit(progress, "Escribiendo staging", 78, f"{counts['fire_baseline']:,} celdas-semana")
        connection.executemany(
            "INSERT INTO non_vegetation_mask (cell_lat, cell_lon, source_type, hits) "
            "VALUES (?,?,?,?)",
            mask,
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    try:
        os.replace(temp_path, staging_path)
    except OSError:
        # Si el archivo está bloqueado por otra lectura, dejamos el temporal.
        raise EtlError(
            f"No se pudo reemplazar el staging {staging_path}. "
            "Cierra cualquier proceso que lo esté usando e inténtalo de nuevo."
        )
    _say(
        log,
        f"Staging guardado en {staging_path} "
        f"({sum(counts.values()):,} filas).",
    )
    _emit(progress, "Staging listo", 82, staging_path.name)
    return counts


# ---------------------------------------------------------------------------
# Fase 6: sincronización con Turso
# ---------------------------------------------------------------------------


def _batch_with_retry(client, statements: list, attempts: int = 3) -> None:
    for attempt in range(1, attempts + 1):
        try:
            client.batch(statements)
            return
        except Exception:
            if attempt >= attempts:
                raise
            time.sleep(2 ** (attempt - 1))


def push_staging(
    staging_path: str | Path | None = None,
    *,
    replace: bool = True,
    batch_size: int = DEFAULT_BATCH_SIZE,
    progress: Callable[[dict], None] | None = None,
    log: Callable[[str], None] | None = None,
    env: dict[str, str] | None = None,
) -> dict:
    """Sube el staging local a Turso. Devuelve conteos y filas enviadas."""
    staging_path = Path(staging_path or DEFAULT_STAGING)
    if not staging_path.exists():
        raise EtlError(f"No existe el staging local: {staging_path}")
    env = env or load_env()
    if not turso_enabled(env):
        raise EtlError(
            "Turso está desactivado (TURSO_ENABLED=false). "
            "Cambia la opción a true en .env para sincronizar."
        )
    try:
        import libsql_client
    except ImportError as exc:  # pragma: no cover
        raise EtlError(
            "Falta la dependencia libsql-client. Ejecuta: pip install -r requirements.txt"
        ) from exc

    url, token = turso_config(env)
    _say(log, f"Conectando con Turso ({url.split('//', 1)[-1].split('.')[0]})...")

    connection = sqlite3.connect(str(staging_path))
    try:
        counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in TABLES
        }
        total = max(1, sum(counts.values()))
        pushed = 0
        client = libsql_client.create_client_sync(url, auth_token=token)
        try:
            for statement in SCHEMA_STATEMENTS:
                client.execute(statement)
            if replace:
                for table in TABLES:
                    client.execute(f"DELETE FROM {table}")
                _say(log, "Tablas destino vaciadas (modo reemplazo).")

            for table in TABLES:
                spec = TABLE_SPECS[table]
                columns = ", ".join(spec["columns"])
                placeholders = ", ".join("?" for _ in spec["columns"])
                verb = "INSERT OR REPLACE" if not replace else "INSERT"
                insert_sql = f"{verb} INTO {table} ({columns}) VALUES ({placeholders})"
                cursor = connection.execute(f"SELECT {columns} FROM {table}")
                table_pushed = 0
                while True:
                    chunk = cursor.fetchmany(batch_size)
                    if not chunk:
                        break
                    statements = [
                        libsql_client.Statement(insert_sql, tuple(row)) for row in chunk
                    ]
                    _batch_with_retry(client, statements)
                    pushed += len(chunk)
                    table_pushed += len(chunk)
                    if table_pushed % (batch_size * 4) == 0 or pushed == total:
                        _say(log, f"{table}: {table_pushed:,}/{counts[table]:,} filas")
                        _emit(
                            progress,
                            "Sincronizando Turso",
                            100 * pushed / total,
                            f"{pushed:,}/{total:,} filas enviadas",
                            pushed=pushed,
                        )
                _say(log, f"{table}: {table_pushed:,} filas sincronizadas.")

            if replace:
                for table, expected in counts.items():
                    result = client.execute(f"SELECT COUNT(*) FROM {table}")
                    actual = result.rows[0][0] if result.rows else 0
                    if actual != expected:
                        raise EtlError(
                            f"Verificación fallida en {table}: "
                            f"Turso tiene {actual:,} filas y el staging {expected:,}."
                        )
                _say(log, "Verificación de conteos en Turso: OK.")
        finally:
            client.close()
    finally:
        connection.close()

    _emit(progress, "Sincronizado", 100, f"{pushed:,} filas en Turso", pushed=pushed)
    return {"pushed": pushed, "counts": counts}


# ---------------------------------------------------------------------------
# Orquestador
# ---------------------------------------------------------------------------


def run_etl(
    sources: Sequence[str | Path] | None = None,
    *,
    include_nrt: bool = True,
    exclude_current_year: bool = True,
    replace: bool = True,
    push: bool = True,
    staging_path: str | Path | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    progress: Callable[[dict], None] | None = None,
    log: Callable[[str], None] | None = None,
    env: dict[str, str] | None = None,
) -> dict:
    """Ejecuta la tubería completa. Devuelve un resumen serializable a JSON."""
    started = time.time()
    env = env or load_env()
    turso_available = turso_enabled(env)
    requested_push = bool(push)
    push = requested_push and turso_available
    staging = Path(staging_path or DEFAULT_STAGING)
    _emit(progress, "Descubriendo archivos", 1, "Buscando CSV de FIRMS...")

    files = discover_files(sources or [DEFAULT_SOURCE])
    if not files:
        raise EtlError(
            "No se encontraron archivos CSV. Revisa la carpeta hackathon o sube archivos."
        )
    _say(log, f"Archivos encontrados: {len(files)}")
    for path in files:
        _say(log, f"  · {path.name} ({path.stat().st_size / 1_048_576:.1f} MB)")

    valid_files, total_rows, factors, min_date, max_date = scan_sources(
        files, include_nrt, progress, log
    )
    _emit(progress, "Fuentes analizadas", 20, f"{total_rows:,} detecciones", total_rows=total_rows)

    daily = aggregate_rows(valid_files, include_nrt, factors, total_rows, progress, log)
    _emit(progress, "Agregación completa", 45, f"{len(daily):,} celdas-día")

    baseline, excluded_year = build_baseline(
        daily, exclude_current_year, progress, log
    )
    status_counts = score_daily(daily, baseline, progress, log)
    _emit(progress, "Anomalías evaluadas", 65, "Calculando máscara no vegetal...")

    mask = build_mask(daily, progress, log)
    staging_counts = write_staging(staging, daily, baseline, mask, progress, log)

    cells = {(row[LAT], row[LON]) for row in daily.values()}
    summary = {
        "files": len(valid_files),
        "detections": total_rows,
        "daily_rows": len(daily),
        "cells": len(cells),
        "baseline_rows": len(baseline),
        "mask_rows": len(mask),
        "status": {
            "critical": status_counts.get("critical", 0),
            "unusual": status_counts.get("unusual", 0),
            "normal": status_counts.get("normal", 0),
        },
        "measured_range": {"from": min_date, "to": max_date},
        "excluded_baseline_year": excluded_year,
        "sensor_frp_factors": factors,
        "staging_path": str(staging),
        "staging_rows": sum(staging_counts.values()),
        "pushed": False,
        "mode": "turso" if turso_available else "local",
        "turso_enabled": turso_available,
        "elapsed_seconds": round(time.time() - started, 1),
    }
    _say(
        log,
        f"ETL local completado en {summary['elapsed_seconds']:.1f}s · "
        f"{summary['detections']:,} detecciones · {summary['cells']:,} celdas",
    )

    if push:
        _emit(progress, "Sincronizando Turso", 82, "Preparando lotes...")

        def push_progress(payload: dict) -> None:
            # La sincronización reporta 0-100; se reescala al tramo 82-100 para
            # que la barra global no retroceda.
            inner = float(payload.get("percent") or 0.0)
            _emit(
                progress,
                str(payload.get("stage") or "Sincronizando Turso"),
                82 + 18 * max(0.0, min(100.0, inner)) / 100,
                str(payload.get("message") or ""),
                pushed=payload.get("pushed"),
            )

        push_result = push_staging(
            staging,
            replace=replace,
            batch_size=batch_size,
            progress=push_progress,
            log=log,
            env=env,
        )
        summary["pushed"] = True
        summary["pushed_rows"] = push_result["pushed"]
        _say(log, f"Turso actualizado: {push_result['pushed']:,} filas.")
    else:
        if requested_push and not turso_available:
            _say(
                log,
                "Turso desactivado (TURSO_ENABLED=false): "
                "resultado solo en el staging local.",
            )
        else:
            _say(log, "Sincronización con Turso omitida.")
        summary["pushed_rows"] = 0

    summary["elapsed_seconds"] = round(time.time() - started, 1)
    _emit(
        progress,
        "Completado",
        100,
        "Proceso ETL finalizado correctamente.",
        summary=summary,
    )
    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _cli_progress(payload: dict) -> None:
    print(
        f"[{payload.get('percent', 0):5.1f}%] "
        f"{payload.get('stage', '')}: {payload.get('message', '')}",
        flush=True,
    )


def _cli_log(message: str) -> None:
    stamp = dt.datetime.now().strftime("%H:%M:%S")
    print(f"[{stamp}] {message}", flush=True)


def _configure_console() -> None:
    if sys.platform != "win32":
        return
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass


def main(argv: Sequence[str] | None = None) -> int:
    _configure_console()
    parser = argparse.ArgumentParser(
        description="MOVIRIS · ETL de focos de calor FIRMS -> Turso"
    )
    parser.add_argument(
        "--source",
        action="append",
        default=None,
        help="Archivo o carpeta CSV (repetible). Por defecto: hackathon/",
    )
    parser.add_argument("--no-nrt", action="store_true", help="Excluir archivos NRT")
    parser.add_argument(
        "--include-current-year",
        action="store_true",
        help="Incluir el año más reciente en la línea base",
    )
    parser.add_argument(
        "--no-push", action="store_true", help="Solo generar el staging local"
    )
    parser.add_argument(
        "--no-replace",
        action="store_true",
        help="No vaciar las tablas de Turso antes de insertar",
    )
    parser.add_argument(
        "--push-only",
        action="store_true",
        help="Sincronizar el staging existente sin recalcular el ETL",
    )
    parser.add_argument(
        "--staging",
        default=str(DEFAULT_STAGING),
        help="Ruta del SQLite de staging",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help="Filas por lote al subir a Turso",
    )
    parser.add_argument(
        "--quiet", action="store_true", help="No imprimir el progreso detallado"
    )
    args = parser.parse_args(argv)

    progress = None if args.quiet else _cli_progress
    log = None if args.quiet else _cli_log
    env = load_env()
    enabled = turso_enabled(env)
    try:
        if args.push_only:
            result = push_staging(
                args.staging,
                replace=not args.no_replace,
                batch_size=max(100, args.batch_size),
                progress=progress,
                log=log,
                env=env,
            )
            print(json.dumps({"ok": True, **result}, indent=2, ensure_ascii=False))
            return 0
        requested_push = not args.no_push
        if requested_push and not enabled and not args.quiet:
            _cli_log(
                "Turso desactivado (TURSO_ENABLED=false): solo staging local."
            )
        summary = run_etl(
            args.source,
            include_nrt=not args.no_nrt,
            exclude_current_year=not args.include_current_year,
            replace=not args.no_replace,
            push=requested_push and enabled,
            staging_path=args.staging,
            batch_size=max(100, args.batch_size),
            progress=progress,
            log=log,
            env=env,
        )
        print(json.dumps({"ok": True, **summary}, indent=2, ensure_ascii=False))
        return 0
    except EtlError as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nCancelado por el usuario.", file=sys.stderr)
        return 130
    except Exception as exc:  # pragma: no cover
        traceback.print_exc()
        print(f"\nERROR inesperado: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
