import os
import sqlite3
from datetime import datetime

def init_db():
    base_dir = os.path.dirname(os.path.dirname(__file__))
    db_dir = os.path.join(base_dir, 'database')
    db_path = os.path.join(db_dir, 'ssp_database.db')
    
    # Create database directory if it doesn't exist
    os.makedirs(db_dir, exist_ok=True)
    
    print(f"Database directory: {db_dir}")
    print(f"Database path: {db_path}")
    
    # Connect to database (creates it if it doesn't exist)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("Creating database tables")

    # Create Transactions table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME NOT NULL,
        file_name TEXT NOT NULL,
        pages INTEGER NOT NULL,
        copies INTEGER NOT NULL,
        color_mode TEXT NOT NULL,
        total_cost REAL NOT NULL,
        amount_paid REAL NOT NULL,
        change_given REAL NOT NULL,
        status TEXT NOT NULL,
        error_message TEXT
    )
    ''')
    print("Created transactions table")

    # Create CashInventory table
    # Use composite PRIMARY KEY to allow both coin and bill for same denomination (e.g., 20 coin and 20 bill)
    # Check if table exists and has old schema (single PRIMARY KEY on denomination)
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cash_inventory'")
        table_exists = cursor.fetchone() is not None
        
        if table_exists:
            # Check if we can insert both 20 coin and 20 bill (test for composite key support)
            try:
                test_time = datetime.now()
                cursor.execute("INSERT INTO cash_inventory (denomination, type, count, last_updated) VALUES (999, 'test', 0, ?)", (test_time,))
                cursor.execute("INSERT INTO cash_inventory (denomination, type, count, last_updated) VALUES (999, 'test2', 0, ?)", (test_time,))
                cursor.execute("DELETE FROM cash_inventory WHERE denomination = 999")
                conn.commit()
                # If we got here, composite key works - table is already correct
                print("Cash inventory table already has composite key schema")
            except sqlite3.IntegrityError:
                # Can't insert duplicate denomination - old schema detected, need to migrate
                print("Detected old cash_inventory schema, migrating to new composite key schema...")
                # Create new table with correct schema
                cursor.execute('''
                CREATE TABLE cash_inventory_new (
                    denomination REAL NOT NULL,
                    type TEXT NOT NULL,
                    count INTEGER NOT NULL,
                    last_updated DATETIME NOT NULL,
                    PRIMARY KEY (denomination, type)
                )
                ''')
                # Copy data from old table
                cursor.execute('''
                INSERT OR IGNORE INTO cash_inventory_new (denomination, type, count, last_updated)
                SELECT denomination, type, count, last_updated FROM cash_inventory
                ''')
                # Drop old table
                cursor.execute('DROP TABLE cash_inventory')
                # Rename new table
                cursor.execute('ALTER TABLE cash_inventory_new RENAME TO cash_inventory')
                conn.commit()
                print("Migration complete")
        else:
            # Table doesn't exist, create with new schema
            cursor.execute('''
            CREATE TABLE cash_inventory (
                denomination REAL NOT NULL,
                type TEXT NOT NULL,
                count INTEGER NOT NULL,
                last_updated DATETIME NOT NULL,
                PRIMARY KEY (denomination, type)
            )
            ''')
            print("Created cash_inventory table with composite key")
    except Exception as e:
        print(f"Error checking/migrating cash_inventory schema: {e}")
        # Fallback: try to create table if it doesn't exist
        try:
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS cash_inventory (
                denomination REAL NOT NULL,
                type TEXT NOT NULL,
                count INTEGER NOT NULL,
                last_updated DATETIME NOT NULL,
                PRIMARY KEY (denomination, type)
            )
            ''')
            print("Created cash_inventory table (fallback)")
        except Exception as e2:
            print(f"Error creating cash_inventory table: {e2}")

    # Create ErrorLog table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS error_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME NOT NULL,
        error_type TEXT NOT NULL,
        error_message TEXT NOT NULL,
        screen_name TEXT NOT NULL,
        resolved BOOLEAN DEFAULT FALSE
    )
    ''')
    print("Created error_log table")

    # Create PrinterStatus table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS printer_status (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME NOT NULL,
        paper_count INTEGER NOT NULL,
        ink_level INTEGER,
        status TEXT NOT NULL
    )
    ''')
    print("Created printer_status table")

    # Create CMYK Ink Levels table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS cmyk_ink_levels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME NOT NULL,
        cyan_level REAL NOT NULL,
        magenta_level REAL NOT NULL,
        yellow_level REAL NOT NULL,
        black_level REAL NOT NULL,
        last_updated DATETIME NOT NULL
    )
    ''')
    print("Created cmyk_ink_levels table")

    # Create Settings table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    ''')
    print("Created settings table")

    # Initialize default settings if they don't exist
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('paper_count', '100')")
    print("Initialized paper_count setting")
    
    # Initialize default CMYK ink levels if none exist
    cursor.execute("SELECT COUNT(*) FROM cmyk_ink_levels")
    cmyk_count = cursor.fetchone()[0]
    if cmyk_count == 0:
        from datetime import datetime
        cursor.execute("""
            INSERT INTO cmyk_ink_levels (cyan_level, magenta_level, yellow_level, black_level, timestamp, last_updated)
            VALUES (100.0, 100.0, 100.0, 100.0, ?, ?)
        """, (datetime.now(), datetime.now()))
        print("Initialized default CMYK ink levels (100%)")
    else:
        print("CMYK ink levels already exist")

    # Initialize default cash inventory if entries don't exist
    # Check if cash inventory is empty
    cursor.execute("SELECT COUNT(*) FROM cash_inventory")
    cash_count = cursor.fetchone()[0]
    if cash_count == 0:
        now = datetime.now()
        # Initialize coins: 1 peso, 5 peso, 20 peso coin
        cursor.execute("""
            INSERT INTO cash_inventory (denomination, count, type, last_updated)
            VALUES (1, 100, 'coin', ?)
        """, (now,))
        cursor.execute("""
            INSERT INTO cash_inventory (denomination, count, type, last_updated)
            VALUES (5, 50, 'coin', ?)
        """, (now,))
        cursor.execute("""
            INSERT INTO cash_inventory (denomination, count, type, last_updated)
            VALUES (20, 0, 'coin', ?)
        """, (now,))
        # Initialize bills: 20 peso, 50 peso, 100 peso
        cursor.execute("""
            INSERT INTO cash_inventory (denomination, count, type, last_updated)
            VALUES (20, 0, 'bill', ?)
        """, (now,))
        cursor.execute("""
            INSERT INTO cash_inventory (denomination, count, type, last_updated)
            VALUES (50, 0, 'bill', ?)
        """, (now,))
        cursor.execute("""
            INSERT INTO cash_inventory (denomination, count, type, last_updated)
            VALUES (100, 0, 'bill', ?)
        """, (now,))
        print("Initialized default cash inventory (1, 5, 20 coins and 20, 50, 100 bills)")
    else:
        # Ensure 20 coin, 50 bill, and 100 bill exist (add if missing)
        now = datetime.now()
        # Check and add 20 coin if missing
        cursor.execute("SELECT COUNT(*) FROM cash_inventory WHERE denomination = 20 AND type = 'coin'")
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                INSERT INTO cash_inventory (denomination, count, type, last_updated)
                VALUES (20, 0, 'coin', ?)
            """, (now,))
            print("Added 20 peso coin to inventory")
        # Check and add 50 bill if missing
        cursor.execute("SELECT COUNT(*) FROM cash_inventory WHERE denomination = 50 AND type = 'bill'")
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                INSERT INTO cash_inventory (denomination, count, type, last_updated)
                VALUES (50, 0, 'bill', ?)
            """, (now,))
            print("Added 50 peso bill to inventory")
        # Check and add 100 bill if missing
        cursor.execute("SELECT COUNT(*) FROM cash_inventory WHERE denomination = 100 AND type = 'bill'")
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                INSERT INTO cash_inventory (denomination, count, type, last_updated)
                VALUES (100, 0, 'bill', ?)
            """, (now,))
            print("Added 100 peso bill to inventory")

    conn.commit()
    conn.close()
    print("Database initialization complete")