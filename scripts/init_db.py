# scripts/init_db.py
from src import create_db_and_tables


def init():
    print("🔄 Initializing Database...")

    try:
        # This creates the tables defined in your models
        create_db_and_tables()
        print("✅ Success: Database tables created at 'data/finance.db'.")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    init()
