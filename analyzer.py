import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional
import database as db


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
            "thickness": sorted_layers.iloc[0]["depth_start"]
        })

    for i in range(1, len(sorted_layers)):
        prev_end = sorted_layers.iloc[i - 1]["depth_end"]
        curr_start = sorted_layers.iloc[i]["depth_start"]
        if curr_start > prev_end:
            missing.append({
                "depth_start": prev_end,
                "depth_end": curr_start,
                "thickness": curr_start - prev_end
            })

    if core_length is not None:
        max_depth = sorted_layers["depth_end"].max()
        if max_depth < core_length:
            missing.append({
                "depth_start": max_depth,
                "depth_end": core_length,
                "thickness": core_length - max_depth
            })

    return missing


def detect_anomalies(layers_df: pd.DataFrame) -> pd.DataFrame:
    if layers_df.empty:
        return layers_df

    df = calculate_layer_thickness(layers_df)
    numeric_cols = ["gravel_pct", "sand_pct", "silt_pct", "clay_pct", "organic_matter", "water_content", "thickness"]
    existing_cols = [col for col in numeric_cols if col in df.columns]

    anomaly_flags = pd.DataFrame(index=df.index)

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


def calculate_correlation(layers_df: pd.DataFrame) -> pd.DataFrame:
    if layers_df.empty:
        return pd.DataFrame()

    numeric_cols = ["gravel_pct", "sand_pct", "silt_pct", "clay_pct", "organic_matter", "water_content"]
    existing_cols = [col for col in numeric_cols if col in layers_df.columns and layers_df[col].notna().sum() > 2]

    if len(existing_cols) < 2:
        return pd.DataFrame()

    df = layers_df[existing_cols].copy()
    corr_matrix = df.corr(method="pearson")
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


def get_core_analysis(core_id: int) -> Dict[str, Any]:
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

    comparison = {
        "individual_analyses": results,
        "combined_layers": pd.concat(all_layers, ignore_index=True) if all_layers else pd.DataFrame(),
        "cross_correlation": {},
    }

    return comparison
