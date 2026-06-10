import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from scipy import stats, interpolate
import database as db


DATING_METHODS = [
    "AMS-14C",
    "常规14C",
    "OSL",
    "TL",
    "ESR",
    "210Pb",
    "137Cs",
    "U-Th",
    "古地磁",
    "生物地层",
    "层位对比",
    "其他",
]

MODEL_TYPES = {
    "linear": "线性拟合",
    "polynomial_2": "二次多项式",
    "polynomial_3": "三次多项式",
    "spline": "样条插值",
    "linear_segmented": "分段线性",
}


def validate_dating_point(depth: float, age: float, core_length: float = None,
                          existing_points: pd.DataFrame = None) -> Dict[str, Any]:
    errors = []
    warnings = []

    if depth is None or np.isnan(depth):
        errors.append("深度值不能为空")
    elif depth < 0:
        errors.append("深度值不能为负数")
    elif core_length is not None and depth > core_length:
        errors.append(f"深度值({depth} cm)超过柱样长度({core_length} cm)")

    if age is None or np.isnan(age):
        errors.append("年龄值不能为空")
    elif age < 0:
        errors.append("年龄值不能为负数")

    if existing_points is not None and not existing_points.empty:
        if depth is not None and not np.isnan(depth):
            if depth in existing_points["depth"].values:
                warnings.append(f"深度 {depth} cm 已存在年代点，可能造成重复")

        if len(existing_points) >= 2:
            sorted_points = existing_points.sort_values("depth")
            sorted_depths = sorted_points["depth"].values
            sorted_ages = sorted_points["age"].values

            if depth is not None and age is not None and not np.isnan(depth) and not np.isnan(age):
                for i in range(len(sorted_depths) - 1):
                    if sorted_depths[i] < depth < sorted_depths[i + 1]:
                        if sorted_ages[i] > age or age > sorted_ages[i + 1]:
                            if not (sorted_ages[i] <= age <= sorted_ages[i + 1]):
                                warnings.append(
                                    f"该点年龄({age})不满足单调性，位于深度 "
                                    f"{sorted_depths[i]}cm(年龄{sorted_ages[i]}) 和 "
                                    f"{sorted_depths[i+1]}cm(年龄{sorted_ages[i+1]}) 之间"
                                )

            age_depth_ratios = np.diff(sorted_ages) / np.maximum(np.diff(sorted_depths), 1e-6)
            if len(age_depth_ratios) > 0 and depth is not None and age is not None:
                if not np.isnan(depth) and not np.isnan(age):
                    all_depths = np.append(sorted_depths, depth)
                    all_ages = np.append(sorted_ages, age)
                    sort_idx = np.argsort(all_depths)
                    all_depths = all_depths[sort_idx]
                    all_ages = all_ages[sort_idx]
                    new_ratios = np.diff(all_ages) / np.maximum(np.diff(all_depths), 1e-6)
                    if len(new_ratios) > 0 and len(age_depth_ratios) > 0:
                        mean_ratio = np.mean(age_depth_ratios)
                        std_ratio = np.std(age_depth_ratios)
                        if std_ratio > 0:
                            for nr in new_ratios:
                                z_score = abs(nr - mean_ratio) / std_ratio
                                if z_score > 2.5:
                                    warnings.append(
                                        f"新增点导致沉积速率异常 (z-score={z_score:.2f})，可能为异常点"
                                    )

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }


def detect_anomalous_points(dating_points: pd.DataFrame, method: str = "zscore",
                            z_threshold: float = 2.5) -> pd.DataFrame:
    if dating_points.empty or len(dating_points) < 4:
        result = dating_points.copy()
        result["is_anomaly"] = False
        result["anomaly_reason"] = ""
        return result

    df = dating_points.copy().sort_values("depth").reset_index(drop=True)

    df["is_anomaly"] = False
    df["anomaly_reason"] = ""

    ages = df["age"].values
    depths = df["depth"].values

    if method == "zscore":
        if len(depths) > 1:
            rates = np.diff(ages) / np.maximum(np.diff(depths), 1e-6)
            if len(rates) > 1:
                mean_rate = np.mean(rates)
                std_rate = np.std(rates)
                if std_rate > 0:
                    for i in range(len(rates)):
                        z = abs(rates[i] - mean_rate) / std_rate
                        if z > z_threshold:
                            df.loc[i, "is_anomaly"] = True
                            df.loc[i, "anomaly_reason"] = (
                                f"与下一点间沉积速率异常(z={z:.2f})"
                            )
                            df.loc[i + 1, "is_anomaly"] = True
                            if not df.loc[i + 1, "anomaly_reason"]:
                                df.loc[i + 1, "anomaly_reason"] = (
                                    f"与上一点间沉积速率异常(z={z:.2f})"
                                )

    elif method == "iqr":
        if len(depths) > 1:
            rates = np.diff(ages) / np.maximum(np.diff(depths), 1e-6)
            if len(rates) > 3:
                q1, q3 = np.percentile(rates, [25, 75])
                iqr = q3 - q1
                lower = q1 - 1.5 * iqr
                upper = q3 + 1.5 * iqr
                for i in range(len(rates)):
                    if rates[i] < lower or rates[i] > upper:
                        df.loc[i, "is_anomaly"] = True
                        df.loc[i, "anomaly_reason"] = "区间沉积速率超出IQR范围"
                        df.loc[i + 1, "is_anomaly"] = True
                        if not df.loc[i + 1, "anomaly_reason"]:
                            df.loc[i + 1, "anomaly_reason"] = "区间沉积速率超出IQR范围"

    ages_clean = ages
    if len(ages_clean) > 3:
        slope, intercept, r_value, p_value, std_err = stats.linregress(depths, ages_clean)
        predicted_ages = slope * depths + intercept
        residuals = ages_clean - predicted_ages
        std_resid = np.std(residuals)
        if std_resid > 0:
            for i in range(len(df)):
                z_res = abs(residuals[i]) / std_resid
                if z_res > z_threshold:
                    df.loc[i, "is_anomaly"] = True
                    existing_reason = df.loc[i, "anomaly_reason"]
                    new_reason = f"线性拟合残差异常(z={z_res:.2f})"
                    df.loc[i, "anomaly_reason"] = (
                        f"{existing_reason}; {new_reason}" if existing_reason else new_reason
                    )

    return df


def fit_age_depth_model(dating_points: pd.DataFrame, model_type: str = "linear",
                        smooth_factor: float = 0.0) -> Dict[str, Any]:
    if dating_points.empty or len(dating_points) < 2:
        return {"success": False, "error": "至少需要2个有效年代点才能建立模型"}

    valid_points = dating_points[dating_points.get("is_valid", 1) == 1].copy()
    if valid_points.empty or len(valid_points) < 2:
        valid_points = dating_points.copy()

    valid_points = valid_points.sort_values("depth").reset_index(drop=True)
    depths = valid_points["depth"].values.astype(float)
    ages = valid_points["age"].values.astype(float)

    if len(depths) < 2:
        return {"success": False, "error": "有效年代点不足"}

    result = {
        "success": True,
        "model_type": model_type,
        "depths": depths.tolist(),
        "ages": ages.tolist(),
        "model_params": {},
    }

    try:
        if model_type == "linear":
            slope, intercept, r_value, p_value, std_err = stats.linregress(depths, ages)
            result["model_params"] = {
                "slope": float(slope),
                "intercept": float(intercept),
                "r_squared": float(r_value ** 2),
                "p_value": float(p_value),
                "std_err": float(std_err),
            }
            predicted = slope * depths + intercept

        elif model_type in ["polynomial_2", "polynomial_3"]:
            degree = 2 if model_type == "polynomial_2" else 3
            degree = min(degree, len(depths) - 1)
            coeffs = np.polyfit(depths, ages, degree)
            poly = np.poly1d(coeffs)
            predicted = poly(depths)
            ss_res = np.sum((ages - predicted) ** 2)
            ss_tot = np.sum((ages - np.mean(ages)) ** 2)
            r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
            result["model_params"] = {
                "coefficients": coeffs.tolist(),
                "degree": degree,
                "r_squared": float(r_squared),
            }

        elif model_type == "spline":
            k = min(3, len(depths) - 1)
            if k >= 1:
                tck = interpolate.splrep(depths, ages, s=smooth_factor, k=k)
                predicted = interpolate.splev(depths, tck)
                ss_res = np.sum((ages - predicted) ** 2)
                ss_tot = np.sum((ages - np.mean(ages)) ** 2)
                r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
                result["model_params"] = {
                    "tck": {
                        "t": tck[0].tolist(),
                        "c": tck[1].tolist(),
                        "k": int(tck[2]),
                    },
                    "smooth_factor": float(smooth_factor),
                    "r_squared": float(r_squared),
                }
            else:
                slope, intercept, r_value, p_value, std_err = stats.linregress(depths, ages)
                result["model_params"] = {
                    "slope": float(slope),
                    "intercept": float(intercept),
                    "r_squared": float(r_value ** 2),
                    "note": "点数不足，使用线性拟合",
                }
                predicted = slope * depths + intercept

        elif model_type == "linear_segmented":
            predicted = ages.copy()
            result["model_params"] = {
                "segments": [],
                "r_squared": 1.0,
            }
            for i in range(len(depths) - 1):
                d1, d2 = depths[i], depths[i + 1]
                a1, a2 = ages[i], ages[i + 1]
                seg_slope = (a2 - a1) / (d2 - d1) if d2 != d1 else 0
                seg_intercept = a1 - seg_slope * d1
                result["model_params"]["segments"].append({
                    "depth_start": float(d1),
                    "depth_end": float(d2),
                    "slope": float(seg_slope),
                    "intercept": float(seg_intercept),
                })

        else:
            return {"success": False, "error": f"不支持的模型类型: {model_type}"}

        rmse = float(np.sqrt(np.mean((ages - predicted) ** 2)))
        result["rmse"] = rmse
        if "r_squared" not in result["model_params"]:
            ss_res = np.sum((ages - predicted) ** 2)
            ss_tot = np.sum((ages - np.mean(ages)) ** 2)
            result["r_squared"] = float(1 - (ss_res / ss_tot)) if ss_tot > 0 else 0.0
        else:
            result["r_squared"] = float(result["model_params"]["r_squared"])

        result["predicted_ages"] = predicted.tolist()

    except Exception as e:
        return {"success": False, "error": f"模型拟合失败: {str(e)}"}

    return result


def predict_age(model_result: Dict[str, Any], depth: float) -> Optional[float]:
    if not model_result.get("success"):
        return None

    model_type = model_result["model_type"]
    params = model_result["model_params"]

    try:
        if model_type == "linear":
            return float(params["slope"] * depth + params["intercept"])

        elif model_type in ["polynomial_2", "polynomial_3"]:
            coeffs = np.array(params["coefficients"])
            poly = np.poly1d(coeffs)
            return float(poly(depth))

        elif model_type == "spline":
            if "tck" in params:
                tck = (
                    np.array(params["tck"]["t"]),
                    np.array(params["tck"]["c"]),
                    params["tck"]["k"],
                )
                return float(interpolate.splev(depth, tck))
            elif "slope" in params:
                return float(params["slope"] * depth + params["intercept"])

        elif model_type == "linear_segmented":
            segments = params.get("segments", [])
            for seg in segments:
                if seg["depth_start"] <= depth <= seg["depth_end"]:
                    return float(seg["slope"] * depth + seg["intercept"])
            if segments:
                if depth < segments[0]["depth_start"]:
                    seg = segments[0]
                    return float(seg["slope"] * depth + seg["intercept"])
                else:
                    seg = segments[-1]
                    return float(seg["slope"] * depth + seg["intercept"])

    except Exception:
        return None

    return None


def predict_age_batch(model_result: Dict[str, Any], depths: np.ndarray) -> np.ndarray:
    result = []
    for d in depths:
        age = predict_age(model_result, float(d))
        result.append(age if age is not None else np.nan)
    return np.array(result)


def calculate_sedimentation_rates(model_result: Dict[str, Any],
                                  layers_df: pd.DataFrame = None,
                                  max_depth: float = None) -> pd.DataFrame:
    if not model_result.get("success"):
        return pd.DataFrame()

    rates = []

    if layers_df is not None and not layers_df.empty:
        for _, layer in layers_df.iterrows():
            d_start = layer["depth_start"]
            d_end = layer["depth_end"]
            a_start = predict_age(model_result, float(d_start))
            a_end = predict_age(model_result, float(d_end))

            if a_start is not None and a_end is not None:
                age_diff = a_end - a_start
                depth_diff = d_end - d_start
                if age_diff > 0 and depth_diff > 0:
                    rate = (depth_diff / age_diff) * 1000
                    rates.append({
                        "depth_start": float(d_start),
                        "depth_end": float(d_end),
                        "mid_depth": float((d_start + d_end) / 2),
                        "age_start": float(a_start),
                        "age_end": float(a_end),
                        "age_duration": float(age_diff),
                        "thickness": float(depth_diff),
                        "sedimentation_rate": float(rate),
                        "layer_name": layer.get("layer_name", ""),
                    })
    else:
        depths = np.array(model_result.get("depths", []))
        if len(depths) >= 2:
            ages = np.array(model_result.get("ages", []))
            sort_idx = np.argsort(depths)
            depths = depths[sort_idx]
            ages = ages[sort_idx]

            for i in range(len(depths) - 1):
                d_start, d_end = depths[i], depths[i + 1]
                a_start, a_end = ages[i], ages[i + 1]
                age_diff = a_end - a_start
                depth_diff = d_end - d_start
                if age_diff > 0 and depth_diff > 0:
                    rate = (depth_diff / age_diff) * 1000
                    rates.append({
                        "depth_start": float(d_start),
                        "depth_end": float(d_end),
                        "mid_depth": float((d_start + d_end) / 2),
                        "age_start": float(a_start),
                        "age_end": float(a_end),
                        "age_duration": float(age_diff),
                        "thickness": float(depth_diff),
                        "sedimentation_rate": float(rate),
                        "layer_name": "",
                    })

    if max_depth is not None and rates:
        last_rate = rates[-1]
        if last_rate["depth_end"] < max_depth:
            d_start = last_rate["depth_end"]
            d_end = max_depth
            a_start = predict_age(model_result, float(d_start))
            a_end = predict_age(model_result, float(d_end))
            if a_start is not None and a_end is not None:
                age_diff = a_end - a_start
                depth_diff = d_end - d_start
                if age_diff > 0 and depth_diff > 0:
                    rate = (depth_diff / age_diff) * 1000
                    rates.append({
                        "depth_start": float(d_start),
                        "depth_end": float(d_end),
                        "mid_depth": float((d_start + d_end) / 2),
                        "age_start": float(a_start),
                        "age_end": float(a_end),
                        "age_duration": float(age_diff),
                        "thickness": float(depth_diff),
                        "sedimentation_rate": float(rate),
                        "layer_name": "",
                    })

    return pd.DataFrame(rates)


def compare_layers_temporal(core_id_a: int, core_id_b: int,
                            model_a: Dict[str, Any], model_b: Dict[str, Any],
                            alignment_groups: List[Dict] = None) -> pd.DataFrame:
    layers_a = db.get_core_layers(core_id_a)
    layers_b = db.get_core_layers(core_id_b)

    if layers_a.empty or layers_b.empty:
        return pd.DataFrame()

    comparisons = []

    if alignment_groups:
        for group in alignment_groups:
            layer_a_info = None
            layer_b_info = None
            for member in group.get("members", []):
                if member.get("core_id") == core_id_a:
                    layer = layers_a[layers_a["id"] == member.get("layer_id")]
                    if not layer.empty:
                        layer_a_info = layer.iloc[0]
                elif member.get("core_id") == core_id_b:
                    layer = layers_b[layers_b["id"] == member.get("layer_id")]
                    if not layer.empty:
                        layer_b_info = layer.iloc[0]

            if layer_a_info is not None and layer_b_info is not None:
                mid_a = (layer_a_info["depth_start"] + layer_a_info["depth_end"]) / 2
                mid_b = (layer_b_info["depth_start"] + layer_b_info["depth_end"]) / 2
                age_a = predict_age(model_a, float(mid_a))
                age_b = predict_age(model_b, float(mid_b))

                comparisons.append({
                    "group_id": group.get("group_id"),
                    "layer_a": layer_a_info["layer_name"],
                    "depth_a": float(mid_a),
                    "age_a": age_a,
                    "layer_b": layer_b_info["layer_name"],
                    "depth_b": float(mid_b),
                    "age_b": age_b,
                    "age_diff": float(age_b - age_a) if age_a and age_b else None,
                    "depth_diff": float(mid_b - mid_a),
                })
    else:
        for _, la in layers_a.iterrows():
            mid_a = (la["depth_start"] + la["depth_end"]) / 2
            age_a = predict_age(model_a, float(mid_a))
            if age_a is None:
                continue

            best_match = None
            best_diff = float("inf")
            for _, lb in layers_b.iterrows():
                mid_b = (lb["depth_start"] + lb["depth_end"]) / 2
                age_b = predict_age(model_b, float(mid_b))
                if age_b is None:
                    continue
                diff = abs(age_a - age_b)
                if diff < best_diff:
                    best_diff = diff
                    best_match = (lb, mid_b, age_b)

            if best_match is not None:
                lb, mid_b, age_b = best_match
                comparisons.append({
                    "group_id": None,
                    "layer_a": la["layer_name"],
                    "depth_a": float(mid_a),
                    "age_a": age_a,
                    "layer_b": lb["layer_name"],
                    "depth_b": float(mid_b),
                    "age_b": age_b,
                    "age_diff": float(age_b - age_a),
                    "depth_diff": float(mid_b - mid_a),
                })

    return pd.DataFrame(comparisons)


def compare_stations_sedimentation(core_ids: List[int],
                                   models: Dict[int, Dict[str, Any]],
                                   layers_dict: Dict[int, pd.DataFrame] = None) -> pd.DataFrame:
    all_rates = []

    for core_id in core_ids:
        model = models.get(core_id)
        if not model or not model.get("success"):
            continue

        layers = None
        if layers_dict:
            layers = layers_dict.get(core_id)

        rates_df = calculate_sedimentation_rates(model, layers)
        if not rates_df.empty:
            core_info = db.get_core_sample(core_id)
            sample_code = core_info.get("sample_code", f"Core_{core_id}") if core_info else f"Core_{core_id}"
            station_code = core_info.get("station_code", "") if core_info else ""
            rates_df["core_id"] = core_id
            rates_df["sample_code"] = sample_code
            rates_df["station_code"] = station_code
            all_rates.append(rates_df)

    if not all_rates:
        return pd.DataFrame()

    return pd.concat(all_rates, ignore_index=True)


def generate_chronology_report(core_id: int, dating_points: pd.DataFrame,
                               model_result: Dict[str, Any],
                               rates_df: pd.DataFrame,
                               annotations: pd.DataFrame = None) -> str:
    core_info = db.get_core_sample(core_id)
    sample_code = core_info.get("sample_code", "") if core_info else ""
    station_code = core_info.get("station_code", "") if core_info else ""

    lines = []
    lines.append("=" * 60)
    lines.append("海底沉积柱样年代约束与沉积速率分析报告")
    lines.append("=" * 60)
    lines.append(f"生成时间: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"站位: {station_code}")
    lines.append(f"柱样编号: {sample_code}")
    lines.append("")

    lines.append("-" * 40)
    lines.append("一、年代点统计")
    lines.append("-" * 40)
    if not dating_points.empty:
        valid_count = dating_points[dating_points.get("is_valid", 1) == 1].shape[0]
        anomaly_count = dating_points[dating_points.get("is_anomaly", 0) == 1].shape[0]
        lines.append(f"年代点总数: {len(dating_points)}")
        lines.append(f"有效年代点数: {valid_count}")
        lines.append(f"异常年代点数: {anomaly_count}")
        lines.append(f"深度范围: {dating_points['depth'].min():.1f} - {dating_points['depth'].max():.1f} cm")
        lines.append(f"年龄范围: {dating_points['age'].min():.1f} - {dating_points['age'].max():.1f} a BP")
        lines.append("")
        lines.append("年代点详情:")
        lines.append(f"{'ID':<6} {'深度(cm)':<12} {'年龄(a BP)':<14} {'方法':<14} {'状态':<10}")
        for _, row in dating_points.iterrows():
            status = "异常" if row.get("is_anomaly", 0) == 1 else "有效"
            if row.get("is_valid", 1) == 0:
                status = "无效"
            lines.append(
                f"{row.get('id', ''):<6} "
                f"{row['depth']:<12.1f} "
                f"{row['age']:<14.1f} "
                f"{str(row.get('dating_method', '')):<14} "
                f"{status:<10}"
            )
    else:
        lines.append("暂无年代点数据")
    lines.append("")

    lines.append("-" * 40)
    lines.append("二、年龄-深度模型")
    lines.append("-" * 40)
    if model_result.get("success"):
        model_type_name = MODEL_TYPES.get(model_result["model_type"], model_result["model_type"])
        lines.append(f"模型类型: {model_type_name}")
        lines.append(f"R²: {model_result.get('r_squared', 'N/A')}")
        lines.append(f"RMSE: {model_result.get('rmse', 'N/A')}")
        params = model_result.get("model_params", {})
        if "slope" in params:
            lines.append(f"沉积速率(斜率): {params['slope'] * 1000:.2f} cm/ka")
            lines.append(f"地表年龄(截距): {params['intercept']:.2f} a BP")
    else:
        lines.append(f"模型构建失败: {model_result.get('error', '未知错误')}")
    lines.append("")

    lines.append("-" * 40)
    lines.append("三、沉积速率分段统计")
    lines.append("-" * 40)
    if not rates_df.empty:
        lines.append(f"速率段数: {len(rates_df)}")
        lines.append(f"平均沉积速率: {rates_df['sedimentation_rate'].mean():.2f} cm/ka")
        lines.append(f"最大沉积速率: {rates_df['sedimentation_rate'].max():.2f} cm/ka "
                     f"({rates_df.loc[rates_df['sedimentation_rate'].idxmax(), 'depth_start']:.1f}-"
                     f"{rates_df.loc[rates_df['sedimentation_rate'].idxmax(), 'depth_end']:.1f} cm)")
        lines.append(f"最小沉积速率: {rates_df['sedimentation_rate'].min():.2f} cm/ka "
                     f"({rates_df.loc[rates_df['sedimentation_rate'].idxmin(), 'depth_start']:.1f}-"
                     f"{rates_df.loc[rates_df['sedimentation_rate'].idxmin(), 'depth_end']:.1f} cm)")
        lines.append("")
        lines.append(f"{'深度区间(cm)':<20} {'年龄区间(a BP)':<22} {'时长(a)':<12} {'速率(cm/ka)':<14}")
        for _, row in rates_df.iterrows():
            lines.append(
                f"{row['depth_start']:.1f}-{row['depth_end']:<13.1f} "
                f"{row['age_start']:.1f}-{row['age_end']:<15.1f} "
                f"{row['age_duration']:<12.1f} "
                f"{row['sedimentation_rate']:<14.2f}"
            )
    else:
        lines.append("暂无沉积速率数据")
    lines.append("")

    if annotations is not None and not annotations.empty:
        lines.append("-" * 40)
        lines.append("四、备注与修正记录")
        lines.append("-" * 40)
        for _, row in annotations.iterrows():
            lines.append(f"[{row.get('created_at', '')}] "
                         f"{row.get('author', '')} - "
                         f"{row.get('annotation_type', '')}: "
                         f"{row.get('content', '')}")
        lines.append("")

    lines.append("=" * 60)
    lines.append("报告结束")
    lines.append("=" * 60)

    return "\n".join(lines)


def get_chronology_summary(core_ids: List[int]) -> pd.DataFrame:
    summary = []
    for core_id in core_ids:
        core_info = db.get_core_sample(core_id)
        dating_points = db.get_dating_points(core_id, valid_only=True)
        models = db.get_age_depth_models(core_id)
        rates = db.get_sedimentation_rates(core_id=core_id)

        avg_rate = None
        if not rates.empty:
            avg_rate = rates["sedimentation_rate"].mean()

        summary.append({
            "core_id": core_id,
            "station_code": core_info.get("station_code", "") if core_info else "",
            "sample_code": core_info.get("sample_code", "") if core_info else "",
            "dating_point_count": len(dating_points),
            "model_count": len(models),
            "avg_sedimentation_rate": avg_rate,
            "has_chronology": len(dating_points) > 0,
        })

    return pd.DataFrame(summary)
