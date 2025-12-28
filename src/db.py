from sqlmodel import SQLModel, create_engine, Session

from src.models import CreditCard, RewardRule, RedemptionPartner, CapBucket, Expense

# 1. The Database Name
sqlite_file_name = "data/finance.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

# 2. The Engine
# check_same_thread=False is needed for SQLite when using it with web servers/MCP
engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})


# 3. The Initialization Function
def create_db_and_tables():
    """
    Creates the database file and all tables defined in src.models.
    Run this once when you set up the project or change the schema.
    """
    # This magic line looks at all SQLModel classes imported above
    # and generates the standard SQL 'CREATE TABLE' commands.
    SQLModel.metadata.create_all(engine)


# 4. Helper to get a session (Optional but useful for scripts)
def get_session():
    with Session(engine) as session:
        yield session
