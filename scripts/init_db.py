import sqlite3
import json
import os

db_path = r'c:\Users\lbisa\OneDrive\Documentos\soft\Line 6\MondoPedalboardSuite\user_data\MondoPBSuite.db'
json_path = r'c:\Users\lbisa\OneDrive\Documentos\soft\Line 6\MondoPedalboardSuite\utils\cabs_mics.json'

def init_db():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS cabs_mics (
        id INTEGER PRIMARY KEY,
        model TEXT,
        type TEXT,
        captured_from TEXT,
        tips TEXT
    )
    ''')

    with open(json_path, 'r', encoding='utf-8') as f:
        mics_data = json.load(f)

    for mic in mics_data:
        cursor.execute('''
        INSERT OR REPLACE INTO cabs_mics (id, model, type, captured_from, tips)
        VALUES (?, ?, ?, ?, ?)
        ''', (mic['id'], mic['model'], mic['type'], mic['captured_from'], mic.get('tips', '')))

    conn.commit()
    conn.close()
    print("Database created and cabs_mics populated.")

if __name__ == '__main__':
    init_db()
