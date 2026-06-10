import pandas as pd
import hashlib
from typing import List, Dict, Tuple, Any, Optional
import database as db


REQUIRED_COLUMNS = {
    "sample_code": ["样品编号", "sample_code", "SampleCode", "sample id", "sample_id"],
    "depth_start": ["深度起点", "depth_start", "top_depth", "起始深度", "起始(cm)"],
    "depth_end": ["深度终点", "depth_end", "bottom_depth", "结束深度", "终止深度", "终止(cm)"],
    "layer_name": ["层位名称", "layer_name", "layer", "层名", "岩性"],
}

OPTIONAL_COLUMNS = {
    "gravel_pct": ["砾石(%)", "gravel_pct", "gravel", "砾石含量", "砾石"],
    "sand_pct": ["砂(%)", "sand_pct", "sand", "砂含量", "砂粒"],
    "silt_pct": ["粉砂(%)", "silt_pct", "silt", "粉砂含量", "粉砂"],
    "clay_pct": ["黏土(%)", "clay_pct", "clay", "黏土含量", "粘粒"],
    "organic_matter": ["有机质(%)", "organic_matter", "organic", "有机质", "有机质含量", "OM"],
    "water_content": ["含水率(%)", "water_content", "water", "含水率", "含水量", "WC"],
    "station_code": ["站位编号", "station_code", "station", "站位"],
}


def _map_columns(df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
    column_mapping = {}
    missing_columns = []

    for std_name, alternatives in REQUIRED_COLUMNS.items():
        found = False
        for alt in alternatives:
            for col in df.columns:
                if str(col).strip().lower() == alt.lower():
                    column_mapping[col] = std_name
                    found = True
                    break
            if found:
                break
        if not found:
            missing_columns.append(std_name)

    for std_name, alternatives in OPTIONAL_COLUMNS.items():
        for alt in alternatives:
            for col in df.columns:
                if str(col).strip().lower() == alt.lower():
                    column_mapping[col] = std_name
                    break

    df = df.rename(columns=column_mapping)
    return df, missing_columns


def _check_duplicate(layer_data: Dict[str, Any],
                     existing_layers: List[Dict[str, Any]]) -> Tuple[bool, Optional[int]]:
    depth_start = layer_data["depth_start"]
    depth_end = layer_data["depth_end"]
    layer_name = layer_data["layer_name"]

    for existing in existing_layers:
        e_start = float(existing["depth_start"])
        e_end = float(existing["depth_end"])
        e_name = existing["layer_name"]

        if (abs(depth_start - e_start) < 0.01 and
                abs(depth_end - e_end) < 0.01 and
                layer_name == e_name):
            return True, int(existing["id"])

    return False, None


def _check_overlap(depth_start: float, depth_end: float,
                   existing_depths: List[Tuple[float, float, str]]) -> List[str]:
    overlaps = []
    for (s, e, name) in existing_depths:
        if not (depth_end <= s or depth_start >= e):
            overlap_start = max(depth_start, s)
            overlap_end = min(depth_end, e)
            overlaps.append(f"{name}({s}-{e}cm)重叠{overlap_start}-{overlap_end}cm")
    return overlaps


def _validate_row(row: pd.Series, row_num: int) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    sample_code = row.get("sample_code", "")
    if pd.isna(sample_code) or str(sample_code).strip() == "":
        return False, "样品编号为空", None

    try:
        depth_start = float(row["depth_start"])
        depth_end = float(row["depth_end"])
    except (ValueError, TypeError):
        return False, "深度值格式错误，无法转换为数字", None

    if depth_start >= depth_end:
        return False, f"深度起点({depth_start})必须小于终点({depth_end})", None

    if depth_start < 0 or depth_end < 0:
        return False, "深度值不能为负数", None

    pct_cols = ["gravel_pct", "sand_pct", "silt_pct", "clay_pct"]
    total_pct = 0.0
    pct_values = {}
    for col in pct_cols:
        if col in row and not pd.isna(row[col]):
            try:
                val = float(row[col])
                if val < 0:
                    return False, f"{col}值为负数({val})", None
                pct_values[col] = val
                total_pct += val
            except (ValueError, TypeError):
                return False, f"{col}值格式错误", None
        else:
            pct_values[col] = 0.0

    if total_pct > 100.1:
        return False, f"颗粒组成百分比总和({total_pct:.1f}%)超过100%", None

    organic_val = None
    if "organic_matter" in row and not pd.isna(row["organic_matter"]):
        try:
            organic_val = float(row["organic_matter"])
            if organic_val < 0:
                return False, f"有机质含量为负数({organic_val})", None
        except (ValueError, TypeError):
            return False, "有机质含量格式错误", None

    water_val = None
    if "water_content" in row and not pd.isna(row["water_content"]):
        try:
            water_val = float(row["water_content"])
            if water_val < 0:
                return False, f"含水率为负数({water_val})", None
        except (ValueError, TypeError):
            return False, "含水率格式错误", None

    layer_data = {
        "sample_code": str(sample_code).strip(),
        "layer_name": str(row["layer_name"]).strip() if "layer_name" in row else "",
        "depth_start": depth_start,
        "depth_end": depth_end,
        "gravel_pct": pct_values.get("gravel_pct", 0),
        "sand_pct": pct_values.get("sand_pct", 0),
        "silt_pct": pct_values.get("silt_pct", 0),
        "clay_pct": pct_values.get("clay_pct", 0),
        "organic_matter": organic_val,
        "water_content": water_val,
    }

    return True, "", layer_data


def _compute_file_hash(file) -> str:
    file.seek(0)
    content = file.read()
    file.seek(0)
    return hashlib.md5(content).hexdigest()


def import_csv_v2(file, file_name: str, import_mode: str = "append",
                  detect_duplicates: bool = True, detect_overlaps: bool = True,
                  session_note: str = "") -> Dict[str, Any]:
    file_hash = _compute_file_hash(file)
    df = pd.read_csv(file)

    df, missing_cols = _map_columns(df)
    if missing_cols:
        raise ValueError(f"缺少必需的列: {', '.join(missing_cols)}")

    total_rows = len(df)
    session_id = db.create_import_session(
        file_name=file_name,
        file_hash=file_hash,
        total_rows=total_rows,
        import_mode=import_mode,
        session_note=session_note
    )

    success_count = 0
    skipped_count = 0
    duplicate_count = 0
    overlap_count = 0
    error_count = 0
    errors = []
    warnings = []

    core_depths: Dict[str, List[Tuple[float, float, str]]] = {}
    core_layer_data: Dict[str, List[Dict[str, Any]]] = {}
    cleared_cores: set = set()

    all_cores = db.get_all_core_samples()
    sample_code_to_id = dict(zip(all_cores["sample_code"], all_cores["id"])) if not all_cores.empty else {}

    for sample_code, core_id in sample_code_to_id.items():
        existing_layers = db.get_core_layers(core_id)
        if not existing_layers.empty:
            core_depths[sample_code] = list(
                zip(existing_layers["depth_start"].astype(float),
                    existing_layers["depth_end"].astype(float),
                    existing_layers["layer_name"])
            )
            core_layer_data[sample_code] = existing_layers.to_dict("records")
        else:
            core_depths[sample_code] = []
            core_layer_data[sample_code] = []

    station_code_col = "station_code" if "station_code" in df.columns else None

    for idx, row in df.iterrows():
        row_num = idx + 2
        sample_code = str(row.get("sample_code", "")).strip()

        if not sample_code:
            error_info = {
                "row_number": row_num,
                "row_data": row.to_dict(),
                "error_reason": "样品编号为空",
                "error_type": "validation"
            }
            errors.append(error_info)
            error_count += 1
            db.log_import_error_v2(session_id, file_name, row_num, str(row.to_dict()),
                                   "样品编号为空", "validation")
            continue

        if sample_code not in core_depths:
            core_depths[sample_code] = []
            core_layer_data[sample_code] = []

        if sample_code in sample_code_to_id and sample_code not in cleared_cores:
            if import_mode == "overwrite":
                existing_core_id = sample_code_to_id[sample_code]
                conn = db.get_connection()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM layers WHERE core_id = ?", (existing_core_id,))
                conn.commit()
                conn.close()
                core_depths[sample_code] = []
                core_layer_data[sample_code] = []
                cleared_cores.add(sample_code)
            elif import_mode == "skip":
                skipped_count += 1
                continue

        is_valid, error_msg, layer_data = _validate_row(row, row_num)

        if not is_valid:
            error_info = {
                "row_number": row_num,
                "row_data": row.to_dict(),
                "error_reason": error_msg,
                "error_type": "validation"
            }
            errors.append(error_info)
            error_count += 1
            db.log_import_error_v2(session_id, file_name, row_num, str(row.to_dict()),
                                   error_msg, "validation")
            continue

        is_dup = False
        dup_of = None
        if detect_duplicates:
            is_dup, dup_of = _check_duplicate(layer_data, core_layer_data[sample_code])
            if is_dup:
                duplicate_count += 1
                warning_info = {
                    "row_number": row_num,
                    "sample_code": sample_code,
                    "warning_type": "duplicate",
                    "details": f"与层位ID {dup_of} 重复"
                }
                warnings.append(warning_info)

        overlaps = []
        if detect_overlaps and not is_dup:
            overlaps = _check_overlap(
                layer_data["depth_start"], layer_data["depth_end"],
                core_depths[sample_code]
            )
            if overlaps:
                overlap_count += 1

        try:
            station_code = str(row[station_code_col]).strip() if station_code_col and not pd.isna(row[station_code_col]) else "默认站位"
            station_id = db.add_station(station_code, station_code)

            if sample_code in sample_code_to_id:
                core_id = sample_code_to_id[sample_code]
            else:
                core_id = db.add_core_sample(station_id, sample_code)
                sample_code_to_id[sample_code] = core_id

            final_layer_data = {
                "layer_name": layer_data["layer_name"],
                "depth_start": layer_data["depth_start"],
                "depth_end": layer_data["depth_end"],
                "gravel_pct": layer_data["gravel_pct"],
                "sand_pct": layer_data["sand_pct"],
                "silt_pct": layer_data["silt_pct"],
                "clay_pct": layer_data["clay_pct"],
                "organic_matter": layer_data["organic_matter"],
                "water_content": layer_data["water_content"],
                "notes": ""
            }

            new_layer_id = db.add_layer(core_id, final_layer_data)

            if is_dup and dup_of is not None:
                db.mark_layer_duplicate(new_layer_id, dup_of)

            if overlaps:
                db.mark_layer_overlap(new_layer_id, "; ".join(overlaps))

            core_depths[sample_code].append((
                layer_data["depth_start"], layer_data["depth_end"], layer_data["layer_name"]
            ))
            core_layer_data[sample_code].append({
                "id": new_layer_id,
                "depth_start": layer_data["depth_start"],
                "depth_end": layer_data["depth_end"],
                "layer_name": layer_data["layer_name"],
            })

            success_count += 1

        except Exception as e:
            error_info = {
                "row_number": row_num,
                "row_data": row.to_dict(),
                "error_reason": f"数据库错误: {str(e)}",
                "error_type": "database"
            }
            errors.append(error_info)
            error_count += 1
            db.log_import_error_v2(session_id, file_name, row_num, str(row.to_dict()),
                                   f"数据库错误: {str(e)}", "database")

    db.update_import_session(
        session_id,
        success_count=success_count,
        skipped_count=skipped_count,
        error_count=error_count,
        duplicate_count=duplicate_count,
        overlap_count=overlap_count
    )

    return {
        "session_id": session_id,
        "total_rows": total_rows,
        "success_count": success_count,
        "skipped_count": skipped_count,
        "error_count": error_count,
        "duplicate_count": duplicate_count,
        "overlap_count": overlap_count,
        "errors": errors,
        "warnings": warnings,
    }


def import_csv(file, file_name: str, overwrite_existing: bool = True) -> Tuple[int, int, List[Dict[str, Any]]]:
    import_mode = "overwrite" if overwrite_existing else "skip"
    result = import_csv_v2(file, file_name, import_mode=import_mode,
                           detect_duplicates=False, detect_overlaps=False)
    return result["success_count"], result["skipped_count"], result["errors"]


def validate_layer_edit(core_id: int, layer_id: int, depth_start: float, depth_end: float) -> Tuple[bool, str]:
    if depth_start >= depth_end:
        return False, f"深度起点({depth_start})必须小于终点({depth_end})"

    if depth_start < 0 or depth_end < 0:
        return False, "深度值不能为负数"

    layers_df = db.get_core_layers(core_id)
    if not layers_df.empty:
        for _, row in layers_df.iterrows():
            if int(row["id"]) == layer_id:
                continue
            s = float(row["depth_start"])
            e = float(row["depth_end"])
            if not (depth_end <= s or depth_start >= e):
                return False, f"深度区间({depth_start}-{depth_end})与已有层位「{row['layer_name']}」({s}-{e})重叠"

    return True, ""


def validate_percentages(gravel_pct: float, sand_pct: float, silt_pct: float, clay_pct: float) -> Tuple[bool, str]:
    pcts = [("砾石", gravel_pct), ("砂", sand_pct), ("粉砂", silt_pct), ("黏土", clay_pct)]
    for name, val in pcts:
        if val < 0:
            return False, f"{name}百分比为负数({val})"

    total = gravel_pct + sand_pct + silt_pct + clay_pct
    if total > 100.1:
        return False, f"颗粒组成百分比总和({total:.1f}%)超过100%"

    return True, ""


def get_expected_columns() -> Dict[str, List[str]]:
    return {
        "必需列": list(REQUIRED_COLUMNS.keys()),
        "可选列": list(OPTIONAL_COLUMNS.keys()),
        "列名别名": {**REQUIRED_COLUMNS, **OPTIONAL_COLUMNS}
    }


def detect_core_duplicates_and_overlaps(core_id: int) -> Dict[str, Any]:
    layers_df = db.get_core_layers(core_id)
    if layers_df.empty:
        return {"duplicates": [], "overlaps": []}

    duplicates = []
    overlaps = []

    layers = layers_df.to_dict("records")

    for i in range(len(layers)):
        for j in range(i + 1, len(layers)):
            li = layers[i]
            lj = layers[j]

            if (abs(float(li["depth_start"]) - float(lj["depth_start"])) < 0.01 and
                    abs(float(li["depth_end"]) - float(lj["depth_end"])) < 0.01 and
                    li["layer_name"] == lj["layer_name"]):
                duplicates.append({
                    "layer_id_1": li["id"],
                    "layer_id_2": lj["id"],
                    "layer_name": li["layer_name"],
                    "depth_start": li["depth_start"],
                    "depth_end": li["depth_end"],
                })

            si, ei = float(li["depth_start"]), float(li["depth_end"])
            sj, ej = float(lj["depth_start"]), float(lj["depth_end"])
            if not (ei <= sj or si >= ej):
                overlap_start = max(si, sj)
                overlap_end = min(ei, ej)
                overlaps.append({
                    "layer_id_1": li["id"],
                    "layer_id_2": lj["id"],
                    "layer_name_1": li["layer_name"],
                    "layer_name_2": lj["layer_name"],
                    "overlap_start": overlap_start,
                    "overlap_end": overlap_end,
                    "overlap_thickness": overlap_end - overlap_start,
                })

    return {
        "duplicates": duplicates,
        "overlaps": overlaps,
    }
