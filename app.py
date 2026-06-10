import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import database as db
import data_validator as validator
import analyzer
import visualizer


st.set_page_config(
    page_title="海底沉积柱样分层判读与指标关联分析平台",
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
    </style>
""", unsafe_allow_html=True)


st.markdown("""
    <div class="main-header">
        <h1>🌊 海底沉积柱样分层判读与指标关联分析平台</h1>
        <p style="opacity: 0.9; margin-top: 0.5rem;">
            海洋地质沉积柱样数据管理、可视化与统计分析系统
        </p>
    </div>
""", unsafe_allow_html=True)


with st.sidebar:
    st.header("导航菜单")
    page = st.radio(
        "选择功能模块",
        ["📊 数据总览", "📥 数据导入", "🔬 单柱样分析", "📈 多柱样对比", "⚙️ 数据管理"]
    )


if page == "📊 数据总览":
    st.header("数据总览")

    col1, col2, col3, col4 = st.columns(4)

    stations_df = db.get_all_stations()
    cores_df = db.get_all_core_samples()

    total_layers = 0
    for _, core in cores_df.iterrows():
        layers = db.get_core_layers(core["id"])
        total_layers += len(layers)

    errors_df = db.get_import_errors(10)

    with col1:
        st.metric("采样站位数", len(stations_df))
    with col2:
        st.metric("沉积柱样数", len(cores_df))
    with col3:
        st.metric("层位记录数", total_layers)
    with col4:
        st.metric("导入错误记录", len(errors_df))

    st.subheader("采样站位列表")
    if not stations_df.empty:
        st.dataframe(
            stations_df[["station_code", "station_name", "location", "created_at"]],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("暂无采样站位数据，请先导入CSV文件。")

    st.subheader("沉积柱样列表")
    if not cores_df.empty:
        display_df = cores_df[["sample_code", "station_code", "core_length", "sampling_date", "created_at"]].copy()
        display_df.columns = ["样品编号", "站位编号", "柱长(cm)", "采样日期", "创建时间"]
        st.dataframe(display_df, use_container_width=True, hide_index=True)
    else:
        st.info("暂无沉积柱样数据，请先导入CSV文件。")

    if len(errors_df) > 0:
        st.subheader("最近导入错误")
        error_display = errors_df[["file_name", "row_number", "error_reason", "created_at"]].copy()
        error_display.columns = ["文件名", "行号", "错误原因", "时间"]
        st.dataframe(error_display, use_container_width=True, hide_index=True)


elif page == "📥 数据导入":
    st.header("数据导入")

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
    overwrite_mode = st.checkbox("覆盖已存在的同名柱样数据", value=True,
                                  help="如果勾选，重复导入同名柱样时将先清除旧数据再导入新数据")

    if uploaded_file is not None:
        try:
            success_count, skipped_count, errors = validator.import_csv(
                uploaded_file, uploaded_file.name, overwrite_existing=overwrite_mode
            )

            if success_count > 0:
                st.success(f"✅ 成功导入 {success_count} 条层位记录")
            if skipped_count > 0 and not overwrite_mode:
                st.info(f"ℹ️ 跳过 {skipped_count} 条已存在的柱样记录")

            if errors:
                st.warning(f"⚠️ 有 {len(errors)} 条记录导入失败")
                st.subheader("导入失败记录详情")

                error_rows = []
                for err in errors:
                    row_dict = err["row_data"]
                    row_dict["错误原因"] = err["error_reason"]
                    row_dict["行号"] = err["row_number"]
                    error_rows.append(row_dict)

                error_df = pd.DataFrame(error_rows)
                cols = ["行号", "错误原因"] + [c for c in error_df.columns if c not in ["行号", "错误原因"]]
                st.dataframe(error_df[cols], use_container_width=True, hide_index=True)

        except ValueError as e:
            st.error(f"❌ 文件格式错误: {str(e)}")
        except Exception as e:
            st.error(f"❌ 导入失败: {str(e)}")

    if st.button("清空导入错误记录"):
        db.clear_import_errors()
        st.success("已清空导入错误记录")


elif page == "🔬 单柱样分析":
    st.header("单柱样详细分析")

    cores_df = db.get_all_core_samples()
    if cores_df.empty:
        st.info("暂无沉积柱样数据，请先导入CSV文件。")
    else:
        core_options = dict(zip(cores_df["sample_code"], cores_df["id"]))
        selected_core = st.selectbox("选择沉积柱样", list(core_options.keys()))
        core_id = core_options[selected_core]

        analysis = analyzer.get_core_analysis(core_id)

        if not analysis or analysis["layers"].empty:
            st.warning("该柱样暂无层位数据")
        else:
            layers_df = analysis["layers"]
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("总采样厚度", f"{analysis.get('total_sampled_thickness', 0):.1f} cm")
            with col2:
                st.metric("缺失层段厚度", f"{analysis.get('total_missing_thickness', 0):.1f} cm")
            with col3:
                st.metric("取芯率", f"{analysis.get('recovery_rate', 0):.1f}%")
            with col4:
                st.metric("层位数量", f"{len(layers_df)} 层")

            tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
                "📋 层位数据表", "📊 分层剖面图", "📈 指标趋势图",
                "🔴 异常检测", "🔗 相关性分析", "📊 层位统计"
            ])

            with tab1:
                st.subheader("层位数据")
                display_layers = layers_df[[
                    "layer_name", "depth_start", "depth_end", "thickness",
                    "gravel_pct", "sand_pct", "silt_pct", "clay_pct",
                    "organic_matter", "water_content"
                ]].copy()
                display_layers.columns = [
                    "层位名称", "深度起点(cm)", "深度终点(cm)", "厚度(cm)",
                    "砾石(%)", "砂(%)", "粉砂(%)", "黏土(%)",
                    "有机质(%)", "含水率(%)"
                ]
                st.dataframe(display_layers, use_container_width=True, hide_index=True)

                if analysis["missing_intervals"]:
                    st.warning("检测到缺失深度区段:")
                    missing_df = pd.DataFrame(analysis["missing_intervals"])
                    missing_df.columns = ["深度起点(cm)", "深度终点(cm)", "厚度(cm)"]
                    st.dataframe(missing_df, use_container_width=True, hide_index=True)

            with tab2:
                core_length = analysis["core_info"].get("core_length")
                fig_section = visualizer.plot_core_section(
                    layers_df, analysis["missing_intervals"],
                    title=f"{selected_core} 分层剖面图",
                    core_length=core_length
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
                    anomaly_display = anomaly_only[[
                        "layer_name", "depth_start", "depth_end", "thickness",
                        "anomaly_details"
                    ]].copy()
                    anomaly_display.columns = [
                        "层位名称", "深度起点", "深度终点", "厚度", "异常指标"
                    ]
                    st.dataframe(anomaly_display, use_container_width=True, hide_index=True)

            with tab5:
                corr_matrix = analysis["correlation"]
                if corr_matrix.empty:
                    st.info("数据不足，无法计算相关性")
                else:
                    fig_corr = visualizer.plot_correlation_heatmap(
                        corr_matrix, title=f"{selected_core} 指标相关性矩阵"
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


elif page == "📈 多柱样对比":
    st.header("多柱样对比分析")

    cores_df = db.get_all_core_samples()
    if cores_df.empty:
        st.info("暂无沉积柱样数据，请先导入CSV文件。")
    else:
        station_grouped = cores_df.groupby("station_code")["sample_code"].apply(list).to_dict()

        st.subheader("选择对比柱样")
        comparison_mode = st.radio("选择模式", ["按站位选择", "手动选择多个柱样"])

        selected_cores = []

        if comparison_mode == "按站位选择":
            if station_grouped:
                selected_station = st.selectbox("选择站位", list(station_grouped.keys()))
                selected_cores = station_grouped[selected_station]
                if len(selected_cores) < 2:
                    st.warning("该站位下柱样数量不足2个，无法对比")
            else:
                st.info("暂无站位数据")
        else:
            selected_cores = st.multiselect(
                "选择要对比的柱样（至少2个）",
                cores_df["sample_code"].tolist()
            )
            if len(selected_cores) < 2:
                st.warning("请至少选择2个柱样进行对比")

        if len(selected_cores) >= 2:
            core_id_map = dict(zip(cores_df["sample_code"], cores_df["id"]))
            core_ids = [core_id_map[code] for code in selected_cores]

            comparison = analyzer.compare_cores(core_ids)

            tab1, tab2, tab3 = st.tabs([
                "📊 并排分层对比", "📈 指标对比", "📋 统计数据对比"
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
                        }.get(x, x)
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

                    import plotly.express as px
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
                st.subheader("各柱样关键指标对比")

                stats_rows = []
                for core_code, core_data in comparison["individual_analyses"].items():
                    layers = core_data["layers"]
                    if layers.empty:
                        continue
                    stats_rows.append({
                        "柱样编号": core_code,
                        "层数": len(layers),
                        "总厚度(cm)": f"{core_data.get('total_sampled_thickness', 0):.1f}",
                        "取芯率(%)": f"{core_data.get('recovery_rate', 0):.1f}",
                        "平均砂(%)": f"{layers['sand_pct'].mean():.1f}",
                        "平均粉砂(%)": f"{layers['silt_pct'].mean():.1f}",
                        "平均黏土(%)": f"{layers['clay_pct'].mean():.1f}",
                        "平均有机质(%)": f"{layers['organic_matter'].mean():.1f}" if "organic_matter" in layers.columns and layers["organic_matter"].notna().any() else "N/A",
                        "平均含水率(%)": f"{layers['water_content'].mean():.1f}" if "water_content" in layers.columns and layers["water_content"].notna().any() else "N/A",
                    })

                if stats_rows:
                    st.dataframe(pd.DataFrame(stats_rows), use_container_width=True, hide_index=True)

                st.info("⚠️ 注意：不同采样站位的数据不直接合并统计，以上为各柱样独立统计结果的对比展示。")


elif page == "⚙️ 数据管理":
    st.header("数据管理")

    cores_df = db.get_all_core_samples()
    if cores_df.empty:
        st.info("暂无沉积柱样数据。")
    else:
        management_tab = st.tabs(["编辑层位", "删除数据"])

        with management_tab[0]:
            st.subheader("编辑层位记录")
            core_options = dict(zip(cores_df["sample_code"], cores_df["id"]))
            edit_core = st.selectbox(
                "选择柱样",
                list(core_options.keys()),
                key="edit_core_select"
            )
            edit_core_id = core_options[edit_core]

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

                if st.button("保存修改", key="save_layer_edit"):
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
                        db.update_layer(layer_id, updated_data)
                        st.success("✅ 修改已保存，厚度和相关性分析将自动重新计算")
                        st.rerun()

        with management_tab[1]:
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
