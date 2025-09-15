import os
import sqlite3
from datetime import datetime

def init_db():
    """Initialize the database and create tables if they don't exist"""
    # Get absolute path to database directory
    base_dir = os.path.dirname(os.path.dirname(__file__))
    db_dir = os.path.join(base_dir, 'database')
    db_path = os.path.join(db_dir, 'ssp_database.db')
    
    # Create database directory if it doesn't exist
    os.makedirs(db_dir, exist_ok=True)
    
    print(f"📁 Database directory: {db_dir}")
    print(f"📄 Database path: {db_path}")
    
    # Connect to database (creates it if it doesn't exist)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("🔨 Creating database tables...")

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
    print("✅ Created transactions table")

    # Create CashInventory table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS cash_inventory (
        denomination REAL PRIMARY KEY,
        count INTEGER NOT NULL,
        type TEXT NOT NULL,
        last_updated DATETIME NOT NULL
    )
    ''')
    print("✅ Created cash_inventory table")

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
    print("✅ Created error_log table")

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
    print("✅ Created printer_status table")

    conn.commit()
    conn.close()
    print("✅ Database initialization complete")