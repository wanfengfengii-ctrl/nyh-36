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
