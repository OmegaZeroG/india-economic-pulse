-- BRONZE layer: raw files exactly as they arrived. No cleaning, no renaming, no type conversion beyond
-- recording what kind of value each cell held. Silver parsers read these tables, never the files.
-- Loaded by src/bronze/load_bronze.py; a file is skipped if its hash is already stored.

CREATE TABLE IF NOT EXISTS bronze_files (
    file_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    source     TEXT    NOT NULL,                 -- upi, ppac, gst_national, gst_state, ewaybill, iip, gdp
    file_name  TEXT    NOT NULL UNIQUE,
    file_date  TEXT,                             -- download date taken from the file name
    file_type  TEXT    NOT NULL,                 -- xlsx, xls, csv or json, detected from the file's bytes
    sha256     TEXT    NOT NULL,
    size_bytes INTEGER NOT NULL,
    n_records  INTEGER NOT NULL,                 -- cells (spreadsheets) or records (JSON) stored
    loaded_at  TEXT    NOT NULL
);

-- One row per non-empty spreadsheet cell. Numbers keep full precision as text, dates are ISO text.
CREATE TABLE IF NOT EXISTS bronze_cells (
    file_id    INTEGER NOT NULL REFERENCES bronze_files(file_id),
    sheet_no   INTEGER NOT NULL,
    sheet      TEXT    NOT NULL,
    row_num    INTEGER NOT NULL,
    col_num    INTEGER NOT NULL,
    cell_type  TEXT    NOT NULL CHECK (cell_type IN ('num', 'date', 'str')),
    value_text TEXT    NOT NULL,
    PRIMARY KEY (file_id, sheet_no, row_num, col_num)
) WITHOUT ROWID;

-- One row per record of an API response saved as JSON.
CREATE TABLE IF NOT EXISTS bronze_api (
    file_id   INTEGER NOT NULL REFERENCES bronze_files(file_id),
    record_no INTEGER NOT NULL,
    payload   TEXT    NOT NULL,
    PRIMARY KEY (file_id, record_no)
) WITHOUT ROWID;
