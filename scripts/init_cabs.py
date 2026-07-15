import sqlite3
import json
import os

db_path = r'c:\Users\lbisa\OneDrive\Documentos\soft\Line 6\MondoPedalboardSuite\user_data\MondoPBSuite.db'
json_path = r'c:\Users\lbisa\OneDrive\Documentos\soft\Line 6\MondoPedalboardSuite\utils\modules.json'

def init_cabs():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS cabs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        model_id TEXT UNIQUE,
        hex_id TEXT UNIQUE,
        name TEXT,
        based_on TEXT,
        subcategory TEXT,
        cap_edge_position REAL
    )
    ''')

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    models = data.get('models', {})
    usb_mapping = data.get('usb_mapping', {})

    for hex_id, mapping_info in usb_mapping.items():
        model_id = mapping_info.get('model_id')
        if not model_id:
            continue
        
        model_data = models.get(model_id)
        if not model_data:
            continue
            
        if model_data.get('category') == 'Cab':
            name = model_data.get('name', '')
            based_on = model_data.get('based_on', '')
            subcategory = 'normal'
            
            cap_edge_position = 3.0 # Default value, user will update manually
            
            cursor.execute('''
            INSERT OR IGNORE INTO cabs (model_id, hex_id, name, based_on, subcategory, cap_edge_position)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (model_id, hex_id, name, based_on, subcategory, cap_edge_position))

    conn.commit()
    conn.close()
    print("Table cabs recreated with auto-incremental ID and populated.")

if __name__ == '__main__':
    init_cabs()
