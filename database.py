import sqlite3
import pandas as pd
import json
from typing import Optional, List, Dict, Any, Tuple


DB_PATH = "sediment_data.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            station_code TEXT UNIQUE NOT NULL,
            station_name TEXT,
            location TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS core_samples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            station_id INTEGER NOT NULL,
            sample_code TEXT UNIQUE NOT NULL,
            core_length REAL,
            sampling_date TEXT,
            version INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (station_id) REFERENCES stations(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS layers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            core_id INTEGER NOT NULL,
            layer_name TEXT NOT NULL,
            depth_start REAL NOT NULL,
            depth_end REAL NOT NULL,
            gravel_pct REAL DEFAULT 0,
            sand_pct REAL DEFAULT 0,
            silt_pct REAL DEFAULT 0,
            clay_pct REAL DEFAULT 0,
            organic_matter REAL,
            water_content REAL,
            notes TEXT,
            is_duplicate INTEGER DEFAULT 0,
            duplicate_of INTEGER,
            is_overlap INTEGER DEFAULT 0,
            overlap_with TEXT,
            is_anomaly INTEGER DEFAULT 0,
            anomaly_status TEXT DEFAULT 'pending',
            anomaly_notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (core_id) REFERENCES core_samples(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS layer_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            layer_id INTEGER NOT NULL,
            core_id INTEGER NOT NULL,
            version INTEGER NOT NULL,
            layer_name TEXT,
            depth_start REAL,
            depth_end REAL,
            gravel_pct REAL,
            sand_pct REAL,
            silt_pct REAL,
            clay_pct REAL,
            organic_matter REAL,
            water_content REAL,
            notes TEXT,
            change_reason TEXT,
            changed_by TEXT DEFAULT 'system',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (layer_id) REFERENCES layers(id),
            FOREIGN KEY (core_id) REFERENCES core_samples(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS anomaly_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            layer_id INTEGER NOT NULL,
            core_id INTEGER NOT NULL,
            anomaly_type TEXT NOT NULL,
            anomaly_details TEXT,
            status TEXT DEFAULT 'pending',
            reviewer TEXT,
            review_notes TEXT,
            reviewed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (layer_id) REFERENCES layers(id),
            FOREIGN KEY (core_id) REFERENCES core_samples(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS import_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_name TEXT NOT NULL,
            file_hash TEXT,
            total_rows INTEGER DEFAULT 0,
            success_count INTEGER DEFAULT 0,
            skipped_count INTEGER DEFAULT 0,
            error_count INTEGER DEFAULT 0,
            duplicate_count INTEGER DEFAULT 0,
            overlap_count INTEGER DEFAULT 0,
            import_mode TEXT DEFAULT 'append',
            session_note TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS import_errors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            file_name TEXT NOT NULL,
            row_number INTEGER,
            row_data TEXT,
            error_type TEXT DEFAULT 'validation',
            error_reason TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES import_sessions(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS export_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            export_type TEXT NOT NULL,
            scope TEXT,
            filters TEXT,
            record_count INTEGER,
            file_name TEXT,
            export_format TEXT DEFAULT 'csv',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    _migrate_existing_tables(cursor)

    conn.commit()
    conn.close()


def _migrate_existing_tables(cursor: sqlite3.Cursor) -> None:
    try:
        cursor.execute("PRAGMA table_info(core_samples)")
        columns = [col["name"] for col in cursor.fetchall()]
        if "version" not in columns:
            cursor.execute("ALTER TABLE core_samples ADD COLUMN version INTEGER DEFAULT 1")
        if "updated_at" not in columns:
            cursor.execute("ALTER TABLE core_samples ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("PRAGMA table_info(layers)")
        columns = [col["name"] for col in cursor.fetchall()]
        new_columns = [
            ("is_duplicate", "INTEGER DEFAULT 0"),
            ("duplicate_of", "INTEGER"),
            ("is_overlap", "INTEGER DEFAULT 0"),
            ("overlap_with", "TEXT"),
            ("is_anomaly", "INTEGER DEFAULT 0"),
            ("anomaly_status", "TEXT DEFAULT 'pending'"),
            ("anomaly_notes", "TEXT"),
            ("updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
        ]
        for col_name, col_def in new_columns:
            if col_name not in columns:
                cursor.execute(f"ALTER TABLE layers ADD COLUMN {col_name} {col_def}")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("PRAGMA table_info(import_errors)")
        columns = [col["name"] for col in cursor.fetchall()]
        if "session_id" not in columns:
            cursor.execute("ALTER TABLE import_errors ADD COLUMN session_id INTEGER")
        if "error_type" not in columns:
            cursor.execute("ALTER TABLE import_errors ADD COLUMN error_type TEXT DEFAULT 'validation'")
    except sqlite3.OperationalError:
        pass


def add_station(station_code: str, station_name: str = "", location: str = "") -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO stations (station_code, station_name, location) VALUES (?, ?, ?)",
        (station_code, station_name, location)
    )
    cursor.execute("SELECT id FROM stations WHERE station_code = ?", (station_code,))
    station_id = cursor.fetchone()["id"]
    conn.commit()
    conn.close()
    return station_id


def add_core_sample(station_id: int, sample_code: str, core_length: Optional[float] = None,
                    sampling_date: str = "") -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO core_samples (station_id, sample_code, core_length, sampling_date) VALUES (?, ?, ?, ?)",
        (station_id, sample_code, core_length, sampling_date)
    )
    cursor.execute("SELECT id FROM core_samples WHERE sample_code = ?", (sample_code,))
    core_id = cursor.fetchone()["id"]
    conn.commit()
    conn.close()
    return core_id


def add_layer(core_id: int, layer_data: Dict[str, Any]) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO layers 
        (core_id, layer_name, depth_start, depth_end, gravel_pct, sand_pct, silt_pct, clay_pct, organic_matter, water_content, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        core_id,
        layer_data["layer_name"],
        layer_data["depth_start"],
        layer_data["depth_end"],
        layer_data.get("gravel_pct", 0),
        layer_data.get("sand_pct", 0),
        layer_data.get("silt_pct", 0),
        layer_data.get("clay_pct", 0),
        layer_data.get("organic_matter"),
        layer_data.get("water_content"),
        layer_data.get("notes", "")
    ))
    layer_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return layer_id


def update_layer(layer_id: int, layer_data: Dict[str, Any]) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE layers SET
            layer_name = ?,
            depth_start = ?,
            depth_end = ?,
            gravel_pct = ?,
            sand_pct = ?,
            silt_pct = ?,
            clay_pct = ?,
            organic_matter = ?,
            water_content = ?,
            notes = ?
        WHERE id = ?
    """, (
        layer_data["layer_name"],
        layer_data["depth_start"],
        layer_data["depth_end"],
        layer_data.get("gravel_pct", 0),
        layer_data.get("sand_pct", 0),
        layer_data.get("silt_pct", 0),
        layer_data.get("clay_pct", 0),
        layer_data.get("organic_matter"),
        layer_data.get("water_content"),
        layer_data.get("notes", ""),
        layer_id
    ))
    conn.commit()
    conn.close()


def delete_layer(layer_id: int) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM layers WHERE id = ?", (layer_id,))
    conn.commit()
    conn.close()


def delete_core_sample(core_id: int) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM layers WHERE core_id = ?", (core_id,))
    cursor.execute("DELETE FROM core_samples WHERE id = ?", (core_id,))
    conn.commit()
    conn.close()


def get_all_stations() -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM stations ORDER BY created_at DESC", conn)
    conn.close()
    return df


def get_all_core_samples() -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT cs.*, s.station_code, s.station_name 
        FROM core_samples cs 
        JOIN stations s ON cs.station_id = s.id 
        ORDER BY cs.created_at DESC
    """, conn)
    conn.close()
    return df


def get_core_layers(core_id: int) -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT * FROM layers WHERE core_id = ? ORDER BY depth_start ASC",
        conn, params=(core_id,)
    )
    conn.close()
    return df


def get_core_samples_by_station(station_id: int) -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT * FROM core_samples WHERE station_id = ? ORDER BY created_at DESC",
        conn, params=(station_id,)
    )
    conn.close()
    return df


def get_core_sample(core_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM core_samples WHERE id = ?", (core_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def log_import_error(file_name: str, row_number: int, row_data: str, error_reason: str) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO import_errors (file_name, row_number, row_data, error_reason)
        VALUES (?, ?, ?, ?)
    """, (file_name, row_number, row_data, error_reason))
    conn.commit()
    conn.close()


def get_import_errors(limit: int = 100) -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT * FROM import_errors ORDER BY created_at DESC LIMIT ?",
        conn, params=(limit,)
    )
    conn.close()
    return df


def clear_import_errors() -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM import_errors")
    conn.commit()
    conn.close()
