import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional, Any
import database as db
import data_validator as validator


def calculate_layer_thickness(layers_df: pd.DataFrame) -> pd.DataFrame:
    if layers_df.empty:
        return layers_df

    df = layers_df.copy()
    df["thickness"] = df["depth_end"] - df["depth_start"]
    df["mid_depth"] = (df["depth_start"] + df["depth_end"]) / 2
    return df


def find_missing_intervals(layers_df: pd.DataFrame, core_length: Optional[float] = None) -> List[Dict[str, float]]:
    if layers_df.empty:
        return []

    sorted_layers = layers_df.sort_values("depth_start").reset_index(drop=True)
    missing = []

    if len(sorted_layers) > 0 and sorted_layers.iloc[0]["depth_start"] > 0:
        missing.append({
            "depth_start": 0,
            "depth_end": sorted_layers.iloc[0]["depth_start"],
            "thickness": sorted_layers.iloc[0]["depth_start"],
            "type": "top_gap"
        })

    for i in range(1, len(sorted_layers)):
        prev_end = sorted_layers.iloc[i - 1]["depth_end"]
        curr_start = sorted_layers.iloc[i]["depth_start"]
        if curr_start > prev_end:
            missing.append({
                "depth_start": prev_end,
                "depth_end": curr_start,
                "thickness": curr_start - prev_end,
                "type": "middle_gap"
            })

    if core_length is not None:
        max_depth = sorted_layers["depth_end"].max()
        if max_depth < core_length:
            missing.append({
                "depth_start": max_depth,
                "depth_end": core_length,
                "thickness": core_length - max_depth,
                "type": "bottom_gap"
            })

    return missing


def detect_anomalies(layers_df: pd.DataFrame) -> pd.DataFrame:
    if layers_df.empty:
        return layers_df

    df = calculate_layer_thickness(layers_df)
    numeric_cols = ["gravel_pct", "sand_pct", "silt_pct", "clay_pct", "organic_matter", "water_content", "thickness"]
    existing_cols = [col for col in numeric_cols if col in df.columns]

    anomaly_flags = pd.DataFrame(index=df.index)
    anomaly_details_list = []

    for col in existing_cols:
        valid_data = df[col].dropna()
        if len(valid_data) < 4:
            anomaly_flags[f"{col}_anomaly"] = [False] * len(df)
            continue

        q1 = valid_data.quantile(0.25)
        q3 = valid_data.quantile(0.75)
        iqr = q3 - q1
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr

        anomaly_flags[f"{col}_anomaly"] = ~df[col].between(lower_bound, upper_bound) & df[col].notna()

    result = pd.concat([df, anomaly_flags], axis=1)
    anomaly_cols = [c for c in result.columns if c.endswith("_anomaly")]
    result["is_anomaly"] = result[anomaly_cols].any(axis=1)
    result["anomaly_details"] = result.apply(
        lambda row: ", ".join([
            col.replace("_anomaly", "")
            for col in anomaly_cols if row[col]
        ]) if row["is_anomaly"] else "",
        axis=1
    )

    return result


def calculate_correlation(layers_df: pd.DataFrame, method: str = "pearson") -> pd.DataFrame:
    if layers_df.empty:
        return pd.DataFrame()

    numeric_cols = ["gravel_pct", "sand_pct", "silt_pct", "clay_pct", "organic_matter", "water_content"]
    existing_cols = [col for col in numeric_cols if col in layers_df.columns and layers_df[col].notna().sum() > 2]

    if len(existing_cols) < 2:
        return pd.DataFrame()

    df = layers_df[existing_cols].copy()
    corr_matrix = df.corr(method=method)
    return corr_matrix


def summarize_layer_types(layers_df: pd.DataFrame) -> pd.DataFrame:
    if layers_df.empty:
        return pd.DataFrame()

    df = calculate_layer_thickness(layers_df)
    summary = df.groupby("layer_name").agg(
        layer_count=("id", "count"),
        total_thickness=("thickness", "sum"),
        avg_thickness=("thickness", "mean"),
        min_depth=("depth_start", "min"),
        max_depth=("depth_end", "max"),
        avg_gravel=("gravel_pct", "mean"),
        avg_sand=("sand_pct", "mean"),
        avg_silt=("silt_pct", "mean"),
        avg_clay=("clay_pct", "mean"),
        avg_organic=("organic_matter", "mean"),
        avg_water=("water_content", "mean"),
    ).reset_index()

    summary["total_thickness_pct"] = (summary["total_thickness"] / summary["total_thickness"].sum() * 100).round(2)
    return summary


def get_core_analysis(core_id: int, include_quality: bool = True) -> Dict[str, Any]:
    core_info = db.get_core_sample(core_id)
    if not core_info:
        return {}

    layers_df = db.get_core_layers(core_id)
    core_length = core_info.get("core_length")

    result = {
        "core_info": core_info,
        "layers": calculate_layer_thickness(layers_df),
        "missing_intervals": find_missing_intervals(layers_df, core_length),
        "anomalies": detect_anomalies(layers_df),
        "correlation": calculate_correlation(layers_df),
        "layer_summary": summarize_layer_types(layers_df),
    }

    if not result["layers"].empty:
        result["total_sampled_thickness"] = result["layers"]["thickness"].sum()
        result["total_missing_thickness"] = sum(
            m["thickness"] for m in result["missing_intervals"]
        )
        result["recovery_rate"] = (
            result["total_sampled_thickness"] /
            (result["total_sampled_thickness"] + result["total_missing_thickness"]) * 100
        ) if (result["total_sampled_thickness"] + result["total_missing_thickness"]) > 0 else 0

    if include_quality:
        quality_info = validator.detect_core_duplicates_and_overlaps(core_id)
        result["quality"] = quality_info
        result["duplicate_count"] = len(quality_info["duplicates"])
        result["overlap_count"] = len(quality_info["overlaps"])

    return result


def compare_cores(core_ids: List[int]) -> Dict[str, Any]:
    results = {}
    all_layers = []

    for core_id in core_ids:
        analysis = get_core_analysis(core_id)
        if analysis:
            sample_code = analysis["core_info"]["sample_code"]
            results[sample_code] = analysis

            if not analysis["layers"].empty:
                layers_copy = analysis["layers"].copy()
                layers_copy["sample_code"] = sample_code
                all_layers.append(layers_copy)

    combined_layers = pd.concat(all_layers, ignore_index=True) if all_layers else pd.DataFrame()

    cross_correlation = {}
    if not combined_layers.empty:
        indicators = ["gravel_pct", "sand_pct", "silt_pct", "clay_pct", "organic_matter", "water_content"]
        for ind in indicators:
            if ind in combined_layers.columns:
                pivot = combined_layers.pivot_table(
                    index="mid_depth", columns="sample_code", values=ind, aggfunc="mean"
                )
                if len(pivot.columns) >= 2:
                    cross_correlation[ind] = pivot.corr()

    comparison = {
        "individual_analyses": results,
        "combined_layers": combined_layers,
        "cross_correlation": cross_correlation,
    }

    return comparison


def get_station_analysis(station_code: str) -> Dict[str, Any]:
    cores_df = db.get_cores_by_station(station_code)
    if cores_df.empty:
        return {}

    core_ids = cores_df["id"].tolist()
    core_codes = cores_df["sample_code"].tolist()

    comparison = compare_cores(core_ids)

    station_info = db.get_station_cores_summary(station_code)
    if not station_info.empty:
        station_summary = station_info.iloc[0].to_dict()
    else:
        station_summary = {}

    layer_type_stats = {}
    if not comparison["combined_layers"].empty:
        combined = comparison["combined_layers"]
        for layer_name in combined["layer_name"].unique():
            layer_data = combined[combined["layer_name"] == layer_name]
            layer_type_stats[layer_name] = {
                "core_count": layer_data["sample_code"].nunique(),
                "total_thickness": layer_data["thickness"].sum(),
                "avg_thickness": layer_data["thickness"].mean(),
                "avg_gravel": layer_data["gravel_pct"].mean(),
                "avg_sand": layer_data["sand_pct"].mean(),
                "avg_silt": layer_data["silt_pct"].mean(),
                "avg_clay": layer_data["clay_pct"].mean(),
            }

    return {
        "station_code": station_code,
        "station_summary": station_summary,
        "core_count": len(core_ids),
        "core_codes": core_codes,
        "core_comparison": comparison,
        "layer_type_stats": layer_type_stats,
    }


def filter_cores(filters: Dict[str, Any]) -> pd.DataFrame:
    all_cores = db.get_all_core_samples()
    if all_cores.empty:
        return all_cores

    result = all_cores.copy()

    if filters.get("station_code") and filters["station_code"] != "全部":
        result = result[result["station_code"] == filters["station_code"]]

    if filters.get("sample_code_keyword"):
        keyword = filters["sample_code_keyword"].strip()
        if keyword:
            result = result[result["sample_code"].str.contains(keyword, case=False, na=False)]

    if filters.get("min_core_length") is not None:
        result = result[result["core_length"].fillna(0) >= filters["min_core_length"]]

    if filters.get("max_core_length") is not None:
        result = result[result["core_length"].fillna(0) <= filters["max_core_length"]]

    if filters.get("min_layer_count") is not None or filters.get("max_layer_count") is not None:
        layer_counts = []
        for _, core in result.iterrows():
            layers = db.get_core_layers(core["id"])
            layer_counts.append(len(layers))
        result["layer_count"] = layer_counts

        if filters.get("min_layer_count") is not None:
            result = result[result["layer_count"] >= filters["min_layer_count"]]
        if filters.get("max_layer_count") is not None:
            result = result[result["layer_count"] <= filters["max_layer_count"]]

    return result


def analyze_interlayer_correlation(core_ids: List[int], depth_range: Optional[Tuple[float, float]] = None) -> Dict[str, Any]:
    if len(core_ids) < 2:
        return {}

    comparison = compare_cores(core_ids)
    individual = comparison["individual_analyses"]

    layer_corr_results = {}
    indicators = ["gravel_pct", "sand_pct", "silt_pct", "clay_pct", "organic_matter", "water_content"]

    all_layer_names = set()
    for core_data in individual.values():
        if not core_data["layers"].empty:
            all_layer_names.update(core_data["layers"]["layer_name"].unique())

    for layer_name in sorted(all_layer_names):
        layer_data_all = []
        for sample_code, core_data in individual.items():
            if core_data["layers"].empty:
                continue
            layer_data = core_data["layers"][core_data["layers"]["layer_name"] == layer_name]
            if not layer_data.empty:
                for _, row in layer_data.iterrows():
                    row_data = {"sample_code": sample_code}
                    for ind in indicators:
                        if ind in row and pd.notna(row[ind]):
                            row_data[ind] = row[ind]
                    layer_data_all.append(row_data)

        if len(layer_data_all) >= 2:
            df = pd.DataFrame(layer_data_all)
            numeric_cols = [c for c in indicators if c in df.columns and df[c].notna().sum() >= 2]
            if len(numeric_cols) >= 2:
                layer_corr_results[layer_name] = {
                    "data": df,
                    "correlation": df[numeric_cols].corr(),
                    "core_count": df["sample_code"].nunique(),
                    "sample_count": len(df),
                }

    return {
        "layer_correlations": layer_corr_results,
        "total_layer_types": len(all_layer_names),
        "analyzed_layer_types": len(layer_corr_results),
    }


def generate_station_report(station_code: str) -> Dict[str, Any]:
    station_analysis = get_station_analysis(station_code)
    if not station_analysis:
        return {}

    report = {
        "station_code": station_code,
        "report_title": f"{station_code} 站位沉积柱样综合对比报告",
        "summary": station_analysis["station_summary"],
        "core_list": station_analysis["core_codes"],
        "core_count": station_analysis["core_count"],
    }

    cores_data = station_analysis["core_comparison"]["individual_analyses"]

    core_stats = []
    for sample_code, data in cores_data.items():
        if data["layers"].empty:
            continue
        stat = {
            "sample_code": sample_code,
            "layer_count": len(data["layers"]),
            "total_thickness": data.get("total_sampled_thickness", 0),
            "recovery_rate": data.get("recovery_rate", 0),
            "missing_thickness": data.get("total_missing_thickness", 0),
            "anomaly_count": len(data["anomalies"][data["anomalies"]["is_anomaly"]]) if not data["anomalies"].empty else 0,
            "avg_sand": data["layers"]["sand_pct"].mean(),
            "avg_silt": data["layers"]["silt_pct"].mean(),
            "avg_clay": data["layers"]["clay_pct"].mean(),
        }
        if "organic_matter" in data["layers"].columns:
            stat["avg_organic"] = data["layers"]["organic_matter"].mean()
        if "water_content" in data["layers"].columns:
            stat["avg_water"] = data["layers"]["water_content"].mean()
        core_stats.append(stat)

    report["core_statistics"] = core_stats

    if station_analysis["layer_type_stats"]:
        report["layer_type_statistics"] = station_analysis["layer_type_stats"]

    return report


def get_all_stations_with_cores() -> List[str]:
    stations_df = db.get_all_stations()
    if stations_df.empty:
        return []
    return stations_df["station_code"].tolist()


def get_missing_severity(missing_intervals: List[Dict[str, float]], core_length: Optional[float] = None) -> Dict[str, Any]:
    if not missing_intervals:
        return {"level": "good", "message": "无缺失层段", "total_missing": 0}

    total_missing = sum(m["thickness"] for m in missing_intervals)
    gap_count = len(missing_intervals)

    if core_length and core_length > 0:
        missing_pct = (total_missing / core_length) * 100
    else:
        missing_pct = 0

    if missing_pct < 5 and gap_count <= 1:
        level = "good"
        message = "缺失层段较少，数据质量良好"
    elif missing_pct < 15 and gap_count <= 3:
        level = "warning"
        message = "存在一定缺失层段，需关注数据完整性"
    else:
        level = "error"
        message = "缺失层段较多，建议补充采样或核实数据"

    return {
        "level": level,
        "message": message,
        "total_missing": total_missing,
        "missing_pct": missing_pct,
        "gap_count": gap_count,
    }
