import sqlite3

db_path = r'c:\Users\lbisa\OneDrive\Documentos\soft\Line 6\MondoPedalboardSuite\user_data\MondoPBSuite.db'

def init_combinations_test():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Drop table to recreate with response_data
    cursor.execute('DROP TABLE IF EXISTS cabs_frequency_response')

    # Create the table with the UNIQUE constraint and foreign keys
    cursor.execute('''
    CREATE TABLE cabs_frequency_response (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cab_id INTEGER,
        mic_id INTEGER,
        position REAL,
        distance REAL,
        response_data BLOB,
        UNIQUE(cab_id, mic_id, position, distance),
        FOREIGN KEY(cab_id) REFERENCES cabs(id),
        FOREIGN KEY(mic_id) REFERENCES cabs_mics(id)
    )
    ''')

    # Get the first 2 cabs
    cursor.execute('SELECT id, cap_edge_position FROM cabs ORDER BY id LIMIT 2')
    test_cabs = cursor.fetchall()

    test_mics = [0, 5]
    test_distances = [1.0, 3.5]
    
    combinations_added = 0

    for cab in test_cabs:
        cab_id = cab[0]
        cap_edge = cab[1] if cab[1] is not None else 3.0
        
        test_positions = [0.0, cap_edge]
        
        for mic_id in test_mics:
            for position in test_positions:
                for distance in test_distances:
                    cursor.execute('''
                    INSERT OR IGNORE INTO cabs_frequency_response (cab_id, mic_id, position, distance)
                    VALUES (?, ?, ?, ?)
                    ''', (cab_id, mic_id, position, distance))
                    
                    if cursor.rowcount > 0:
                        combinations_added += 1

    conn.commit()
    
    # Check total rows in the table
    cursor.execute('SELECT COUNT(*) FROM cabs_frequency_response')
    total_rows = cursor.fetchone()[0]
    
    print(f"Test combinations added: {combinations_added}")
    print(f"Total rows in table: {total_rows}")
    
    conn.close()

if __name__ == '__main__':
    init_combinations_test()
