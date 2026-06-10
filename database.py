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

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alignment_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_name TEXT NOT NULL,
            core_ids TEXT NOT NULL,
            method TEXT DEFAULT 'combined',
            threshold REAL DEFAULT 0.6,
            alignment_data TEXT,
            continuity_data TEXT,
            surface_data TEXT,
            evolution_data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alignment_corrections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alignment_id INTEGER NOT NULL,
            group_id INTEGER NOT NULL,
            sample_code TEXT NOT NULL,
            layer_id INTEGER NOT NULL,
            original_depth_start REAL,
            original_depth_end REAL,
            corrected_depth_start REAL,
            corrected_depth_end REAL,
            correction_type TEXT DEFAULT 'manual',
            correction_reason TEXT,
            corrected_by TEXT DEFAULT 'geologist',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (alignment_id) REFERENCES alignment_results(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alignment_annotations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alignment_id INTEGER NOT NULL,
            annotation_type TEXT NOT NULL,
            target_type TEXT DEFAULT 'group',
            target_id INTEGER,
            content TEXT NOT NULL,
            author TEXT DEFAULT 'geologist',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (alignment_id) REFERENCES alignment_results(id)
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


def add_layer_version(layer_id: int, core_id: int, layer_data: Dict[str, Any],
                      change_reason: str = "", changed_by: str = "system") -> int:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT MAX(version) as max_ver FROM layer_versions WHERE layer_id = ?", (layer_id,))
    row = cursor.fetchone()
    next_version = (row["max_ver"] or 0) + 1

    cursor.execute("""
        INSERT INTO layer_versions
        (layer_id, core_id, version, layer_name, depth_start, depth_end,
         gravel_pct, sand_pct, silt_pct, clay_pct, organic_matter, water_content,
         notes, change_reason, changed_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        layer_id, core_id, next_version,
        layer_data.get("layer_name"),
        layer_data.get("depth_start"),
        layer_data.get("depth_end"),
        layer_data.get("gravel_pct"),
        layer_data.get("sand_pct"),
        layer_data.get("silt_pct"),
        layer_data.get("clay_pct"),
        layer_data.get("organic_matter"),
        layer_data.get("water_content"),
        layer_data.get("notes", ""),
        change_reason,
        changed_by
    ))
    version_id = cursor.lastrowid

    cursor.execute("UPDATE core_samples SET version = version + 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (core_id,))

    conn.commit()
    conn.close()
    return version_id


def get_layer_versions(layer_id: int) -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT * FROM layer_versions WHERE layer_id = ? ORDER BY version DESC",
        conn, params=(layer_id,)
    )
    conn.close()
    return df


def get_core_versions(core_id: int) -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT lv.*, l.layer_name as current_layer_name
        FROM layer_versions lv
        LEFT JOIN layers l ON lv.layer_id = l.id
        WHERE lv.core_id = ?
        ORDER BY lv.created_at DESC
    """, conn, params=(core_id,))
    conn.close()
    return df


def add_anomaly_review(layer_id: int, core_id: int, anomaly_type: str,
                       anomaly_details: str = "") -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO anomaly_reviews (layer_id, core_id, anomaly_type, anomaly_details)
        VALUES (?, ?, ?, ?)
    """, (layer_id, core_id, anomaly_type, anomaly_details))
    review_id = cursor.lastrowid

    cursor.execute("UPDATE layers SET is_anomaly = 1, anomaly_status = 'pending' WHERE id = ?", (layer_id,))

    conn.commit()
    conn.close()
    return review_id


def update_anomaly_review(review_id: int, status: str, review_notes: str = "",
                          reviewer: str = "") -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE anomaly_reviews
        SET status = ?, review_notes = ?, reviewer = ?, reviewed_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (status, review_notes, reviewer, review_id))

    cursor.execute("SELECT layer_id FROM anomaly_reviews WHERE id = ?", (review_id,))
    row = cursor.fetchone()
    if row:
        cursor.execute("UPDATE layers SET anomaly_status = ? WHERE id = ?", (status, row["layer_id"]))

    conn.commit()
    conn.close()


def get_anomaly_reviews(core_id: int = None, status: str = None) -> pd.DataFrame:
    conn = get_connection()
    query = "SELECT ar.*, l.layer_name, l.depth_start, l.depth_end, cs.sample_code, s.station_code " \
            "FROM anomaly_reviews ar " \
            "JOIN layers l ON ar.layer_id = l.id " \
            "JOIN core_samples cs ON ar.core_id = cs.id " \
            "JOIN stations s ON cs.station_id = s.id WHERE 1=1"
    params = []

    if core_id is not None:
        query += " AND ar.core_id = ?"
        params.append(core_id)

    if status is not None:
        query += " AND ar.status = ?"
        params.append(status)

    query += " ORDER BY ar.created_at DESC"
    df = pd.read_sql_query(query, conn, params=params if params else None)
    conn.close()
    return df


def create_import_session(file_name: str, total_rows: int = 0,
                          import_mode: str = "append", file_hash: str = "",
                          session_note: str = "") -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO import_sessions (file_name, file_hash, total_rows, import_mode, session_note)
        VALUES (?, ?, ?, ?, ?)
    """, (file_name, file_hash, total_rows, import_mode, session_note))
    session_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return session_id


def update_import_session(session_id: int, **kwargs) -> None:
    if not kwargs:
        return
    conn = get_connection()
    cursor = conn.cursor()
    set_clause = ", ".join([f"{k} = ?" for k in kwargs.keys()])
    params = list(kwargs.values()) + [session_id]
    cursor.execute(f"UPDATE import_sessions SET {set_clause} WHERE id = ?", params)
    conn.commit()
    conn.close()


def get_import_sessions(limit: int = 20) -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT * FROM import_sessions ORDER BY created_at DESC LIMIT ?",
        conn, params=(limit,)
    )
    conn.close()
    return df


def log_import_error_v2(session_id: int, file_name: str, row_number: int,
                        row_data: str, error_reason: str, error_type: str = "validation") -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO import_errors (session_id, file_name, row_number, row_data, error_type, error_reason)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (session_id, file_name, row_number, row_data, error_type, error_reason))
    conn.commit()
    conn.close()


def mark_layer_duplicate(layer_id: int, duplicate_of: int) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE layers SET is_duplicate = 1, duplicate_of = ? WHERE id = ?",
                   (duplicate_of, layer_id))
    conn.commit()
    conn.close()


def mark_layer_overlap(layer_id: int, overlap_with: str) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE layers SET is_overlap = 1, overlap_with = ? WHERE id = ?",
                   (overlap_with, layer_id))
    conn.commit()
    conn.close()


def clear_layer_flags(core_id: int) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE layers SET is_duplicate = 0, duplicate_of = NULL, is_overlap = 0, overlap_with = NULL
        WHERE core_id = ?
    """, (core_id,))
    conn.commit()
    conn.close()


def get_duplicate_layers(core_id: int) -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT * FROM layers WHERE core_id = ? AND is_duplicate = 1 ORDER BY depth_start
    """, conn, params=(core_id,))
    conn.close()
    return df


def get_overlap_layers(core_id: int) -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT * FROM layers WHERE core_id = ? AND is_overlap = 1 ORDER BY depth_start
    """, conn, params=(core_id,))
    conn.close()
    return df


def get_station_cores_summary(station_code: str = None) -> pd.DataFrame:
    conn = get_connection()
    query = """
        SELECT s.station_code, s.station_name, s.location,
               COUNT(cs.id) as core_count,
               COUNT(l.id) as layer_count,
               SUM(l.depth_end - l.depth_start) as total_thickness
        FROM stations s
        LEFT JOIN core_samples cs ON s.id = cs.station_id
        LEFT JOIN layers l ON cs.id = l.core_id
    """
    params = []
    if station_code:
        query += " WHERE s.station_code = ?"
        params.append(station_code)
    query += " GROUP BY s.id ORDER BY s.station_code"

    df = pd.read_sql_query(query, conn, params=params if params else None)
    conn.close()
    return df


def get_cores_by_station(station_code: str) -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT cs.*, s.station_code, s.station_name
        FROM core_samples cs
        JOIN stations s ON cs.station_id = s.id
        WHERE s.station_code = ?
        ORDER BY cs.sample_code
    """, conn, params=(station_code,))
    conn.close()
    return df


def add_export_record(export_type: str, scope: str, filters: Dict, record_count: int,
                      file_name: str, export_format: str = "csv") -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO export_records (export_type, scope, filters, record_count, file_name, export_format)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (export_type, scope, json.dumps(filters), record_count, file_name, export_format))
    export_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return export_id


def get_export_records(limit: int = 10) -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT * FROM export_records ORDER BY created_at DESC LIMIT ?",
        conn, params=(limit,)
    )
    conn.close()
    return df


def update_layer_with_version(layer_id: int, layer_data: Dict[str, Any],
                              change_reason: str = "", changed_by: str = "user") -> None:
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM layers WHERE id = ?", (layer_id,))
    old_row = cursor.fetchone()
    if old_row:
        old_data = dict(old_row)
        cursor.execute("SELECT MAX(version) as max_ver FROM layer_versions WHERE layer_id = ?", (layer_id,))
        ver_row = cursor.fetchone()
        next_version = (ver_row["max_ver"] or 0) + 1

        cursor.execute("""
            INSERT INTO layer_versions
            (layer_id, core_id, version, layer_name, depth_start, depth_end,
             gravel_pct, sand_pct, silt_pct, clay_pct, organic_matter, water_content,
             notes, change_reason, changed_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            layer_id, old_data["core_id"], next_version,
            old_data["layer_name"], old_data["depth_start"], old_data["depth_end"],
            old_data["gravel_pct"], old_data["sand_pct"], old_data["silt_pct"],
            old_data["clay_pct"], old_data["organic_matter"], old_data["water_content"],
            old_data["notes"], change_reason, changed_by
        ))

        cursor.execute("""
            UPDATE layers SET
                layer_name = ?, depth_start = ?, depth_end = ?,
                gravel_pct = ?, sand_pct = ?, silt_pct = ?, clay_pct = ?,
                organic_matter = ?, water_content = ?, notes = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (
            layer_data["layer_name"], layer_data["depth_start"], layer_data["depth_end"],
            layer_data.get("gravel_pct", 0), layer_data.get("sand_pct", 0),
            layer_data.get("silt_pct", 0), layer_data.get("clay_pct", 0),
            layer_data.get("organic_matter"), layer_data.get("water_content"),
            layer_data.get("notes", ""), layer_id
        ))

        cursor.execute("""
            UPDATE core_samples SET version = version + 1, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (old_data["core_id"],))

    conn.commit()
    conn.close()


def get_layer_by_id(layer_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM layers WHERE id = ?", (layer_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def save_alignment_result(session_name: str, core_ids: List[int], method: str = "combined",
                          threshold: float = 0.6, alignment_data: str = "",
                          continuity_data: str = "", surface_data: str = "",
                          evolution_data: str = "") -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO alignment_results
        (session_name, core_ids, method, threshold, alignment_data, continuity_data, surface_data, evolution_data)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (session_name, json.dumps(core_ids), method, threshold,
          alignment_data, continuity_data, surface_data, evolution_data))
    result_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return result_id


def get_alignment_results(limit: int = 20) -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT * FROM alignment_results ORDER BY created_at DESC LIMIT ?",
        conn, params=(limit,)
    )
    conn.close()
    return df


def get_alignment_result(alignment_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM alignment_results WHERE id = ?", (alignment_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def add_alignment_correction(alignment_id: int, group_id: int, sample_code: str,
                             layer_id: int, original_depth_start: float,
                             original_depth_end: float, corrected_depth_start: float,
                             corrected_depth_end: float, correction_type: str = "manual",
                             correction_reason: str = "", corrected_by: str = "geologist") -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO alignment_corrections
        (alignment_id, group_id, sample_code, layer_id,
         original_depth_start, original_depth_end,
         corrected_depth_start, corrected_depth_end,
         correction_type, correction_reason, corrected_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (alignment_id, group_id, sample_code, layer_id,
          original_depth_start, original_depth_end,
          corrected_depth_start, corrected_depth_end,
          correction_type, correction_reason, corrected_by))
    correction_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return correction_id


def get_alignment_corrections(alignment_id: int) -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT * FROM alignment_corrections WHERE alignment_id = ? ORDER BY created_at DESC",
        conn, params=(alignment_id,)
    )
    conn.close()
    return df


def add_alignment_annotation(alignment_id: int, annotation_type: str, content: str,
                             target_type: str = "group", target_id: int = None,
                             author: str = "geologist") -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO alignment_annotations
        (alignment_id, annotation_type, target_type, target_id, content, author)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (alignment_id, annotation_type, target_type, target_id, content, author))
    annotation_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return annotation_id


def get_alignment_annotations(alignment_id: int, annotation_type: str = None) -> pd.DataFrame:
    conn = get_connection()
    if annotation_type:
        df = pd.read_sql_query(
            "SELECT * FROM alignment_annotations WHERE alignment_id = ? AND annotation_type = ? ORDER BY created_at DESC",
            conn, params=(alignment_id, annotation_type)
        )
    else:
        df = pd.read_sql_query(
            "SELECT * FROM alignment_annotations WHERE alignment_id = ? ORDER BY created_at DESC",
            conn, params=(alignment_id,)
        )
    conn.close()
    return df


def delete_alignment_result(alignment_id: int) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM alignment_corrections WHERE alignment_id = ?", (alignment_id,))
    cursor.execute("DELETE FROM alignment_annotations WHERE alignment_id = ?", (alignment_id,))
    cursor.execute("DELETE FROM alignment_results WHERE id = ?", (alignment_id,))
    conn.commit()
    conn.close()


def update_alignment_result(alignment_id: int, **kwargs) -> None:
    if not kwargs:
        return
    conn = get_connection()
    cursor = conn.cursor()
    set_clause = ", ".join([f"{k} = ?" for k in kwargs.keys()])
    params = list(kwargs.values()) + [alignment_id]
    cursor.execute(f"UPDATE alignment_results SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?", params)
    conn.commit()
    conn.close()


def get_correction_dicts(alignment_id: int) -> List[Dict[str, Any]]:
    df = get_alignment_corrections(alignment_id)
    if df.empty:
        return []
    return df.to_dict("records")


def get_annotation_dicts(alignment_id: int, annotation_type: str = None) -> List[Dict[str, Any]]:
    df = get_alignment_annotations(alignment_id, annotation_type)
    if df.empty:
        return []
    return df.to_dict("records")
