import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from typing import List, Dict, Any, Optional


LAYER_COLORS = {
    "砂层": "#f4a460",
    "粉砂层": "#daa520",
    "黏土层": "#8b4513",
    "淤泥层": "#556b2f",
    "砾石层": "#808080",
    "砂质粉砂": "#d2b48c",
    "粉砂质砂": "#cd853f",
    "粉砂质黏土": "#a0522d",
    "黏土质粉砂": "#6b4423",
    "有机质层": "#2e8b57",
}


def _get_layer_color(layer_name: str) -> str:
    for key, color in LAYER_COLORS.items():
        if key in layer_name:
            return color
    hash_val = hash(layer_name) % len(LAYER_COLORS)
    return list(LAYER_COLORS.values())[hash_val]


def plot_core_section(layers_df: pd.DataFrame, missing_intervals: List[Dict[str, float]],
                      title: str = "沉积柱样分层剖面图", core_length: Optional[float] = None) -> go.Figure:
    if layers_df.empty:
        fig = go.Figure()
        fig.update_layout(title=title, xaxis_title="", yaxis_title="深度 (cm)")
        return fig

    max_depth = core_length if core_length else layers_df["depth_end"].max()

    fig = go.Figure()

    for idx, row in layers_df.iterrows():
        thickness = row["depth_end"] - row["depth_start"]
        color = _get_layer_color(row["layer_name"])

        fig.add_trace(go.Bar(
            x=[1],
            y=[-thickness],
            base=[-row["depth_start"]],
            orientation="v",
            marker_color=color,
            marker_line_color="black",
            marker_line_width=1,
            width=0.8,
            name=row["layer_name"],
            legendgroup=row["layer_name"],
            showlegend=(row["layer_name"] not in [t.name for t in fig.data if hasattr(t, "name")]),
            hovertext=(
                f"层位: {row['layer_name']}<br>"
                f"深度: {row['depth_start']} - {row['depth_end']} cm<br>"
                f"厚度: {thickness:.1f} cm<br>"
                f"砾石: {row.get('gravel_pct', 0):.1f}%<br>"
                f"砂: {row.get('sand_pct', 0):.1f}%<br>"
                f"粉砂: {row.get('silt_pct', 0):.1f}%<br>"
                f"黏土: {row.get('clay_pct', 0):.1f}%<br>"
                f"有机质: {row.get('organic_matter', 'N/A')}%<br>"
                f"含水率: {row.get('water_content', 'N/A')}%"
            ),
            hoverinfo="text",
        ))

    for missing in missing_intervals:
        thickness = missing["depth_end"] - missing["depth_start"]
        fig.add_trace(go.Bar(
            x=[1],
            y=[-thickness],
            base=[-missing["depth_start"]],
            orientation="v",
            marker_color="rgba(255, 0, 0, 0.2)",
            marker_line_color="red",
            marker_line_width=2,
            marker_pattern_shape="/",
            width=0.8,
            name="缺失层段",
            legendgroup="missing",
            showlegend=(missing == missing_intervals[0]),
            hovertext=(
                f"缺失层段<br>"
                f"深度: {missing['depth_start']} - {missing['depth_end']} cm<br>"
                f"厚度: {thickness:.1f} cm"
            ),
            hoverinfo="text",
        ))

    tick_vals = []
    tick_texts = []
    for _, row in layers_df.iterrows():
        mid = -(row["depth_start"] + row["depth_end"]) / 2
        tick_vals.append(mid)
        tick_texts.append(row["layer_name"])

    fig.update_layout(
        title=title,
        barmode="stack",
        xaxis=dict(
            showticklabels=False,
            range=[0.5, 1.5],
        ),
        yaxis=dict(
            title="深度 (cm)",
            tickmode="array",
            tickvals=tick_vals,
            ticktext=tick_texts,
            autorange="reversed" if False else True,
        ),
        showlegend=True,
        height=max(500, max_depth * 3),
        width=500,
    )

    depth_ticks = np.arange(0, max_depth + 10, 20)
    fig.update_layout(
        yaxis2=dict(
            overlaying="y",
            side="right",
            range=[-max_depth, 0],
            tickvals=[-d for d in depth_ticks],
            ticktext=[f"{d}" for d in depth_ticks],
            title="",
            showgrid=False,
        )
    )

    return fig


def plot_indicator_trends(layers_df: pd.DataFrame, title: str = "指标随深度变化趋势") -> go.Figure:
    if layers_df.empty:
        fig = go.Figure()
        fig.update_layout(title=title)
        return fig

    df = layers_df.copy()
    df["mid_depth"] = (df["depth_start"] + df["depth_end"]) / 2

    indicators = [
        ("gravel_pct", "砾石 (%)", "#808080"),
        ("sand_pct", "砂 (%)", "#f4a460"),
        ("silt_pct", "粉砂 (%)", "#daa520"),
        ("clay_pct", "黏土 (%)", "#8b4513"),
        ("organic_matter", "有机质 (%)", "#2e8b57"),
        ("water_content", "含水率 (%)", "#4682b4"),
    ]

    existing_indicators = [(col, name, color) for col, name, color in indicators
                           if col in df.columns and df[col].notna().any()]

    if not existing_indicators:
        fig = go.Figure()
        fig.update_layout(title=title + " (无数据)")
        return fig

    fig = make_subplots(
        rows=1, cols=len(existing_indicators),
        shared_yaxes=True,
        subplot_titles=[name for _, name, _ in existing_indicators],
        horizontal_spacing=0.05,
    )

    for i, (col, name, color) in enumerate(existing_indicators, 1):
        valid_data = df.dropna(subset=[col])
        if not valid_data.empty:
            fig.add_trace(
                go.Scatter(
                    x=valid_data[col],
                    y=-valid_data["mid_depth"],
                    mode="lines+markers",
                    name=name,
                    line=dict(color=color, width=2),
                    marker=dict(size=8, color=color),
                    hovertemplate=f"{name}: %{{x:.1f}}%<br>深度: %{{y:.1f}} cm<extra></extra>",
                ),
                row=1, col=i
            )

            if "is_anomaly" in df.columns:
                anomaly_data = df[df["is_anomaly"] & df[col].notna()]
                if not anomaly_data.empty:
                    fig.add_trace(
                        go.Scatter(
                            x=anomaly_data[col],
                            y=-anomaly_data["mid_depth"],
                            mode="markers",
                            name="异常值",
                            marker=dict(
                                size=12,
                                color="red",
                                symbol="triangle-up",
                                line=dict(width=2, color="darkred")
                            ),
                            showlegend=(i == 1),
                            hovertemplate=f"异常 - {name}: %{{x:.1f}}%<br>深度: %{{y:.1f}} cm<extra></extra>",
                        ),
                        row=1, col=i
                    )

            fig.update_xaxes(title_text="", row=1, col=i)

    fig.update_yaxes(title_text="深度 (cm)", row=1, col=1)

    max_depth = df["depth_end"].max()
    fig.update_yaxes(range=[-max_depth - 5, 5])

    fig.update_layout(
        title=title,
        height=600,
        showlegend=True,
    )

    return fig


def plot_correlation_heatmap(corr_matrix: pd.DataFrame, title: str = "指标相关性矩阵") -> go.Figure:
    if corr_matrix.empty:
        fig = go.Figure()
        fig.update_layout(title=title + " (数据不足)")
        return fig

    col_names = {
        "gravel_pct": "砾石",
        "sand_pct": "砂",
        "silt_pct": "粉砂",
        "clay_pct": "黏土",
        "organic_matter": "有机质",
        "water_content": "含水率",
    }

    display_cols = [col_names.get(c, c) for c in corr_matrix.columns]
    display_idx = [col_names.get(i, i) for i in corr_matrix.index]

    fig = go.Figure(data=go.Heatmap(
        z=corr_matrix.values,
        x=display_cols,
        y=display_idx,
        zmin=-1,
        zmax=1,
        colorscale="RdBu_r",
        reversescale=False,
        text=corr_matrix.values.round(2),
        texttemplate="%{text}",
        textfont={"size": 12},
        hovertemplate="%{x} vs %{y}<br>相关系数: %{z:.3f}<extra></extra>",
    ))

    fig.update_layout(
        title=title,
        xaxis_title="",
        yaxis_title="",
        height=500,
        width=600,
    )

    return fig


def plot_multi_core_comparison(cores_data: Dict[str, Dict[str, Any]],
                               title: str = "多柱样对比剖面图") -> go.Figure:
    if not cores_data:
        fig = go.Figure()
        fig.update_layout(title=title)
        return fig

    fig = go.Figure()

    all_max_depths = []
    for core_code, data in cores_data.items():
        if not data["layers"].empty:
            all_max_depths.append(data["layers"]["depth_end"].max())
    global_max = max(all_max_depths) if all_max_depths else 100

    core_codes = list(cores_data.keys())
    n_cores = len(core_codes)
    bar_width = 0.8 / max(1, n_cores)

    for core_idx, core_code in enumerate(core_codes):
        data = cores_data[core_code]
        layers_df = data["layers"]
        missing_intervals = data["missing_intervals"]

        if layers_df.empty:
            continue

        x_pos = core_idx + 1

        for _, row in layers_df.iterrows():
            thickness = row["depth_end"] - row["depth_start"]
            color = _get_layer_color(row["layer_name"])

            fig.add_trace(go.Bar(
                x=[x_pos],
                y=[-thickness],
                base=[-row["depth_start"]],
                orientation="v",
                marker_color=color,
                marker_line_color="black",
                marker_line_width=0.5,
                width=bar_width,
                name=f"{core_code} - {row['layer_name']}",
                legendgroup=row["layer_name"],
                showlegend=False,
                hovertext=(
                    f"柱样: {core_code}<br>"
                    f"层位: {row['layer_name']}<br>"
                    f"深度: {row['depth_start']} - {row['depth_end']} cm<br>"
                    f"厚度: {thickness:.1f} cm"
                ),
                hoverinfo="text",
            ))

        for missing in missing_intervals:
            thickness = missing["depth_end"] - missing["depth_start"]
            fig.add_trace(go.Bar(
                x=[x_pos],
                y=[-thickness],
                base=[-missing["depth_start"]],
                orientation="v",
                marker_color="rgba(255, 0, 0, 0.2)",
                marker_line_color="red",
                marker_line_width=1,
                width=bar_width,
                name="缺失层段",
                legendgroup="missing",
                showlegend=False,
                hovertext=(
                    f"柱样: {core_code}<br>"
                    f"缺失层段<br>"
                    f"深度: {missing['depth_start']} - {missing['depth_end']} cm<br>"
                    f"厚度: {thickness:.1f} cm"
                ),
                hoverinfo="text",
            ))

    unique_layers = set()
    for data in cores_data.values():
        if not data["layers"].empty:
            for _, row in data["layers"].iterrows():
                if row["layer_name"] not in unique_layers:
                    unique_layers.add(row["layer_name"])
                    fig.add_trace(go.Scatter(
                        x=[None], y=[None],
                        mode="markers",
                        marker=dict(size=15, color=_get_layer_color(row["layer_name"])),
                        name=row["layer_name"],
                        showlegend=True,
                    ))

    fig.update_layout(
        title=title,
        barmode="overlay",
        xaxis=dict(
            tickmode="array",
            tickvals=list(range(1, n_cores + 1)),
            ticktext=core_codes,
            title="柱样编号",
        ),
        yaxis=dict(
            title="深度 (cm)",
            range=[-global_max - 5, 5],
        ),
        showlegend=True,
        legend_title="层位类型",
        height=700,
        width=max(600, n_cores * 200),
    )

    return fig


def plot_grain_size_distribution(layers_df: pd.DataFrame, title: str = "颗粒组成三角图") -> go.Figure:
    if layers_df.empty:
        fig = go.Figure()
        fig.update_layout(title=title + " (无数据)")
        return fig

    fig = go.Figure()

    sand = layers_df.get("sand_pct", pd.Series())
    silt = layers_df.get("silt_pct", pd.Series())
    clay = layers_df.get("clay_pct", pd.Series())

    if sand.empty or silt.empty or clay.empty:
        fig.update_layout(title=title + " (颗粒数据不足)")
        return fig

    fig.add_trace(go.Scatterternary({
        "mode": "markers+text",
        "a": sand.values,
        "b": clay.values,
        "c": silt.values,
        "text": layers_df["layer_name"].values if "layer_name" in layers_df.columns else "",
        "textposition": "top center",
        "marker": {
            "size": 12,
            "color": [_get_layer_color(name) for name in layers_df["layer_name"]],
            "line": {"width": 2, "color": "black"},
        },
        "hovertext": [
            f"{row['layer_name']}<br>"
            f"深度: {row['depth_start']}-{row['depth_end']} cm<br>"
            f"砂: {row['sand_pct']:.1f}%<br>"
            f"粉砂: {row['silt_pct']:.1f}%<br>"
            f"黏土: {row['clay_pct']:.1f}%"
            for _, row in layers_df.iterrows()
        ],
        "hoverinfo": "text",
    }))

    fig.update_layout({
        "title": title,
        "ternary": {
            "sum": 100,
            "aaxis": {"title": "砂 (%)", "min": 0.01, "linewidth": 2, "ticks": "outside"},
            "baxis": {"title": "黏土 (%)", "min": 0.01, "linewidth": 2, "ticks": "outside"},
            "caxis": {"title": "粉砂 (%)", "min": 0.01, "linewidth": 2, "ticks": "outside"},
        },
        "height": 600,
        "width": 700,
    })

    return fig


def plot_layer_thickness_bar(summary_df: pd.DataFrame, title: str = "各层位厚度统计") -> go.Figure:
    if summary_df.empty:
        fig = go.Figure()
        fig.update_layout(title=title + " (无数据)")
        return fig

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=summary_df["layer_name"],
        y=summary_df["total_thickness"],
        marker_color=[_get_layer_color(name) for name in summary_df["layer_name"]],
        text=summary_df["total_thickness_pct"].astype(str) + "%",
        textposition="outside",
        hovertext=[
            f"{row['layer_name']}<br>"
            f"总厚度: {row['total_thickness']:.1f} cm<br>"
            f"层数: {row['layer_count']}<br>"
            f"平均厚度: {row['avg_thickness']:.1f} cm<br>"
            f"占比: {row['total_thickness_pct']:.1f}%"
            for _, row in summary_df.iterrows()
        ],
        hoverinfo="text",
    ))

    fig.update_layout(
        title=title,
        xaxis_title="层位名称",
        yaxis_title="总厚度 (cm)",
        height=500,
    )

    return fig


def plot_cross_correlation_heatmap(corr_dict: Dict[str, pd.DataFrame],
                                   title: str = "多柱样交叉相关性") -> go.Figure:
    if not corr_dict:
        fig = go.Figure()
        fig.update_layout(title=title + " (无数据)")
        return fig

    indicators = list(corr_dict.keys())
    n_indicators = len(indicators)

    fig = make_subplots(
        rows=1, cols=n_indicators,
        subplot_titles=indicators,
        horizontal_spacing=0.08,
    )

    for i, ind in enumerate(indicators, 1):
        corr_matrix = corr_dict[ind]
        if corr_matrix.empty:
            continue

        fig.add_trace(
            go.Heatmap(
                z=corr_matrix.values,
                x=corr_matrix.columns,
                y=corr_matrix.index,
                zmin=-1,
                zmax=1,
                colorscale="RdBu_r",
                text=corr_matrix.values.round(2),
                texttemplate="%{text}",
                textfont={"size": 10},
                hovertemplate="%{x} vs %{y}<br>相关系数: %{z:.3f}<extra></extra>",
                showscale=(i == n_indicators),
            ),
            row=1, col=i
        )

    fig.update_layout(
        title=title,
        height=400,
        width=300 * n_indicators + 100,
    )

    return fig


def plot_quality_markers(core_section_fig: go.Figure, layers_df: pd.DataFrame,
                         duplicates: List[Dict], overlaps: List[Dict]) -> go.Figure:
    if layers_df.empty:
        return core_section_fig

    for dup in duplicates:
        layer = layers_df[layers_df["id"] == dup["layer_id_2"]]
        if not layer.empty:
            depth_mid = -(float(layer["depth_start"].iloc[0]) + float(layer["depth_end"].iloc[0])) / 2
            core_section_fig.add_annotation(
                x=1,
                y=depth_mid,
                text="⚠️ 重复",
                showarrow=True,
                arrowhead=2,
                ax=50,
                ay=0,
                font=dict(color="orange", size=10),
                bgcolor="rgba(255,255,255,0.8)",
            )

    for overlap in overlaps:
        layer = layers_df[layers_df["id"] == overlap["layer_id_2"]]
        if not layer.empty:
            depth_mid = -(float(layer["depth_start"].iloc[0]) + float(layer["depth_end"].iloc[0])) / 2
            core_section_fig.add_annotation(
                x=1,
                y=depth_mid,
                text="🔴 重叠",
                showarrow=True,
                arrowhead=2,
                ax=50,
                ay=0,
                font=dict(color="red", size=10),
                bgcolor="rgba(255,255,255,0.8)",
            )

    return core_section_fig


def plot_station_comparison_radar(core_stats_list: List[Dict[str, Any]],
                                  title: str = "站位内多柱样指标对比雷达图") -> go.Figure:
    if not core_stats_list:
        fig = go.Figure()
        fig.update_layout(title=title + " (无数据)")
        return fig

    indicators = ["avg_sand", "avg_silt", "avg_clay", "avg_organic", "recovery_rate"]
    indicator_names = {
        "avg_sand": "平均砂含量 (%)",
        "avg_silt": "平均粉砂含量 (%)",
        "avg_clay": "平均黏土含量 (%)",
        "avg_organic": "平均有机质 (%)",
        "recovery_rate": "取芯率 (%)",
    }

    fig = go.Figure()

    colors = px.colors.qualitative.Plotly

    for idx, stats in enumerate(core_stats_list):
        values = []
        for ind in indicators:
            val = stats.get(ind, 0)
            if pd.isna(val):
                val = 0
            values.append(float(val))

        fig.add_trace(go.Scatterpolar(
            r=values,
            theta=[indicator_names[ind] for ind in indicators],
            fill='toself',
            name=stats.get("sample_code", f"柱样{idx+1}"),
            line=dict(color=colors[idx % len(colors)]),
        ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 100]
            )),
        showlegend=True,
        title=title,
        height=500,
    )

    return fig


def plot_anomaly_status_pie(anomalies_df: pd.DataFrame,
                            title: str = "异常复核状态分布") -> go.Figure:
    if anomalies_df.empty:
        fig = go.Figure()
        fig.update_layout(title=title + " (无数据)")
        return fig

    status_counts = anomalies_df["status"].value_counts()

    colors = {
        "pending": "#ffc107",
        "reviewed": "#28a745",
        "confirmed": "#dc3545",
        "dismissed": "#6c757d",
    }

    fig = go.Figure(data=[go.Pie(
        labels=status_counts.index,
        values=status_counts.values,
        hole=0.4,
        marker=dict(
            colors=[colors.get(s, "#999") for s in status_counts.index]
        ),
        textinfo="label+percent",
        hovertemplate="%{label}: %{value} 个 (%{percent})<extra></extra>",
    )])

    fig.update_layout(
        title=title,
        height=400,
    )

    return fig


def plot_version_timeline(versions_df: pd.DataFrame,
                          title: str = "层位版本历史") -> go.Figure:
    if versions_df.empty:
        fig = go.Figure()
        fig.update_layout(title=title + " (无数据)")
        return fig

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=versions_df["created_at"],
        y=versions_df["version"],
        mode="lines+markers",
        name="版本号",
        marker=dict(size=10, color="#2d5f8f"),
        line=dict(width=2),
        hovertext=[
            f"版本: v{row['version']}<br>"
            f"深度: {row['depth_start']}-{row['depth_end']} cm<br>"
            f"修改原因: {row.get('change_reason', 'N/A')}<br>"
            f"修改人: {row.get('changed_by', 'system')}<br>"
            f"时间: {row['created_at']}"
            for _, row in versions_df.iterrows()
        ],
        hoverinfo="text",
    ))

    fig.update_layout(
        title=title,
        xaxis_title="时间",
        yaxis_title="版本号",
        height=400,
    )

    return fig


def plot_missing_severity_gauge(missing_pct: float, title: str = "数据完整度评估") -> go.Figure:
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=100 - missing_pct,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': title},
        gauge={
            'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "darkblue"},
            'bar': {'color': "darkblue"},
            'bgcolor': "white",
            'borderwidth': 2,
            'bordercolor': "gray",
            'steps': [
                {'range': [0, 70], 'color': '#dc3545'},
                {'range': [70, 90], 'color': '#ffc107'},
                {'range': [90, 100], 'color': '#28a745'},
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': 100 - missing_pct
            }
        }
    ))

    fig.update_layout(
        height=300,
    )

    return fig


SURFACE_COLORS = {
    "flooding_surface": "#1565C0",
    "regression_surface": "#C62828",
    "lithology_change": "#FF8F00",
    "gradational_change": "#2E7D32",
}

ZONE_COLORS = {
    "近源粗粒沉积区": "#8D6E63",
    "滨岸砂质沉积区": "#F4A460",
    "过渡带砂泥混合区": "#DAA520",
    "深水泥质沉积区": "#5D4037",
    "陆棚粉砂沉积区": "#BCAAA4",
    "混合沉积区": "#9E9E9E",
    "有机质富集区": "#2E7D32",
}

CONTINUITY_COLORS = {
    "continuous": "#28a745",
    "transitional": "#ffc107",
    "discontinuous": "#dc3545",
    "isolated": "#6c757d",
}


def plot_alignment_diagram(alignment_result: Dict[str, Any],
                           title: str = "多柱样层位对齐图") -> go.Figure:
    core_data = alignment_result.get("core_data", {})
    aligned_groups = alignment_result.get("aligned_groups", [])

    if not core_data:
        fig = go.Figure()
        fig.update_layout(title=title + " (无数据)")
        return fig

    sample_codes = list(core_data.keys())
    n_cores = len(sample_codes)

    all_max_depths = []
    for code in sample_codes:
        layers = core_data[code]["layers"]
        if not layers.empty:
            all_max_depths.append(layers["depth_end"].max())
    global_max = max(all_max_depths) if all_max_depths else 100

    fig = go.Figure()

    x_positions = list(range(1, n_cores + 1))
    spacing = 2.5

    for core_idx, code in enumerate(sample_codes):
        layers = core_data[code]["layers"]
        if layers.empty:
            continue
        x_pos = core_idx * spacing + 1

        for _, row in layers.iterrows():
            thickness = row["depth_end"] - row["depth_start"]
            color = _get_layer_color(row["layer_name"])

            fig.add_trace(go.Bar(
                x=[x_pos],
                y=[-thickness],
                base=[-row["depth_start"]],
                orientation="v",
                marker_color=color,
                marker_line_color="black",
                marker_line_width=1,
                width=0.8,
                name=row["layer_name"],
                legendgroup=row["layer_name"],
                showlegend=False,
                hovertext=(
                    f"柱样: {code}<br>"
                    f"层位: {row['layer_name']}<br>"
                    f"深度: {row['depth_start']} - {row['depth_end']} cm<br>"
                    f"厚度: {thickness:.1f} cm"
                ),
                hoverinfo="text",
            ))

    alignment_colors = px.colors.qualitative.Set2
    for group_idx, group in enumerate(aligned_groups):
        color = alignment_colors[group_idx % len(alignment_colors)]
        members = group["members"]

        for m_idx in range(len(members) - 1):
            m_a = members[m_idx]
            m_b = members[m_idx + 1]

            idx_a = sample_codes.index(m_a["sample_code"]) if m_a["sample_code"] in sample_codes else None
            idx_b = sample_codes.index(m_b["sample_code"]) if m_b["sample_code"] in sample_codes else None

            if idx_a is not None and idx_b is not None:
                x_a = idx_a * spacing + 1
                x_b = idx_b * spacing + 1

                fig.add_trace(go.Scatter(
                    x=[x_a + 0.4, x_b - 0.4],
                    y=[-m_a["depth"], -m_b["depth"]],
                    mode="lines",
                    line=dict(color=color, width=2, dash="dot"),
                    showlegend=False,
                    hoverinfo="skip",
                ))

    for group_idx, group in enumerate(aligned_groups[:20]):
        color = alignment_colors[group_idx % len(alignment_colors)]
        fig.add_trace(go.Scatter(
            x=[None], y=[None],
            mode="markers",
            marker=dict(size=10, color=color, symbol="diamond"),
            name=f"对齐组{group['group_id']}: {group['representative_name']}",
            showlegend=True,
        ))

    fig.update_layout(
        title=title,
        barmode="overlay",
        xaxis=dict(
            tickmode="array",
            tickvals=[i * spacing + 1 for i in range(n_cores)],
            ticktext=sample_codes,
            title="柱样编号",
        ),
        yaxis=dict(
            title="深度 (cm)",
            range=[-global_max - 10, 5],
        ),
        showlegend=True,
        legend_title="对齐组",
        height=700,
        width=max(800, n_cores * 250),
    )

    return fig


def plot_key_surface_tracking(surface_result: Dict[str, Any], core_data: Dict[str, Any],
                               title: str = "关键界面追踪图") -> go.Figure:
    key_surfaces = surface_result.get("key_surfaces", [])
    correlations = surface_result.get("surface_correlations", [])

    if not key_surfaces or not core_data:
        fig = go.Figure()
        fig.update_layout(title=title + " (无数据)")
        return fig

    sample_codes = list(core_data.keys())
    n_cores = len(sample_codes)
    spacing = 2.5

    all_max_depths = []
    for code in sample_codes:
        layers = core_data[code]["layers"]
        if not layers.empty:
            all_max_depths.append(layers["depth_end"].max())
    global_max = max(all_max_depths) if all_max_depths else 100

    fig = go.Figure()

    for core_idx, code in enumerate(sample_codes):
        layers = core_data[code]["layers"]
        if layers.empty:
            continue
        x_pos = core_idx * spacing + 1

        for _, row in layers.iterrows():
            thickness = row["depth_end"] - row["depth_start"]
            color = _get_layer_color(row["layer_name"])
            fig.add_trace(go.Bar(
                x=[x_pos],
                y=[-thickness],
                base=[-row["depth_start"]],
                orientation="v",
                marker_color=color,
                marker_line_color="black",
                marker_line_width=1,
                width=0.8,
                showlegend=False,
                hovertext=(
                    f"柱样: {code}<br>"
                    f"层位: {row['layer_name']}<br>"
                    f"深度: {row['depth_start']} - {row['depth_end']} cm"
                ),
                hoverinfo="text",
            ))

    for surface in key_surfaces:
        sc = surface["sample_code"]
        if sc not in sample_codes:
            continue
        core_idx = sample_codes.index(sc)
        x_pos = core_idx * spacing + 1

        stype = surface["surface_type"]
        marker_color = SURFACE_COLORS.get(stype, "#666666")

        fig.add_trace(go.Scatter(
            x=[x_pos - 0.5, x_pos + 0.5],
            y=[-surface["depth"], -surface["depth"]],
            mode="lines",
            line=dict(color=marker_color, width=3),
            showlegend=False,
            hovertext=(
                f"界面类型: {stype}<br>"
                f"深度: {surface['depth']:.1f} cm<br>"
                f"上覆: {surface['layer_above']}<br>"
                f"下伏: {surface['layer_below']}"
            ),
            hoverinfo="text",
        ))

    for corr in correlations:
        code_a = corr["core_a"]
        code_b = corr["core_b"]
        if code_a not in sample_codes or code_b not in sample_codes:
            continue

        idx_a = sample_codes.index(code_a)
        idx_b = sample_codes.index(code_b)
        x_a = idx_a * spacing + 1
        x_b = idx_b * spacing + 1

        stype = corr["surface_type"]
        line_color = SURFACE_COLORS.get(stype, "#666666")

        fig.add_trace(go.Scatter(
            x=[x_a + 0.5, x_b - 0.5],
            y=[-corr["depth_a"], -corr["depth_b"]],
            mode="lines",
            line=dict(color=line_color, width=2, dash="dash"),
            showlegend=False,
            hovertext=(
                f"相关界面: {stype}<br>"
                f"{code_a}: {corr['depth_a']:.1f} cm<br>"
                f"{code_b}: {corr['depth_b']:.1f} cm<br>"
                f"相关性: {corr['correlation_score']:.3f}"
            ),
            hoverinfo="text",
        ))

    for stype, color in SURFACE_COLORS.items():
        count = sum(1 for s in key_surfaces if s["surface_type"] == stype)
        if count > 0:
            fig.add_trace(go.Scatter(
                x=[None], y=[None],
                mode="lines",
                line=dict(color=color, width=3),
                name=f"{stype} ({count})",
                showlegend=True,
            ))

    fig.update_layout(
        title=title,
        barmode="overlay",
        xaxis=dict(
            tickmode="array",
            tickvals=[i * spacing + 1 for i in range(n_cores)],
            ticktext=sample_codes,
            title="柱样编号",
        ),
        yaxis=dict(
            title="深度 (cm)",
            range=[-global_max - 10, 5],
        ),
        showlegend=True,
        legend_title="界面类型",
        height=700,
        width=max(800, n_cores * 250),
    )

    return fig


def plot_regional_evolution_map(evolution_result: Dict[str, Any],
                                 title: str = "区域沉积演化分区图") -> go.Figure:
    zones = evolution_result.get("zones", [])
    stages = evolution_result.get("evolution_stages", [])

    if not zones and not stages:
        fig = go.Figure()
        fig.update_layout(title=title + " (无数据)")
        return fig

    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=["沉积分区", "演化趋势"],
        column_widths=[0.5, 0.5],
    )

    if zones:
        zone_names = [z["zone_type"] for z in zones]
        zone_counts = [z["core_count"] for z in zones]
        zone_colors = [ZONE_COLORS.get(z["zone_type"], "#999999") for z in zones]

        fig.add_trace(go.Bar(
            x=zone_names,
            y=zone_counts,
            marker_color=zone_colors,
            text=[f"{z['avg_sand']:.0f}%砂" for z in zones],
            textposition="outside",
            name="柱样数",
            hovertext=[
                f"分区: {z['zone_type']}<br>"
                f"柱样数: {z['core_count']}<br>"
                f"平均砂: {z['avg_sand']:.1f}%<br>"
                f"平均粉砂: {z['avg_silt']:.1f}%<br>"
                f"平均黏土: {z['avg_clay']:.1f}%"
                for z in zones
            ],
            hoverinfo="text",
        ), row=1, col=1)

    if stages:
        sample_codes = [s["sample_code"] for s in stages]
        trends = [s["overall_trend"] for s in stages]

        trend_colors = []
        for t in trends:
            if "海退" in t:
                trend_colors.append("#C62828")
            elif "海进" in t:
                trend_colors.append("#1565C0")
            else:
                trend_colors.append("#2E7D32")

        fig.add_trace(go.Bar(
            x=sample_codes,
            y=[1] * len(sample_codes),
            marker_color=trend_colors,
            text=trends,
            textposition="outside",
            name="演化趋势",
            hovertext=[
                f"柱样: {s['sample_code']}<br>"
                f"趋势: {s['overall_trend']}<br>"
                f"阶段数: {len(s['segments'])}"
                for s in stages
            ],
            hoverinfo="text",
        ), row=1, col=2)

    fig.update_layout(
        title=title,
        height=500,
        showlegend=False,
    )

    return fig


def plot_continuity_chart(continuity_result: Dict[str, Any],
                           title: str = "层序延续性分析图") -> go.Figure:
    continuity = continuity_result.get("continuity", [])
    if not continuity:
        fig = go.Figure()
        fig.update_layout(title=title + " (无数据)")
        return fig

    layer_names = [c["layer_name"] for c in continuity]
    confidences = [c["confidence"] for c in continuity]
    cont_types = [c["continuity_type"] for c in continuity]
    colors = [CONTINUITY_COLORS.get(ct, "#999") for ct in cont_types]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=layer_names,
        y=confidences,
        marker_color=colors,
        text=[f"{c:.2f}" for c in confidences],
        textposition="outside",
        hovertext=[
            f"层位: {c['layer_name']}<br>"
            f"类型: {c['continuity_type']}<br>"
            f"置信度: {c['confidence']:.3f}<br>"
            f"出现次数: {c['occurrence_count']}<br>"
            f"涉及站位: {c['station_count']}"
            for c in continuity
        ],
        hoverinfo="text",
    ))

    for ctype, color in CONTINUITY_COLORS.items():
        count = sum(1 for c in continuity if c["continuity_type"] == ctype)
        if count > 0:
            fig.add_trace(go.Scatter(
                x=[None], y=[None],
                mode="markers",
                marker=dict(size=10, color=color, symbol="square"),
                name=f"{ctype} ({count})",
                showlegend=True,
            ))

    fig.update_layout(
        title=title,
        xaxis_title="层位名称",
        yaxis_title="延续性置信度",
        yaxis=dict(range=[0, 1.1]),
        height=500,
    )

    return fig


def plot_similar_segments_heatmap(similar_result: Dict[str, Any],
                                   title: str = "相似层段识别热力图") -> go.Figure:
    segment_pairs = similar_result.get("segment_pairs", [])
    if not segment_pairs:
        fig = go.Figure()
        fig.update_layout(title=title + " (无数据)")
        return fig

    all_segments = similar_result.get("similar_segments", [])

    if not all_segments:
        fig = go.Figure()
        fig.update_layout(title=title + " (无数据)")
        return fig

    pair_labels = []
    similarity_values = []
    segment_labels = []

    for seg in all_segments[:50]:
        label = f"{seg['core_a']} vs {seg['core_b']}"
        pair_labels.append(label)
        similarity_values.append(seg["similarity"])
        seg_label = (f"{seg['layers_a'][0]}... ↔ {seg['layers_b'][0]}...")
        segment_labels.append(seg_label)

    fig = go.Figure(go.Bar(
        x=segment_labels,
        y=similarity_values,
        marker_color=[
            "#28a745" if s >= 0.8 else "#ffc107" if s >= 0.6 else "#dc3545"
            for s in similarity_values
        ],
        text=[f"{s:.3f}" for s in similarity_values],
        textposition="outside",
        hovertext=[
            f"{seg['core_a']} vs {seg['core_b']}<br>"
            f"深度A: {seg['start_depth_a']:.1f}-{seg['end_depth_a']:.1f} cm<br>"
            f"深度B: {seg['start_depth_b']:.1f}-{seg['end_depth_b']:.1f} cm<br>"
            f"相似度: {seg['similarity']:.4f}"
            for seg in all_segments[:50]
        ],
        hoverinfo="text",
    ))

    fig.update_layout(
        title=title,
        xaxis_title="层段",
        yaxis_title="相似度",
        yaxis=dict(range=[0, 1.1]),
        height=500,
    )

    return fig


def plot_cross_section_correlation(alignment_result: Dict[str, Any],
                                     surface_result: Optional[Dict[str, Any]] = None,
                                     title: str = "多柱样层序对比横断面图") -> go.Figure:
    core_data = alignment_result.get("core_data", {})
    aligned_groups = alignment_result.get("aligned_groups", [])

    if not core_data:
        fig = go.Figure()
        fig.update_layout(title=title + " (无数据)")
        return fig

    sample_codes = list(core_data.keys())
    n_cores = len(sample_codes)

    all_max_depths = []
    for code in sample_codes:
        layers = core_data[code]["layers"]
        if not layers.empty:
            all_max_depths.append(layers["depth_end"].max())
    global_max = max(all_max_depths) if all_max_depths else 100

    fig = go.Figure()

    spacing = 3.0
    bar_width = 1.2

    for core_idx, code in enumerate(sample_codes):
        layers = core_data[code]["layers"]
        if layers.empty:
            continue
        x_center = core_idx * spacing + 1

        for _, row in layers.iterrows():
            thickness = row["depth_end"] - row["depth_start"]
            color = _get_layer_color(row["layer_name"])

            fig.add_trace(go.Bar(
                x=[x_center],
                y=[-thickness],
                base=[-row["depth_start"]],
                orientation="v",
                marker_color=color,
                marker_line_color="black",
                marker_line_width=1,
                width=bar_width,
                name=row["layer_name"],
                legendgroup=row["layer_name"],
                showlegend=False,
                hovertext=(
                    f"柱样: {code}<br>"
                    f"层位: {row['layer_name']}<br>"
                    f"深度: {row['depth_start']} - {row['depth_end']} cm<br>"
                    f"厚度: {thickness:.1f} cm<br>"
                    f"砂: {row.get('sand_pct', 0):.1f}%<br>"
                    f"黏土: {row.get('clay_pct', 0):.1f}%"
                ),
                hoverinfo="text",
            ))

        fig.add_annotation(
            x=x_center, y=5,
            text=f"<b>{code}</b>",
            showarrow=False,
            font=dict(size=12),
        )

    alignment_colors = px.colors.qualitative.Set2
    for group_idx, group in enumerate(aligned_groups):
        color = alignment_colors[group_idx % len(alignment_colors)]
        members = group["members"]

        for m_idx in range(len(members)):
            for m_jdx in range(m_idx + 1, len(members)):
                m_a = members[m_idx]
                m_b = members[m_jdx]

                if m_a["sample_code"] not in sample_codes or m_b["sample_code"] not in sample_codes:
                    continue

                idx_a = sample_codes.index(m_a["sample_code"])
                idx_b = sample_codes.index(m_b["sample_code"])
                x_a = idx_a * spacing + 1
                x_b = idx_b * spacing + 1

                fig.add_trace(go.Scatter(
                    x=[x_a + bar_width / 2, x_b - bar_width / 2],
                    y=[-m_a["depth"], -m_b["depth"]],
                    mode="lines",
                    line=dict(color=color, width=1.5, dash="dot"),
                    showlegend=False,
                    hoverinfo="skip",
                ))

    if surface_result:
        key_surfaces = surface_result.get("key_surfaces", [])
        for surface in key_surfaces:
            sc = surface["sample_code"]
            if sc not in sample_codes:
                continue
            core_idx = sample_codes.index(sc)
            x_center = core_idx * spacing + 1
            stype = surface["surface_type"]
            marker_color = SURFACE_COLORS.get(stype, "#666666")
            marker_symbol = {
                "flooding_surface": "triangle-up",
                "regression_surface": "triangle-down",
                "lithology_change": "diamond",
                "gradational_change": "circle",
            }.get(stype, "circle")

            fig.add_trace(go.Scatter(
                x=[x_center + bar_width / 2 + 0.15],
                y=[-surface["depth"]],
                mode="markers",
                marker=dict(size=10, color=marker_color, symbol=marker_symbol,
                            line=dict(width=1, color="black")),
                showlegend=False,
                hovertext=(
                    f"{surface.get('surface_label', stype)}<br>"
                    f"深度: {surface['depth']:.1f}cm<br>"
                    f"上覆: {surface['layer_above']}<br>"
                    f"下伏: {surface['layer_below']}"
                ),
                hoverinfo="text",
            ))

    unique_layers = set()
    for code in sample_codes:
        layers = core_data[code]["layers"]
        if not layers.empty:
            for _, row in layers.iterrows():
                if row["layer_name"] not in unique_layers:
                    unique_layers.add(row["layer_name"])
                    fig.add_trace(go.Scatter(
                        x=[None], y=[None],
                        mode="markers",
                        marker=dict(size=10, color=_get_layer_color(row["layer_name"]),
                                    symbol="square"),
                        name=row["layer_name"],
                        showlegend=True,
                    ))

    fig.update_layout(
        title=title,
        barmode="overlay",
        xaxis=dict(
            tickmode="array",
            tickvals=[i * spacing + 1 for i in range(n_cores)],
            ticktext=sample_codes,
            title="柱样编号",
            range=[-0.5, n_cores * spacing + 0.5],
        ),
        yaxis=dict(
            title="深度 (cm)",
            range=[-global_max - 15, 15],
        ),
        showlegend=True,
        legend_title="图例",
        height=max(700, global_max * 3),
        width=max(900, n_cores * 280),
    )

    return fig


def plot_alignment_quality(quality: Dict[str, Any],
                            title: str = "对齐质量评估") -> go.Figure:
    if not quality or not quality.get("details"):
        fig = go.Figure()
        fig.update_layout(title=title + " (无数据)")
        return fig

    details = quality["details"]
    categories = ["层位覆盖率", "多站位对齐率", "平均相似度", "同名匹配率"]
    values = [
        details.get("coverage_ratio", 0),
        details.get("multi_station_group_ratio", 0),
        details.get("avg_similarity", 0),
        details.get("name_match_ratio", 0),
    ]

    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=["质量指标雷达图", "质量指标柱状图"],
        column_widths=[0.5, 0.5],
    )

    fig.add_trace(go.Scatterpolar(
        r=values + [values[0]],
        theta=categories + [categories[0]],
        fill="toself",
        name="质量评分",
        line=dict(color="#2d5f8f", width=2),
        fillcolor="rgba(45, 95, 143, 0.3)",
    ), row=1, col=1)

    colors = ["#28a745" if v >= 0.7 else "#ffc107" if v >= 0.4 else "#dc3545" for v in values]
    fig.add_trace(go.Bar(
        x=categories,
        y=values,
        marker_color=colors,
        text=[f"{v:.1%}" for v in values],
        textposition="outside",
        name="评分",
    ), row=1, col=2)

    fig.update_layout(
        title=f"{title} - 总评分: {quality.get('overall_score', 0):.3f} ({quality.get('grade', 'N/A')})",
        polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
        height=500,
        showlegend=False,
    )
    fig.update_yaxes(range=[0, 1.2], row=1, col=2)

    return fig


def plot_regional_evolution_detailed(evolution_result: Dict[str, Any],
                                      title: str = "区域沉积演化综合分析图") -> go.Figure:
    zones = evolution_result.get("zones", [])
    stages = evolution_result.get("evolution_stages", [])
    core_data = evolution_result.get("core_data", {})

    if not zones and not stages:
        fig = go.Figure()
        fig.update_layout(title=title + " (无数据)")
        return fig

    fig = make_subplots(
        rows=2, cols=3,
        subplot_titles=["沉积分区", "演化趋势", "颗粒组成对比",
                         "砂黏比垂直变化", "沉积环境三角图", "分区柱样统计"],
        vertical_spacing=0.15,
        horizontal_spacing=0.1,
    )

    if zones:
        zone_names = [z["zone_type"] for z in zones]
        zone_counts = [z["core_count"] for z in zones]
        zone_colors = [ZONE_COLORS.get(z["zone_type"], "#999999") for z in zones]

        fig.add_trace(go.Bar(
            x=zone_names, y=zone_counts,
            marker_color=zone_colors,
            text=[f"{z['avg_sand']:.0f}%砂" for z in zones],
            textposition="outside",
            name="柱样数",
        ), row=1, col=1)

    if stages:
        sample_codes = [s["sample_code"] for s in stages]
        trends = [s["overall_trend"] for s in stages]
        trend_colors = []
        for t in trends:
            if "海退" in t:
                trend_colors.append("#C62828")
            elif "海进" in t:
                trend_colors.append("#1565C0")
            else:
                trend_colors.append("#2E7D32")

        fig.add_trace(go.Bar(
            x=sample_codes, y=[1] * len(sample_codes),
            marker_color=trend_colors,
            text=trends,
            textposition="outside",
            name="演化趋势",
        ), row=1, col=2)

    if zones:
        sand_vals = [z["avg_sand"] for z in zones]
        silt_vals = [z["avg_silt"] for z in zones]
        clay_vals = [z["avg_clay"] for z in zones]

        fig.add_trace(go.Bar(
            x=["砂", "粉砂", "黏土"],
            y=[np.mean(sand_vals), np.mean(silt_vals), np.mean(clay_vals)],
            marker_color=["#f4a460", "#daa520", "#8b4513"],
            name="平均颗粒组成",
        ), row=1, col=3)

    if core_data and stages:
        colors_list = px.colors.qualitative.Plotly
        for idx, (code, data) in enumerate(core_data.items()):
            layers = data["layers"].sort_values("depth_start")
            if layers.empty:
                continue
            sand_clay_ratio = layers["sand_pct"] / layers["clay_pct"].replace(0, 0.1)
            mid_depth = (layers["depth_start"] + layers["depth_end"]) / 2

            fig.add_trace(go.Scatter(
                x=sand_clay_ratio,
                y=-mid_depth,
                mode="lines+markers",
                name=code,
                line=dict(color=colors_list[idx % len(colors_list)], width=2),
                marker=dict(size=5),
            ), row=2, col=1)

        fig.update_xaxes(title_text="砂黏比", row=2, col=1)
        fig.update_yaxes(title_text="深度 (cm)", row=2, col=1)

    if core_data:
        all_sand = []
        all_clay = []
        all_silt = []
        all_codes = []
        for code, data in core_data.items():
            layers = data["layers"]
            if not layers.empty:
                all_sand.extend(layers["sand_pct"].tolist())
                all_clay.extend(layers["clay_pct"].tolist())
                all_silt.extend(layers["silt_pct"].tolist())
                all_codes.extend([code] * len(layers))

        if all_sand:
            fig.add_trace(go.Scatterternary({
                "mode": "markers",
                "a": all_sand,
                "b": all_clay,
                "c": all_silt,
                "text": all_codes,
                "marker": {
                    "size": 8,
                    "color": all_codes,
                    "line": {"width": 1, "color": "black"},
                },
                "name": "颗粒组成",
            }), row=2, col=2)

    if zones:
        zone_names = [z["zone_type"] for z in zones]
        zone_core_counts = [z["core_count"] for z in zones]
        zone_colors_bar = [ZONE_COLORS.get(z["zone_type"], "#999") for z in zones]

        fig.add_trace(go.Pie(
            labels=zone_names,
            values=zone_core_counts,
            marker=dict(colors=zone_colors_bar),
            textinfo="label+percent",
            name="分区占比",
        ), row=2, col=3)

    fig.update_layout(
        title=title,
        height=900,
        showlegend=False,
    )

    return fig


def plot_surface_significance_chart(surface_result: Dict[str, Any],
                                      title: str = "关键界面重要性分析") -> go.Figure:
    key_surfaces = surface_result.get("key_surfaces", [])
    if not key_surfaces:
        fig = go.Figure()
        fig.update_layout(title=title + " (无数据)")
        return fig

    sample_codes = [s["sample_code"] for s in key_surfaces]
    depths = [s["depth"] for s in key_surfaces]
    grain_changes = [s.get("grain_change", 0) for s in key_surfaces]
    significance = [s.get("significance", "low") for s in key_surfaces]

    sig_colors = {"high": "#dc3545", "medium": "#ffc107", "low": "#28a745"}
    colors = [sig_colors.get(s, "#999") for s in significance]

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=sample_codes,
        y=depths,
        mode="markers",
        marker=dict(
            size=[gc / 3 + 8 for gc in grain_changes],
            color=colors,
            symbol=["triangle-up" if s.get("surface_type") == "flooding_surface" else
                     "triangle-down" if s.get("surface_type") == "regression_surface" else
                     "diamond" for s in key_surfaces],
            line=dict(width=1, color="black"),
        ),
        text=[f"{s.get('surface_label', s['surface_type'])}<br>"
              f"深度: {s['depth']:.1f}cm<br>"
              f"粒度变化: {s.get('grain_change', 0):.1f}<br>"
              f"重要性: {s.get('significance', 'low')}"
              for s in key_surfaces],
        hoverinfo="text",
        name="界面",
    ))

    for sig_level, color in sig_colors.items():
        label_map = {"high": "高重要性", "medium": "中等重要性", "low": "低重要性"}
        fig.add_trace(go.Scatter(
            x=[None], y=[None],
            mode="markers",
            marker=dict(size=10, color=color, symbol="diamond"),
            name=label_map.get(sig_level, sig_level),
            showlegend=True,
        ))

    fig.update_layout(
        title=title,
        xaxis_title="柱样编号",
        yaxis_title="深度 (cm)",
        yaxis=dict(autorange="reversed"),
        height=600,
        showlegend=True,
    )

    return fig


def plot_age_depth_scatter(dating_points: pd.DataFrame,
                            model_result: Dict[str, Any] = None,
                            title: str = "年龄-深度关系图") -> go.Figure:
    fig = go.Figure()

    if not dating_points.empty:
        valid_points = dating_points[dating_points.get("is_valid", 1) == 1]
        anomaly_points = dating_points[dating_points.get("is_anomaly", 0) == 1]
        invalid_points = dating_points[dating_points.get("is_valid", 1) == 0]

        if not valid_points.empty:
            normal_points = valid_points[valid_points.get("is_anomaly", 0) == 0]
            if not normal_points.empty:
                fig.add_trace(go.Scatter(
                    x=normal_points["age"],
                    y=normal_points["depth"],
                    mode="markers",
                    marker=dict(size=12, color="#2d5f8f", symbol="circle",
                                line=dict(width=2, color="black")),
                    name="有效年代点",
                    text=normal_points.apply(lambda r: (
                        f"深度: {r['depth']:.1f} cm<br>"
                        f"年龄: {r['age']:.1f} a BP<br>"
                        f"方法: {r.get('dating_method', 'N/A')}<br>"
                        f"标签: {r.get('sample_label', 'N/A')}"
                    ), axis=1),
                    hoverinfo="text",
                ))

            if not anomaly_points.empty:
                fig.add_trace(go.Scatter(
                    x=anomaly_points["age"],
                    y=anomaly_points["depth"],
                    mode="markers",
                    marker=dict(size=14, color="#dc3545", symbol="triangle-up",
                                line=dict(width=2, color="darkred")),
                    name="异常年代点",
                    text=anomaly_points.apply(lambda r: (
                        f"深度: {r['depth']:.1f} cm<br>"
                        f"年龄: {r['age']:.1f} a BP<br>"
                        f"异常原因: {r.get('anomaly_reason', 'N/A')}"
                    ), axis=1),
                    hoverinfo="text",
                ))

        if not invalid_points.empty:
            fig.add_trace(go.Scatter(
                x=invalid_points["age"],
                y=invalid_points["depth"],
                mode="markers",
                marker=dict(size=10, color="#6c757d", symbol="x",
                            line=dict(width=2, color="black")),
                name="已排除/无效",
                text=invalid_points.apply(lambda r: (
                    f"深度: {r['depth']:.1f} cm<br>"
                    f"年龄: {r['age']:.1f} a BP"
                ), axis=1),
                hoverinfo="text",
            ))

    if model_result and model_result.get("success"):
        import chronology_engine as ce
        max_depth = max(dating_points["depth"].max() * 1.1, 10) if not dating_points.empty else 100
        depths = np.linspace(0, max_depth, 200)
        ages = ce.predict_age_batch(model_result, depths)

        valid_mask = ~np.isnan(ages)
        if valid_mask.any():
            model_type_name = {
                "linear": "线性拟合",
                "polynomial_2": "二次多项式",
                "polynomial_3": "三次多项式",
                "spline": "样条插值",
                "linear_segmented": "分段线性",
            }.get(model_result["model_type"], model_result["model_type"])

            label = f"{model_type_name}"
            r2 = model_result.get("r_squared")
            rmse = model_result.get("rmse")
            if r2 is not None:
                label += f" (R²={r2:.3f}"
                if rmse is not None:
                    label += f", RMSE={rmse:.1f}"
                label += ")"

            fig.add_trace(go.Scatter(
                x=ages[valid_mask],
                y=depths[valid_mask],
                mode="lines",
                line=dict(color="#e67e22", width=3),
                name=label,
            ))

    fig.update_layout(
        title=title,
        xaxis_title="年龄 (a BP)",
        yaxis_title="深度 (cm)",
        yaxis=dict(autorange="reversed"),
        height=600,
        width=700,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    return fig


def plot_sedimentation_rate(rates_df: pd.DataFrame,
                             title: str = "沉积速率垂直分布图") -> go.Figure:
    if rates_df.empty:
        fig = go.Figure()
        fig.update_layout(title=title + " (无数据)")
        return fig

    fig = go.Figure()

    for _, row in rates_df.iterrows():
        fig.add_trace(go.Bar(
            x=[row["sedimentation_rate"]],
            y=[-(row["depth_start"] + row["depth_end"]) / 2],
            width=row["thickness"] * 0.8,
            orientation="h",
            marker_color="#2d5f8f",
            marker_line_color="black",
            marker_line_width=1,
            name=row.get("layer_name", ""),
            showlegend=False,
            text=f"{row['sedimentation_rate']:.2f} cm/ka",
            textposition="auto",
            hovertext=(
                f"层位: {row.get('layer_name', 'N/A')}<br>"
                f"深度: {row['depth_start']:.1f} - {row['depth_end']:.1f} cm<br>"
                f"年龄: {row['age_start']:.1f} - {row['age_end']:.1f} a BP<br>"
                f"时长: {row['age_duration']:.1f} a<br>"
                f"厚度: {row['thickness']:.1f} cm<br>"
                f"沉积速率: {row['sedimentation_rate']:.2f} cm/ka"
            ),
            hoverinfo="text",
        ))

    avg_rate = rates_df["sedimentation_rate"].mean()
    fig.add_vline(x=avg_rate, line_dash="dash", line_color="#e67e22",
                  annotation_text=f"平均: {avg_rate:.2f} cm/ka",
                  annotation_position="top")

    fig.update_layout(
        title=title,
        xaxis_title="沉积速率 (cm/ka)",
        yaxis_title="深度 (cm)",
        height=600,
        width=600,
    )

    return fig


def plot_time_section(layers_df: pd.DataFrame,
                       model_result: Dict[str, Any],
                       title: str = "时间剖面图") -> go.Figure:
    if layers_df.empty or not model_result.get("success"):
        fig = go.Figure()
        fig.update_layout(title=title + " (无数据或模型未建立)")
        return fig

    import chronology_engine as ce

    fig = go.Figure()

    for _, row in layers_df.iterrows():
        d_start = row["depth_start"]
        d_end = row["depth_end"]
        a_start = ce.predict_age(model_result, float(d_start))
        a_end = ce.predict_age(model_result, float(d_end))

        if a_start is None or a_end is None:
            continue

        thickness = a_end - a_start
        if thickness <= 0:
            continue

        color = _get_layer_color(row["layer_name"])

        fig.add_trace(go.Bar(
            x=[1],
            y=[-thickness],
            base=[-a_start],
            orientation="v",
            marker_color=color,
            marker_line_color="black",
            marker_line_width=1,
            width=0.8,
            name=row["layer_name"],
            legendgroup=row["layer_name"],
            showlegend=(row["layer_name"] not in [t.name for t in fig.data if hasattr(t, "name")]),
            hovertext=(
                f"层位: {row['layer_name']}<br>"
                f"深度: {d_start:.1f} - {d_end:.1f} cm<br>"
                f"年龄: {a_start:.1f} - {a_end:.1f} a BP<br>"
                f"时长: {thickness:.1f} a<br>"
                f"砾石: {row.get('gravel_pct', 0):.1f}%<br>"
                f"砂: {row.get('sand_pct', 0):.1f}%<br>"
                f"粉砂: {row.get('silt_pct', 0):.1f}%<br>"
                f"黏土: {row.get('clay_pct', 0):.1f}%"
            ),
            hoverinfo="text",
        ))

    fig.update_layout(
        title=title,
        barmode="stack",
        xaxis=dict(showticklabels=False, range=[0.5, 1.5]),
        yaxis=dict(title="年龄 (a BP)"),
        showlegend=True,
        height=600,
        width=500,
    )

    return fig


def plot_multi_station_sedimentation(comparison_df: pd.DataFrame,
                                      title: str = "多站位沉积演化速率对比") -> go.Figure:
    if comparison_df.empty:
        fig = go.Figure()
        fig.update_layout(title=title + " (无数据)")
        return fig

    fig = go.Figure()

    sample_codes = comparison_df["sample_code"].unique()
    colors = px.colors.qualitative.Plotly

    for idx, code in enumerate(sample_codes):
        core_data = comparison_df[comparison_df["sample_code"] == code]
        color = colors[idx % len(colors)]

        x_vals = []
        y_vals = []
        for _, row in core_data.iterrows():
            x_vals.extend([row["age_start"], row["age_end"], row["age_end"], None])
            y_vals.extend([row["sedimentation_rate"], row["sedimentation_rate"], None, None])

        station = row.get("station_code", "")
        label = f"{station}-{code}" if station else code

        fig.add_trace(go.Scatter(
            x=x_vals,
            y=y_vals,
            mode="lines",
            line=dict(color=color, width=3),
            name=label,
            fill="tozeroy",
            fillcolor=f"rgba{tuple(int(color.lstrip('#')[i:i+2], 16) for i in (0, 2, 4)) + (0.2,)}",
        ))

    fig.update_layout(
        title=title,
        xaxis_title="年龄 (a BP)",
        yaxis_title="沉积速率 (cm/ka)",
        xaxis=dict(autorange="reversed"),
        height=500,
        width=900,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    return fig


def plot_temporal_layer_comparison(comparison_df: pd.DataFrame,
                                    title: str = "层位时间对比图") -> go.Figure:
    if comparison_df.empty:
        fig = go.Figure()
        fig.update_layout(title=title + " (无数据)")
        return fig

    fig = go.Figure()

    for idx, row in comparison_df.iterrows():
        if row["age_a"] is None or row["age_b"] is None:
            continue

        color = "#28a745" if abs(row["age_diff"]) < 500 else "#ffc107" if abs(row["age_diff"]) < 2000 else "#dc3545"

        fig.add_trace(go.Scatter(
            x=[row["age_a"], row["age_b"]],
            y=[1, 2],
            mode="lines+markers",
            line=dict(color=color, width=3),
            marker=dict(size=12, color=color, symbol=["circle", "square"]),
            showlegend=False,
            hovertext=(
                f"柱样A: {row['layer_a']}<br>"
                f"年龄A: {row['age_a']:.1f} a BP<br>"
                f"柱样B: {row['layer_b']}<br>"
                f"年龄B: {row['age_b']:.1f} a BP<br>"
                f"年龄差: {row['age_diff']:.1f} a"
            ),
            hoverinfo="text",
        ))

    fig.add_hline(y=1, line_dash="dash", line_color="gray")
    fig.add_hline(y=2, line_dash="dash", line_color="gray")

    fig.add_annotation(x=0.5, y=1, text="柱样 A", showarrow=False, yshift=20, font=dict(size=14))
    fig.add_annotation(x=0.5, y=2, text="柱样 B", showarrow=False, yshift=20, font=dict(size=14))

    fig.update_layout(
        title=title,
        xaxis_title="年龄 (a BP)",
        yaxis=dict(showticklabels=False, range=[0.5, 2.5]),
        xaxis=dict(autorange="reversed"),
        height=400,
        width=800,
    )

    return fig


def plot_chronology_stats(chronology_summary: pd.DataFrame,
                           title: str = "年代约束统计概览") -> go.Figure:
    if chronology_summary.empty:
        fig = go.Figure()
        fig.update_layout(title=title + " (无数据)")
        return fig

    fig = make_subplots(
        rows=1, cols=3,
        subplot_titles=["年代点数量", "模型数量", "平均沉积速率 (cm/ka)"],
    )

    fig.add_trace(go.Bar(
        x=chronology_summary["sample_code"],
        y=chronology_summary["dating_point_count"],
        marker_color="#2d5f8f",
        text=chronology_summary["dating_point_count"],
        textposition="outside",
        name="年代点数",
    ), row=1, col=1)

    fig.add_trace(go.Bar(
        x=chronology_summary["sample_code"],
        y=chronology_summary["model_count"],
        marker_color="#e67e22",
        text=chronology_summary["model_count"],
        textposition="outside",
        name="模型数",
    ), row=1, col=2)

    rate_vals = chronology_summary["avg_sedimentation_rate"].fillna(0)
    fig.add_trace(go.Bar(
        x=chronology_summary["sample_code"],
        y=rate_vals,
        marker_color=["#28a745" if v > 0 else "#6c757d" for v in rate_vals],
        text=[f"{v:.1f}" if v > 0 else "N/A" for v in rate_vals],
        textposition="outside",
        name="平均速率",
    ), row=1, col=3)

    fig.update_layout(
        title=title,
        height=450,
        showlegend=False,
    )

    return fig
