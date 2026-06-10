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
import alignment_engine as align
import chronology_engine as chrono


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
            "🔗 层位对齐与区域演化",
            "🎯 质量控制工作台",
            "⏳ 年代约束与沉积速率",
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


elif page == "🔗 层位对齐与区域演化":
    st.header("层位对齐与区域沉积演化解释")

    filters = st.session_state.filters
    cores_df = analyzer.filter_cores(filters)

    if cores_df.empty:
        st.info("暂无符合筛选条件的沉积柱样数据，请先导入CSV文件或调整筛选条件。")
    else:
        col_select_mode, col_station = st.columns([1, 2])
        with col_select_mode:
            alignment_mode = st.radio(
                "选择柱样方式",
                ["跨站位选择", "按站位选择"],
                horizontal=True,
                help="层位对齐支持跨站位对比，不同站位柱样可通过归一化深度进行对齐"
            )

        selected_alignment_cores = []
        if alignment_mode == "按站位选择":
            station_grouped = cores_df.groupby("station_code")["sample_code"].apply(list).to_dict()
            if station_grouped:
                sel_station = st.selectbox(
                    "选择站位",
                    list(station_grouped.keys()),
                    key="align_station_select"
                )
                selected_alignment_cores = station_grouped[sel_station]
                if len(selected_alignment_cores) < 2:
                    st.warning("该站位下柱样数量不足2个")
            else:
                st.info("暂无站位数据")
        else:
            selected_alignment_cores = st.multiselect(
                "选择要对齐的柱样（至少2个）",
                cores_df["sample_code"].tolist(),
                key="align_core_multiselect"
            )
            if len(selected_alignment_cores) < 2:
                st.warning("请至少选择2个柱样进行对齐分析")

        if len(selected_alignment_cores) >= 2:
            core_id_map = dict(zip(cores_df["sample_code"], cores_df["id"]))
            selected_core_ids = [core_id_map[code] for code in selected_alignment_cores if code in core_id_map]

            if len(selected_core_ids) >= 2:
                st.success(f"✅ 已选择 {len(selected_alignment_cores)} 个柱样进行层位对齐分析")

                col_method, col_threshold, col_depth_tol = st.columns(3)
                with col_method:
                    align_method = st.selectbox(
                        "对齐方法",
                        ["combined", "lithology", "depth", "dtw"],
                        format_func=lambda x: {
                            "combined": "综合对齐（岩性+深度）",
                            "lithology": "岩性相似性对齐",
                            "depth": "深度归一化对齐",
                            "dtw": "DTW动态时间规整对齐",
                        }.get(x, x),
                        key="align_method_select"
                    )
                with col_threshold:
                    sim_threshold = st.slider(
                        "相似度阈值",
                        min_value=0.3, max_value=0.95, value=0.6, step=0.05,
                        help="低于此阈值的层位对不会被视为对齐",
                        key="align_threshold"
                    )
                with col_depth_tol:
                    depth_tolerance = st.slider(
                        "深度容差 (cm)",
                        min_value=1, max_value=50, value=10, step=5,
                        help="归一化深度差在此范围内的层位优先匹配",
                        key="align_depth_tol"
                    )

                with st.expander("⚙️ 高级参数设置"):
                    st.subheader("指标权重配置")
                    st.caption("调整不同指标在相似度计算中的权重，权重越大该指标影响越大")

                    indicator_weight_config = {}
                    weight_cols = st.columns(3)
                    indicator_display = {
                        "gravel_pct": "砾石含量",
                        "sand_pct": "砂含量",
                        "silt_pct": "粉砂含量",
                        "clay_pct": "黏土含量",
                        "organic_matter": "有机质含量",
                        "water_content": "含水率",
                    }
                    default_weights = align.DEFAULT_INDICATOR_WEIGHTS
                    for idx, (ind_key, ind_name) in enumerate(indicator_display.items()):
                        with weight_cols[idx % 3]:
                            indicator_weight_config[ind_key] = st.slider(
                                ind_name, min_value=0.0, max_value=3.0,
                                value=default_weights.get(ind_key, 1.0), step=0.1,
                                key=f"weight_{ind_key}"
                            )

                    enforce_strat_order = st.checkbox(
                        "启用层序约束",
                        value=True,
                        help="约束对齐结果必须符合地层层序规律，位置差异大的层位将被惩罚",
                        key="enforce_strat_order"
                    )

                if st.button("🔄 执行层位对齐分析", type="primary", use_container_width=True):
                    with st.spinner("正在进行层位对齐分析..."):
                        alignment_result = align.align_horizons(
                            selected_core_ids,
                            method=align_method,
                            similarity_threshold=sim_threshold,
                            depth_tolerance=depth_tolerance,
                            indicator_weights=indicator_weight_config if any(
                                v != default_weights.get(k, 1.0) for k, v in indicator_weight_config.items()
                            ) else None,
                            enforce_stratigraphic_order=enforce_strat_order,
                        )
                        continuity_result = align.analyze_sequence_continuity(selected_core_ids)
                        surface_result = align.track_key_surfaces(selected_core_ids, depth_tolerance=depth_tolerance)
                        evolution_result = align.regional_evolution_analysis(selected_core_ids)

                        st.session_state.alignment_result = alignment_result
                        st.session_state.continuity_result = continuity_result
                        st.session_state.surface_result = surface_result
                        st.session_state.evolution_result = evolution_result
                        st.session_state.alignment_core_ids = selected_core_ids

                        session_name = f"对齐_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                        alignment_id = db.save_alignment_result(
                            session_name=session_name,
                            core_ids=selected_core_ids,
                            method=align_method,
                            threshold=sim_threshold,
                            alignment_data=json.dumps({
                                "aligned_groups": alignment_result.get("aligned_groups", []),
                                "unaligned_layers": alignment_result.get("unaligned_layers", []),
                                "quality": alignment_result.get("quality", {}),
                            }, default=str),
                            continuity_data=json.dumps({
                                "continuity_score": continuity_result.get("continuity_score", 0),
                                "total_layer_types": continuity_result.get("total_layer_types", 0),
                            }, default=str),
                            surface_data=json.dumps({
                                "surface_type_summary": surface_result.get("surface_type_summary", {}),
                            }, default=str),
                            evolution_data=json.dumps({
                                "zones": evolution_result.get("zones", []),
                                "summary": evolution_result.get("summary", {}),
                            }, default=str),
                        )
                        st.session_state.current_alignment_id = alignment_id
                        st.success(f"✅ 层位对齐分析完成！对齐会话ID: {alignment_id}")

                # 检测参数或柱样选择是否变化，如果变化则清除旧结果
                should_clear_results = False
                if "alignment_core_ids" in st.session_state:
                    if set(st.session_state.alignment_core_ids) != set(selected_core_ids):
                        should_clear_results = True

                # 检测参数变化
                last_params = st.session_state.get("last_alignment_params")
                current_params = {
                    "method": align_method,
                    "threshold": sim_threshold,
                    "depth_tolerance": depth_tolerance,
                    "weights": indicator_weight_config,
                    "strat_order": enforce_strat_order,
                }
                if last_params and last_params != current_params:
                    should_clear_results = True
                st.session_state.last_alignment_params = current_params

                if "align_export_data" in st.session_state:
                    del st.session_state.align_export_data

                if should_clear_results:
                    for key in ["alignment_result", "continuity_result", "surface_result",
                                "evolution_result", "alignment_core_ids", "current_alignment_id",
                                "similar_result"]:
                        if key in st.session_state:
                            del st.session_state[key]
                    st.warning("⚠️ 检测到柱样选择或参数已变化，旧对齐结果已清除，请重新执行分析")

                if "alignment_result" in st.session_state:
                    a_result = st.session_state.alignment_result
                    c_result = st.session_state.get("continuity_result", {})
                    s_result = st.session_state.get("surface_result", {})
                    e_result = st.session_state.get("evolution_result", {})

                    col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns(5)
                    with col_m1:
                        st.metric("对齐组数", len(a_result.get("aligned_groups", [])))
                    with col_m2:
                        st.metric("延续性评分", f"{c_result.get('continuity_score', 0):.3f}")
                    with col_m3:
                        st.metric("关键界面", len(s_result.get("key_surfaces", [])))
                    with col_m4:
                        st.metric("沉积分区", len(e_result.get("zones", [])))
                    with col_m5:
                        quality = a_result.get("quality", {})
                        if quality:
                            grade_color = "🟢" if "A" in quality.get("grade", "") else "🟡" if "B" in quality.get("grade", "") else "🔴"
                            st.metric("对齐质量", f"{grade_color} {quality.get('grade', 'N/A')}",
                                      delta=f"评分 {quality.get('overall_score', 0):.3f}")
                        else:
                            st.metric("对齐质量", "N/A")

                    if quality and quality.get("overall_score", 0) < 0.4:
                        st.warning("⚠️ 对齐质量较低，建议调整相似度阈值、对齐方法或指标权重后重新分析")

                    align_tab1, align_tab2, align_tab3, align_tab4, align_tab5, align_tab6, align_tab7, align_tab8, align_tab9 = st.tabs([
                        "🗺️ 层序对比横断面", "🔗 层位对齐图", "📊 对齐质量评估",
                        "📋 对齐结果详情", "📊 相似层段识别",
                        "📏 层序延续性", "🌊 关键界面追踪", "🗺️ 区域演化分区",
                        "✏️ 人工校正与备注"
                    ])

                    with align_tab1:
                        st.subheader("多柱样层序对比横断面图")
                        st.caption("综合展示柱样分层、层位对齐关系与关键界面追踪，是地质对比的核心图件")

                        fig_cross = visualizer.plot_cross_section_correlation(
                            a_result, surface_result=s_result,
                            title="层序对比横断面图"
                        )
                        st.plotly_chart(fig_cross, use_container_width=True)

                        st.info("💡 横断面图综合展示了柱样分层剖面、对齐层位连接线和关键界面标记，"
                                "虚线连接表示对齐的层位，三角形标记表示关键界面位置")

                    with align_tab2:
                        st.subheader("多柱样层位对齐图")
                        fig_align = visualizer.plot_alignment_diagram(
                            a_result, title="层位自动对齐结果"
                        )
                        st.plotly_chart(fig_align, use_container_width=True)

                        if a_result.get("unaligned_layers"):
                            with st.expander(f"未对齐层位 ({len(a_result['unaligned_layers'])} 个)"):
                                unaligned_df = pd.DataFrame(a_result["unaligned_layers"])
                                st.dataframe(unaligned_df, use_container_width=True, hide_index=True)

                    with align_tab4:
                        st.subheader("对齐结果详情")
                        aligned_groups = a_result.get("aligned_groups", [])

                        if aligned_groups:
                            group_rows = []
                            for group in aligned_groups:
                                for member in group["members"]:
                                    group_rows.append({
                                        "对齐组ID": group["group_id"],
                                        "代表名称": group["representative_name"],
                                        "柱样编号": member["sample_code"],
                                        "层位名称": member["layer_name"],
                                        "深度(cm)": round(member["depth"], 1),
                                        "归一化深度": round(member["norm_depth"], 4),
                                        "相似度": round(group["avg_similarity"], 4),
                                        "涉及站位数": group["station_count"],
                                    })
                            group_df = pd.DataFrame(group_rows)
                            st.dataframe(group_df, use_container_width=True, hide_index=True)
                        else:
                            st.info("未识别到对齐层位，请调整相似度阈值或对齐方法后重试")

                        all_alignments = a_result.get("alignments", [])
                        if all_alignments:
                            with st.expander(f"原始对齐对 ({len(all_alignments)} 对)"):
                                align_pair_df = pd.DataFrame(all_alignments)
                                display_cols = [c for c in [
                                    "core_a", "core_b", "layer_name_a", "layer_name_b",
                                    "depth_a", "depth_b", "similarity", "combined_score", "layer_name_match"
                                ] if c in align_pair_df.columns]
                                align_display = align_pair_df[display_cols].copy()
                                align_display.columns = [
                                    "柱样A", "柱样B", "层位A", "层位B",
                                    "深度A", "深度B", "相似度", "综合评分", "同名匹配"
                                ]
                                st.dataframe(align_display.round(4), use_container_width=True, hide_index=True)

                    with align_tab5:
                        st.subheader("相似层段识别")

                        col_w1, col_t1 = st.columns(2)
                        with col_w1:
                            window_size = st.slider("滑动窗口大小", min_value=2, max_value=6, value=3, step=1,
                                                     key="sim_window_size")
                        with col_t1:
                            seg_threshold = st.slider("相似度阈值", min_value=0.5, max_value=0.95, value=0.7, step=0.05,
                                                       key="sim_seg_threshold")

                        if st.button("🔍 识别相似层段", key="run_similar_segments"):
                            with st.spinner("正在识别相似层段..."):
                                similar_result = align.find_similar_segments(
                                    st.session_state.alignment_core_ids,
                                    window_size=window_size,
                                    similarity_threshold=seg_threshold
                                )
                                st.session_state.similar_result = similar_result

                        if "similar_result" in st.session_state:
                            sim_res = st.session_state.similar_result
                            st.metric("识别到相似层段", sim_res.get("total_similar", 0))

                            fig_sim = visualizer.plot_similar_segments_heatmap(
                                sim_res, title="相似层段识别结果"
                            )
                            st.plotly_chart(fig_sim, use_container_width=True)

                            segment_pairs = sim_res.get("segment_pairs", [])
                            if segment_pairs:
                                for pair in segment_pairs:
                                    with st.expander(f"{pair['core_a']} vs {pair['core_b']} ({pair['segment_count']} 段)"):
                                        seg_rows = []
                                        for seg in pair["segments"]:
                                            seg_rows.append({
                                                "柱样A深度": f"{seg['start_depth_a']:.1f}-{seg['end_depth_a']:.1f}",
                                                "柱样B深度": f"{seg['start_depth_b']:.1f}-{seg['end_depth_b']:.1f}",
                                                "层位A": " → ".join(seg["layers_a"]),
                                                "层位B": " → ".join(seg["layers_b"]),
                                                "相似度": f"{seg['similarity']:.4f}",
                                            })
                                        st.dataframe(pd.DataFrame(seg_rows), use_container_width=True, hide_index=True)

                    with align_tab6:
                        st.subheader("层序延续性分析")

                        if c_result:
                            fig_cont = visualizer.plot_continuity_chart(
                                c_result, title="各层位延续性分析"
                            )
                            st.plotly_chart(fig_cont, use_container_width=True)

                            cont_data = c_result.get("continuity", [])
                            if cont_data:
                                cont_rows = []
                                for c in cont_data:
                                    row = {
                                        "层位名称": c["layer_name"],
                                        "延续类型": c["continuity_type"],
                                        "置信度": f"{c['confidence']:.4f}",
                                        "出现次数": c["occurrence_count"],
                                        "涉及站位": c["station_count"],
                                    }
                                    if c.get("depth_range"):
                                        row["归一化起点均值"] = f"{c['depth_range']['norm_start_mean']:.4f}"
                                        row["归一化终点均值"] = f"{c['depth_range']['norm_end_mean']:.4f}"
                                        row["起点标准差"] = f"{c['depth_range']['start_std']:.4f}"
                                        row["终点标准差"] = f"{c['depth_range']['end_std']:.4f}"
                                    cont_rows.append(row)
                                st.dataframe(pd.DataFrame(cont_rows), use_container_width=True, hide_index=True)

                            cont_type_labels = {
                                "continuous": "连续（站位间稳定延续）",
                                "transitional": "过渡（站位间有变化）",
                                "discontinuous": "不连续（站位间差异大）",
                                "isolated": "孤立（仅单站出现）",
                            }
                            st.info(
                                f"💡 延续性解读：整体评分 {c_result.get('continuity_score', 0):.3f}，"
                                f"连续层位 {c_result.get('continuous_count', 0)} 种，"
                                f"过渡层位 {c_result.get('transitional_count', 0)} 种，"
                                f"不连续层位 {c_result.get('discontinuous_count', 0)} 种"
                            )

                    with align_tab7:
                        st.subheader("关键界面追踪")

                        if s_result:
                            fig_surface = visualizer.plot_key_surface_tracking(
                                s_result,
                                a_result.get("core_data", {}),
                                title="关键界面追踪与相关性"
                            )
                            st.plotly_chart(fig_surface, use_container_width=True)

                            fig_sig = visualizer.plot_surface_significance_chart(
                                s_result, title="关键界面重要性分析"
                            )
                            st.plotly_chart(fig_sig, use_container_width=True)

                            key_surfaces = s_result.get("key_surfaces", [])
                            if key_surfaces:
                                surface_rows = []
                                for s in key_surfaces:
                                    surface_rows.append({
                                        "柱样": s["sample_code"],
                                        "深度(cm)": f"{s['depth']:.1f}",
                                        "界面类型": s.get("surface_label", s["surface_type"]),
                                        "上覆层位": s["layer_above"],
                                        "下伏层位": s["layer_below"],
                                        "粒度变化": f"{s['grain_change']:.1f}",
                                        "重要性": s.get("significance", "low"),
                                    })
                                st.dataframe(pd.DataFrame(surface_rows), use_container_width=True, hide_index=True)

                            correlations = s_result.get("surface_correlations", [])
                            if correlations:
                                st.subheader("界面间相关性")
                                corr_rows = []
                                for corr in correlations:
                                    corr_rows.append({
                                        "界面类型": corr.get("surface_label", corr.get("surface_type", "")),
                                        "柱样A": corr["core_a"],
                                        "深度A": f"{corr['depth_a']:.1f}",
                                        "柱样B": corr["core_b"],
                                        "深度B": f"{corr['depth_b']:.1f}",
                                        "深度相关": f"{corr['correlation_score']:.4f}",
                                        "综合相关": f"{corr.get('combined_correlation', corr['correlation_score']):.4f}",
                                    })
                                st.dataframe(pd.DataFrame(corr_rows), use_container_width=True, hide_index=True)

                    with align_tab8:
                        st.subheader("区域沉积演化分区展示")

                        if e_result:
                            fig_evo = visualizer.plot_regional_evolution_map(
                                e_result, title="区域沉积演化分区"
                            )
                            st.plotly_chart(fig_evo, use_container_width=True)

                            fig_evo_detail = visualizer.plot_regional_evolution_detailed(
                                e_result, title="区域沉积演化综合分析"
                            )
                            st.plotly_chart(fig_evo_detail, use_container_width=True)

                            zones = e_result.get("zones", [])
                            if zones:
                                st.subheader("沉积分区详情")
                                zone_rows = []
                                for z in zones:
                                    zone_rows.append({
                                        "分区类型": z["zone_type"],
                                        "柱样数": z["core_count"],
                                        "涉及柱样": ", ".join(z.get("sample_codes", [])),
                                        "平均砂(%)": z["avg_sand"],
                                        "平均粉砂(%)": z["avg_silt"],
                                        "平均黏土(%)": z["avg_clay"],
                                        "平均砾石(%)": z["avg_gravel"],
                                    })
                                st.dataframe(pd.DataFrame(zone_rows), use_container_width=True, hide_index=True)

                            stages = e_result.get("evolution_stages", [])
                            if stages:
                                st.subheader("各柱样演化阶段推断")
                                for stage in stages:
                                    with st.expander(f"📊 {stage['sample_code']}: {stage['overall_trend']}"):
                                        seg_rows = []
                                        for seg in stage["segments"]:
                                            seg_rows.append({
                                                "阶段": seg["segment"],
                                                "深度范围(cm)": seg["depth_range"],
                                                "平均砂(%)": seg["avg_sand"],
                                                "平均黏土(%)": seg["avg_clay"],
                                                "砂黏比": seg["sand_clay_ratio"],
                                                "沉积环境": seg["environment"],
                                                "层位组成": " → ".join(seg["layer_names"]),
                                            })
                                        st.dataframe(pd.DataFrame(seg_rows), use_container_width=True, hide_index=True)
                                        trend_labels = {
                                            "海退序列（变浅）": "🔴 海退：沉积环境由深变浅，砂含量向上增加",
                                            "海进序列（变深）": "🔵 海进：沉积环境由浅变深，黏土含量向上增加",
                                            "稳定沉积": "🟢 稳定：沉积环境基本不变，粒度组成稳定",
                                        }
                                        st.info(trend_labels.get(stage["overall_trend"], stage["overall_trend"]))

                    with align_tab9:
                        st.subheader("人工校正与解释备注")

                        current_alignment_id = st.session_state.get("current_alignment_id")
                        if not current_alignment_id:
                            st.info("请先执行层位对齐分析后再进行人工校正")
                        else:
                            correction_tab, annotation_tab, history_tab = st.tabs([
                                "✏️ 深度校正", "📝 解释备注", "📜 校正历史"
                            ])

                            with correction_tab:
                                st.subheader("层位深度校正")
                                aligned_groups = a_result.get("aligned_groups", [])

                                if aligned_groups:
                                    group_options = []
                                    for group in aligned_groups:
                                        label = f"组{group['group_id']}: {group['representative_name']} ({group['station_count']}站)"
                                        group_options.append((label, group["group_id"]))

                                    sel_group_label = st.selectbox(
                                        "选择对齐组",
                                        [g[0] for g in group_options],
                                        key="correct_group_select"
                                    )
                                    sel_group_id = dict(group_options)[sel_group_label]

                                    sel_group = next((g for g in aligned_groups if g["group_id"] == sel_group_id), None)
                                    if sel_group:
                                        member_options = [
                                            f"{m['sample_code']} - {m['layer_name']} ({m['depth']:.1f}cm)"
                                            for m in sel_group["members"]
                                        ]
                                        sel_member_label = st.selectbox(
                                            "选择要校正的层位",
                                            member_options,
                                            key="correct_member_select"
                                        )
                                        sel_member_idx = member_options.index(sel_member_label)
                                        sel_member = sel_group["members"][sel_member_idx]

                                        layer_data = db.get_layer_by_id(sel_member["layer_id"])
                                        if layer_data:
                                            st.info(f"当前深度: {layer_data['depth_start']:.1f} - {layer_data['depth_end']:.1f} cm")

                                            col_corr1, col_corr2 = st.columns(2)
                                            with col_corr1:
                                                new_depth_start = st.number_input(
                                                    "校正后深度起点 (cm)",
                                                    value=float(layer_data["depth_start"]),
                                                    min_value=0.0,
                                                    key="correct_depth_start"
                                                )
                                            with col_corr2:
                                                new_depth_end = st.number_input(
                                                    "校正后深度终点 (cm)",
                                                    value=float(layer_data["depth_end"]),
                                                    min_value=0.0,
                                                    key="correct_depth_end"
                                                )

                                            correction_reason = st.text_input(
                                                "校正原因",
                                                placeholder="说明校正依据（如：根据相邻站位层位对比调整）",
                                                key="correct_reason"
                                            )
                                            corrected_by = st.text_input("校正人", value="地质员", key="corrected_by")

                                            if st.button("✅ 提交校正", key="submit_correction"):
                                                if not correction_reason.strip():
                                                    st.warning("请填写校正原因")
                                                elif new_depth_start >= new_depth_end:
                                                    st.error("深度起点必须小于终点")
                                                else:
                                                    core_id = layer_data["core_id"]
                                                    all_layers = db.get_core_layers(core_id)
                                                    overlap_found = False
                                                    overlap_details = []
                                                    for _, other_layer in all_layers.iterrows():
                                                        if other_layer["id"] == sel_member["layer_id"]:
                                                            continue
                                                        other_start = float(other_layer["depth_start"])
                                                        other_end = float(other_layer["depth_end"])
                                                        if (new_depth_start < other_end and new_depth_end > other_start):
                                                            overlap_found = True
                                                            overlap_details.append(
                                                                f"层位 '{other_layer['layer_name']}' "
                                                                f"({other_start:.1f}-{other_end:.1f}cm)"
                                                            )

                                                    if overlap_found:
                                                        st.error(
                                                            "❌ 深度重叠校验失败！\n\n"
                                                            f"校正后深度 {new_depth_start:.1f}-{new_depth_end:.1f}cm "
                                                            f"与以下层位重叠：\n" +
                                                            "\n".join(f"  • {d}" for d in overlap_details) +
                                                            "\n\n请调整深度范围后再提交。"
                                                        )
                                                    else:
                                                        db.add_alignment_correction(
                                                            alignment_id=current_alignment_id,
                                                            group_id=sel_group_id,
                                                            sample_code=sel_member["sample_code"],
                                                            layer_id=sel_member["layer_id"],
                                                            original_depth_start=float(layer_data["depth_start"]),
                                                            original_depth_end=float(layer_data["depth_end"]),
                                                            corrected_depth_start=new_depth_start,
                                                            corrected_depth_end=new_depth_end,
                                                            correction_reason=correction_reason,
                                                            corrected_by=corrected_by,
                                                        )
                                                        db.update_layer_with_version(
                                                            sel_member["layer_id"],
                                                            {
                                                                "layer_name": layer_data["layer_name"],
                                                                "depth_start": new_depth_start,
                                                                "depth_end": new_depth_end,
                                                                "gravel_pct": layer_data["gravel_pct"] or 0,
                                                                "sand_pct": layer_data["sand_pct"] or 0,
                                                                "silt_pct": layer_data["silt_pct"] or 0,
                                                                "clay_pct": layer_data["clay_pct"] or 0,
                                                                "organic_matter": layer_data["organic_matter"],
                                                                "water_content": layer_data["water_content"],
                                                                "notes": layer_data["notes"] or "",
                                                            },
                                                            change_reason=f"层位对齐校正: {correction_reason}",
                                                            changed_by=corrected_by,
                                                        )
                                                        st.success("✅ 校正已提交并记录到版本历史")
                                else:
                                    st.info("暂无对齐组可校正")

                            with annotation_tab:
                                st.subheader("解释备注")

                                annotation_type = st.selectbox(
                                    "备注类型",
                                    ["interpretation", "question", "suggestion", "boundary_definition"],
                                    format_func=lambda x: {
                                        "interpretation": "地质解释",
                                        "question": "待确认问题",
                                        "suggestion": "建议修改",
                                        "boundary_definition": "界面定义",
                                    }.get(x, x),
                                    key="annotation_type"
                                )

                                target_type = st.selectbox(
                                    "备注对象",
                                    ["group", "surface", "zone", "general"],
                                    format_func=lambda x: {
                                        "group": "对齐组",
                                        "surface": "关键界面",
                                        "zone": "沉积分区",
                                        "general": "总体说明",
                                    }.get(x, x),
                                    key="annotation_target_type"
                                )

                                target_id = None
                                if target_type == "group" and a_result.get("aligned_groups"):
                                    group_opts = [(f"组{g['group_id']}: {g['representative_name']}", g["group_id"])
                                                  for g in a_result["aligned_groups"]]
                                    sel_target_label = st.selectbox(
                                        "选择对齐组",
                                        [o[0] for o in group_opts],
                                        key="annotation_group"
                                    )
                                    target_id = dict(group_opts)[sel_target_label]
                                elif target_type == "surface" and s_result.get("key_surfaces"):
                                    surface_opts = list(set(
                                        s.get("surface_label", s["surface_type"])
                                        for s in s_result["key_surfaces"]
                                    ))
                                    sel_surface = st.selectbox("选择界面类型", surface_opts, key="annotation_surface")
                                    target_id = sel_surface

                                annotation_content = st.text_area(
                                    "备注内容",
                                    placeholder="输入地质解释或备注信息...",
                                    height=150,
                                    key="annotation_content"
                                )
                                annotation_author = st.text_input("备注人", value="地质员", key="annotation_author")

                                if st.button("📝 添加备注", key="submit_annotation"):
                                    if not annotation_content.strip():
                                        st.warning("请输入备注内容")
                                    else:
                                        db.add_alignment_annotation(
                                            alignment_id=current_alignment_id,
                                            annotation_type=annotation_type,
                                            content=annotation_content,
                                            target_type=target_type,
                                            target_id=target_id,
                                            author=annotation_author,
                                        )
                                        st.success("✅ 备注已保存")

                                existing_annotations = db.get_alignment_annotations(current_alignment_id)
                                if not existing_annotations.empty:
                                    st.subheader("已有备注")
                                    type_labels = {
                                        "interpretation": "地质解释",
                                        "question": "待确认问题",
                                        "suggestion": "建议修改",
                                        "boundary_definition": "界面定义",
                                    }
                                    target_labels = {
                                        "group": "对齐组",
                                        "surface": "关键界面",
                                        "zone": "沉积分区",
                                        "general": "总体说明",
                                    }
                                    ann_display = existing_annotations[["annotation_type", "target_type", "target_id", "content", "author", "created_at"]].copy()
                                    ann_display["annotation_type"] = ann_display["annotation_type"].map(type_labels)
                                    ann_display["target_type"] = ann_display["target_type"].map(target_labels)
                                    ann_display.columns = ["备注类型", "对象类型", "对象ID", "内容", "备注人", "时间"]
                                    st.dataframe(ann_display, use_container_width=True, hide_index=True)

                            with history_tab:
                                st.subheader("校正历史记录")
                                corrections_df = db.get_alignment_corrections(current_alignment_id)
                                if corrections_df.empty:
                                    st.info("暂无校正记录")
                                else:
                                    corr_display = corrections_df[[
                                        "group_id", "sample_code", "layer_id",
                                        "original_depth_start", "original_depth_end",
                                        "corrected_depth_start", "corrected_depth_end",
                                        "correction_reason", "corrected_by", "created_at"
                                    ]].copy()
                                    corr_display.columns = [
                                        "对齐组ID", "柱样编号", "层位ID",
                                        "原始起点", "原始终点",
                                        "校正起点", "校正终点",
                                        "校正原因", "校正人", "时间"
                                    ]
                                    st.dataframe(corr_display, use_container_width=True, hide_index=True)

                st.divider()
                st.subheader("📥 成果图件与解释报告导出")

                col_exp_type, col_exp_btn = st.columns([1, 1])
                with col_exp_type:
                    export_choice = st.selectbox(
                        "选择导出内容",
                        [
                            "完整解释报告", "对齐结果数据", "层序延续性数据",
                            "关键界面数据", "区域演化数据",
                            "层序对比横断面图", "对齐质量评估图", "区域演化综合图",
                        ],
                        key="align_export_choice"
                    )
                with col_exp_btn:
                    if st.button("📤 生成导出", key="align_export_btn"):
                        if "alignment_result" not in st.session_state:
                            st.warning("请先执行层位对齐分析")
                        else:
                            export_filters = {
                                "core_ids": selected_core_ids,
                                "method": align_method,
                                "threshold": sim_threshold,
                                "alignment_id": st.session_state.get("current_alignment_id"),
                            }
                            if export_choice == "完整解释报告":
                                correction_records = []
                                annotation_records = []
                                current_alignment_id = st.session_state.get("current_alignment_id")
                                if current_alignment_id:
                                    correction_records = db.get_correction_dicts(current_alignment_id)
                                    annotation_records = db.get_annotation_dicts(current_alignment_id)
                                report = align.generate_alignment_report(
                                    st.session_state.alignment_result,
                                    st.session_state.get("continuity_result", {}),
                                    st.session_state.get("surface_result", {}),
                                    st.session_state.get("evolution_result", {}),
                                    correction_records=correction_records,
                                    annotation_records=annotation_records,
                                )
                                export_filename = f"层位对齐解释报告_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                                st.session_state.align_export_data = {
                                    "data": report["report_text"],
                                    "filename": export_filename,
                                    "type": "txt",
                                }
                                report_length = len(report["report_text"].splitlines())
                                db.add_export_record(
                                    export_type="alignment_report",
                                    scope="alignment",
                                    filters=export_filters,
                                    record_count=report_length,
                                    file_name=export_filename,
                                    export_format="txt"
                                )
                            elif export_choice == "对齐结果数据":
                                groups = st.session_state.alignment_result.get("aligned_groups", [])
                                rows = []
                                for g in groups:
                                    for m in g["members"]:
                                        rows.append({
                                            "对齐组ID": g["group_id"],
                                            "代表名称": g["representative_name"],
                                            "柱样编号": m["sample_code"],
                                            "层位名称": m["layer_name"],
                                            "深度(cm)": m["depth"],
                                            "归一化深度": m["norm_depth"],
                                            "相似度": g["avg_similarity"],
                                        })
                                csv_data = pd.DataFrame(rows).to_csv(index=False, encoding="utf-8-sig")
                                export_filename = f"对齐结果_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                                st.session_state.align_export_data = {
                                    "data": csv_data,
                                    "filename": export_filename,
                                    "type": "csv",
                                }
                                db.add_export_record(
                                    export_type="alignment_data",
                                    scope="alignment",
                                    filters=export_filters,
                                    record_count=len(rows),
                                    file_name=export_filename,
                                    export_format="csv"
                                )
                            elif export_choice == "层序延续性数据":
                                cont = st.session_state.get("continuity_result", {}).get("continuity", [])
                                csv_data = pd.DataFrame(cont).to_csv(index=False, encoding="utf-8-sig")
                                export_filename = f"层序延续性_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                                st.session_state.align_export_data = {
                                    "data": csv_data,
                                    "filename": export_filename,
                                    "type": "csv",
                                }
                                db.add_export_record(
                                    export_type="continuity_data",
                                    scope="alignment",
                                    filters=export_filters,
                                    record_count=len(cont),
                                    file_name=export_filename,
                                    export_format="csv"
                                )
                            elif export_choice == "关键界面数据":
                                surfaces = st.session_state.get("surface_result", {}).get("key_surfaces", [])
                                csv_data = pd.DataFrame(surfaces).to_csv(index=False, encoding="utf-8-sig")
                                export_filename = f"关键界面_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                                st.session_state.align_export_data = {
                                    "data": csv_data,
                                    "filename": export_filename,
                                    "type": "csv",
                                }
                                db.add_export_record(
                                    export_type="surface_data",
                                    scope="alignment",
                                    filters=export_filters,
                                    record_count=len(surfaces),
                                    file_name=export_filename,
                                    export_format="csv"
                                )
                            elif export_choice == "区域演化数据":
                                zones = st.session_state.get("evolution_result", {}).get("zones", [])
                                csv_data = pd.DataFrame(zones).to_csv(index=False, encoding="utf-8-sig")
                                export_filename = f"区域演化_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                                st.session_state.align_export_data = {
                                    "data": csv_data,
                                    "filename": export_filename,
                                    "type": "csv",
                                }
                                db.add_export_record(
                                    export_type="evolution_data",
                                    scope="alignment",
                                    filters=export_filters,
                                    record_count=len(zones),
                                    file_name=export_filename,
                                    export_format="csv"
                                )
                            elif export_choice == "层序对比横断面图":
                                fig = visualizer.plot_cross_section_correlation(
                                    st.session_state.alignment_result,
                                    surface_result=st.session_state.get("surface_result", {}),
                                    title="层序对比横断面图"
                                )
                                img_bytes = fig.to_image(format="png", width=1200, height=600, scale=2)
                                export_filename = f"层序对比横断面_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                                st.session_state.align_export_data = {
                                    "data": img_bytes,
                                    "filename": export_filename,
                                    "type": "png",
                                }
                                db.add_export_record(
                                    export_type="alignment_figure",
                                    scope="alignment",
                                    filters=export_filters,
                                    record_count=1,
                                    file_name=export_filename,
                                    export_format="png"
                                )
                            elif export_choice == "对齐质量评估图":
                                quality = st.session_state.alignment_result.get("quality", {})
                                if quality:
                                    fig = visualizer.plot_alignment_quality(quality, title="对齐质量评估")
                                    img_bytes = fig.to_image(format="png", width=1000, height=500, scale=2)
                                    export_filename = f"对齐质量评估_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                                    st.session_state.align_export_data = {
                                        "data": img_bytes,
                                        "filename": export_filename,
                                        "type": "png",
                                    }
                                    db.add_export_record(
                                        export_type="alignment_figure",
                                        scope="alignment",
                                        filters=export_filters,
                                        record_count=1,
                                        file_name=export_filename,
                                        export_format="png"
                                    )
                                else:
                                    st.warning("暂无质量评估数据，请先执行对齐分析")
                            elif export_choice == "区域演化综合图":
                                evo = st.session_state.get("evolution_result", {})
                                if evo:
                                    fig = visualizer.plot_regional_evolution_detailed(evo, title="区域沉积演化综合分析")
                                    img_bytes = fig.to_image(format="png", width=1400, height=800, scale=2)
                                    export_filename = f"区域演化综合_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                                    st.session_state.align_export_data = {
                                        "data": img_bytes,
                                        "filename": export_filename,
                                        "type": "png",
                                    }
                                    db.add_export_record(
                                        export_type="alignment_figure",
                                        scope="alignment",
                                        filters=export_filters,
                                        record_count=1,
                                        file_name=export_filename,
                                        export_format="png"
                                    )
                                else:
                                    st.warning("暂无区域演化数据，请先执行对齐分析")
                            st.success("✅ 导出数据已生成")

                if "align_export_data" in st.session_state:
                    export_type = st.session_state.align_export_data["type"]
                    mime_map = {"txt": "text/plain", "csv": "text/csv", "png": "image/png"}
                    st.download_button(
                        label="⬇️ 下载导出文件",
                        data=st.session_state.align_export_data["data"],
                        file_name=st.session_state.align_export_data["filename"],
                        mime=mime_map.get(export_type, "application/octet-stream"),
                        use_container_width=True,
                    )

                st.divider()
                st.subheader("📜 历史对齐会话")
                history_df = db.get_alignment_results(10)
                if history_df.empty:
                    st.info("暂无历史对齐会话")
                else:
                    hist_display = history_df[["id", "session_name", "method", "threshold", "created_at"]].copy()
                    method_labels = {"combined": "综合对齐", "lithology": "岩性对齐", "depth": "深度对齐", "dtw": "DTW对齐"}
                    hist_display["method"] = hist_display["method"].map(method_labels)
                    hist_display.columns = ["ID", "会话名称", "方法", "阈值", "创建时间"]
                    st.dataframe(hist_display, use_container_width=True, hide_index=True)


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


elif page == "⏳ 年代约束与沉积速率":
    st.header("⏳ 年代约束与沉积速率反演分析")
    st.caption("基于年代测定数据构建年龄-深度模型，反演沉积速率并进行时空演化对比分析")

    filters = st.session_state.filters
    cores_df = analyzer.filter_cores(filters)

    if cores_df.empty:
        st.info("暂无沉积柱样数据，请先导入CSV文件或调整筛选条件。")
    else:
        chrono_main_tabs = st.tabs([
            "📋 数据总览",
            "📍 年代点录入与校验",
            "📐 年龄-深度模型拟合",
            "📊 沉积速率计算",
            "⏱️ 时间剖面图",
            "🔍 异常年代点识别",
            "🔗 层位时间对比",
            "🌐 多站位沉积演化对比",
            "✏️ 模型修正与备注",
            "📤 分析报告导出"
        ])

        with chrono_main_tabs[0]:
            st.subheader("年代约束数据总览")
            all_core_ids = cores_df["id"].tolist()
            chrono_summary = chrono.get_chronology_summary(all_core_ids)

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("柱样总数", len(all_core_ids))
            with col2:
                with_chrono = chrono_summary[chrono_summary["has_chronology"]].shape[0] if not chrono_summary.empty else 0
                st.metric("已有年代约束", with_chrono,
                          delta=f"{with_chrono/len(all_core_ids)*100:.1f}%" if all_core_ids else "0%")
            with col3:
                total_points = chrono_summary["dating_point_count"].sum() if not chrono_summary.empty else 0
                st.metric("年代点总数", int(total_points))
            with col4:
                total_models = chrono_summary["model_count"].sum() if not chrono_summary.empty else 0
                st.metric("已建模型数", int(total_models))

            if not chrono_summary.empty:
                display_summary = chrono_summary.copy()
                display_summary.columns = [
                    "柱样ID", "站位", "样品编号", "年代点数",
                    "模型数", "平均沉积速率(cm/ka)", "已有年代约束"
                ]
                st.dataframe(display_summary, use_container_width=True, hide_index=True)

                if not chrono_summary.empty and chrono_summary["dating_point_count"].sum() > 0:
                    fig_stats = visualizer.plot_chronology_stats(chrono_summary)
                    st.plotly_chart(fig_stats, use_container_width=True)

        with chrono_main_tabs[1]:
            st.subheader("年代点录入与校验")

            core_options = dict(zip(cores_df["sample_code"], cores_df["id"]))
            selected_core = st.selectbox(
                "选择沉积柱样",
                list(core_options.keys()),
                key="dating_point_core_select"
            )
            selected_core_id = core_options[selected_core]
            core_info = db.get_core_sample(selected_core_id)
            core_length = core_info.get("core_length") if core_info else None

            col_a, col_b = st.columns([1, 1])
            with col_a:
                st.markdown("#### 录入单一年代点")
                with st.form("add_dating_point_form", clear_on_submit=True):
                    dp_depth = st.number_input("深度 (cm)", min_value=0.0, step=1.0,
                                               max_value=float(core_length) if core_length else 10000.0,
                                               help="年代控制点的深度位置")
                    dp_age = st.number_input("年龄 (a BP)", min_value=0.0, step=10.0,
                                             help="距今年代，单位为年前 (a BP)")
                    dp_age_error = st.number_input("年龄误差 (±a)", min_value=0.0, step=1.0, value=0.0)
                    dp_method = st.selectbox("测年方法", chrono.DATING_METHODS)
                    dp_label = st.text_input("样品标签/编号", placeholder="如: C-14-001")
                    dp_notes = st.text_area("备注", placeholder="测年实验室、材料类型等说明...")

                    submitted = st.form_submit_button("➕ 添加年代点", type="primary")
                    if submitted:
                        existing_points = db.get_dating_points(selected_core_id)
                        validation = chrono.validate_dating_point(
                            dp_depth, dp_age, core_length, existing_points
                        )
                        if not validation["valid"]:
                            for err in validation["errors"]:
                                st.error(f"❌ {err}")
                        else:
                            point_id = db.add_dating_point(
                                selected_core_id, dp_depth, dp_age, dp_age_error,
                                dp_method, dp_label, dp_notes
                            )
                            st.success(f"✅ 年代点已添加 (ID: {point_id})")
                            if validation["warnings"]:
                                for warn in validation["warnings"]:
                                    st.warning(f"⚠️ {warn}")
                            st.rerun()

            with col_b:
                st.markdown("#### 批量导入年代点")
                st.info("CSV格式：depth,age,age_error,dating_method,sample_label,notes")
                batch_file = st.file_uploader("上传年代点CSV文件", type=["csv"], key="batch_dating_upload")
                if batch_file is not None:
                    try:
                        batch_df = pd.read_csv(batch_file)
                        st.write(f"预览 ({len(batch_df)} 条记录):")
                        st.dataframe(batch_df.head(), use_container_width=True)

                        if st.button("🚀 批量导入", key="batch_import_dating"):
                            existing_points = db.get_dating_points(selected_core_id)
                            success_count = 0
                            error_count = 0
                            for _, row in batch_df.iterrows():
                                validation = chrono.validate_dating_point(
                                    row.get("depth"), row.get("age"),
                                    core_length, existing_points
                                )
                                if validation["valid"]:
                                    db.add_dating_point(
                                        selected_core_id,
                                        float(row.get("depth", 0)),
                                        float(row.get("age", 0)),
                                        float(row.get("age_error", 0)) if pd.notna(row.get("age_error")) else None,
                                        str(row.get("dating_method", "")),
                                        str(row.get("sample_label", "")),
                                        str(row.get("notes", ""))
                                    )
                                    success_count += 1
                                else:
                                    error_count += 1
                            st.success(f"✅ 导入完成：成功 {success_count} 条，失败 {error_count} 条")
                            st.rerun()
                    except Exception as e:
                        st.error(f"文件解析失败: {str(e)}")

            st.divider()
            st.markdown("#### 已录入年代点列表")
            dating_points_df = db.get_dating_points(selected_core_id)

            if dating_points_df.empty:
                st.info("该柱样暂未录入年代点数据")
            else:
                display_dp = dating_points_df.copy()
                display_dp["状态"] = display_dp.apply(
                    lambda r: "🔴 异常" if r.get("is_anomaly", 0) == 1
                    else ("⚪ 已排除" if r.get("is_valid", 1) == 0 else "🟢 有效"),
                    axis=1
                )
                display_cols = ["id", "depth", "age", "age_error", "dating_method",
                                "sample_label", "状态", "notes"]
                display_names = ["ID", "深度(cm)", "年龄(a BP)", "误差(±a)", "测年方法",
                                 "样品标签", "状态", "备注"]
                display_dp = display_dp[display_cols]
                display_dp.columns = display_names
                st.dataframe(display_dp, use_container_width=True, hide_index=True)

                with st.expander("批量操作年代点"):
                    col_act1, col_act2, col_act3 = st.columns(3)
                    with col_act1:
                        point_ids = dating_points_df["id"].tolist()
                        point_options = [f"#{pid} - {dating_points_df[dating_points_df['id']==pid]['depth'].values[0]}cm"
                                         for pid in point_ids]
                        edit_pid = st.selectbox("选择要编辑的年代点", point_options, key="edit_dp_select")
                        edit_id = point_ids[point_options.index(edit_pid)]
                        dp_data = db.get_dating_point(edit_id)
                        if dp_data:
                            new_depth = st.number_input("新深度", value=float(dp_data["depth"]), step=1.0)
                            new_age = st.number_input("新年龄", value=float(dp_data["age"]), step=10.0)
                            new_notes = st.text_input("备注", value=dp_data.get("notes", ""))
                            if st.button("💾 保存修改", key="save_dp_edit"):
                                db.update_dating_point(edit_id, depth=new_depth, age=new_age, notes=new_notes)
                                st.success("已更新")
                                st.rerun()
                    with col_act2:
                        del_pid = st.selectbox("选择要删除的年代点", point_options, key="del_dp_select")
                        del_id = point_ids[point_options.index(del_pid)]
                        if st.button("🗑️ 删除年代点", type="secondary", key="delete_dp"):
                            db.delete_dating_point(del_id)
                            st.success("已删除")
                            st.rerun()
                    with col_act3:
                        toggle_pid = st.selectbox("选择年代点", point_options, key="toggle_dp_select")
                        toggle_id = point_ids[point_options.index(toggle_pid)]
                        toggle_dp = db.get_dating_point(toggle_id)
                        current_valid = toggle_dp.get("is_valid", 1) if toggle_dp else 1
                        action_label = "🔓 恢复为有效" if current_valid == 0 else "🔒 标记为无效/排除"
                        if st.button(action_label, key="toggle_dp_valid"):
                            db.update_dating_point(toggle_id, is_valid=0 if current_valid == 1 else 1)
                            st.success("状态已更新")
                            st.rerun()

                fig_ad = visualizer.plot_age_depth_scatter(dating_points_df)
                st.plotly_chart(fig_ad, use_container_width=True)

        with chrono_main_tabs[2]:
            st.subheader("年龄-深度模型拟合")

            core_options = dict(zip(cores_df["sample_code"], cores_df["id"]))
            model_core = st.selectbox("选择沉积柱样", list(core_options.keys()),
                                      key="model_core_select")
            model_core_id = core_options[model_core]

            dating_points = db.get_dating_points(model_core_id, valid_only=True)

            if dating_points.empty or len(dating_points) < 2:
                st.warning("⚠️ 至少需要2个有效年代点才能拟合模型。请先在「年代点录入」中添加数据。")
            else:
                col_m1, col_m2 = st.columns(2)
                with col_m1:
                    model_type = st.selectbox(
                        "选择拟合模型类型",
                        list(chrono.MODEL_TYPES.keys()),
                        format_func=lambda x: chrono.MODEL_TYPES[x],
                        key="model_type_select"
                    )
                    smooth_factor = 0.0
                    if model_type == "spline":
                        smooth_factor = st.slider("样条平滑因子", 0.0, 10.0, 0.0, 0.1)

                with col_m2:
                    st.markdown("#### 拟合参数设置")
                    model_name = st.text_input("模型名称",
                                               value=f"{model_core}_{chrono.MODEL_TYPES[model_type]}_{datetime.now().strftime('%Y%m%d')}")
                    model_notes = st.text_area("模型备注", placeholder="模型构建说明、数据来源、特殊处理等...")
                    exclude_anomalies = st.checkbox("排除异常年代点", value=True)

                if exclude_anomalies:
                    fit_points = dating_points[dating_points.get("is_anomaly", 0) == 0].copy()
                else:
                    fit_points = dating_points.copy()

                if st.button("🔬 开始拟合模型", type="primary", key="fit_model_btn"):
                    with st.spinner("正在拟合模型..."):
                        model_result = chrono.fit_age_depth_model(fit_points, model_type, smooth_factor)
                        st.session_state[f"current_model_{model_core_id}"] = model_result

                        if model_result["success"]:
                            model_id = db.add_age_depth_model(
                                model_core_id, model_name, model_type,
                                model_result.get("model_params"),
                                model_result.get("r_squared"),
                                model_result.get("rmse"),
                                notes=model_notes
                            )
                            st.session_state[f"current_model_id_{model_core_id}"] = model_id
                            st.success(f"✅ 模型拟合成功！模型ID: {model_id}")
                        else:
                            st.error(f"❌ 模型拟合失败: {model_result.get('error', '未知错误')}")

                if f"current_model_{model_core_id}" in st.session_state:
                    model_result = st.session_state[f"current_model_{model_core_id}"]

                    col_r1, col_r2, col_r3 = st.columns(3)
                    with col_r1:
                        st.metric("模型类型", chrono.MODEL_TYPES.get(model_result.get("model_type", ""), "未知"))
                    with col_r2:
                        r2 = model_result.get("r_squared")
                        st.metric("R²", f"{r2:.4f}" if r2 is not None else "N/A")
                    with col_r3:
                        rmse = model_result.get("rmse")
                        st.metric("RMSE", f"{rmse:.2f}" if rmse is not None else "N/A")

                    fig_model = visualizer.plot_age_depth_scatter(dating_points, model_result)
                    st.plotly_chart(fig_model, use_container_width=True)

                    with st.expander("查看模型参数详情"):
                        params = model_result.get("model_params", {})
                        if params:
                            st.json(params)

                st.divider()
                st.markdown("#### 已保存的模型")
                saved_models = db.get_age_depth_models(model_core_id)
                if saved_models.empty:
                    st.info("暂无已保存的模型")
                else:
                    saved_models_display = saved_models.copy()
                    saved_models_display["model_type_display"] = saved_models_display["model_type"].map(
                        lambda x: chrono.MODEL_TYPES.get(x, x)
                    )
                    saved_models_display = saved_models_display[[
                        "id", "model_name", "model_type_display", "r_squared", "rmse", "notes", "created_at"
                    ]]
                    saved_models_display.columns = ["ID", "模型名称", "类型", "R²", "RMSE", "备注", "创建时间"]
                    st.dataframe(saved_models_display, use_container_width=True, hide_index=True)

                    col_load, col_del = st.columns(2)
                    with col_load:
                        load_model_id = st.selectbox(
                            "选择模型ID进行加载",
                            saved_models["id"].tolist(),
                            key="load_model_select"
                        )
                        if st.button("📂 加载此模型", key="load_saved_model"):
                            loaded_model = db.get_age_depth_model(load_model_id)
                            if loaded_model:
                                params = loaded_model.get("model_params")
                                if isinstance(params, str):
                                    try:
                                        params = json.loads(params)
                                    except:
                                        params = {}
                                model_result = {
                                    "success": True,
                                    "model_type": loaded_model["model_type"],
                                    "model_params": params or {},
                                    "r_squared": loaded_model.get("r_squared"),
                                    "rmse": loaded_model.get("rmse"),
                                    "depths": fit_points["depth"].tolist() if not fit_points.empty else [],
                                    "ages": fit_points["age"].tolist() if not fit_points.empty else [],
                                }
                                st.session_state[f"current_model_{model_core_id}"] = model_result
                                st.session_state[f"current_model_id_{model_core_id}"] = load_model_id
                                st.success("✅ 模型已加载")
                                st.rerun()
                    with col_del:
                        del_model_id = st.selectbox(
                            "选择模型ID进行删除",
                            saved_models["id"].tolist(),
                            key="del_model_select"
                        )
                        if st.button("🗑️ 删除模型", key="delete_model", type="secondary"):
                            db.delete_age_depth_model(del_model_id)
                            st.success("已删除")
                            st.rerun()

        with chrono_main_tabs[3]:
            st.subheader("沉积速率分段计算")

            core_options = dict(zip(cores_df["sample_code"], cores_df["id"]))
            rate_core = st.selectbox("选择沉积柱样", list(core_options.keys()),
                                     key="rate_core_select")
            rate_core_id = core_options[rate_core]

            if f"current_model_{rate_core_id}" not in st.session_state:
                saved_models = db.get_age_depth_models(rate_core_id)
                if saved_models.empty:
                    st.warning("⚠️ 请先在「年龄-深度模型拟合」中构建或加载模型")
                else:
                    latest = saved_models.iloc[0]
                    params = latest.get("model_params")
                    if isinstance(params, str):
                        try:
                            params = json.loads(params)
                        except:
                            params = {}
                    fit_points = db.get_dating_points(rate_core_id, valid_only=True)
                    model_result = {
                        "success": True,
                        "model_type": latest["model_type"],
                        "model_params": params or {},
                        "r_squared": latest.get("r_squared"),
                        "rmse": latest.get("rmse"),
                        "depths": fit_points["depth"].tolist() if not fit_points.empty else [],
                        "ages": fit_points["age"].tolist() if not fit_points.empty else [],
                    }
                    st.session_state[f"current_model_{rate_core_id}"] = model_result
                    st.session_state[f"current_model_id_{rate_core_id}"] = latest["id"]
                    st.info(f"ℹ️ 已自动加载最新模型: {latest['model_name']}")

            if f"current_model_{rate_core_id}" in st.session_state:
                model_result = st.session_state[f"current_model_{rate_core_id}"]
                core_info = db.get_core_sample(rate_core_id)
                layers_df = db.get_core_layers(rate_core_id)

                col_s1, col_s2 = st.columns(2)
                with col_s1:
                    use_layers = st.checkbox("按层位分段计算", value=True,
                                             help="勾选则按每层计算，否则按年代点间隔计算")
                with col_s2:
                    core_length = core_info.get("core_length") if core_info else None
                    extend_to_bottom = st.checkbox("延伸到柱样底部", value=True)

                if st.button("📊 计算沉积速率", type="primary", key="calc_rates_btn"):
                    with st.spinner("正在计算沉积速率..."):
                        layers_for_rate = layers_df if use_layers and not layers_df.empty else None
                        rates_df = chrono.calculate_sedimentation_rates(
                            model_result,
                            layers_for_rate,
                            max_depth=float(core_length) if (extend_to_bottom and core_length) else None
                        )
                        st.session_state[f"rates_df_{rate_core_id}"] = rates_df

                        model_id = st.session_state.get(f"current_model_id_{rate_core_id}")
                        if model_id and not rates_df.empty:
                            db.delete_sedimentation_rates(model_id)
                            for _, row in rates_df.iterrows():
                                db.add_sedimentation_rate(
                                    rate_core_id, model_id,
                                    float(row["depth_start"]), float(row["depth_end"]),
                                    float(row["age_start"]), float(row["age_end"]),
                                    float(row["sedimentation_rate"])
                                )

                if f"rates_df_{rate_core_id}" in st.session_state:
                    rates_df = st.session_state[f"rates_df_{rate_core_id}"]

                    if rates_df.empty:
                        st.warning("未计算出沉积速率数据")
                    else:
                        col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
                        with col_stat1:
                            st.metric("速率段数", len(rates_df))
                        with col_stat2:
                            st.metric("平均速率", f"{rates_df['sedimentation_rate'].mean():.2f} cm/ka")
                        with col_stat3:
                            st.metric("最大速率", f"{rates_df['sedimentation_rate'].max():.2f} cm/ka")
                        with col_stat4:
                            st.metric("最小速率", f"{rates_df['sedimentation_rate'].min():.2f} cm/ka")

                        fig_rates = visualizer.plot_sedimentation_rate(rates_df)
                        st.plotly_chart(fig_rates, use_container_width=True)

                        display_rates = rates_df.copy()
                        if "layer_name" in display_rates.columns:
                            display_rates = display_rates[[
                                "layer_name", "depth_start", "depth_end",
                                "age_start", "age_end", "age_duration",
                                "thickness", "sedimentation_rate"
                            ]]
                            display_rates.columns = [
                                "层位名称", "深度起点(cm)", "深度终点(cm)",
                                "年龄起点(a BP)", "年龄终点(a BP)", "历时(a)",
                                "厚度(cm)", "沉积速率(cm/ka)"
                            ]
                        else:
                            display_rates = display_rates[[
                                "depth_start", "depth_end",
                                "age_start", "age_end", "age_duration",
                                "thickness", "sedimentation_rate"
                            ]]
                            display_rates.columns = [
                                "深度起点(cm)", "深度终点(cm)",
                                "年龄起点(a BP)", "年龄终点(a BP)", "历时(a)",
                                "厚度(cm)", "沉积速率(cm/ka)"
                            ]
                        st.dataframe(display_rates, use_container_width=True, hide_index=True)

        with chrono_main_tabs[4]:
            st.subheader("时间剖面图")
            st.caption("将空间深度序列转换为时间序列的沉积剖面展示")

            core_options = dict(zip(cores_df["sample_code"], cores_df["id"]))
            ts_core = st.selectbox("选择沉积柱样", list(core_options.keys()),
                                   key="timesection_core_select")
            ts_core_id = core_options[ts_core]

            layers_df = db.get_core_layers(ts_core_id)

            if f"current_model_{ts_core_id}" not in st.session_state:
                saved_models = db.get_age_depth_models(ts_core_id)
                if not saved_models.empty:
                    latest = saved_models.iloc[0]
                    params = latest.get("model_params")
                    if isinstance(params, str):
                        try:
                            params = json.loads(params)
                        except:
                            params = {}
                    fit_points = db.get_dating_points(ts_core_id, valid_only=True)
                    model_result = {
                        "success": True,
                        "model_type": latest["model_type"],
                        "model_params": params or {},
                        "r_squared": latest.get("r_squared"),
                        "rmse": latest.get("rmse"),
                        "depths": fit_points["depth"].tolist() if not fit_points.empty else [],
                        "ages": fit_points["age"].tolist() if not fit_points.empty else [],
                    }
                    st.session_state[f"current_model_{ts_core_id}"] = model_result
                    st.session_state[f"current_model_id_{ts_core_id}"] = latest["id"]

            if f"current_model_{ts_core_id}" in st.session_state and not layers_df.empty:
                model_result = st.session_state[f"current_model_{ts_core_id}"]

                col_view1, col_view2 = st.columns(2)
                with col_view1:
                    st.markdown("##### 空间深度剖面")
                    core_analysis = analyzer.get_core_analysis(ts_core_id)
                    missing = core_analysis.get("missing_intervals", [])
                    fig_depth = visualizer.plot_core_section(layers_df, missing)
                    st.plotly_chart(fig_depth, use_container_width=True)

                with col_view2:
                    st.markdown("##### 时间剖面（年龄尺度）")
                    fig_time = visualizer.plot_time_section(layers_df, model_result)
                    st.plotly_chart(fig_time, use_container_width=True)

                with st.expander("查看每层对应的时间区间"):
                    time_layers = []
                    import chronology_engine as ce
                    for _, row in layers_df.iterrows():
                        d_start = row["depth_start"]
                        d_end = row["depth_end"]
                        a_start = chrono.predict_age(model_result, float(d_start))
                        a_end = chrono.predict_age(model_result, float(d_end))
                        time_layers.append({
                            "层位名称": row["layer_name"],
                            "深度(cm)": f"{d_start:.1f} - {d_end:.1f}",
                            "年龄(a BP)": f"{a_start:.1f} - {a_end:.1f}" if (a_start and a_end) else "N/A",
                            "历时(a)": f"{a_end - a_start:.1f}" if (a_start and a_end and a_end > a_start) else "N/A",
                        })
                    st.dataframe(pd.DataFrame(time_layers), use_container_width=True, hide_index=True)

            elif layers_df.empty:
                st.info("该柱样暂无层位数据")

        with chrono_main_tabs[5]:
            st.subheader("异常年代点识别")
            st.caption("基于统计方法自动检测可能存在问题的年代控制点")

            core_options = dict(zip(cores_df["sample_code"], cores_df["id"]))
            anom_core = st.selectbox("选择沉积柱样", list(core_options.keys()),
                                     key="anomaly_core_select")
            anom_core_id = core_options[anom_core]

            dating_points = db.get_dating_points(anom_core_id)

            if dating_points.empty or len(dating_points) < 4:
                st.warning("⚠️ 至少需要4个年代点才能进行异常检测")
            else:
                col_an1, col_an2 = st.columns(2)
                with col_an1:
                    anomaly_method = st.selectbox(
                        "异常检测方法",
                        ["zscore", "iqr"],
                        format_func=lambda x: {"zscore": "Z-score法 (推荐)", "iqr": "四分位距法(IQR)"}.get(x, x)
                    )
                with col_an2:
                    z_threshold = st.slider("Z-score阈值", 1.5, 4.0, 2.5, 0.1,
                                            help="值越大检测越严格，异常点越少")

                if st.button("🔍 开始异常检测", type="primary", key="run_anomaly_detect"):
                    with st.spinner("正在检测异常点..."):
                        anomaly_df = chrono.detect_anomalous_points(dating_points, anomaly_method, z_threshold)

                        for _, row in anomaly_df.iterrows():
                            db.update_dating_point(
                                int(row["id"]),
                                is_anomaly=1 if row["is_anomaly"] else 0,
                                anomaly_reason=row.get("anomaly_reason", "")
                            )

                        detected = anomaly_df["is_anomaly"].sum()
                        st.success(f"✅ 检测完成：共发现 {int(detected)} 个异常点")
                        st.rerun()

                dating_points = db.get_dating_points(anom_core_id)

                anomaly_points = dating_points[dating_points.get("is_anomaly", 0) == 1]
                normal_points = dating_points[dating_points.get("is_anomaly", 0) == 0]

                col_cnt1, col_cnt2 = st.columns(2)
                with col_cnt1:
                    st.metric("异常年代点", len(anomaly_points), delta_color="inverse")
                with col_cnt2:
                    st.metric("正常年代点", len(normal_points))

                fig_anomaly = visualizer.plot_age_depth_scatter(dating_points)
                st.plotly_chart(fig_anomaly, use_container_width=True)

                if not anomaly_points.empty:
                    st.markdown("#### 检测到的异常点")
                    anom_display = anomaly_points[["id", "depth", "age", "dating_method", "anomaly_reason"]].copy()
                    anom_display.columns = ["ID", "深度(cm)", "年龄(a BP)", "测年方法", "异常原因"]
                    st.dataframe(anom_display, use_container_width=True, hide_index=True)

                    with st.expander("批量处理异常点"):
                        anom_ids = anomaly_points["id"].tolist()
                        anom_options = [f"#{pid} - {anomaly_points[anomaly_points['id']==pid]['depth'].values[0]}cm"
                                        for pid in anom_ids]
                        handle_pid = st.selectbox("选择异常点", anom_options, key="handle_anomaly_select")
                        handle_id = anom_ids[anom_options.index(handle_pid)]

                        col_h1, col_h2, col_h3 = st.columns(3)
                        with col_h1:
                            if st.button("🔓 标记为正常", key="mark_normal"):
                                db.update_dating_point(handle_id, is_anomaly=0, anomaly_reason="")
                                st.success("已标记为正常")
                                st.rerun()
                        with col_h2:
                            if st.button("🔒 排除此点", key="exclude_anomaly"):
                                db.update_dating_point(handle_id, is_valid=0)
                                st.success("已排除")
                                st.rerun()
                        with col_h3:
                            new_note = st.text_input("修正备注", key="anomaly_note")
                            if st.button("💾 保存备注", key="save_anomaly_note"):
                                db.update_dating_point(handle_id, notes=new_note)
                                st.success("备注已保存")

        with chrono_main_tabs[6]:
            st.subheader("层位时间对比")
            st.caption("比较两个柱样对应层位在时间尺度上的差异")

            core_options = dict(zip(cores_df["sample_code"], cores_df["id"]))
            col_cmp1, col_cmp2 = st.columns(2)
            with col_cmp1:
                cmp_core_a = st.selectbox("柱样 A", list(core_options.keys()), key="cmp_core_a")
                cmp_core_a_id = core_options[cmp_core_a]
            with col_cmp2:
                other_options = [k for k in core_options.keys() if k != cmp_core_a]
                cmp_core_b = st.selectbox("柱样 B", other_options, key="cmp_core_b")
                cmp_core_b_id = core_options[cmp_core_b]

            def get_or_load_model(core_id, core_name):
                if f"current_model_{core_id}" in st.session_state:
                    return st.session_state[f"current_model_{core_id}"]
                saved = db.get_age_depth_models(core_id)
                if not saved.empty:
                    latest = saved.iloc[0]
                    params = latest.get("model_params")
                    if isinstance(params, str):
                        try:
                            params = json.loads(params)
                        except:
                            params = {}
                    fit_points = db.get_dating_points(core_id, valid_only=True)
                    return {
                        "success": True,
                        "model_type": latest["model_type"],
                        "model_params": params or {},
                        "r_squared": latest.get("r_squared"),
                        "rmse": latest.get("rmse"),
                        "depths": fit_points["depth"].tolist() if not fit_points.empty else [],
                        "ages": fit_points["age"].tolist() if not fit_points.empty else [],
                    }
                return None

            model_a = get_or_load_model(cmp_core_a_id, cmp_core_a)
            model_b = get_or_load_model(cmp_core_b_id, cmp_core_b)

            if model_a is None or model_b is None:
                missing = []
                if model_a is None:
                    missing.append(cmp_core_a)
                if model_b is None:
                    missing.append(cmp_core_b)
                st.warning(f"⚠️ 柱样 {', '.join(missing)} 尚未建立年龄-深度模型")
            else:
                use_alignment = st.checkbox("使用层位对齐结果（如有）", value=False)

                if st.button("📐 进行时间对比", type="primary", key="run_temporal_cmp"):
                    with st.spinner("正在计算层位时间对比..."):
                        alignment_groups = None
                        if use_alignment:
                            pass
                        temporal_cmp_df = chrono.compare_layers_temporal(
                            cmp_core_a_id, cmp_core_b_id,
                            model_a, model_b,
                            alignment_groups
                        )
                        st.session_state["temporal_cmp_df"] = temporal_cmp_df

                if "temporal_cmp_df" in st.session_state:
                    temporal_cmp_df = st.session_state["temporal_cmp_df"]
                    if temporal_cmp_df.empty:
                        st.warning("未找到可对比的层位对")
                    else:
                        col_tc1, col_tc2 = st.columns(2)
                        with col_tc1:
                            valid_cmp = temporal_cmp_df.dropna(subset=["age_diff"])
                            if not valid_cmp.empty:
                                st.metric("对比层数", len(valid_cmp))
                                avg_diff = abs(valid_cmp["age_diff"]).mean()
                                st.metric("平均|年龄差|", f"{avg_diff:.1f} a")
                        with col_tc2:
                            if not valid_cmp.empty:
                                max_diff_row = valid_cmp.loc[abs(valid_cmp["age_diff"]).idxmax()]
                                st.metric("最大年龄差",
                                          f"{max_diff_row['age_diff']:.1f} a",
                                          delta=f"{max_diff_row['layer_a']} vs {max_diff_row['layer_b']}")

                        fig_tc = visualizer.plot_temporal_layer_comparison(temporal_cmp_df,
                                                                             title=f"{cmp_core_a} vs {cmp_core_b} 层位时间对比")
                        st.plotly_chart(fig_tc, use_container_width=True)

                        display_tc = temporal_cmp_df.copy()
                        display_tc = display_tc[[
                            "layer_a", "depth_a", "age_a",
                            "layer_b", "depth_b", "age_b",
                            "age_diff"
                        ]]
                        display_tc.columns = [
                            f"{cmp_core_a}层位", "深度A(cm)", f"年龄A(a BP)",
                            f"{cmp_core_b}层位", "深度B(cm)", f"年龄B(a BP)",
                            "年龄差(a)"
                        ]
                        st.dataframe(display_tc, use_container_width=True, hide_index=True)

        with chrono_main_tabs[7]:
            st.subheader("多站位沉积演化速率对比")
            st.caption("对比多个柱样在时间尺度上的沉积速率变化")

            all_stations = cores_df["station_code"].unique().tolist() if "station_code" in cores_df.columns else []
            multi_select_mode = st.radio(
                "选择模式",
                ["按站位选择", "手动选择柱样"],
                horizontal=True
            )

            selected_core_ids = []
            if multi_select_mode == "按站位选择":
                selected_stations = st.multiselect("选择站位", all_stations, default=all_stations[:min(3, len(all_stations))])
                if selected_stations:
                    for sc in selected_stations:
                        station_cores = cores_df[cores_df["station_code"] == sc]
                        selected_core_ids.extend(station_cores["id"].tolist())
            else:
                core_options_multi = dict(zip(cores_df["sample_code"], cores_df["id"]))
                selected_core_codes = st.multiselect("选择柱样", list(core_options_multi.keys()),
                                                      default=list(core_options_multi.keys())[:min(3, len(core_options_multi))])
                selected_core_ids = [core_options_multi[c] for c in selected_core_codes]

            if st.button("🌐 生成多站位对比图", type="primary", key="multi_station_compare"):
                with st.spinner("正在计算多站位对比..."):
                    models_dict = {}
                    layers_dict = {}
                    for cid in selected_core_ids:
                        model = None
                        if f"current_model_{cid}" in st.session_state:
                            model = st.session_state[f"current_model_{cid}"]
                        else:
                            saved = db.get_age_depth_models(cid)
                            if not saved.empty:
                                latest = saved.iloc[0]
                                params = latest.get("model_params")
                                if isinstance(params, str):
                                    try:
                                        params = json.loads(params)
                                    except:
                                        params = {}
                                fit_pts = db.get_dating_points(cid, valid_only=True)
                                model = {
                                    "success": True,
                                    "model_type": latest["model_type"],
                                    "model_params": params or {},
                                    "depths": fit_pts["depth"].tolist() if not fit_pts.empty else [],
                                    "ages": fit_pts["age"].tolist() if not fit_pts.empty else [],
                                }
                        if model and model.get("success"):
                            models_dict[cid] = model
                            layers_dict[cid] = db.get_core_layers(cid)

                    comparison_df = chrono.compare_stations_sedimentation(
                        selected_core_ids, models_dict, layers_dict
                    )
                    st.session_state["multi_station_comparison"] = comparison_df

            if "multi_station_comparison" in st.session_state:
                comparison_df = st.session_state["multi_station_comparison"]
                if comparison_df.empty:
                    st.warning("⚠️ 所选柱样中没有有效的年龄-深度模型。请先为各柱样构建模型。")
                else:
                    fig_multi = visualizer.plot_multi_station_sedimentation(comparison_df)
                    st.plotly_chart(fig_multi, use_container_width=True)

                    with st.expander("查看详细对比数据"):
                        display_multi = comparison_df.copy()
                        display_multi = display_multi[[
                            "station_code", "sample_code", "depth_start", "depth_end",
                            "age_start", "age_end", "sedimentation_rate"
                        ]]
                        display_multi.columns = [
                            "站位", "柱样", "深度起点(cm)", "深度终点(cm)",
                            "年龄起点(a BP)", "年龄终点(a BP)", "沉积速率(cm/ka)"
                        ]
                        st.dataframe(display_multi, use_container_width=True, hide_index=True)

                    pivot_stats = comparison_df.groupby(["station_code", "sample_code"]).agg(
                        平均速率=("sedimentation_rate", "mean"),
                        最大速率=("sedimentation_rate", "max"),
                        最小速率=("sedimentation_rate", "min"),
                        速率标准差=("sedimentation_rate", "std")
                    ).reset_index()
                    st.markdown("#### 各柱样沉积速率统计")
                    st.dataframe(pivot_stats, use_container_width=True, hide_index=True)

        with chrono_main_tabs[8]:
            st.subheader("模型人工修正与备注")
            st.caption("对年龄-深度模型进行人工修正、添加说明和备注")

            core_options = dict(zip(cores_df["sample_code"], cores_df["id"]))
            ann_core = st.selectbox("选择沉积柱样", list(core_options.keys()),
                                    key="annotation_core_select")
            ann_core_id = core_options[ann_core]

            saved_models = db.get_age_depth_models(ann_core_id)

            if saved_models.empty:
                st.info("该柱样暂无已保存的模型")
            else:
                model_id_options = dict(zip(saved_models["id"], saved_models["model_name"]))
                selected_model_id = st.selectbox(
                    "选择模型",
                    list(model_id_options.keys()),
                    format_func=lambda x: f"#{x} - {model_id_options[x]}",
                    key="annotation_model_select"
                )

                tab_ann1, tab_ann2 = st.tabs(["📝 添加备注/修正", "📋 查看历史记录"])

                with tab_ann1:
                    col_ann_type, col_ann_target = st.columns(2)
                    with col_ann_type:
                        ann_type = st.selectbox(
                            "备注类型",
                            ["模型修正", "数据说明", "异常解释", "参考资料", "其他"],
                            key="ann_type_select"
                        )
                    with col_ann_target:
                        ann_target_type = st.selectbox(
                            "目标类型",
                            ["模型整体", "年代点", "模型参数"],
                            key="ann_target_type"
                        )

                    ann_content = st.text_area(
                        "备注/修正内容",
                        height=120,
                        placeholder="详细描述修正内容、原因、依据等...",
                        key="ann_content"
                    )
                    ann_author = st.text_input("作者/修改人", value="geologist", key="ann_author")

                    if st.button("💾 保存备注", type="primary", key="save_annotation"):
                        if ann_content.strip():
                            anno_id = db.add_chronology_annotation(
                                ann_core_id, ann_type, ann_content.strip(),
                                model_id=selected_model_id,
                                target_type=ann_target_type,
                                author=ann_author
                            )
                            st.success(f"✅ 备注已保存 (ID: {anno_id})")
                            st.rerun()
                        else:
                            st.warning("⚠️ 备注内容不能为空")

                    st.divider()
                    st.markdown("#### 快速模型调整")
                    st.caption("对现有模型进行简单调整，将生成新的模型版本")

                    loaded_model = db.get_age_depth_model(selected_model_id)
                    if loaded_model:
                        st.write(f"当前模型: {loaded_model['model_name']} (类型: {chrono.MODEL_TYPES.get(loaded_model['model_type'], '未知')})")

                        adjustment = st.radio(
                            "调整方式",
                            ["平移整体年龄", "调整地表年龄", "调整沉积速率"],
                            horizontal=True
                        )

                        if adjustment == "平移整体年龄":
                            shift_years = st.number_input("平移年数 (正=变老，负=变年轻)", step=10.0, value=0.0)
                        elif adjustment == "调整地表年龄":
                            new_surface_age = st.number_input("新的地表年龄 (a BP)", step=10.0, value=0.0)
                        elif adjustment == "调整沉积速率":
                            rate_factor = st.slider("速率倍率", 0.5, 2.0, 1.0, 0.05)

                        if st.button("✨ 生成调整后模型", key="adjust_model"):
                            params = loaded_model.get("model_params") or {}
                            if isinstance(params, str):
                                try:
                                    params = json.loads(params)
                                except:
                                    params = {}

                            if adjustment == "平移整体年龄" and "intercept" in params:
                                params["intercept"] = float(params["intercept"]) + shift_years
                            elif adjustment == "调整地表年龄" and "intercept" in params:
                                params["intercept"] = float(new_surface_age)
                            elif adjustment == "调整沉积速率" and "slope" in params:
                                params["slope"] = float(params["slope"]) * rate_factor

                            new_model_id = db.add_age_depth_model(
                                ann_core_id,
                                f"{loaded_model['model_name']}_adjusted_{datetime.now().strftime('%H%M%S')}",
                                loaded_model["model_type"],
                                params,
                                loaded_model.get("r_squared"),
                                loaded_model.get("rmse"),
                                notes=f"基于模型#{selected_model_id}调整: {adjustment}"
                            )
                            db.add_chronology_annotation(
                                ann_core_id, "模型修正",
                                f"人工调整模型: {adjustment}，生成新模型#{new_model_id}",
                                model_id=new_model_id,
                                author=ann_author
                            )
                            st.success(f"✅ 已生成新模型 (ID: {new_model_id})")
                            st.rerun()

                with tab_ann2:
                    annotations = db.get_chronology_annotations(ann_core_id, selected_model_id)
                    if annotations.empty:
                        st.info("暂无备注记录")
                    else:
                        for _, ann in annotations.iterrows():
                            with st.container():
                                col_hd, col_del = st.columns([10, 1])
                                with col_hd:
                                    st.markdown(f"**[{ann.get('annotation_type', '')}]** "
                                                f"*{ann.get('author', '')}* "
                                                f"- {ann.get('created_at', '')}")
                                    st.write(ann.get("content", ""))
                                with col_del:
                                    if st.button("🗑️", key=f"del_ann_{ann['id']}", help="删除此备注"):
                                        db.delete_chronology_annotation(ann["id"])
                                        st.rerun()
                                st.divider()

        with chrono_main_tabs[9]:
            st.subheader("分析报告导出")
            st.caption("生成年代约束与沉积速率分析报告并导出")

            core_options = dict(zip(cores_df["sample_code"], cores_df["id"]))
            exp_core = st.selectbox("选择沉积柱样", list(core_options.keys()),
                                    key="export_core_select")
            exp_core_id = core_options[exp_core]

            col_exp1, col_exp2 = st.columns(2)
            with col_exp1:
                export_format = st.radio("导出格式", ["TXT文本报告", "CSV数据", "Excel (多Sheet)"])
            with col_exp2:
                include_annotations = st.checkbox("包含备注与修正记录", value=True)
                include_rates = st.checkbox("包含沉积速率数据", value=True)

            dating_points = db.get_dating_points(exp_core_id)
            saved_models = db.get_age_depth_models(exp_core_id)

            if dating_points.empty:
                st.warning("⚠️ 该柱样暂未录入年代点数据")
            else:
                model_result = None
                if not saved_models.empty:
                    latest = saved_models.iloc[0]
                    params = latest.get("model_params")
                    if isinstance(params, str):
                        try:
                            params = json.loads(params)
                        except:
                            params = {}
                    fit_points = dating_points[dating_points.get("is_valid", 1) == 1]
                    model_result = {
                        "success": True,
                        "model_type": latest["model_type"],
                        "model_params": params or {},
                        "r_squared": latest.get("r_squared"),
                        "rmse": latest.get("rmse"),
                        "depths": fit_points["depth"].tolist() if not fit_points.empty else [],
                        "ages": fit_points["age"].tolist() if not fit_points.empty else [],
                    }

                rates_df = pd.DataFrame()
                if model_result and model_result.get("success"):
                    layers_df = db.get_core_layers(exp_core_id)
                    rates_df = chrono.calculate_sedimentation_rates(
                        model_result,
                        layers_df if not layers_df.empty else None
                    )

                annotations_df = pd.DataFrame()
                if include_annotations:
                    annotations_df = db.get_chronology_annotations(exp_core_id)

                if st.button("📄 生成分析报告", type="primary", key="gen_chronology_report"):
                    with st.spinner("正在生成报告..."):
                        report = chrono.generate_chronology_report(
                            exp_core_id, dating_points,
                            model_result or {"success": False, "error": "未建立模型"},
                            rates_df if include_rates else pd.DataFrame(),
                            annotations_df if include_annotations else None
                        )
                        st.session_state["chronology_report_text"] = report
                        st.success("✅ 报告已生成")

                if "chronology_report_text" in st.session_state:
                    with st.expander("预览报告", expanded=True):
                        st.text(st.session_state["chronology_report_text"])

                    col_dl1, col_dl2 = st.columns(2)
                    with col_dl1:
                        st.download_button(
                            label="⬇️ 下载TXT报告",
                            data=st.session_state["chronology_report_text"],
                            file_name=f"年代约束分析报告_{exp_core}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                            mime="text/plain",
                            use_container_width=True
                        )

                    with col_dl2:
                        if not dating_points.empty:
                            output = BytesIO()
                            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                                dating_points.copy().to_excel(writer, sheet_name="年代点", index=False)
                                if model_result and not saved_models.empty:
                                    saved_models.to_excel(writer, sheet_name="模型列表", index=False)
                                if include_rates and not rates_df.empty:
                                    rates_df.to_excel(writer, sheet_name="沉积速率", index=False)
                                if include_annotations and not annotations_df.empty:
                                    annotations_df.to_excel(writer, sheet_name="备注记录", index=False)

                            excel_data = output.getvalue()
                            st.download_button(
                                label="⬇️ 下载Excel数据包",
                                data=excel_data,
                                file_name=f"年代约束数据包_{exp_core}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                use_container_width=True
                            )

                db.add_export_record(
                    export_type="chronology_report",
                    scope=exp_core,
                    filters={"format": export_format},
                    record_count=len(dating_points),
                    file_name=f"年代约束分析报告_{exp_core}_{datetime.now().strftime('%Y%m%d')}",
                    export_format="txt"
                )


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
