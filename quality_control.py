import pandas as pd
from typing import List, Dict, Any, Optional
import database as db
import analyzer


ANOMALY_STATUS = {
    "pending": "待复核",
    "reviewing": "复核中",
    "confirmed": "已确认",
    "dismissed": "已驳回",
    "resolved": "已修复",
}


ANOMALY_TYPES = {
    "value_outlier": "数值异常",
    "depth_overlap": "深度重叠",
    "duplicate_layer": "重复层位",
    "missing_interval": "缺失层段",
    "percentage_error": "百分比错误",
    "other": "其他异常",
}


def scan_core_anomalies(core_id: int) -> Dict[str, Any]:
    analysis = analyzer.get_core_analysis(core_id)
    if not analysis:
        return {"core_id": core_id, "total_anomalies": 0, "anomalies": []}

    anomalies = []

    anomalies_df = analysis["anomalies"]
    if not anomalies_df.empty and "is_anomaly" in anomalies_df.columns:
        anomaly_layers = anomalies_df[anomalies_df["is_anomaly"]]
        for _, row in anomaly_layers.iterrows():
            anomalies.append({
                "layer_id": int(row["id"]),
                "layer_name": row["layer_name"],
                "depth_start": row["depth_start"],
                "depth_end": row["depth_end"],
                "anomaly_type": "value_outlier",
                "anomaly_details": row.get("anomaly_details", ""),
                "severity": "high" if "thickness" in str(row.get("anomaly_details", "")) else "medium",
            })

    quality = analysis.get("quality", {})
    for dup in quality.get("duplicates", []):
        anomalies.append({
            "layer_id": dup["layer_id_2"],
            "layer_id_1": dup["layer_id_1"],
            "layer_name": dup["layer_name"],
            "depth_start": dup["depth_start"],
            "depth_end": dup["depth_end"],
            "anomaly_type": "duplicate_layer",
            "anomaly_details": f"与层位ID {dup['layer_id_1']} 重复",
            "severity": "medium",
        })

    for overlap in quality.get("overlaps", []):
        anomalies.append({
            "layer_id": overlap["layer_id_2"],
            "layer_id_1": overlap["layer_id_1"],
            "layer_name": overlap["layer_name_2"],
            "depth_start": overlap["overlap_start"],
            "depth_end": overlap["overlap_end"],
            "anomaly_type": "depth_overlap",
            "anomaly_details": f"与层位「{overlap['layer_name_1']}」重叠，重叠厚度 {overlap['overlap_thickness']:.2f}cm",
            "severity": "high",
        })

    missing_intervals = analysis.get("missing_intervals", [])
    for missing in missing_intervals:
        if missing.get("type") == "middle_gap":
            anomalies.append({
                "layer_id": None,
                "layer_name": "缺失层段",
                "depth_start": missing["depth_start"],
                "depth_end": missing["depth_end"],
                "anomaly_type": "missing_interval",
                "anomaly_details": f"层间缺失，厚度 {missing['thickness']:.2f}cm",
                "severity": "medium",
            })

    return {
        "core_id": core_id,
        "total_anomalies": len(anomalies),
        "anomalies": anomalies,
        "by_type": _group_by_type(anomalies),
        "by_severity": _group_by_severity(anomalies),
    }


def _group_by_type(anomalies: List[Dict]) -> Dict[str, int]:
    result = {}
    for a in anomalies:
        t = a.get("anomaly_type", "other")
        result[t] = result.get(t, 0) + 1
    return result


def _group_by_severity(anomalies: List[Dict]) -> Dict[str, int]:
    result = {}
    for a in anomalies:
        s = a.get("severity", "low")
        result[s] = result.get(s, 0) + 1
    return result


def submit_anomaly_review(layer_id: int, core_id: int, anomaly_type: str,
                          anomaly_details: str = "") -> int:
    return db.add_anomaly_review(layer_id, core_id, anomaly_type, anomaly_details)


def review_anomaly(review_id: int, status: str, review_notes: str = "",
                   reviewer: str = "analyst") -> None:
    db.update_anomaly_review(review_id, status, review_notes, reviewer)


def get_anomaly_list(station_code: str = None, status: str = None,
                     anomaly_type: str = None) -> pd.DataFrame:
    reviews_df = db.get_anomaly_reviews(status=status)
    if reviews_df.empty:
        return reviews_df

    if station_code and station_code != "全部":
        reviews_df = reviews_df[reviews_df["station_code"] == station_code]

    if anomaly_type and anomaly_type != "全部":
        reviews_df = reviews_df[reviews_df["anomaly_type"] == anomaly_type]

    return reviews_df


def get_quality_dashboard_data() -> Dict[str, Any]:
    all_stations = db.get_all_stations()
    all_cores = db.get_all_core_samples()
    all_reviews = db.get_anomaly_reviews()

    station_stats = []
    for _, station in all_stations.iterrows():
        station_code = station["station_code"]
        station_cores = all_cores[all_cores["station_code"] == station_code]
        core_count = len(station_cores)

        total_layers = 0
        for _, core in station_cores.iterrows():
            layers = db.get_core_layers(core["id"])
            total_layers += len(layers)

        station_anomalies = all_reviews[all_reviews["station_code"] == station_code] if not all_reviews.empty else pd.DataFrame()

        station_stats.append({
            "station_code": station_code,
            "station_name": station.get("station_name", ""),
            "core_count": core_count,
            "total_layers": total_layers,
            "anomaly_count": len(station_anomalies),
            "pending_count": len(station_anomalies[station_anomalies["status"] == "pending"]) if not station_anomalies.empty else 0,
            "confirmed_count": len(station_anomalies[station_anomalies["status"] == "confirmed"]) if not station_anomalies.empty else 0,
        })

    overall_stats = {
        "total_stations": len(all_stations),
        "total_cores": len(all_cores),
        "total_layers": sum(s["total_layers"] for s in station_stats),
        "total_anomalies": len(all_reviews),
        "pending_anomalies": len(all_reviews[all_reviews["status"] == "pending"]) if not all_reviews.empty else 0,
        "resolved_anomalies": len(all_reviews[all_reviews["status"].isin(["resolved", "dismissed"])]) if not all_reviews.empty else 0,
    }

    return {
        "overall": overall_stats,
        "stations": station_stats,
    }


def get_core_version_history(core_id: int) -> Dict[str, Any]:
    versions_df = db.get_core_versions(core_id)
    core_info = db.get_core_sample(core_id)

    if versions_df.empty:
        return {
            "core_info": core_info,
            "current_version": core_info.get("version", 1) if core_info else 1,
            "total_changes": 0,
            "version_summary": [],
            "versions": versions_df,
        }

    layer_versions = {}
    for _, row in versions_df.iterrows():
        layer_id = row["layer_id"]
        if layer_id not in layer_versions:
            layer_versions[layer_id] = {
                "layer_name": row.get("current_layer_name", f"层位{layer_id}"),
                "versions": [],
            }
        layer_versions[layer_id]["versions"].append(row)

    version_summary = []
    for layer_id, data in layer_versions.items():
        version_summary.append({
            "layer_id": layer_id,
            "layer_name": data["layer_name"],
            "version_count": len(data["versions"]),
            "last_change": data["versions"][0]["created_at"] if data["versions"] else None,
        })

    return {
        "core_info": core_info,
        "current_version": core_info.get("version", 1) if core_info else 1,
        "total_changes": len(versions_df),
        "modified_layers": len(layer_versions),
        "version_summary": version_summary,
        "versions": versions_df,
    }


def export_quality_report(station_code: str = None) -> Dict[str, Any]:
    dashboard = get_quality_dashboard_data()

    if station_code and station_code != "全部":
        station_data = [s for s in dashboard["stations"] if s["station_code"] == station_code]
        dashboard["stations"] = station_data
        if station_data:
            dashboard["overall"]["total_stations"] = 1
            dashboard["overall"]["total_cores"] = station_data[0]["core_count"]
            dashboard["overall"]["total_layers"] = station_data[0]["total_layers"]
            dashboard["overall"]["total_anomalies"] = station_data[0]["anomaly_count"]

    anomalies = get_anomaly_list(station_code=station_code)

    return {
        "report_title": "沉积柱样质量控制报告",
        "generated_at": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
        "overview": dashboard["overall"],
        "station_details": dashboard["stations"],
        "anomalies": anomalies,
    }
