import pandas as pd
from typing import List, Dict, Tuple, Any
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


def _validate_row(row: pd.Series, row_num: int, existing_depths: List[Tuple[float, float]]) -> Tuple[bool, str]:
    sample_code = row.get("sample_code", "")
    if pd.isna(sample_code) or str(sample_code).strip() == "":
        return False, f"样品编号为空"

    try:
        depth_start = float(row["depth_start"])
        depth_end = float(row["depth_end"])
    except (ValueError, TypeError):
        return False, f"深度值格式错误，无法转换为数字"

    if depth_start >= depth_end:
        return False, f"深度起点({depth_start})必须小于终点({depth_end})"

    if depth_start < 0 or depth_end < 0:
        return False, f"深度值不能为负数"

    for (s, e) in existing_depths:
        if not (depth_end <= s or depth_start >= e):
            return False, f"深度区间({depth_start}-{depth_end})与已有区间({s}-{e})重叠"

    pct_cols = ["gravel_pct", "sand_pct", "silt_pct", "clay_pct"]
    total_pct = 0.0
    for col in pct_cols:
        if col in row and not pd.isna(row[col]):
            try:
                val = float(row[col])
                if val < 0:
                    return False, f"{col}值为负数({val})"
                total_pct += val
            except (ValueError, TypeError):
                return False, f"{col}值格式错误"

    if total_pct > 100.1:
        return False, f"颗粒组成百分比总和({total_pct:.1f}%)超过100%"

    if "organic_matter" in row and not pd.isna(row["organic_matter"]):
        try:
            val = float(row["organic_matter"])
            if val < 0:
                return False, f"有机质含量为负数({val})"
        except (ValueError, TypeError):
            return False, "有机质含量格式错误"

    if "water_content" in row and not pd.isna(row["water_content"]):
        try:
            val = float(row["water_content"])
            if val < 0:
                return False, f"含水率为负数({val})"
        except (ValueError, TypeError):
            return False, "含水率格式错误"

    return True, ""


def import_csv(file, file_name: str, overwrite_existing: bool = True) -> Tuple[int, int, List[Dict[str, Any]]]:
    df = pd.read_csv(file)

    df, missing_cols = _map_columns(df)
    if missing_cols:
        raise ValueError(f"缺少必需的列: {', '.join(missing_cols)}")

    success_count = 0
    skipped_count = 0
    errors = []
    core_depths: Dict[str, List[Tuple[float, float]]] = {}
    cleared_cores: set = set()

    all_cores = db.get_all_core_samples()
    sample_code_to_id = dict(zip(all_cores["sample_code"], all_cores["id"])) if not all_cores.empty else {}

    for sample_code, core_id in sample_code_to_id.items():
        existing_layers = db.get_core_layers(core_id)
        if not existing_layers.empty:
            core_depths[sample_code] = list(
                zip(existing_layers["depth_start"], existing_layers["depth_end"])
            )
        else:
            core_depths[sample_code] = []

    station_code_col = "station_code" if "station_code" in df.columns else None

    for idx, row in df.iterrows():
        row_num = idx + 2
        sample_code = str(row["sample_code"]).strip()

        if sample_code not in core_depths:
            core_depths[sample_code] = []

        if sample_code in sample_code_to_id and sample_code not in cleared_cores:
            if overwrite_existing:
                existing_core_id = sample_code_to_id[sample_code]
                conn = db.get_connection()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM layers WHERE core_id = ?", (existing_core_id,))
                conn.commit()
                conn.close()
                core_depths[sample_code] = []
                cleared_cores.add(sample_code)
            else:
                skipped_count += 1
                continue

        is_valid, error_msg = _validate_row(row, row_num, core_depths[sample_code])

        if not is_valid:
            error_info = {
                "row_number": row_num,
                "row_data": row.to_dict(),
                "error_reason": error_msg
            }
            errors.append(error_info)
            db.log_import_error(file_name, row_num, str(row.to_dict()), error_msg)
            continue

        try:
            station_code = str(row[station_code_col]).strip() if station_code_col and not pd.isna(row[station_code_col]) else "默认站位"
            station_id = db.add_station(station_code, station_code)

            if sample_code in sample_code_to_id:
                core_id = sample_code_to_id[sample_code]
            else:
                core_id = db.add_core_sample(station_id, sample_code)
                sample_code_to_id[sample_code] = core_id

            layer_data = {
                "layer_name": str(row["layer_name"]).strip(),
                "depth_start": float(row["depth_start"]),
                "depth_end": float(row["depth_end"]),
                "gravel_pct": float(row["gravel_pct"]) if "gravel_pct" in row and not pd.isna(row["gravel_pct"]) else 0,
                "sand_pct": float(row["sand_pct"]) if "sand_pct" in row and not pd.isna(row["sand_pct"]) else 0,
                "silt_pct": float(row["silt_pct"]) if "silt_pct" in row and not pd.isna(row["silt_pct"]) else 0,
                "clay_pct": float(row["clay_pct"]) if "clay_pct" in row and not pd.isna(row["clay_pct"]) else 0,
                "organic_matter": float(row["organic_matter"]) if "organic_matter" in row and not pd.isna(row["organic_matter"]) else None,
                "water_content": float(row["water_content"]) if "water_content" in row and not pd.isna(row["water_content"]) else None,
                "notes": ""
            }

            db.add_layer(core_id, layer_data)
            core_depths[sample_code].append((layer_data["depth_start"], layer_data["depth_end"]))
            success_count += 1

        except Exception as e:
            error_info = {
                "row_number": row_num,
                "row_data": row.to_dict(),
                "error_reason": f"数据库错误: {str(e)}"
            }
            errors.append(error_info)
            db.log_import_error(file_name, row_num, str(row.to_dict()), str(e))

    return success_count, skipped_count, errors


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
