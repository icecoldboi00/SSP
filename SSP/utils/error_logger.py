import threading
from database.db_manager import DatabaseManager

_thread_local = threading.local()

def get_db_manager():
    if not hasattr(_thread_local, 'db_manager'):
        _thread_local.db_manager = DatabaseManager()
    return _thread_local.db_manager

def log_error(error_type, message, context):
    try:
        db = get_db_manager()
        db.log_error(error_type, message, context)
    except Exception as e:
        print(f"Original error: {error_type} - {message}")

def cleanup_db_connections():
    try:
        if hasattr(_thread_local, 'db_manager'):
            _thread_local.db_manager.close()
            delattr(_thread_local, 'db_manager')
    except Exception as e:
        print(f"Error cleaning up database connections: {e}")

# Has its own connection to the database
# For writing errors to the database instead of creating a new connection for each error