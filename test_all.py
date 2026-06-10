import database as db
import data_validator as validator
import analyzer
import quality_control as qc
import os
import sys

errors = []

def test(name, func):
    try:
        result = func()
        print(f"✅ {name}: {result}")
        return result
    except Exception as e:
        print(f"❌ {name}: {e}")
        errors.append((name, str(e)))
        return None

if os.path.exists("sediment_data.db"):
    os.remove("sediment_data.db")

print("=" * 50)
print("海底沉积柱样分析平台 - 综合功能测试")
print("=" * 50)

# 1. 数据库初始化
def t1():
    db.init_db()
    return "初始化成功"
test("数据库初始化", t1)

# 2. 创建测试数据
station_id = None
core_id_1 = None
core_id_2 = None
core_id_3 = None

def t2():
    global station_id, station_id2, core_id_1, core_id_2, core_id_3
    station_id = db.add_station("ST001", "测试站1", "东海")
    station_id2 = db.add_station("ST002", "测试站2", "南海")
    core_id_1 = db.add_core_sample(station_id, "ST001-C01", 100.0, "2024-01-15")
    core_id_2 = db.add_core_sample(station_id, "ST001-C02", 95.0, "2024-01-15")
    core_id_3 = db.add_core_sample(station_id2, "ST002-C01", 80.0, "2024-02-10")
    return f"2站位, 3柱样"
test("创建测试数据", t2)

# 3. 添加层位
def t3():
    layers = [
        {"layer_name": "表层砂", "depth_start": 0.0, "depth_end": 10.0,
         "gravel_pct": 5.0, "sand_pct": 60.0, "silt_pct": 25.0, "clay_pct": 10.0,
         "organic_matter": 2.0, "water_content": 30.0, "notes": "表层"},
        {"layer_name": "粉砂层", "depth_start": 10.0, "depth_end": 30.0,
         "gravel_pct": 2.0, "sand_pct": 30.0, "silt_pct": 45.0, "clay_pct": 23.0,
         "organic_matter": 1.5, "water_content": 25.0, "notes": ""},
        {"layer_name": "黏土层", "depth_start": 30.0, "depth_end": 50.0,
         "gravel_pct": 1.0, "sand_pct": 15.0, "silt_pct": 35.0, "clay_pct": 49.0,
         "organic_matter": 1.0, "water_content": 20.0, "notes": ""},
        {"layer_name": "砂层", "depth_start": 50.0, "depth_end": 70.0,
         "gravel_pct": 8.0, "sand_pct": 70.0, "silt_pct": 15.0, "clay_pct": 7.0,
         "organic_matter": 0.5, "water_content": 15.0, "notes": ""},
        {"layer_name": "黏土层", "depth_start": 70.0, "depth_end": 100.0,
         "gravel_pct": 0.5, "sand_pct": 10.0, "silt_pct": 30.0, "clay_pct": 59.5,
         "organic_matter": 0.8, "water_content": 18.0, "notes": ""},
    ]
    for l in layers:
        db.add_layer(core_id_1, l)

    layers2 = [
        {"layer_name": "表层砂", "depth_start": 0.0, "depth_end": 8.0,
         "gravel_pct": 6.0, "sand_pct": 55.0, "silt_pct": 28.0, "clay_pct": 11.0,
         "organic_matter": 2.5, "water_content": 32.0, "notes": ""},
        {"layer_name": "粉砂层", "depth_start": 8.0, "depth_end": 28.0,
         "gravel_pct": 3.0, "sand_pct": 32.0, "silt_pct": 42.0, "clay_pct": 23.0,
         "organic_matter": 1.8, "water_content": 26.0, "notes": ""},
        {"layer_name": "黏土层", "depth_start": 28.0, "depth_end": 52.0,
         "gravel_pct": 1.5, "sand_pct": 18.0, "silt_pct": 32.0, "clay_pct": 48.5,
         "organic_matter": 1.2, "water_content": 22.0, "notes": ""},
        {"layer_name": "砂层", "depth_start": 52.0, "depth_end": 72.0,
         "gravel_pct": 7.0, "sand_pct": 65.0, "silt_pct": 18.0, "clay_pct": 10.0,
         "organic_matter": 0.6, "water_content": 16.0, "notes": ""},
        {"layer_name": "黏土层", "depth_start": 72.0, "depth_end": 95.0,
         "gravel_pct": 0.8, "sand_pct": 12.0, "silt_pct": 28.0, "clay_pct": 59.2,
         "organic_matter": 0.9, "water_content": 19.0, "notes": ""},
    ]
    for l in layers2:
        db.add_layer(core_id_2, l)

    layers3 = [
        {"layer_name": "表层泥", "depth_start": 0.0, "depth_end": 20.0,
         "gravel_pct": 2.0, "sand_pct": 20.0, "silt_pct": 40.0, "clay_pct": 38.0,
         "organic_matter": 3.0, "water_content": 40.0, "notes": ""},
        {"layer_name": "粉砂质泥", "depth_start": 20.0, "depth_end": 50.0,
         "gravel_pct": 1.0, "sand_pct": 25.0, "silt_pct": 35.0, "clay_pct": 39.0,
         "organic_matter": 2.0, "water_content": 35.0, "notes": ""},
        {"layer_name": "泥层", "depth_start": 50.0, "depth_end": 80.0,
         "gravel_pct": 0.5, "sand_pct": 10.0, "silt_pct": 30.0, "clay_pct": 59.5,
         "organic_matter": 1.5, "water_content": 30.0, "notes": ""},
    ]
    for l in layers3:
        db.add_layer(core_id_3, l)

    n1 = len(db.get_core_layers(core_id_1))
    n2 = len(db.get_core_layers(core_id_2))
    n3 = len(db.get_core_layers(core_id_3))
    return f"柱样1:{n1}层, 柱样2:{n2}层, 柱样3:{n3}层"
test("添加层位数据", t3)

# 4. 单柱样分析
def t4():
    result = analyzer.get_core_analysis(core_id_1)
    layers = result["layers"]
    n = len(layers)
    thick = result["total_sampled_thickness"]
    recovery = result["recovery_rate"]
    missing = len(result["missing_intervals"])
    return f"{n}层, 总厚{thick}cm, 取芯率{recovery}%, 缺失{missing}段"
test("单柱样分析", t4)

# 5. 相关性矩阵
def t5():
    layers = db.get_core_layers(core_id_1)
    corr = analyzer.calculate_correlation(layers)
    return f"矩阵 {corr.shape[0]}x{corr.shape[1]}"
test("相关性分析矩阵", t5)

# 6. 多柱对比
def t6():
    comp = analyzer.compare_cores([core_id_1, core_id_2])
    n_combined = len(comp["combined_layers"])
    n_individual = len(comp["individual_analyses"])
    cross = comp.get("cross_correlation", {})
    return f"合并{n_combined}层, {n_individual}个独立分析, 交叉相关{len(cross)}指标"
test("多柱样对比", t6)

# 7. 层间相关性
def t7():
    inter = analyzer.analyze_interlayer_correlation([core_id_1, core_id_2])
    return f"{inter['total_layer_types']}种层位, {inter['analyzed_layer_types']}种可分析"
test("层间相关性分析", t7)

# 8. 站位分析
def t8():
    sa = analyzer.get_station_analysis("ST001")
    return f"{sa['core_count']}个柱样, {len(sa['layer_type_stats'])}种层位类型"
test("站位隔离统计", t8)

# 9. 质量扫描
def t9():
    scan = qc.scan_core_anomalies(core_id_1)
    n = scan["total_anomalies"]
    by_type = scan.get("by_type", {})
    types = ",".join([f"{k}:{v}" for k, v in by_type.items()])
    return f"{n}个异常, {types}"
test("质量异常扫描", t9)

# 10. 版本追踪
def t10():
    layers = db.get_core_layers(core_id_1)
    layer_id = layers.iloc[0]["id"]
    old_layer = layers.iloc[0].to_dict()
    update_data = old_layer.copy()
    update_data["gravel_pct"] = 6.0
    db.update_layer_with_version(layer_id, update_data, "测试修改砾石含量", "测试员")
    core_info = db.get_core_sample(core_id_1)
    versions = db.get_layer_versions(layer_id)
    return f"柱样版本v{core_info['version']}, 该层{len(versions)}个历史版本"
test("版本历史追踪", t10)

# 11. 异常复核流程
def t11():
    scan = qc.scan_core_anomalies(core_id_1)
    anomalies = scan.get("anomalies", [])
    if not anomalies:
        return "无异常可提交"
    first = anomalies[0]
    layer_id_a = first.get("layer_id", 0)
    review_id = qc.submit_anomaly_review(
        layer_id_a, core_id_1,
        first["anomaly_type"], first["anomaly_details"]
    )
    qc.review_anomaly(review_id, "reviewing", "核实中", "审核员A")
    qc.review_anomaly(review_id, "confirmed", "确认异常", "审核员A")
    return f"复核记录ID={review_id}, 状态=confirmed"
test("异常复核流转", t11)

# 12. 筛选功能
def t12():
    filters = {"station_code": "ST001", "min_core_length": 90.0}
    filtered = analyzer.filter_cores(filters)
    return f"筛选后{len(filtered)}个柱样"
test("全局筛选联动", t12)

# 13. 站位综合报告
def t13():
    report = analyzer.generate_station_report("ST001")
    return f"{report['report_title']}, {report['core_count']}柱样, {len(report.get('core_statistics', []))}项统计"
test("站位综合报告", t13)

# 14. 导入/导出记录
def t14():
    session_id = db.create_import_session("test.csv", 10, "测试导入")
    export_id = db.add_export_record("layers", "all", {}, 100, "test.csv", "csv")
    return f"导入会话{session_id}, 导出记录{export_id}"
test("导入导出记录", t14)

# 15. 缺失层段严重度
def t15():
    analysis = analyzer.get_core_analysis(core_id_1)
    missing = analysis["missing_intervals"]
    core_len = analysis["core_info"]["core_length"]
    sev = analyzer.get_missing_severity(missing, core_len)
    return f"完整度等级={sev['level']}, 缺失{sev.get('missing_percentage', 0):.1f}%"
test("缺失层段分级预警", t15)

# 16. 质量控制面板
def t16():
    dashboard = qc.get_quality_dashboard_data()
    overall = dashboard["overall"]
    return f"{overall['total_stations']}站/{overall['total_cores']}样/{overall['total_anomalies']}异常"
test("质量控制总览", t16)

# 17. 数据验证器
def t17():
    ok, err = validator.validate_percentages(30, 30, 30, 10)
    if not ok:
        return f"校验失败: {err}"
    ok2, err2 = validator.validate_layer_edit(core_id_1, 999, 0, 10)
    return f"百分比校验通过, 层位编辑校验={ok2}"
test("数据校验与冲突检测", t17)

print("\n" + "=" * 50)
if errors:
    print(f"❌ 测试失败: {len(errors)} 项")
    for name, err in errors:
        print(f"  - {name}: {err}")
    sys.exit(1)
else:
    print("✅ 所有功能测试通过!")
    print("=" * 50)
