import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from io import BytesIO, StringIO
import json
from datetime import datetime

import database as db
import data_validator as validator
import analyzer
import visualizer
import quality_control as qc


st.set_page_config(
    page_title="海底沉积柱样质量控制与指标关联分析工作台",
    page_icon="🌊",
    layout="wide",
)


db.init_db()


st.markdown("""
    <style>
        .main-header {
            text-align: center;
            padding: 1rem;
            background: linear-gradient(135deg, #1e3a5f 0%, #2d5f8f 100%);
            color: white;
            border-radius: 10px;
            margin-bottom: 2rem;
        }
        .metric-card {
            background: #f0f8ff;
            padding: 1rem;
            border-radius: 8px;
            border-left: 4px solid #2d5f8f;
        }
        .warning-box {
            background: #fff3cd;
            padding: 0.5rem 1rem;
            border-radius: 5px;
            border-left: 4px solid #ffc107;
        }
        .error-box {
            background: #f8d7da;
            padding: 0.5rem 1rem;
            border-radius: 5px;
            border-left: 4px solid #dc3545;
        }
        .success-box {
            background: #d4edda;
            padding: 0.5rem 1rem;
            border-radius: 5px;
            border-left: 4px solid #28a745;
        }
        .info-box {
            background: #d1ecf1;
            padding: 0.5rem 1rem;
            border-radius: 5px;
            border-left: 4px solid #17a2b8;
        }
        .quality-good { color: #28a745; font-weight: bold; }
        .quality-warning { color: #ffc107; font-weight: bold; }
        .quality-error { color: #dc3545; font-weight: bold; }
        .stTabs [data-baseweb="tab-list"] {
            gap: 2px;
        }
        .stTabs [data-baseweb="tab"] {
            height: 50px;
            white-space: pre-wrap;
            background-color: #f0f2f6;
            border-radius: 4px 4px 0px 0px;
            gap: 1px;
            padding-top: 10px;
            padding-bottom: 10px;
        }
        .stTabs [aria-selected="true"] {
            background-color: #2d5f8f;
            color: white;
        }
    </style>
""", unsafe_allow_html=True)


st.markdown("""
    <div class="main-header">
        <h1>🌊 海底沉积柱样质量控制与指标关联分析工作台</h1>
        <p style="opacity: 0.9; margin-top: 0.5rem;">
            海洋地质沉积柱样数据管理 · 质量控制 · 可视化分析 · 多柱对比
        </p>
    </div>
""", unsafe_allow_html=True)


with st.sidebar:
    st.header("导航菜单")
    page = st.radio(
        "选择功能模块",
        [
            "📊 数据总览",
            "📥 数据导入与去重",
            "🔬 单柱样分析",
            "📈 多柱样对比",
            "🎯 质量控制工作台",
            "⚙️ 数据管理与版本"
        ]
    )

    st.divider()
    st.subheader("🔍 全局筛选")

    all_stations = db.get_all_stations()
    station_options = ["全部"] + (all_stations["station_code"].tolist() if not all_stations.empty else [])
    selected_station = st.selectbox("选择站位", station_options, key="global_station_filter")

    if "filters" not in st.session_state:
        st.session_state.filters = {
            "station_code": "全部",
            "min_core_length": None,
            "max_core_length": None,
            "min_layer_count": None,
            "max_layer_count": None,
            "sample_code_keyword": "",
        }

    st.session_state.filters["station_code"] = selected_station

    with st.expander("高级筛选"):
        st.session_state.filters["sample_code_keyword"] = st.text_input(
            "柱样编号关键词", value=st.session_state.filters.get("sample_code_keyword", "")
        )

        length_range = st.slider(
            "柱长范围 (cm)",
            min_value=0, max_value=500, value=(0, 500), step=10
        )
        st.session_state.filters["min_core_length"] = length_range[0]
        st.session_state.filters["max_core_length"] = length_range[1]

        layer_range = st.slider(
            "层数范围",
            min_value=0, max_value=100, value=(0, 100), step=1
        )
        st.session_state.filters["min_layer_count"] = layer_range[0]
        st.session_state.filters["max_layer_count"] = layer_range[1]

    if st.button("🔄 重置筛选", use_container_width=True):
        st.session_state.filters = {
            "station_code": "全部",
            "min_core_length": None,
            "max_core_length": None,
            "min_layer_count": None,
            "max_layer_count": None,
            "sample_code_keyword": "",
        }
        st.rerun()


if page == "📊 数据总览":
    st.header("数据总览")

    filters = st.session_state.filters
    stations_df = db.get_all_stations()
    all_cores = analyzer.filter_cores(filters)

    total_layers = 0
    for _, core in all_cores.iterrows():
        layers = db.get_core_layers(core["id"])
        total_layers += len(layers)

    errors_df = db.get_import_errors(10)
    quality_data = qc.get_quality_dashboard_data()
    pending_anomalies = quality_data["overall"]["pending_anomalies"]
    total_anomalies = quality_data["overall"]["total_anomalies"]

    import_sessions = db.get_import_sessions(5)

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    with col1:
        st.metric("采样站位数", len(stations_df))
    with col2:
        st.metric("沉积柱样数", len(all_cores))
    with col3:
        st.metric("层位记录数", total_layers)
    with col4:
        st.metric("待复核异常", pending_anomalies, delta=f"共{total_anomalies}个")
    with col5:
        st.metric("导入错误记录", len(errors_df))
    with col6:
        st.metric("导入会话数", len(import_sessions))

    tab1, tab2, tab3 = st.tabs(["📍 站位概览", "📋 柱样列表", "📊 质量统计"])

    with tab1:
        st.subheader("采样站位列表")
        if not stations_df.empty:
            station_summary = db.get_station_cores_summary()
            if not station_summary.empty:
                display_stations = station_summary.copy()
                display_stations.columns = [
                    "站位编号", "站名", "位置", "柱样数",
                    "层位数", "总厚度(cm)"
                ]
                st.dataframe(display_stations, use_container_width=True, hide_index=True)
            else:
                st.dataframe(
                    stations_df[["station_code", "station_name", "location", "created_at"]],
                    use_container_width=True,
                    hide_index=True,
                )
        else:
            st.info("暂无采样站位数据，请先导入CSV文件。")

    with tab2:
        st.subheader("沉积柱样列表")
        if not all_cores.empty:
            display_df = all_cores[["sample_code", "station_code", "core_length", "sampling_date", "version", "updated_at"]].copy()
            display_df.columns = ["样品编号", "站位编号", "柱长(cm)", "采样日期", "版本号", "更新时间"]
            st.dataframe(display_df, use_container_width=True, hide_index=True)
            st.caption(f"显示 {len(display_df)} 条记录（受全局筛选条件过滤）")
        else:
            st.info("暂无沉积柱样数据，请先导入CSV文件。")

    with tab3:
        st.subheader("质量控制统计")

        col_q1, col_q2 = st.columns(2)

        with col_q1:
            st.metric("总异常数", total_anomalies)
            st.metric("待复核", pending_anomalies)
            st.metric("已处理", quality_data["overall"]["resolved_anomalies"])

        with col_q2:
            all_reviews = db.get_anomaly_reviews()
            if not all_reviews.empty:
                fig_status = visualizer.plot_anomaly_status_pie(all_reviews, "异常复核状态分布")
                st.plotly_chart(fig_status, use_container_width=True)
            else:
                st.info("暂无异常记录")

        if quality_data["stations"]:
            st.subheader("各站位质量情况")
            station_quality_df = pd.DataFrame(quality_data["stations"])
            station_quality_df.columns = [
                "站位编号", "站名", "柱样数", "总层数",
                "异常数", "待复核数", "已确认数"
            ]
            st.dataframe(station_quality_df, use_container_width=True, hide_index=True)

    if len(errors_df) > 0:
        st.subheader("最近导入错误")
        error_display = errors_df[["file_name", "row_number", "error_type", "error_reason", "created_at"]].copy()
        error_display.columns = ["文件名", "行号", "错误类型", "错误原因", "时间"]
        st.dataframe(error_display, use_container_width=True, hide_index=True)


elif page == "📥 数据导入与去重":
    st.header("数据导入与去重")

    tab1, tab2, tab3 = st.tabs(["📤 导入数据", "📜 导入历史", "🔍 重复与重叠检测"])

    with tab1:
        st.subheader("CSV文件格式说明")
        with st.expander("查看列名要求和示例"):
            col_info = validator.get_expected_columns()
            st.write("**必需列:**", ", ".join(col_info["必需列"]))
            st.write("**可选列:**", ", ".join(col_info["可选列"]))
            st.write("**支持的列名别名:**")
            alias_df = pd.DataFrame([
                {"标准列名": k, "可用别名": ", ".join(v)}
                for k, v in col_info["列名别名"].items()
            ])
            st.dataframe(alias_df, use_container_width=True, hide_index=True)

        st.subheader("上传CSV文件")
        uploaded_file = st.file_uploader("选择CSV文件", type=["csv"])

        col_mode, col_detect = st.columns(2)
        with col_mode:
            import_mode = st.radio(
                "导入模式",
                ["append", "overwrite", "skip"],
                format_func=lambda x: {
                    "append": "追加模式（新增到现有数据）",
                    "overwrite": "覆盖模式（清空同名柱样后导入）",
                    "skip": "跳过模式（跳过已存在的柱样）",
                }.get(x, x),
                index=0,
                help="选择导入数据时如何处理已存在的同名柱样"
            )

        with col_detect:
            detect_duplicates = st.checkbox("检测重复记录", value=True,
                                             help="自动标记深度区间和层位名称完全相同的记录")
            detect_overlaps = st.checkbox("检测重叠层段", value=True,
                                         help="自动标记深度区间存在重叠的记录")

        session_note = st.text_input("导入备注（可选）", placeholder="记录本次导入的目的或说明...")

        if uploaded_file is not None:
            if st.button("🚀 开始导入", type="primary", use_container_width=True):
                with st.spinner("正在导入数据..."):
                    try:
                        result = validator.import_csv_v2(
                            uploaded_file, uploaded_file.name,
                            import_mode=import_mode,
                            detect_duplicates=detect_duplicates,
                            detect_overlaps=detect_overlaps,
                            session_note=session_note
                        )

                        col_s, col_d, col_o, col_e = st.columns(4)
                        with col_s:
                            st.metric("成功导入", f"{result['success_count']} 条")
                        with col_d:
                            st.metric("重复记录", f"{result['duplicate_count']} 条",
                                      delta="已标记" if result['duplicate_count'] > 0 else "无")
                        with col_o:
                            st.metric("重叠层段", f"{result['overlap_count']} 条",
                                      delta="已标记" if result['overlap_count'] > 0 else "无")
                        with col_e:
                            st.metric("导入失败", f"{result['error_count']} 条")

                        if result["errors"]:
                            with st.expander(f"查看 {len(result['errors'])} 条错误详情"):
                                error_rows = []
                                for err in result["errors"]:
                                    row_dict = err["row_data"]
                                    row_dict["错误原因"] = err["error_reason"]
                                    row_dict["行号"] = err["row_number"]
                                    row_dict["错误类型"] = err.get("error_type", "validation")
                                    error_rows.append(row_dict)
                                error_df = pd.DataFrame(error_rows)
                                cols = ["行号", "错误类型", "错误原因"] + [
                                    c for c in error_df.columns
                                    if c not in ["行号", "错误类型", "错误原因"]
                                ]
                                st.dataframe(error_df[cols], use_container_width=True, hide_index=True)

                        if result["warnings"]:
                            with st.expander(f"查看 {len(result['warnings'])} 条警告"):
                                warn_df = pd.DataFrame(result["warnings"])
                                st.dataframe(warn_df, use_container_width=True, hide_index=True)

                        st.success(f"✅ 导入完成！会话ID: {result['session_id']}")
                        st.rerun()

                    except ValueError as e:
                        st.error(f"❌ 文件格式错误: {str(e)}")
                    except Exception as e:
                        st.error(f"❌ 导入失败: {str(e)}")

        if st.button("清空导入错误记录"):
            db.clear_import_errors()
            st.success("已清空导入错误记录")

    with tab2:
        st.subheader("导入历史记录")
        sessions = db.get_import_sessions(20)
        if sessions.empty:
            st.info("暂无导入历史记录")
        else:
            display_sessions = sessions.copy()
            display_sessions.columns = [
                "ID", "文件名", "文件哈希", "总行数",
                "成功数", "跳过数", "错误数",
                "重复数", "重叠数", "导入模式", "备注", "导入时间"
            ]
            st.dataframe(display_sessions, use_container_width=True, hide_index=True)

    with tab3:
        st.subheader("重复与重叠检测")
        st.info("对现有数据中的重复记录和重叠层段进行检测")

        all_cores = db.get_all_core_samples()
        if all_cores.empty:
            st.info("暂无沉积柱样数据")
        else:
            core_options = dict(zip(all_cores["sample_code"], all_cores["id"]))
            check_core = st.selectbox(
                "选择要检测的柱样",
                list(core_options.keys()),
                key="dup_check_core"
            )
            check_core_id = core_options[check_core]

            if st.button("🔍 开始检测", key="run_dup_check"):
                with st.spinner("正在检测..."):
                    quality_info = validator.detect_core_duplicates_and_overlaps(check_core_id)

                    col_d, col_o = st.columns(2)
                    with col_d:
                        st.metric("重复记录", f"{len(quality_info['duplicates'])} 对")
                    with col_o:
                        st.metric("重叠层段", f"{len(quality_info['overlaps'])} 对")

                    if quality_info["duplicates"]:
                        st.warning("⚠️ 检测到重复记录")
                        dup_df = pd.DataFrame(quality_info["duplicates"])
                        dup_df.columns = ["层位ID 1", "层位ID 2", "层位名称", "深度起点", "深度终点"]
                        st.dataframe(dup_df, use_container_width=True, hide_index=True)

                    if quality_info["overlaps"]:
                        st.error("🔴 检测到重叠层段")
                        overlap_df = pd.DataFrame(quality_info["overlaps"])
                        overlap_df.columns = [
                            "层位ID 1", "层位ID 2", "层位名称 1", "层位名称 2",
                            "重叠起点", "重叠终点", "重叠厚度"
                        ]
                        st.dataframe(overlap_df, use_container_width=True, hide_index=True)

                    if not quality_info["duplicates"] and not quality_info["overlaps"]:
                        st.success("✅ 未检测到重复记录和重叠层段，数据质量良好")


elif page == "🔬 单柱样分析":
    st.header("单柱样详细分析")

    filters = st.session_state.filters
    cores_df = analyzer.filter_cores(filters)

    if cores_df.empty:
        st.info("暂无符合筛选条件的沉积柱样数据，请先导入CSV文件或调整筛选条件。")
    else:
        col_sel, col_info = st.columns([2, 1])
        with col_sel:
            core_options = dict(zip(cores_df["sample_code"], cores_df["id"]))
            selected_core = st.selectbox("选择沉积柱样", list(core_options.keys()),
                                         help="受全局筛选条件过滤")
            core_id = core_options[selected_core]

        analysis = analyzer.get_core_analysis(core_id)

        if not analysis or analysis["layers"].empty:
            st.warning("该柱样暂无层位数据")
        else:
            layers_df = analysis["layers"]
            core_info = analysis["core_info"]
            version = core_info.get("version", 1)

            with col_info:
                st.metric("当前版本", f"v{version}")
                if core_info.get("station_code"):
                    st.caption(f"站位: {core_info['station_code']}")

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("总采样厚度", f"{analysis.get('total_sampled_thickness', 0):.1f} cm")
            with col2:
                missing_thickness = analysis.get('total_missing_thickness', 0)
                st.metric("缺失层段厚度", f"{missing_thickness:.1f} cm",
                          delta=f"{missing_thickness/(analysis.get('total_sampled_thickness', 1)+missing_thickness)*100:.1f}%")
            with col3:
                st.metric("取芯率", f"{analysis.get('recovery_rate', 0):.1f}%")
            with col4:
                st.metric("层位数量", f"{len(layers_df)} 层")

            missing_severity = analyzer.get_missing_severity(
                analysis["missing_intervals"],
                core_info.get("core_length")
            )
            if missing_severity["level"] == "error":
                st.error(f"🔴 {missing_severity['message']}（缺失 {missing_severity['missing_pct']:.1f}%，共 {missing_severity['gap_count']} 处缺口）")
            elif missing_severity["level"] == "warning":
                st.warning(f"🟡 {missing_severity['message']}（缺失 {missing_severity['missing_pct']:.1f}%，共 {missing_severity['gap_count']} 处缺口）")
            else:
                st.success(f"🟢 {missing_severity['message']}")

            dup_count = analysis.get("duplicate_count", 0)
            overlap_count = analysis.get("overlap_count", 0)
            if dup_count > 0 or overlap_count > 0:
                st.warning(f"⚠️ 质量提示：检测到 {dup_count} 条重复记录，{overlap_count} 处重叠层段")

            tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
                "📋 层位数据表", "📊 分层剖面图", "📈 指标趋势图",
                "🔴 异常检测", "🔗 相关性分析", "📊 层位统计", "📜 版本历史"
            ])

            with tab1:
                st.subheader("层位数据")

                show_flags = st.checkbox("显示质量标记", value=True)
                display_cols = [
                    "layer_name", "depth_start", "depth_end", "thickness",
                    "gravel_pct", "sand_pct", "silt_pct", "clay_pct",
                    "organic_matter", "water_content"
                ]
                display_names = [
                    "层位名称", "深度起点(cm)", "深度终点(cm)", "厚度(cm)",
                    "砾石(%)", "砂(%)", "粉砂(%)", "黏土(%)",
                    "有机质(%)", "含水率(%)"
                ]

                if show_flags:
                    display_cols.extend(["is_duplicate", "is_overlap", "anomaly_status"])
                    display_names.extend(["重复标记", "重叠标记", "异常状态"])

                display_layers = layers_df[display_cols].copy()
                display_layers.columns = display_names
                st.dataframe(display_layers, use_container_width=True, hide_index=True)

                if analysis["missing_intervals"]:
                    st.warning("检测到缺失深度区段:")
                    missing_df = pd.DataFrame(analysis["missing_intervals"])
                    display_missing = missing_df[["depth_start", "depth_end", "thickness", "type"]].copy()
                    display_missing.columns = ["深度起点(cm)", "深度终点(cm)", "厚度(cm)", "缺失类型"]
                    display_missing["缺失类型"] = display_missing["缺失类型"].map({
                        "top_gap": "顶部缺失",
                        "middle_gap": "层间缺失",
                        "bottom_gap": "底部缺失"
                    })
                    st.dataframe(display_missing, use_container_width=True, hide_index=True)

                st.subheader("数据完整度评估")
                core_length = core_info.get("core_length")
                if core_length and core_length > 0:
                    missing_pct = missing_severity["missing_pct"]
                    fig_gauge = visualizer.plot_missing_severity_gauge(
                        missing_pct,
                        title=f"{selected_core} 数据完整度"
                    )
                    st.plotly_chart(fig_gauge, use_container_width=True)

            with tab2:
                core_length = analysis["core_info"].get("core_length")
                fig_section = visualizer.plot_core_section(
                    layers_df, analysis["missing_intervals"],
                    title=f"{selected_core} 分层剖面图",
                    core_length=core_length
                )

                quality = analysis.get("quality", {})
                if quality.get("duplicates") or quality.get("overlaps"):
                    fig_section = visualizer.plot_quality_markers(
                        fig_section, layers_df,
                        quality.get("duplicates", []),
                        quality.get("overlaps", [])
                    )

                st.plotly_chart(fig_section, use_container_width=True)

            with tab3:
                anomalies_df = analysis["anomalies"]
                fig_trends = visualizer.plot_indicator_trends(
                    anomalies_df, title=f"{selected_core} 指标深度变化趋势"
                )
                st.plotly_chart(fig_trends, use_container_width=True)

            with tab4:
                anomalies_df = analysis["anomalies"]
                anomaly_only = anomalies_df[anomalies_df["is_anomaly"]]

                if anomaly_only.empty:
                    st.success("✅ 未检测到异常指标")
                else:
                    st.warning(f"⚠️ 检测到 {len(anomaly_only)} 个异常层位")

                    col_add_a, col_add_b = st.columns([3, 1])
                    with col_add_a:
                        st.subheader("异常层位列表")
                    with col_add_b:
                        if st.button("批量提交复核", key="batch_review_btn"):
                            for _, row in anomaly_only.iterrows():
                                qc.submit_anomaly_review(
                                    int(row["id"]), core_id,
                                    "value_outlier",
                                    row.get("anomaly_details", "")
                                )
                            st.success(f"✅ 已提交 {len(anomaly_only)} 条异常记录复核")
                            st.rerun()

                    anomaly_display = anomaly_only[[
                        "layer_name", "depth_start", "depth_end", "thickness",
                        "anomaly_details"
                    ]].copy()
                    anomaly_display.columns = [
                        "层位名称", "深度起点", "深度终点", "厚度", "异常指标"
                    ]
                    st.dataframe(anomaly_display, use_container_width=True, hide_index=True)

                st.subheader("异常复核记录")
                reviews_df = db.get_anomaly_reviews(core_id=core_id)
                if reviews_df.empty:
                    st.info("暂无复核记录")
                else:
                    review_display = reviews_df[[
                        "layer_name", "anomaly_type", "status",
                        "reviewer", "reviewed_at", "created_at"
                    ]].copy()
                    review_display.columns = [
                        "层位名称", "异常类型", "状态", "复核人", "复核时间", "提交时间"
                    ]
                    st.dataframe(review_display, use_container_width=True, hide_index=True)

            with tab5:
                corr_method = st.radio(
                    "相关性计算方法",
                    ["pearson", "spearman"],
                    format_func=lambda x: {"pearson": "Pearson 相关系数", "spearman": "Spearman 秩相关"}.get(x, x),
                    horizontal=True
                )
                corr_matrix = analyzer.calculate_correlation(layers_df, method=corr_method)
                if corr_matrix.empty:
                    st.info("数据不足，无法计算相关性")
                else:
                    fig_corr = visualizer.plot_correlation_heatmap(
                        corr_matrix, title=f"{selected_core} 指标相关性矩阵 ({corr_method})"
                    )
                    st.plotly_chart(fig_corr, use_container_width=True)

                    st.subheader("相关性数值表")
                    st.dataframe(corr_matrix.round(3), use_container_width=True)

            with tab6:
                summary_df = analysis["layer_summary"]
                if not summary_df.empty:
                    fig_thickness = visualizer.plot_layer_thickness_bar(summary_df)
                    st.plotly_chart(fig_thickness, use_container_width=True)

                    fig_grain = visualizer.plot_grain_size_distribution(layers_df)
                    st.plotly_chart(fig_grain, use_container_width=True)

                    st.subheader("层位统计详情")
                    summary_display = summary_df.copy()
                    summary_display.columns = [
                        "层位名称", "层数", "总厚度(cm)", "平均厚度(cm)",
                        "最小深度", "最大深度", "平均砾石(%)", "平均砂(%)",
                        "平均粉砂(%)", "平均黏土(%)", "平均有机质(%)",
                        "平均含水率(%)", "厚度占比(%)"
                    ]
                    st.dataframe(summary_display.round(2), use_container_width=True, hide_index=True)

            with tab7:
                st.subheader("柱样版本历史")
                version_history = qc.get_core_version_history(core_id)

                col_v1, col_v2, col_v3 = st.columns(3)
                with col_v1:
                    st.metric("当前版本", f"v{version_history['current_version']}")
                with col_v2:
                    st.metric("总修改次数", version_history["total_changes"])
                with col_v3:
                    st.metric("涉及层位数", version_history["modified_layers"])

                if version_history["version_summary"]:
                    st.subheader("各层位修改统计")
                    ver_summary_df = pd.DataFrame(version_history["version_summary"])
                    ver_summary_df.columns = ["层位ID", "层位名称", "修改次数", "最后修改时间"]
                    st.dataframe(ver_summary_df, use_container_width=True, hide_index=True)
                else:
                    st.info("暂无历史修改记录，版本记录将在首次编辑层位后生成")

                if not version_history["versions"].empty:
                    st.subheader("详细修改记录")
                    ver_display = version_history["versions"][[
                        "version", "layer_name", "depth_start", "depth_end",
                        "change_reason", "changed_by", "created_at"
                    ]].copy()
                    ver_display.columns = [
                        "版本号", "层位名称", "深度起点", "深度终点",
                        "修改原因", "修改人", "修改时间"
                    ]
                    st.dataframe(ver_display, use_container_width=True, hide_index=True)


elif page == "📈 多柱样对比":
    st.header("多柱样对比分析")

    filters = st.session_state.filters
    cores_df = analyzer.filter_cores(filters)

    if cores_df.empty:
        st.info("暂无符合筛选条件的沉积柱样数据，请先导入CSV文件或调整筛选条件。")
    else:
        station_grouped = cores_df.groupby("station_code")["sample_code"].apply(list).to_dict()

        col_mode, col_station = st.columns([1, 2])
        with col_mode:
            comparison_mode = st.radio("选择模式", ["按站位对比", "手动选择柱样"], horizontal=True)

        selected_cores = []
        selected_station_name = None

        if comparison_mode == "按站位对比":
            if station_grouped:
                selected_station = st.selectbox(
                    "选择站位",
                    list(station_grouped.keys()),
                    help="同一站位内的柱样可直接对比统计"
                )
                selected_station_name = selected_station
                selected_cores = station_grouped[selected_station]

                if len(selected_cores) < 2:
                    st.warning("该站位下柱样数量不足2个，无法对比")
                else:
                    st.success(f"✅ 已选择站位「{selected_station}」的 {len(selected_cores)} 个柱样进行对比")
            else:
                st.info("暂无站位数据")
        else:
            selected_cores = st.multiselect(
                "选择要对比的柱样（至少2个，仅限同一站位）",
                cores_df["sample_code"].tolist(),
                help="必须选择同一站位的柱样进行对比，不同站位的数据禁止混合统计"
            )
            if len(selected_cores) < 2:
                st.warning("请至少选择2个柱样进行对比")
            else:
                stations_in_selection = cores_df[cores_df["sample_code"].isin(selected_cores)]["station_code"].unique()
                if len(stations_in_selection) > 1:
                    st.error(
                        f"❌ 禁止跨站位混合统计！您选择了 {len(stations_in_selection)} 个不同站位的柱样："
                        f"{', '.join(stations_in_selection)}。\n\n"
                        f"根据海洋地质数据规范，不同站位的沉积环境、采样条件可能存在显著差异，"
                        f"数据不可直接混合统计。请选择同一站位的柱样进行对比。"
                    )
                    selected_cores = []
                else:
                    selected_station_name = stations_in_selection[0]
                    st.success(f"✅ 已选择 {len(selected_cores)} 个柱样（同属站位 {stations_in_selection[0]}）")

        if len(selected_cores) >= 2:
            core_id_map = dict(zip(cores_df["sample_code"], cores_df["id"]))
            core_ids = [core_id_map[code] for code in selected_cores]

            comparison = analyzer.compare_cores(core_ids)
            interlayer_corr = analyzer.analyze_interlayer_correlation(core_ids)

            col_export, _ = st.columns([1, 3])
            with col_export:
                if st.button("📥 导出对比报告", type="primary", use_container_width=True):
                    report = {
                        "报告标题": f"多柱样对比分析报告",
                        "生成时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "对比柱样": ", ".join(selected_cores),
                        "柱样数量": len(selected_cores),
                    }

                    if selected_station_name:
                        report["站位"] = selected_station_name
                        station_report = analyzer.generate_station_report(selected_station_name)
                        report["统计详情"] = str(station_report.get("core_statistics", []))

                    report_df = pd.DataFrame([report])

                    csv_buffer = StringIO()
                    report_df.to_csv(csv_buffer, index=False, encoding="utf-8-sig")
                    csv_str = csv_buffer.getvalue()

                    combined_layers = comparison["combined_layers"]
                    combined_csv = combined_layers.to_csv(index=False, encoding="utf-8-sig")

                    export_filename = f"多柱样对比_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    st.session_state.export_data = {
                        "report_csv": csv_str,
                        "layers_csv": combined_csv,
                        "filename": export_filename
                    }

                    db.add_export_record(
                        export_type="comparison_report",
                        scope="station" if selected_station_name else "selected",
                        filters={
                            "station": selected_station_name,
                            "cores": selected_cores
                        },
                        record_count=len(combined_layers),
                        file_name=f"{export_filename}.zip",
                        export_format="csv"
                    )

                    st.success("✅ 报告已生成，可在下方下载，导出记录已保存")

            if "export_data" in st.session_state:
                col_dl1, col_dl2 = st.columns(2)
                with col_dl1:
                    st.download_button(
                        label="📄 下载报告摘要 (CSV)",
                        data=st.session_state.export_data["report_csv"],
                        file_name=f"{st.session_state.export_data['filename']}_摘要.csv",
                        mime="text/csv"
                    )
                with col_dl2:
                    st.download_button(
                        label="📊 下载层位数据 (CSV)",
                        data=st.session_state.export_data["layers_csv"],
                        file_name=f"{st.session_state.export_data['filename']}_层位数据.csv",
                        mime="text/csv"
                    )

            tab1, tab2, tab3, tab4, tab5 = st.tabs([
                "📊 并排分层对比", "📈 指标对比",
                "🔗 层间相关性", "📋 统计数据对比", "🗂️ 综合报告"
            ])

            with tab1:
                fig_compare = visualizer.plot_multi_core_comparison(
                    comparison["individual_analyses"],
                    title="多柱样分层剖面图对比"
                )
                st.plotly_chart(fig_compare, use_container_width=True)

            with tab2:
                combined = comparison["combined_layers"]
                if not combined.empty:
                    indicator = st.selectbox(
                        "选择对比指标",
                        ["gravel_pct", "sand_pct", "silt_pct", "clay_pct",
                         "organic_matter", "water_content", "thickness"],
                        format_func=lambda x: {
                            "gravel_pct": "砾石 (%)",
                            "sand_pct": "砂 (%)",
                            "silt_pct": "粉砂 (%)",
                            "clay_pct": "黏土 (%)",
                            "organic_matter": "有机质 (%)",
                            "water_content": "含水率 (%)",
                            "thickness": "层厚 (cm)",
                        }.get(x, x),
                        key="compare_indicator_select"
                    )

                    display_name = {
                        "gravel_pct": "砾石 (%)",
                        "sand_pct": "砂 (%)",
                        "silt_pct": "粉砂 (%)",
                        "clay_pct": "黏土 (%)",
                        "organic_matter": "有机质 (%)",
                        "water_content": "含水率 (%)",
                        "thickness": "层厚 (cm)",
                    }.get(indicator, indicator)

                    st.subheader(f"各柱样{display_name}箱线图对比")

                    fig_box = px.box(
                        combined,
                        x="sample_code",
                        y=indicator,
                        color="sample_code",
                        title=f"各柱样{display_name}分布对比",
                        labels={"sample_code": "柱样编号", indicator: display_name}
                    )
                    st.plotly_chart(fig_box, use_container_width=True)

                    st.subheader(f"各柱样{display_name}随深度变化")
                    fig = go.Figure()
                    colors = px.colors.qualitative.Plotly

                    for idx, core_code in enumerate(selected_cores):
                        core_data = comparison["individual_analyses"][core_code]
                        core_layers = core_data["layers"]
                        if not core_layers.empty and indicator in core_layers.columns:
                            valid = core_layers.dropna(subset=[indicator])
                            if not valid.empty:
                                fig.add_trace(go.Scatter(
                                    x=valid[indicator],
                                    y=-(valid["depth_start"] + valid["depth_end"]) / 2,
                                    mode="lines+markers",
                                    name=core_code,
                                    line=dict(color=colors[idx % len(colors)], width=2),
                                    marker=dict(size=6),
                                ))

                    fig.update_layout(
                        xaxis_title=display_name,
                        yaxis_title="深度 (cm)",
                        height=600,
                        legend_title="柱样编号",
                    )
                    st.plotly_chart(fig, use_container_width=True)

            with tab3:
                st.subheader("多柱样交叉相关性")

                cross_corr = comparison.get("cross_correlation", {})
                if cross_corr:
                    fig_cross = visualizer.plot_cross_correlation_heatmap(
                        cross_corr,
                        title="各指标多柱样交叉相关系数"
                    )
                    st.plotly_chart(fig_cross, use_container_width=True)

                    st.info("💡 解读：相关系数越接近1，表示两个柱样在该指标上的深度变化趋势越相似")
                else:
                    st.info("数据不足，无法计算交叉相关性")

                st.divider()
                st.subheader("层间相关性分析")

                if interlayer_corr.get("layer_correlations"):
                    st.write(f"共 {interlayer_corr['total_layer_types']} 种层位类型，"
                             f"可分析 {interlayer_corr['analyzed_layer_types']} 种")

                    layer_names = list(interlayer_corr["layer_correlations"].keys())
                    if layer_names:
                        selected_layer_type = st.selectbox(
                            "选择层位类型查看相关性",
                            layer_names
                        )
                        layer_corr = interlayer_corr["layer_correlations"][selected_layer_type]

                        st.caption(f"涉及 {layer_corr['core_count']} 个柱样，共 {layer_corr['sample_count']} 个样本")

                        if not layer_corr["correlation"].empty:
                            fig_layer_corr = visualizer.plot_correlation_heatmap(
                                layer_corr["correlation"],
                                title=f"{selected_layer_type} - 指标相关性矩阵"
                            )
                            st.plotly_chart(fig_layer_corr, use_container_width=True)
                else:
                    st.info("数据不足，无法进行层间相关性分析")

            with tab4:
                st.subheader("各柱样关键指标对比")

                stats_rows = []
                for core_code, core_data in comparison["individual_analyses"].items():
                    layers = core_data["layers"]
                    if layers.empty:
                        continue
                    row = {
                        "柱样编号": core_code,
                        "层数": len(layers),
                        "总厚度(cm)": f"{core_data.get('total_sampled_thickness', 0):.1f}",
                        "取芯率(%)": f"{core_data.get('recovery_rate', 0):.1f}",
                        "平均砂(%)": f"{layers['sand_pct'].mean():.1f}",
                        "平均粉砂(%)": f"{layers['silt_pct'].mean():.1f}",
                        "平均黏土(%)": f"{layers['clay_pct'].mean():.1f}",
                    }
                    if "organic_matter" in layers.columns and layers["organic_matter"].notna().any():
                        row["平均有机质(%)"] = f"{layers['organic_matter'].mean():.1f}"
                    else:
                        row["平均有机质(%)"] = "N/A"
                    if "water_content" in layers.columns and layers["water_content"].notna().any():
                        row["平均含水率(%)"] = f"{layers['water_content'].mean():.1f}"
                    else:
                        row["平均含水率(%)"] = "N/A"
                    stats_rows.append(row)

                if stats_rows:
                    stats_df = pd.DataFrame(stats_rows)
                    st.dataframe(stats_df, use_container_width=True, hide_index=True)

                    st.subheader("指标雷达图对比")
                    radar_stats = []
                    for core_code, core_data in comparison["individual_analyses"].items():
                        layers = core_data["layers"]
                        if layers.empty:
                            continue
                        radar_stats.append({
                            "sample_code": core_code,
                            "avg_sand": layers["sand_pct"].mean(),
                            "avg_silt": layers["silt_pct"].mean(),
                            "avg_clay": layers["clay_pct"].mean(),
                            "avg_organic": layers["organic_matter"].mean() if "organic_matter" in layers.columns and layers["organic_matter"].notna().any() else 0,
                            "recovery_rate": core_data.get("recovery_rate", 0),
                        })

                    if radar_stats:
                        fig_radar = visualizer.plot_station_comparison_radar(
                            radar_stats,
                            title="多柱样关键指标雷达对比"
                        )
                        st.plotly_chart(fig_radar, use_container_width=True)

                if selected_station_name:
                    st.success(f"✅ 数据来自同一站位「{selected_station_name}」，可直接进行统计对比")
                else:
                    st.warning("⚠️ 注意：不同采样站位的数据不直接合并统计，以上为各柱样独立统计结果的对比展示。")

            with tab5:
                st.subheader("站位综合对比报告")

                if selected_station_name:
                    station_report = analyzer.generate_station_report(selected_station_name)
                    if station_report:
                        st.info(f"📋 {station_report['report_title']}")
                        st.caption(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

                        summary = station_report.get("summary", {})
                        col_sum1, col_sum2, col_sum3 = st.columns(3)
                        with col_sum1:
                            st.metric("柱样数量", station_report.get("core_count", 0))
                        with col_sum2:
                            st.metric("总层数", summary.get("layer_count", 0))
                        with col_sum3:
                            st.metric("总厚度", f"{summary.get('total_thickness', 0):.1f} cm")

                        if station_report.get("core_statistics"):
                            st.subheader("各柱样统计")
                            core_stats_df = pd.DataFrame(station_report["core_statistics"])
                            display_cols = [
                                "sample_code", "layer_count", "total_thickness",
                                "recovery_rate", "anomaly_count",
                                "avg_sand", "avg_silt", "avg_clay"
                            ]
                            display_cols = [c for c in display_cols if c in core_stats_df.columns]
                            st.dataframe(core_stats_df[display_cols],
                                         use_container_width=True, hide_index=True)

                        if station_report.get("layer_type_statistics"):
                            st.subheader("各层位类型统计")
                            layer_stats = station_report["layer_type_statistics"]
                            layer_stats_df = pd.DataFrame.from_dict(layer_stats, orient="index")
                            layer_stats_df.index.name = "层位名称"
                            st.dataframe(layer_stats_df.round(2), use_container_width=True)
                else:
                    st.info("💡 选择同一站位的柱样可生成站位综合对比报告")
                    st.write("站位综合报告包含：")
                    st.write("- 站位整体统计数据")
                    st.write("- 各柱样指标对比")
                    st.write("- 各层位类型统计")
                    st.write("- 异常数据汇总")


elif page == "🎯 质量控制工作台":
    st.header("质量控制工作台")

    dashboard = qc.get_quality_dashboard_data()
    overall = dashboard["overall"]

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("采样站位数", overall["total_stations"])
    with col2:
        st.metric("沉积柱样数", overall["total_cores"])
    with col3:
        st.metric("待复核异常", overall["pending_anomalies"],
                  delta=f"共{overall['total_anomalies']}个")
    with col4:
        st.metric("已处理异常", overall["resolved_anomalies"])

    qc_tab1, qc_tab2, qc_tab3 = st.tabs([
        "📋 异常复核列表", "🔍 异常扫描", "📊 质量统计"
    ])

    with qc_tab1:
        st.subheader("异常复核列表")

        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            stations = ["全部"] + [s["station_code"] for s in dashboard["stations"]]
            qc_station = st.selectbox("筛选站位", stations, key="qc_station_filter")
        with col_f2:
            status_options = ["全部", "pending", "reviewing", "confirmed", "dismissed", "resolved"]
            status_labels = {
                "pending": "待复核", "reviewing": "复核中",
                "confirmed": "已确认", "dismissed": "已驳回",
                "resolved": "已修复"
            }
            qc_status = st.selectbox(
                "筛选状态", status_options,
                format_func=lambda x: status_labels.get(x, x),
                key="qc_status_filter"
            )
        with col_f3:
            type_options = ["全部", "value_outlier", "depth_overlap", "duplicate_layer", "missing_interval", "percentage_error", "other"]
            type_labels = {
                "value_outlier": "数值异常",
                "depth_overlap": "深度重叠",
                "duplicate_layer": "重复层位",
                "missing_interval": "缺失层段",
                "percentage_error": "百分比错误",
                "other": "其他异常",
            }
            qc_type = st.selectbox(
                "筛选异常类型", type_options,
                format_func=lambda x: type_labels.get(x, x),
                key="qc_type_filter"
            )

        filter_status = None if qc_status == "全部" else qc_status
        filter_station = None if qc_station == "全部" else qc_station
        filter_type = None if qc_type == "全部" else qc_type

        anomalies_df = qc.get_anomaly_list(
            station_code=filter_station,
            status=filter_status
        )

        if filter_type and not anomalies_df.empty:
            anomalies_df = anomalies_df[anomalies_df["anomaly_type"] == filter_type]

        if anomalies_df.empty:
            st.info("暂无异常记录")
        else:
            st.write(f"共 {len(anomalies_df)} 条异常记录")

            review_columns = [
                "id", "station_code", "sample_code", "layer_name",
                "depth_start", "depth_end", "anomaly_type",
                "status", "created_at"
            ]
            review_columns = [c for c in review_columns if c in anomalies_df.columns]
            display_df = anomalies_df[review_columns].copy()
            display_df.columns = [
                "ID", "站位", "柱样", "层位",
                "深度起点", "深度终点", "异常类型",
                "状态", "提交时间"
            ]
            st.dataframe(display_df, use_container_width=True, hide_index=True)

            st.divider()
            st.subheader("处理选中的异常")

            if len(anomalies_df) > 0:
                review_ids = anomalies_df["id"].tolist()
                review_id_labels = [
                    f"#{row['id']} - {row['station_code']}/{row['sample_code']} - {row['layer_name']}"
                    for _, row in anomalies_df.iterrows()
                ]

                selected_review = st.selectbox(
                    "选择异常记录进行处理",
                    review_ids,
                    format_func=lambda x: dict(zip(review_ids, review_id_labels)).get(x, x)
                )

                sel_row = anomalies_df[anomalies_df["id"] == selected_review].iloc[0]

                st.info(f"""
                **详情:**
                - 柱样: {sel_row['sample_code']}
                - 层位: {sel_row['layer_name']}
                - 深度: {sel_row['depth_start']} - {sel_row['depth_end']} cm
                - 类型: {sel_row['anomaly_type']}
                - 详情: {sel_row.get('anomaly_details', '无')}
                """)

                new_status = st.selectbox(
                    "更新状态",
                    ["pending", "reviewing", "confirmed", "dismissed", "resolved"],
                    format_func=lambda x: status_labels.get(x, x)
                )

                reviewer_name = st.text_input("复核人姓名", value="地质员")
                review_notes = st.text_area("复核意见", placeholder="请填写复核意见...")

                if st.button("提交复核结果", type="primary"):
                    qc.review_anomaly(
                        selected_review, new_status,
                        review_notes, reviewer_name
                    )
                    st.success("✅ 复核结果已保存")
                    st.rerun()

    with qc_tab2:
        st.subheader("异常扫描")
        st.info("对指定柱样进行全面质量检查，自动检测各类异常")

        filters = st.session_state.filters
        scan_cores = analyzer.filter_cores(filters)

        if scan_cores.empty:
            st.info("暂无符合条件的柱样数据")
        else:
            col_scan1, col_scan2 = st.columns([2, 1])
            with col_scan1:
                scan_core_options = dict(zip(scan_cores["sample_code"], scan_cores["id"]))
                scan_core = st.selectbox(
                    "选择要扫描的柱样",
                    list(scan_core_options.keys()),
                    key="scan_core_select"
                )
                scan_core_id = scan_core_options[scan_core]

            if st.button("🔍 开始扫描", type="primary"):
                with st.spinner("正在扫描..."):
                    scan_result = qc.scan_core_anomalies(scan_core_id)

                    col_r1, col_r2, col_r3 = st.columns(3)
                    with col_r1:
                        st.metric("异常总数", scan_result["total_anomalies"])
                    with col_r2:
                        by_type = scan_result.get("by_type", {})
                        st.metric("数值异常", by_type.get("value_outlier", 0))
                    with col_r3:
                        st.metric("质量问题", by_type.get("depth_overlap", 0) + by_type.get("duplicate_layer", 0))

                    if scan_result["anomalies"]:
                        st.warning("⚠️ 检测到以下异常")
                        scan_df = pd.DataFrame(scan_result["anomalies"])
                        display_scan = scan_df[[
                            "layer_name", "depth_start", "depth_end",
                            "anomaly_type", "anomaly_details", "severity"
                        ]].copy()
                        display_scan.columns = [
                            "层位名称", "深度起点", "深度终点",
                            "异常类型", "异常详情", "严重程度"
                        ]
                        st.dataframe(display_scan, use_container_width=True, hide_index=True)

                        if st.button("批量提交复核", key="batch_scan_review"):
                            for anomaly in scan_result["anomalies"]:
                                if anomaly.get("layer_id"):
                                    qc.submit_anomaly_review(
                                        int(anomaly["layer_id"]),
                                        scan_core_id,
                                        anomaly["anomaly_type"],
                                        anomaly["anomaly_details"]
                                    )
                            st.success("✅ 已批量提交复核")
                            st.rerun()
                    else:
                        st.success("✅ 未检测到异常，数据质量良好")

    with qc_tab3:
        st.subheader("质量统计")

        if dashboard["stations"]:
            station_quality_df = pd.DataFrame(dashboard["stations"])
            station_quality_df.columns = [
                "站位编号", "站名", "柱样数", "总层数",
                "异常数", "待复核数", "已确认数"
            ]
            st.dataframe(station_quality_df, use_container_width=True, hide_index=True)

        all_reviews = db.get_anomaly_reviews()
        if not all_reviews.empty:
            fig_status = visualizer.plot_anomaly_status_pie(
                all_reviews, "异常复核状态分布"
            )
            st.plotly_chart(fig_status, use_container_width=True)

            st.subheader("按类型统计")
            type_counts = all_reviews["anomaly_type"].value_counts()
            fig_type = px.bar(
                x=type_counts.index,
                y=type_counts.values,
                title="各类型异常数量",
                labels={"x": "异常类型", "y": "数量"}
            )
            st.plotly_chart(fig_type, use_container_width=True)


elif page == "⚙️ 数据管理与版本":
    st.header("数据管理与版本")

    filters = st.session_state.filters
    cores_df = analyzer.filter_cores(filters)

    if cores_df.empty:
        st.info("暂无沉积柱样数据。")
    else:
        management_tab = st.tabs(["编辑层位", "版本历史", "删除数据"])

        with management_tab[0]:
            st.subheader("编辑层位记录")
            core_options = dict(zip(cores_df["sample_code"], cores_df["id"]))
            edit_core = st.selectbox(
                "选择柱样",
                list(core_options.keys()),
                key="edit_core_select"
            )
            edit_core_id = core_options[edit_core]

            core_info = db.get_core_sample(edit_core_id)
            if core_info:
                st.caption(f"当前版本: v{core_info.get('version', 1)}")

            layers_df = db.get_core_layers(edit_core_id)
            if layers_df.empty:
                st.info("该柱样暂无层位数据")
            else:
                layer_options = dict(zip(
                    layers_df.apply(lambda r: f"{r['layer_name']} ({r['depth_start']}-{r['depth_end']}cm)", axis=1),
                    layers_df["id"]
                ))
                selected_layer = st.selectbox(
                    "选择要编辑的层位",
                    list(layer_options.keys()),
                    key="layer_select"
                )
                layer_id = layer_options[selected_layer]

                layer_data = layers_df[layers_df["id"] == layer_id].iloc[0]

                col1, col2 = st.columns(2)
                with col1:
                    layer_name = st.text_input("层位名称", value=layer_data["layer_name"])
                    depth_start = st.number_input("深度起点 (cm)", value=float(layer_data["depth_start"]), min_value=0.0)
                    depth_end = st.number_input("深度终点 (cm)", value=float(layer_data["depth_end"]), min_value=0.0)

                with col2:
                    gravel_pct = st.number_input("砾石 (%)", value=float(layer_data["gravel_pct"] or 0), min_value=0.0, max_value=100.0)
                    sand_pct = st.number_input("砂 (%)", value=float(layer_data["sand_pct"] or 0), min_value=0.0, max_value=100.0)
                    silt_pct = st.number_input("粉砂 (%)", value=float(layer_data["silt_pct"] or 0), min_value=0.0, max_value=100.0)
                    clay_pct = st.number_input("黏土 (%)", value=float(layer_data["clay_pct"] or 0), min_value=0.0, max_value=100.0)

                organic_matter = st.number_input(
                    "有机质 (%)",
                    value=float(layer_data["organic_matter"]) if pd.notna(layer_data["organic_matter"]) else 0.0,
                    min_value=0.0
                )
                water_content = st.number_input(
                    "含水率 (%)",
                    value=float(layer_data["water_content"]) if pd.notna(layer_data["water_content"]) else 0.0,
                    min_value=0.0
                )
                notes = st.text_area("备注", value=layer_data["notes"] or "")

                col_r1, col_r2 = st.columns([2, 1])
                with col_r1:
                    change_reason = st.text_input(
                        "修改原因",
                        placeholder="请简要说明修改原因（将记录到版本历史）"
                    )
                with col_r2:
                    changed_by = st.text_input("修改人", value="地质员")

                if st.button("保存修改", key="save_layer_edit", type="primary"):
                    depth_ok, depth_err = validator.validate_layer_edit(
                        edit_core_id, layer_id, depth_start, depth_end
                    )
                    pct_ok, pct_err = validator.validate_percentages(
                        gravel_pct, sand_pct, silt_pct, clay_pct
                    )

                    if not depth_ok:
                        st.error(f"❌ {depth_err}")
                    elif not pct_ok:
                        st.error(f"❌ {pct_err}")
                    elif organic_matter < 0:
                        st.error("❌ 有机质含量不能为负数")
                    elif water_content < 0:
                        st.error("❌ 含水率不能为负数")
                    elif not change_reason.strip():
                        st.warning("⚠️ 请填写修改原因，以便版本追踪")
                    else:
                        updated_data = {
                            "layer_name": layer_name,
                            "depth_start": depth_start,
                            "depth_end": depth_end,
                            "gravel_pct": gravel_pct,
                            "sand_pct": sand_pct,
                            "silt_pct": silt_pct,
                            "clay_pct": clay_pct,
                            "organic_matter": organic_matter if organic_matter > 0 else None,
                            "water_content": water_content if water_content > 0 else None,
                            "notes": notes,
                        }
                        db.update_layer_with_version(
                            layer_id, updated_data,
                            change_reason=change_reason,
                            changed_by=changed_by
                        )
                        st.success("✅ 修改已保存，版本已更新")
                        st.rerun()

        with management_tab[1]:
            st.subheader("版本历史追踪")

            version_history = qc.get_core_version_history(edit_core_id)

            col_vh1, col_vh2, col_vh3 = st.columns(3)
            with col_vh1:
                st.metric("当前版本", f"v{version_history['current_version']}")
            with col_vh2:
                st.metric("总修改次数", version_history["total_changes"])
            with col_vh3:
                st.metric("涉及层位数", version_history["modified_layers"])

            if version_history["version_summary"]:
                st.subheader("各层位修改统计")
                ver_summary_df = pd.DataFrame(version_history["version_summary"])
                ver_summary_df.columns = ["层位ID", "层位名称", "修改次数", "最后修改时间"]
                st.dataframe(ver_summary_df, use_container_width=True, hide_index=True)

            if not version_history["versions"].empty:
                st.subheader("详细修改记录")
                ver_display = version_history["versions"][[
                    "version", "current_layer_name", "depth_start", "depth_end",
                    "change_reason", "changed_by", "created_at"
                ]].copy()
                ver_display.columns = [
                    "版本号", "层位名称", "深度起点", "深度终点",
                    "修改原因", "修改人", "修改时间"
                ]
                st.dataframe(ver_display, use_container_width=True, hide_index=True)
            else:
                st.info("暂无历史修改记录，首次编辑层位后将生成版本记录")

        with management_tab[2]:
            st.subheader("删除数据")
            st.warning("⚠️ 删除操作不可恢复，请谨慎操作！")

            core_options = dict(zip(cores_df["sample_code"], cores_df["id"]))
            del_core = st.selectbox(
                "选择要删除的柱样",
                list(core_options.keys()),
                key="del_core_select"
            )

            if st.button("删除该柱样及其所有层位数据", type="primary"):
                db.delete_core_sample(core_options[del_core])
                st.success(f"✅ 已删除柱样 {del_core}")
                st.rerun()

    st.divider()
    st.subheader("📥 数据导出")

    col_exp1, col_exp2 = st.columns(2)
    with col_exp1:
        export_type = st.selectbox(
            "导出类型",
            ["层位数据", "质量报告", "对比报告"],
            key="export_type_select"
        )
    with col_exp2:
        export_scope = st.selectbox(
            "导出范围",
            ["全部数据", "当前筛选结果", "指定站位"],
            key="export_scope_select"
        )

    if export_scope == "指定站位":
        all_stations_list = db.get_all_stations()
        if not all_stations_list.empty:
            export_station = st.selectbox(
                "选择站位",
                all_stations_list["station_code"].tolist(),
                key="export_station_select"
            )
        else:
            st.info("暂无站位数据")

    if st.button("📤 生成导出文件", type="primary"):
        if export_type == "层位数据":
            if export_scope == "全部数据":
                export_cores = db.get_all_core_samples()
            elif export_scope == "当前筛选结果":
                export_cores = analyzer.filter_cores(st.session_state.filters)
            else:
                export_cores = db.get_cores_by_station(export_station)

            all_layers = []
            for _, core in export_cores.iterrows():
                layers = db.get_core_layers(core["id"])
                if not layers.empty:
                    layers["station_code"] = core["station_code"]
                    layers["sample_code"] = core["sample_code"]
                    all_layers.append(layers)

            if all_layers:
                export_df = pd.concat(all_layers, ignore_index=True)
                csv_data = export_df.to_csv(index=False, encoding="utf-8-sig")

                db.add_export_record(
                    export_type="layers",
                    scope=export_scope,
                    filters={"station": export_station} if export_scope == "指定站位" else {},
                    record_count=len(export_df),
                    file_name=f"层位数据_{datetime.now().strftime('%Y%m%d')}.csv",
                    export_format="csv"
                )

                st.session_state.export_file = {
                    "data": csv_data,
                    "filename": f"层位数据_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    "type": "csv"
                }
                st.success(f"✅ 已生成导出文件，共 {len(export_df)} 条记录")
            else:
                st.warning("⚠️ 没有可导出的数据")

        elif export_type == "质量报告":
            station_filter = None
            if export_scope == "指定站位":
                station_filter = export_station

            report_data = qc.export_quality_report(station_code=station_filter)

            report_text = f"""
{report_data['report_title']}
生成时间: {report_data['generated_at']}

=== 概览 ===
站位数: {report_data['overview']['total_stations']}
柱样数: {report_data['overview']['total_cores']}
总层数: {report_data['overview']['total_layers']}
异常总数: {report_data['overview']['total_anomalies']}
待复核: {report_data['overview']['pending_anomalies']}
已处理: {report_data['overview']['resolved_anomalies']}
"""

            if report_data["station_details"]:
                report_text += "\n=== 各站详情 ===\n"
                for s in report_data["station_details"]:
                    report_text += f"\n{s['station_code']}:"
                    report_text += f" 柱样{s['core_count']}个"
                    report_text += f" 层位{s['total_layers']}个"
                    report_text += f" 异常{s['anomaly_count']}个\n"

            db.add_export_record(
                export_type="quality_report",
                scope=export_scope,
                filters={},
                record_count=len(report_data.get("anomalies", pd.DataFrame())),
                file_name=f"质量报告_{datetime.now().strftime('%Y%m%d')}.txt",
                export_format="txt"
            )

            st.session_state.export_file = {
                "data": report_text,
                "filename": f"质量报告_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                "type": "txt"
            }
            st.success("✅ 报告已生成")

    if "export_file" in st.session_state and st.session_state.export_file:
        st.download_button(
            label="⬇️ 下载导出文件",
            data=st.session_state.export_file["data"],
            file_name=st.session_state.export_file["filename"],
            mime="text/plain" if st.session_state.export_file["type"] == "txt" else "text/csv",
            use_container_width=True
        )

    st.subheader("导出历史")
    export_history = db.get_export_records(10)
    if export_history.empty:
        st.info("暂无导出记录")
    else:
        exp_display = export_history[[
            "export_type", "scope", "record_count", "file_name", "created_at"
        ]].copy()

        type_mapping = {
            "layers": "层位数据",
            "quality_report": "质量报告",
            "comparison_report": "对比报告",
        }

        exp_display["export_type"] = exp_display["export_type"].map(
            lambda x: type_mapping.get(x, x)
        )

        exp_display.columns = ["导出类型", "范围", "记录数", "文件名", "时间"]
        st.dataframe(exp_display, use_container_width=True, hide_index=True)
