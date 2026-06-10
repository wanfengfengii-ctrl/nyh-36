import database as db
import os
import sqlite3

if os.path.exists('test_version.db'):
    os.remove('test_version.db')

db.DB_PATH = 'test_version.db'
db.init_db()

station_id = db.add_station('ST001', 'Test', 'Loc')
core_id = db.add_core_sample(station_id, 'C01', 100.0, '2024-01-01')

layer_data = {
    'layer_name': 'sand', 'depth_start': 0.0, 'depth_end': 10.0,
    'gravel_pct': 5.0, 'sand_pct': 60.0, 'silt_pct': 25.0, 'clay_pct': 10.0,
    'organic_matter': 2.0, 'water_content': 30.0, 'notes': ''
}
layer_id = db.add_layer(core_id, layer_data)
print(f'layer_id = {layer_id}')

core_before = db.get_core_sample(core_id)
print(f'core version before: {core_before["version"]}')

# 完整更新
full_update = {
    'layer_name': 'sand', 'depth_start': 0.0, 'depth_end': 10.0,
    'gravel_pct': 6.0, 'sand_pct': 60.0, 'silt_pct': 25.0, 'clay_pct': 10.0,
    'organic_matter': 2.0, 'water_content': 30.0, 'notes': ''
}
db.update_layer_with_version(layer_id, full_update, 'test change', 'tester')

core_after = db.get_core_sample(core_id)
print(f'core version after: {core_after["version"]}')

versions = db.get_layer_versions(layer_id)
print(f'versions count: {len(versions)}')

db.DB_PATH = 'sediment_data.db'
os.remove('test_version.db')
