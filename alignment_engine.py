import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from scipy import stats
import database as db


def compute_layer_signature(layers_df: pd.DataFrame) -> pd.DataFrame:
    if layers_df.empty:
        return layers_df
    df = layers_df.copy()
    indicators = ["gravel_pct", "sand_pct", "silt_pct", "clay_pct", "organic_matter", "water_content"]
    existing = [c for c in indicators if c in df.columns and df[c].notna().any()]
    if not existing:
        df["signature"] = 0.0
        return df
    df["signature"] = df[existing].fillna(0).values.tolist()
    return df


def _euclidean_distance(vec1: np.ndarray, vec2: np.ndarray) -> float:
    if len(vec1) != len(vec2):
        return float("inf")
    diff = vec1 - vec2
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    if norm1 == 0 and norm2 == 0:
        return 0.0
    return float(np.linalg.norm(diff) / max(norm1 + norm2, 1e-10))


SURFACE_TYPE_LABELS = {
    "flooding_surface": "海侵面",
    "regression_surface": "海退面",
    "lithology_change": "岩性突变面",
    "gradational_change": "渐变面",
    "layer_boundary": "层位界面",
    "unknown": "未知界面",
}

DEFAULT_INDICATOR_WEIGHTS = {
    "gravel_pct": 1.0,
    "sand_pct": 1.5,
    "silt_pct": 1.2,
    "clay_pct": 1.5,
    "organic_matter": 0.8,
    "water_content": 0.8,
}


def _weighted_cosine_similarity(vec1: np.ndarray, vec2: np.ndarray,
                                 weights: Optional[np.ndarray] = None) -> float:
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    if weights is not None:
        vec1_w = vec1 * weights[:len(vec1)]
        vec2_w = vec2 * weights[:len(vec2)]
        dot = np.dot(vec1_w, vec2_w)
        denom = np.linalg.norm(vec1_w) * np.linalg.norm(vec2_w)
        return float(dot / max(denom, 1e-10))
    return float(np.dot(vec1, vec2) / (norm1 * norm2))


def _dtw_distance(seq_a: np.ndarray, seq_b: np.ndarray) -> float:
    n, m = len(seq_a), len(seq_b)
    if n == 0 or m == 0:
        return float("inf")
    dtw_matrix = np.full((n + 1, m + 1), np.inf)
    dtw_matrix[0, 0] = 0.0
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = np.linalg.norm(seq_a[i - 1] - seq_b[j - 1])
            dtw_matrix[i, j] = cost + min(
                dtw_matrix[i - 1, j],
                dtw_matrix[i, j - 1],
                dtw_matrix[i - 1, j - 1],
            )
    return float(dtw_matrix[n, m])


def _dtw_alignment_path(seq_a: np.ndarray, seq_b: np.ndarray) -> List[Tuple[int, int]]:
    n, m = len(seq_a), len(seq_b)
    if n == 0 or m == 0:
        return []
    dtw_matrix = np.full((n + 1, m + 1), np.inf)
    dtw_matrix[0, 0] = 0.0
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = np.linalg.norm(seq_a[i - 1] - seq_b[j - 1])
            dtw_matrix[i, j] = cost + min(
                dtw_matrix[i - 1, j],
                dtw_matrix[i, j - 1],
                dtw_matrix[i - 1, j - 1],
            )
    path = []
    i, j = n, m
    while i > 0 and j > 0:
        path.append((i - 1, j - 1))
        candidates = [
            (dtw_matrix[i - 1, j - 1], i - 1, j - 1),
            (dtw_matrix[i - 1, j], i - 1, j),
            (dtw_matrix[i, j - 1], i, j - 1),
        ]
        _, i, j = min(candidates, key=lambda x: x[0])
    path.reverse()
    return path


def _prepare_core_vectors(layers_df: pd.DataFrame, indicators: List[str],
                           indicator_weights: Optional[Dict[str, float]] = None) -> np.ndarray:
    if layers_df.empty:
        return np.array([])
    existing = [c for c in indicators if c in layers_df.columns]
    if not existing:
        return np.array([])
    weights = indicator_weights or DEFAULT_INDICATOR_WEIGHTS
    w = np.array([weights.get(c, 1.0) for c in existing])
    data = layers_df[existing].fillna(0).values.astype(float)
    data = data * w[:len(existing)]
    from sklearn.preprocessing import StandardScaler
    if data.shape[0] > 1:
        scaler = StandardScaler()
        data = scaler.fit_transform(data)
    return data


def _cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return float(np.dot(vec1, vec2) / (norm1 * norm2))


def align_horizons(core_ids: List[int], method: str = "combined",
                   similarity_threshold: float = 0.6,
                   depth_tolerance: float = 10.0,
                   indicator_weights: Optional[Dict[str, float]] = None,
                   enforce_stratigraphic_order: bool = True) -> Dict[str, Any]:
    if len(core_ids) < 2:
        return {"alignments": [], "aligned_groups": [], "unaligned_layers": [], "quality": {}}

    core_data = {}
    indicators = ["gravel_pct", "sand_pct", "silt_pct", "clay_pct", "organic_matter", "water_content"]

    for core_id in core_ids:
        core_info = db.get_core_sample(core_id)
        layers_df = db.get_core_layers(core_id)
        if layers_df.empty:
            continue
        sample_code = core_info["sample_code"]
        layers_df["thickness"] = layers_df["depth_end"] - layers_df["depth_start"]
        layers_df["mid_depth"] = (layers_df["depth_start"] + layers_df["depth_end"]) / 2
        layers_df["sample_code"] = sample_code
        core_data[sample_code] = {
            "core_id": core_id,
            "core_info": core_info,
            "layers": layers_df,
        }

    if len(core_data) < 2:
        return {"alignments": [], "aligned_groups": [], "unaligned_layers": [], "quality": {}}

    if method == "dtw":
        return _align_horizons_dtw(core_data, indicators, similarity_threshold,
                                    depth_tolerance, indicator_weights)

    weights = indicator_weights or DEFAULT_INDICATOR_WEIGHTS
    alignments = []
    sample_codes = list(core_data.keys())

    for i in range(len(sample_codes)):
        for j in range(i + 1, len(sample_codes)):
            code_a = sample_codes[i]
            code_b = sample_codes[j]
            layers_a = core_data[code_a]["layers"]
            layers_b = core_data[code_b]["layers"]

            core_a = core_data[code_a]["core_info"]
            core_b = core_data[code_b]["core_info"]
            len_a = core_a.get("core_length") or layers_a["depth_end"].max()
            len_b = core_b.get("core_length") or layers_b["depth_end"].max()

            for idx_a, row_a in layers_a.iterrows():
                for idx_b, row_b in layers_b.iterrows():
                    norm_depth_a = row_a["mid_depth"] / max(len_a, 1)
                    norm_depth_b = row_b["mid_depth"] / max(len_b, 1)
                    depth_diff = abs(norm_depth_a - norm_depth_b) * max(len_a, len_b)

                    if enforce_stratigraphic_order:
                        strat_penalty = _stratigraphic_order_penalty(
                            layers_a, layers_b, idx_a, idx_b, norm_depth_a, norm_depth_b
                        )
                    else:
                        strat_penalty = 0.0

                    vec_a = row_a[[c for c in indicators if c in row_a.index and pd.notna(row_a[c])]].values.astype(float)
                    vec_b = row_b[[c for c in indicators if c in row_b.index and pd.notna(row_b[c])]].values.astype(float)

                    min_len = min(len(vec_a), len(vec_b))
                    if min_len < 2:
                        continue

                    weight_arr = np.array([weights.get(c, 1.0) for c in indicators
                                           if c in row_a.index and pd.notna(row_a[c])
                                           and c in row_b.index and pd.notna(row_b[c])])
                    if len(weight_arr) < min_len:
                        weight_arr = np.ones(min_len)
                    vec_a_w = vec_a[:min_len] * weight_arr[:min_len]
                    vec_b_w = vec_b[:min_len] * weight_arr[:min_len]

                    if method == "lithology":
                        similarity = _weighted_cosine_similarity(vec_a_w, vec_b_w)
                    elif method == "depth":
                        depth_sim = max(0, 1 - depth_diff / max(depth_tolerance, 1))
                        similarity = depth_sim
                    else:
                        litho_sim = _weighted_cosine_similarity(vec_a_w, vec_b_w)
                        depth_sim = max(0, 1 - depth_diff / max(depth_tolerance, 1))
                        similarity = 0.6 * litho_sim + 0.4 * depth_sim

                    similarity *= (1.0 - strat_penalty)

                    layer_name_match = 1.0 if row_a["layer_name"] == row_b["layer_name"] else 0.0
                    combined_score = 0.5 * similarity + 0.3 * layer_name_match + 0.2 * (1 - abs(norm_depth_a - norm_depth_b))

                    if combined_score >= similarity_threshold:
                        alignments.append({
                            "core_a": code_a,
                            "core_b": code_b,
                            "layer_id_a": int(row_a["id"]),
                            "layer_id_b": int(row_b["id"]),
                            "layer_name_a": row_a["layer_name"],
                            "layer_name_b": row_b["layer_name"],
                            "depth_a": row_a["mid_depth"],
                            "depth_b": row_b["mid_depth"],
                            "norm_depth_a": norm_depth_a,
                            "norm_depth_b": norm_depth_b,
                            "similarity": round(similarity, 4),
                            "combined_score": round(combined_score, 4),
                            "layer_name_match": layer_name_match == 1.0,
                            "strat_penalty": round(strat_penalty, 4),
                        })

    aligned_groups = _build_alignment_groups(alignments, sample_codes)

    aligned_layer_ids = set()
    for group in aligned_groups:
        for member in group["members"]:
            aligned_layer_ids.add((member["sample_code"], member["layer_id"]))

    unaligned_layers = []
    for code in sample_codes:
        for _, row in core_data[code]["layers"].iterrows():
            if (code, int(row["id"])) not in aligned_layer_ids:
                unaligned_layers.append({
                    "sample_code": code,
                    "layer_id": int(row["id"]),
                    "layer_name": row["layer_name"],
                    "mid_depth": row["mid_depth"],
                })

    quality = assess_alignment_quality(aligned_groups, unaligned_layers, core_data)

    return {
        "alignments": alignments,
        "aligned_groups": aligned_groups,
        "unaligned_layers": unaligned_layers,
        "core_data": core_data,
        "method": method,
        "threshold": similarity_threshold,
        "quality": quality,
    }


def _align_horizons_dtw(core_data: Dict, indicators: List[str],
                          similarity_threshold: float,
                          depth_tolerance: float,
                          indicator_weights: Optional[Dict[str, float]]) -> Dict[str, Any]:
    sample_codes = list(core_data.keys())
    weights = indicator_weights or DEFAULT_INDICATOR_WEIGHTS
    all_alignments = []

    for i in range(len(sample_codes)):
        for j in range(i + 1, len(sample_codes)):
            code_a = sample_codes[i]
            code_b = sample_codes[j]
            layers_a = core_data[code_a]["layers"].sort_values("depth_start").reset_index(drop=True)
            layers_b = core_data[code_b]["layers"].sort_values("depth_start").reset_index(drop=True)

            core_a = core_data[code_a]["core_info"]
            core_b = core_data[code_b]["core_info"]
            len_a = core_a.get("core_length") or layers_a["depth_end"].max()
            len_b = core_b.get("core_length") or layers_b["depth_end"].max()

            vecs_a = _prepare_core_vectors(layers_a, indicators, weights)
            vecs_b = _prepare_core_vectors(layers_b, indicators, weights)

            if len(vecs_a) == 0 or len(vecs_b) == 0:
                continue

            path = _dtw_alignment_path(vecs_a, vecs_b)
            max_dtw_dist = _dtw_distance(vecs_a, vecs_b)
            norm_factor = max(len(vecs_a), len(vecs_b)) * np.max(
                [np.linalg.norm(v) for v in vecs_a] + [np.linalg.norm(v) for v in vecs_b] + [1.0]
            )
            normalized_dtw = max_dtw_dist / max(norm_factor, 1e-10)

            for idx_a, idx_b in path:
                row_a = layers_a.iloc[idx_a]
                row_b = layers_b.iloc[idx_b]

                norm_depth_a = row_a["mid_depth"] / max(len_a, 1)
                norm_depth_b = row_b["mid_depth"] / max(len_b, 1)

                dtw_sim = max(0, 1.0 - normalized_dtw)
                depth_sim = max(0, 1 - abs(norm_depth_a - norm_depth_b) * max(len_a, len_b) / max(depth_tolerance, 1))
                layer_name_match = 1.0 if row_a["layer_name"] == row_b["layer_name"] else 0.0

                similarity = 0.5 * dtw_sim + 0.3 * depth_sim + 0.2 * layer_name_match

                if similarity >= similarity_threshold:
                    all_alignments.append({
                        "core_a": code_a,
                        "core_b": code_b,
                        "layer_id_a": int(row_a["id"]),
                        "layer_id_b": int(row_b["id"]),
                        "layer_name_a": row_a["layer_name"],
                        "layer_name_b": row_b["layer_name"],
                        "depth_a": row_a["mid_depth"],
                        "depth_b": row_b["mid_depth"],
                        "norm_depth_a": norm_depth_a,
                        "norm_depth_b": norm_depth_b,
                        "similarity": round(similarity, 4),
                        "combined_score": round(similarity, 4),
                        "layer_name_match": layer_name_match == 1.0,
                        "dtw_path_idx": (idx_a, idx_b),
                    })

    aligned_groups = _build_alignment_groups(all_alignments, sample_codes)

    aligned_layer_ids = set()
    for group in aligned_groups:
        for member in group["members"]:
            aligned_layer_ids.add((member["sample_code"], member["layer_id"]))

    unaligned_layers = []
    for code in sample_codes:
        for _, row in core_data[code]["layers"].iterrows():
            if (code, int(row["id"])) not in aligned_layer_ids:
                unaligned_layers.append({
                    "sample_code": code,
                    "layer_id": int(row["id"]),
                    "layer_name": row["layer_name"],
                    "mid_depth": row["mid_depth"],
                })

    quality = assess_alignment_quality(aligned_groups, unaligned_layers, core_data)

    return {
        "alignments": all_alignments,
        "aligned_groups": aligned_groups,
        "unaligned_layers": unaligned_layers,
        "core_data": core_data,
        "method": "dtw",
        "threshold": similarity_threshold,
        "quality": quality,
    }


def _stratigraphic_order_penalty(layers_a: pd.DataFrame, layers_b: pd.DataFrame,
                                   idx_a, idx_b: int,
                                   norm_depth_a: float, norm_depth_b: float) -> float:
    pos_a = layers_a.index.get_loc(idx_a) if idx_a in layers_a.index else 0
    pos_b = layers_b.index.get_loc(idx_b) if idx_b in layers_b.index else 0
    n_a = len(layers_a)
    n_b = len(layers_b)
    if n_a == 0 or n_b == 0:
        return 0.0
    norm_pos_a = pos_a / max(n_a - 1, 1)
    norm_pos_b = pos_b / max(n_b - 1, 1)
    pos_diff = abs(norm_pos_a - norm_pos_b)
    if pos_diff > 0.5:
        return min(0.5, pos_diff * 0.3)
    return 0.0


def assess_alignment_quality(aligned_groups: List[Dict], unaligned_layers: List[Dict],
                              core_data: Dict) -> Dict[str, Any]:
    if not aligned_groups and not unaligned_layers:
        return {"overall_score": 0, "grade": "N/A", "details": {}}

    total_layers = sum(len(cd["layers"]) for cd in core_data.values())
    aligned_count = total_layers - len(unaligned_layers)
    coverage_ratio = aligned_count / max(total_layers, 1)

    multi_station_groups = [g for g in aligned_groups if g.get("station_count", 0) >= 2]
    multi_station_ratio = len(multi_station_groups) / max(len(aligned_groups), 1)

    scores = [g.get("avg_similarity", 0) for g in aligned_groups]
    avg_similarity = np.mean(scores) if scores else 0

    name_match_count = sum(1 for g in aligned_groups if g.get("representative_name", "").startswith("对齐组") is False)
    name_match_ratio = name_match_count / max(len(aligned_groups), 1)

    overall = (0.35 * coverage_ratio + 0.25 * multi_station_ratio +
               0.25 * avg_similarity + 0.15 * name_match_ratio)

    if overall >= 0.8:
        grade = "A（优秀）"
    elif overall >= 0.6:
        grade = "B（良好）"
    elif overall >= 0.4:
        grade = "C（一般）"
    else:
        grade = "D（需改进）"

    return {
        "overall_score": round(overall, 4),
        "grade": grade,
        "details": {
            "coverage_ratio": round(coverage_ratio, 4),
            "aligned_layer_count": aligned_count,
            "total_layer_count": total_layers,
            "multi_station_group_ratio": round(multi_station_ratio, 4),
            "avg_similarity": round(avg_similarity, 4),
            "name_match_ratio": round(name_match_ratio, 4),
        },
    }


def _build_alignment_groups(alignments: List[Dict], sample_codes: List[str]) -> List[Dict]:
    if not alignments:
        return []

    groups = []
    used_pairs = set()

    for align in alignments:
        pair_key = (align["layer_id_a"], align["layer_id_b"])
        if pair_key in used_pairs:
            continue
        used_pairs.add(pair_key)

        group = {
            "group_id": len(groups) + 1,
            "members": [
                {
                    "sample_code": align["core_a"],
                    "layer_id": align["layer_id_a"],
                    "layer_name": align["layer_name_a"],
                    "depth": align["depth_a"],
                    "norm_depth": align["norm_depth_a"],
                },
                {
                    "sample_code": align["core_b"],
                    "layer_id": align["layer_id_b"],
                    "layer_name": align["layer_name_b"],
                    "depth": align["depth_b"],
                    "norm_depth": align["norm_depth_b"],
                },
            ],
            "avg_similarity": align["combined_score"],
            "representative_name": align["layer_name_a"] if align["layer_name_match"] else f"对齐组{len(groups) + 1}",
        }

        merged = False
        for existing_group in groups:
            existing_ids = {(m["sample_code"], m["layer_id"]) for m in existing_group["members"]}
            new_ids = {(m["sample_code"], m["layer_id"]) for m in group["members"]}
            if existing_ids & new_ids:
                for member in group["members"]:
                    if (member["sample_code"], member["layer_id"]) not in existing_ids:
                        existing_group["members"].append(member)
                existing_ids_new = {(m["sample_code"], m["layer_id"]) for m in existing_group["members"]}
                if all(m["layer_name"] == existing_group["members"][0]["layer_name"] for m in existing_group["members"]):
                    existing_group["representative_name"] = existing_group["members"][0]["layer_name"]
                merged = True
                break

        if not merged:
            groups.append(group)

    for group in groups:
        group["station_count"] = len(set(m["sample_code"] for m in group["members"]))

    groups.sort(key=lambda g: -g["avg_similarity"])

    return groups


def find_similar_segments(core_ids: List[int], window_size: int = 3,
                          similarity_threshold: float = 0.7) -> Dict[str, Any]:
    if len(core_ids) < 2:
        return {"similar_segments": [], "segment_pairs": []}

    core_data = {}
    indicators = ["gravel_pct", "sand_pct", "silt_pct", "clay_pct", "organic_matter", "water_content"]

    for core_id in core_ids:
        core_info = db.get_core_sample(core_id)
        layers_df = db.get_core_layers(core_id)
        if layers_df.empty:
            continue
        sample_code = core_info["sample_code"]
        layers_df["thickness"] = layers_df["depth_end"] - layers_df["depth_start"]
        layers_df["mid_depth"] = (layers_df["depth_start"] + layers_df["depth_end"]) / 2
        core_data[sample_code] = {"core_id": core_id, "layers": layers_df}

    if len(core_data) < 2:
        return {"similar_segments": [], "segment_pairs": []}

    similar_segments = []
    sample_codes = list(core_data.keys())

    for i in range(len(sample_codes)):
        for j in range(i + 1, len(sample_codes)):
            code_a = sample_codes[i]
            code_b = sample_codes[j]
            layers_a = core_data[code_a]["layers"].reset_index(drop=True)
            layers_b = core_data[code_b]["layers"].reset_index(drop=True)

            existing_ind = [c for c in indicators if c in layers_a.columns and c in layers_b.columns]

            for start_a in range(len(layers_a) - window_size + 1):
                seg_a = layers_a.iloc[start_a:start_a + window_size]
                for start_b in range(len(layers_b) - window_size + 1):
                    seg_b = layers_b.iloc[start_b:start_b + window_size]

                    similarity_scores = []
                    for col in existing_ind:
                        vals_a = seg_a[col].fillna(0).values
                        vals_b = seg_b[col].fillna(0).values
                        if len(vals_a) == len(vals_b) and len(vals_a) > 0:
                            sim = _cosine_similarity(vals_a, vals_b)
                            similarity_scores.append(sim)

                    avg_sim = np.mean(similarity_scores) if similarity_scores else 0

                    if avg_sim >= similarity_threshold:
                        similar_segments.append({
                            "core_a": code_a,
                            "core_b": code_b,
                            "start_depth_a": seg_a["depth_start"].iloc[0],
                            "end_depth_a": seg_a["depth_end"].iloc[-1],
                            "start_depth_b": seg_b["depth_start"].iloc[0],
                            "end_depth_b": seg_b["depth_end"].iloc[-1],
                            "layers_a": seg_a["layer_name"].tolist(),
                            "layers_b": seg_b["layer_name"].tolist(),
                            "similarity": round(avg_sim, 4),
                            "window_size": window_size,
                        })

    segment_pairs = []
    for seg in similar_segments:
        pair_key = f"{seg['core_a']}-{seg['core_b']}"
        found = False
        for pair in segment_pairs:
            if pair["pair_key"] == pair_key:
                pair["segments"].append(seg)
                found = True
                break
        if not found:
            segment_pairs.append({
                "pair_key": pair_key,
                "core_a": seg["core_a"],
                "core_b": seg["core_b"],
                "segments": [seg],
            })

    for pair in segment_pairs:
        pair["segment_count"] = len(pair["segments"])

    return {
        "similar_segments": similar_segments,
        "segment_pairs": segment_pairs,
        "total_similar": len(similar_segments),
    }


def analyze_sequence_continuity(core_ids: List[int]) -> Dict[str, Any]:
    if len(core_ids) < 2:
        return {"continuity": [], "continuity_score": 0}

    core_data = {}
    for core_id in core_ids:
        core_info = db.get_core_sample(core_id)
        layers_df = db.get_core_layers(core_id)
        if layers_df.empty:
            continue
        sample_code = core_info["sample_code"]
        layers_df["thickness"] = layers_df["depth_end"] - layers_df["depth_start"]
        layers_df["mid_depth"] = (layers_df["depth_start"] + layers_df["depth_end"]) / 2
        core_data[sample_code] = {
            "core_id": core_id,
            "layers": layers_df,
            "core_length": core_info.get("core_length") or layers_df["depth_end"].max(),
        }

    if len(core_data) < 2:
        return {"continuity": [], "continuity_score": 0}

    all_layer_names = set()
    for data in core_data.values():
        all_layer_names.update(data["layers"]["layer_name"].unique())

    continuity_results = []
    for layer_name in sorted(all_layer_names):
        occurrences = []
        for code, data in core_data.items():
            layer_rows = data["layers"][data["layers"]["layer_name"] == layer_name]
            if not layer_rows.empty:
                for _, row in layer_rows.iterrows():
                    occurrences.append({
                        "sample_code": code,
                        "depth_start": row["depth_start"],
                        "depth_end": row["depth_end"],
                        "thickness": row["thickness"],
                        "norm_depth_start": row["depth_start"] / max(data["core_length"], 1),
                        "norm_depth_end": row["depth_end"] / max(data["core_length"], 1),
                    })

        if len(occurrences) < 2:
            continuity_results.append({
                "layer_name": layer_name,
                "occurrence_count": len(occurrences),
                "station_count": len(set(o["sample_code"] for o in occurrences)),
                "continuity_type": "isolated",
                "depth_range": None,
                "confidence": 0.0,
            })
            continue

        norm_starts = [o["norm_depth_start"] for o in occurrences]
        norm_ends = [o["norm_depth_end"] for o in occurrences]

        start_std = np.std(norm_starts)
        end_std = np.std(norm_ends)

        depth_overlap = True
        starts_sorted = sorted(norm_starts)
        ends_sorted = sorted(norm_ends, reverse=True)
        if starts_sorted[-1] > ends_sorted[0]:
            depth_overlap = False

        station_count = len(set(o["sample_code"] for o in occurrences))

        if start_std < 0.05 and end_std < 0.05:
            cont_type = "continuous"
            confidence = min(1.0, 1.0 - (start_std + end_std) / 0.1)
        elif start_std < 0.15 and end_std < 0.15:
            cont_type = "transitional"
            confidence = min(1.0, 1.0 - (start_std + end_std) / 0.3)
        else:
            cont_type = "discontinuous"
            confidence = max(0.0, 1.0 - (start_std + end_std) / 0.5)

        continuity_results.append({
            "layer_name": layer_name,
            "occurrence_count": len(occurrences),
            "station_count": station_count,
            "continuity_type": cont_type,
            "depth_range": {
                "norm_start_mean": round(np.mean(norm_starts), 4),
                "norm_end_mean": round(np.mean(norm_ends), 4),
                "start_std": round(start_std, 4),
                "end_std": round(end_std, 4),
            },
            "confidence": round(confidence, 4),
            "occurrences": occurrences,
        })

    total_confidence = np.mean([c["confidence"] for c in continuity_results]) if continuity_results else 0

    return {
        "continuity": continuity_results,
        "continuity_score": round(total_confidence, 4),
        "total_layer_types": len(continuity_results),
        "continuous_count": sum(1 for c in continuity_results if c["continuity_type"] == "continuous"),
        "transitional_count": sum(1 for c in continuity_results if c["continuity_type"] == "transitional"),
        "discontinuous_count": sum(1 for c in continuity_results if c["continuity_type"] == "discontinuous"),
    }


def track_key_surfaces(core_ids: List[int], depth_tolerance: float = 5.0) -> Dict[str, Any]:
    if len(core_ids) < 2:
        return {"key_surfaces": [], "surface_correlations": [], "surface_type_summary": {}}

    core_data = {}
    for core_id in core_ids:
        core_info = db.get_core_sample(core_id)
        layers_df = db.get_core_layers(core_id)
        if layers_df.empty:
            continue
        sample_code = core_info["sample_code"]
        layers_df["thickness"] = layers_df["depth_end"] - layers_df["depth_start"]
        layers_df["mid_depth"] = (layers_df["depth_start"] + layers_df["depth_end"]) / 2
        core_data[sample_code] = {
            "core_id": core_id,
            "layers": layers_df,
            "core_length": core_info.get("core_length") or layers_df["depth_end"].max(),
        }

    if len(core_data) < 2:
        return {"key_surfaces": [], "surface_correlations": [], "surface_type_summary": {}}

    key_surfaces = []
    sample_codes = list(core_data.keys())

    for code in sample_codes:
        layers = core_data[code]["layers"].sort_values("depth_start").reset_index(drop=True)
        core_length = core_data[code]["core_length"]

        for idx in range(len(layers) - 1):
            curr = layers.iloc[idx]
            next_l = layers.iloc[idx + 1]

            grain_change = 0.0
            for col in ["sand_pct", "silt_pct", "clay_pct", "gravel_pct"]:
                if col in curr.index and col in next_l.index:
                    v_curr = curr[col] if pd.notna(curr[col]) else 0
                    v_next = next_l[col] if pd.notna(next_l[col]) else 0
                    grain_change += abs(v_curr - v_next)

            organic_change = 0.0
            if "organic_matter" in curr.index and "organic_matter" in next_l.index:
                v_curr = curr["organic_matter"] if pd.notna(curr["organic_matter"]) else 0
                v_next = next_l["organic_matter"] if pd.notna(next_l["organic_matter"]) else 0
                organic_change = abs(v_curr - v_next)

            surface_type = "unknown"
            surface_label = "未知界面"
            significance = "low"

            if curr["layer_name"] != next_l["layer_name"]:
                if "黏土" in curr["layer_name"] and "砂" in next_l["layer_name"]:
                    surface_type = "flooding_surface"
                    surface_label = "海侵面"
                    significance = "high"
                elif "砂" in curr["layer_name"] and "黏土" in next_l["layer_name"]:
                    surface_type = "regression_surface"
                    surface_label = "海退面"
                    significance = "high"
                elif grain_change > 30:
                    surface_type = "lithology_change"
                    surface_label = "岩性突变面"
                    significance = "medium"
                else:
                    surface_type = "layer_boundary"
                    surface_label = "层位界面"
                    significance = "low"
            elif grain_change > 20:
                surface_type = "gradational_change"
                surface_label = "渐变面"
                significance = "medium"

            if organic_change > 3 and surface_type == "unknown":
                surface_type = "gradational_change"
                surface_label = "有机质变化面"
                significance = "medium"

            if surface_type != "unknown":
                norm_depth = curr["depth_end"] / max(core_length, 1)
                key_surfaces.append({
                    "sample_code": code,
                    "depth": curr["depth_end"],
                    "norm_depth": norm_depth,
                    "surface_type": surface_type,
                    "surface_label": surface_label,
                    "layer_above": curr["layer_name"],
                    "layer_below": next_l["layer_name"],
                    "grain_change": round(grain_change, 2),
                    "organic_change": round(organic_change, 2),
                    "significance": significance,
                })

    surface_correlations = []
    surface_types = set(s["surface_type"] for s in key_surfaces)

    for stype in surface_types:
        surfaces_by_type = [s for s in key_surfaces if s["surface_type"] == stype]
        if len(surfaces_by_type) < 2:
            continue

        by_station = {}
        for s in surfaces_by_type:
            code = s["sample_code"]
            if code not in by_station:
                by_station[code] = []
            by_station[code].append(s)

        station_codes = list(by_station.keys())
        for i in range(len(station_codes)):
            for j in range(i + 1, len(station_codes)):
                code_a = station_codes[i]
                code_b = station_codes[j]
                for sa in by_station[code_a]:
                    for sb in by_station[code_b]:
                        len_a = core_data.get(code_a, {}).get("core_length", 100)
                        len_b = core_data.get(code_b, {}).get("core_length", 100)
                        norm_diff = abs(sa["norm_depth"] - sb["norm_depth"])
                        correlation_score = max(0, 1 - norm_diff * 5)

                        grain_similarity = 1.0 - abs(sa["grain_change"] - sb["grain_change"]) / max(
                            max(sa["grain_change"], sb["grain_change"]), 1)

                        combined_corr = 0.6 * correlation_score + 0.4 * grain_similarity

                        if combined_corr > 0.3:
                            surface_correlations.append({
                                "surface_type": stype,
                                "surface_label": SURFACE_TYPE_LABELS.get(stype, stype),
                                "core_a": code_a,
                                "core_b": code_b,
                                "depth_a": sa["depth"],
                                "depth_b": sb["depth"],
                                "norm_depth_a": sa["norm_depth"],
                                "norm_depth_b": sb["norm_depth"],
                                "correlation_score": round(correlation_score, 4),
                                "combined_correlation": round(combined_corr, 4),
                                "grain_similarity": round(grain_similarity, 4),
                                "layer_above_a": sa["layer_above"],
                                "layer_below_a": sa["layer_below"],
                                "layer_above_b": sb["layer_above"],
                                "layer_below_b": sb["layer_below"],
                            })

    type_summary = {}
    for stype in surface_types:
        label = SURFACE_TYPE_LABELS.get(stype, stype)
        count = len([s for s in key_surfaces if s["surface_type"] == stype])
        type_summary[stype] = {"count": count, "label": label}

    return {
        "key_surfaces": key_surfaces,
        "surface_correlations": surface_correlations,
        "surface_type_summary": type_summary,
    }


def regional_evolution_analysis(core_ids: List[int]) -> Dict[str, Any]:
    if len(core_ids) < 2:
        return {"zones": [], "evolution_stages": [], "summary": {}}

    core_data = {}
    for core_id in core_ids:
        core_info = db.get_core_sample(core_id)
        layers_df = db.get_core_layers(core_id)
        if layers_df.empty:
            continue
        sample_code = core_info["sample_code"]
        layers_df["thickness"] = layers_df["depth_end"] - layers_df["depth_start"]
        layers_df["mid_depth"] = (layers_df["depth_start"] + layers_df["depth_end"]) / 2
        core_data[sample_code] = {
            "core_id": core_id,
            "layers": layers_df,
            "core_length": core_info.get("core_length") or layers_df["depth_end"].max(),
            "station_code": core_info.get("station_code", ""),
        }

    if len(core_data) < 2:
        return {"zones": [], "evolution_stages": [], "summary": {}}

    zones = _classify_depositional_zones(core_data)
    evolution_stages = _infer_evolution_stages(core_data, zones)

    return {
        "zones": zones,
        "evolution_stages": evolution_stages,
        "core_data": core_data,
        "summary": {
            "total_cores": len(core_data),
            "zone_count": len(zones),
            "stage_count": len(evolution_stages),
            "dominant_zone": max(zones, key=lambda z: z["core_count"])["zone_type"] if zones else "unknown",
        },
    }


def _classify_depositional_zones(core_data: Dict) -> List[Dict]:
    zones = []

    for sample_code, data in core_data.items():
        layers = data["layers"]
        if layers.empty:
            continue

        avg_sand = layers["sand_pct"].mean()
        avg_silt = layers["silt_pct"].mean()
        avg_clay = layers["clay_pct"].mean()
        avg_gravel = layers["gravel_pct"].mean()

        if avg_gravel > 10:
            zone_type = "近源粗粒沉积区"
        elif avg_sand > 50:
            zone_type = "滨岸砂质沉积区"
        elif avg_sand > 30 and avg_clay > 20:
            zone_type = "过渡带砂泥混合区"
        elif avg_clay > 50:
            zone_type = "深水泥质沉积区"
        elif avg_silt > 40:
            zone_type = "陆棚粉砂沉积区"
        else:
            zone_type = "混合沉积区"

        if "organic_matter" in layers.columns and layers["organic_matter"].notna().any():
            avg_organic = layers["organic_matter"].mean()
            if avg_organic > 5:
                zone_type = "有机质富集区"

        zones.append({
            "sample_code": sample_code,
            "zone_type": zone_type,
            "avg_sand": round(avg_sand, 2),
            "avg_silt": round(avg_silt, 2),
            "avg_clay": round(avg_clay, 2),
            "avg_gravel": round(avg_gravel, 2),
            "core_count": 1,
        })

    merged_zones = []
    for zone in zones:
        found = False
        for existing in merged_zones:
            if existing["zone_type"] == zone["zone_type"]:
                existing["sample_codes"] = existing.get("sample_codes", [existing["sample_code"]])
                existing["sample_codes"].append(zone["sample_code"])
                existing["core_count"] += 1
                existing["avg_sand"] = round((existing["avg_sand"] + zone["avg_sand"]) / 2, 2)
                existing["avg_silt"] = round((existing["avg_silt"] + zone["avg_silt"]) / 2, 2)
                existing["avg_clay"] = round((existing["avg_clay"] + zone["avg_clay"]) / 2, 2)
                existing["avg_gravel"] = round((existing["avg_gravel"] + zone["avg_gravel"]) / 2, 2)
                found = True
                break
        if not found:
            zone["sample_codes"] = [zone["sample_code"]]
            merged_zones.append(zone)

    return merged_zones


def _infer_evolution_stages(core_data: Dict, zones: List[Dict]) -> List[Dict]:
    stages = []

    for sample_code, data in core_data.items():
        layers = data["layers"].sort_values("depth_start").reset_index(drop=True)
        if layers.empty:
            continue

        depth_segments = []
        n = len(layers)
        segment_size = max(1, n // 3)

        for seg_idx in range(3):
            start_i = seg_idx * segment_size
            end_i = min(start_i + segment_size, n) if seg_idx < 2 else n
            seg_layers = layers.iloc[start_i:end_i]
            if seg_layers.empty:
                continue

            avg_sand = seg_layers["sand_pct"].mean()
            avg_clay = seg_layers["clay_pct"].mean()
            sand_clay_ratio = avg_sand / max(avg_clay, 0.1)

            if sand_clay_ratio > 2:
                env = "高能环境（浅水/近岸）"
            elif sand_clay_ratio > 1:
                env = "中等能量环境（过渡带）"
            elif sand_clay_ratio > 0.5:
                env = "低能环境（深水/远岸）"
            else:
                env = "极低能环境（深海/盆地）"

            depth_segments.append({
                "segment": seg_idx + 1,
                "depth_range": f"{seg_layers['depth_start'].iloc[0]:.1f}-{seg_layers['depth_end'].iloc[-1]:.1f}",
                "avg_sand": round(avg_sand, 2),
                "avg_clay": round(avg_clay, 2),
                "sand_clay_ratio": round(sand_clay_ratio, 4),
                "environment": env,
                "layer_names": seg_layers["layer_name"].tolist(),
            })

        if len(depth_segments) >= 2:
            first_ratio = depth_segments[0]["sand_clay_ratio"]
            last_ratio = depth_segments[-1]["sand_clay_ratio"]

            if last_ratio > first_ratio * 1.2:
                trend = "海退序列（变浅）"
            elif last_ratio < first_ratio * 0.8:
                trend = "海进序列（变深）"
            else:
                trend = "稳定沉积"

            stages.append({
                "sample_code": sample_code,
                "segments": depth_segments,
                "overall_trend": trend,
            })

    return stages


def generate_alignment_report(alignment_result: Dict, continuity_result: Dict,
                               surface_result: Dict, evolution_result: Dict,
                               correction_records: Optional[List[Dict]] = None,
                               annotation_records: Optional[List[Dict]] = None) -> Dict[str, Any]:
    from datetime import datetime
    report_lines = []
    report_lines.append("=" * 70)
    report_lines.append("  海底沉积柱样层位对齐与区域演化解释报告")
    report_lines.append(f"  生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append("=" * 70)

    report_lines.append("\n【一、层位对齐结果】")
    aligned_groups = alignment_result.get("aligned_groups", [])
    quality = alignment_result.get("quality", {})
    method = alignment_result.get("method", "combined")
    threshold = alignment_result.get("threshold", 0.6)

    method_labels = {"combined": "综合对齐（岩性+深度）", "lithology": "岩性相似性对齐",
                     "depth": "深度归一化对齐", "dtw": "DTW动态时间规整对齐"}
    report_lines.append(f"  对齐方法: {method_labels.get(method, method)}")
    report_lines.append(f"  相似度阈值: {threshold}")
    report_lines.append(f"  共识别 {len(aligned_groups)} 组对齐层位")

    if quality:
        report_lines.append(f"  对齐质量评分: {quality.get('overall_score', 0):.3f} ({quality.get('grade', 'N/A')})")
        details = quality.get("details", {})
        report_lines.append(f"  层位覆盖率: {details.get('coverage_ratio', 0):.1%}")
        report_lines.append(f"  多站位对齐率: {details.get('multi_station_group_ratio', 0):.1%}")

    for group in aligned_groups[:15]:
        report_lines.append(f"  - {group['representative_name']}: "
                           f"涉及 {group['station_count']} 个站位，"
                           f"相似度 {group['avg_similarity']:.3f}")

    report_lines.append("\n【二、层序延续性分析】")
    if continuity_result:
        report_lines.append(f"  整体延续性评分: {continuity_result.get('continuity_score', 0):.3f}")
        report_lines.append(f"  连续层位: {continuity_result.get('continuous_count', 0)} 种")
        report_lines.append(f"  过渡层位: {continuity_result.get('transitional_count', 0)} 种")
        report_lines.append(f"  不连续层位: {continuity_result.get('discontinuous_count', 0)} 种")

        for c in continuity_result.get("continuity", []):
            label_map = {"continuous": "连续", "transitional": "过渡",
                         "discontinuous": "不连续", "isolated": "孤立"}
            report_lines.append(f"  - {c['layer_name']}: {label_map.get(c['continuity_type'], c['continuity_type'])} "
                               f"(置信度 {c['confidence']:.3f}, 涉及 {c['station_count']} 站位)")

    report_lines.append("\n【三、关键界面追踪】")
    if surface_result:
        key_surfaces = surface_result.get("key_surfaces", [])
        correlations = surface_result.get("surface_correlations", [])
        type_summary = surface_result.get("surface_type_summary", {})
        report_lines.append(f"  共识别 {len(key_surfaces)} 个关键界面")
        for stype, info in type_summary.items():
            label = info.get("label", stype) if isinstance(info, dict) else stype
            count = info.get("count", 0) if isinstance(info, dict) else info
            report_lines.append(f"  - {label}: {count} 个")
        report_lines.append(f"  界面间相关性: {len(correlations)} 对")
        for corr in correlations[:10]:
            label = corr.get("surface_label", corr.get("surface_type", ""))
            report_lines.append(f"  - {label}: {corr['core_a']}({corr['depth_a']:.1f}cm) ↔ "
                               f"{corr['core_b']}({corr['depth_b']:.1f}cm) "
                               f"综合相关: {corr.get('combined_correlation', corr.get('correlation_score', 0)):.3f}")

    report_lines.append("\n【四、区域沉积演化分区】")
    if evolution_result:
        zones = evolution_result.get("zones", [])
        stages = evolution_result.get("evolution_stages", [])
        summary = evolution_result.get("summary", {})
        report_lines.append(f"  优势沉积区: {summary.get('dominant_zone', '未知')}")
        for zone in zones:
            report_lines.append(f"  - {zone['zone_type']}: {zone['core_count']} 个柱样 "
                               f"(砂{zone['avg_sand']:.1f}% 粉砂{zone['avg_silt']:.1f}% 黏土{zone['avg_clay']:.1f}%)")
        report_lines.append(f"\n  演化阶段推断:")
        for stage in stages:
            report_lines.append(f"  - {stage['sample_code']}: {stage['overall_trend']}")
            for seg in stage.get("segments", []):
                report_lines.append(f"    阶段{seg['segment']}: {seg['depth_range']}cm "
                                   f"砂黏比{seg['sand_clay_ratio']:.2f} {seg['environment']}")

    if correction_records:
        report_lines.append("\n【五、人工校正记录】")
        report_lines.append(f"  共 {len(correction_records)} 条校正记录")
        for corr in correction_records:
            report_lines.append(f"  - {corr.get('sample_code', '')}: "
                               f"{corr.get('original_depth_start', 0):.1f}-{corr.get('original_depth_end', 0):.1f} → "
                               f"{corr.get('corrected_depth_start', 0):.1f}-{corr.get('corrected_depth_end', 0):.1f}cm "
                               f"({corr.get('correction_reason', '')})")

    if annotation_records:
        report_lines.append("\n【六、地质解释备注】")
        for ann in annotation_records:
            report_lines.append(f"  - [{ann.get('annotation_type', '')}] {ann.get('content', '')} "
                               f"({ann.get('author', '')})")

    report_lines.append("\n" + "=" * 70)
    report_lines.append("  报告结束")
    report_lines.append("=" * 70)

    return {
        "report_title": "海底沉积柱样层位对齐与区域演化解释报告",
        "report_text": "\n".join(report_lines),
        "sections": {
            "alignment": len(aligned_groups),
            "alignment_quality": quality.get("overall_score", 0) if quality else 0,
            "alignment_grade": quality.get("grade", "N/A") if quality else "N/A",
            "continuity_score": continuity_result.get("continuity_score", 0) if continuity_result else 0,
            "key_surfaces": len(surface_result.get("key_surfaces", [])) if surface_result else 0,
            "surface_correlations": len(surface_result.get("surface_correlations", [])) if surface_result else 0,
            "zones": len(evolution_result.get("zones", [])) if evolution_result else 0,
            "evolution_stages": len(evolution_result.get("evolution_stages", [])) if evolution_result else 0,
            "corrections": len(correction_records) if correction_records else 0,
            "annotations": len(annotation_records) if annotation_records else 0,
        },
    }
