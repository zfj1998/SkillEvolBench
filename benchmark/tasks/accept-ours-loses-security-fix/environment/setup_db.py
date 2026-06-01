"""Database setup helper."""
import sqlite3


def setup_database(db_path="app.db"):
    """Create and populate test database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL
        )
    """)
    # Clear existing data
    cursor.execute("DELETE FROM users")
    # Insert test data
    test_users = [
        ("Alice Smith", "alice@example.com"),
        ("Bob Jones", "bob@example.com"),
        ("Charlie Brown", "charlie@example.com"),
        ("Alice Johnson", "alicej@example.com"),
    ]
    cursor.executemany("INSERT INTO users (name, email) VALUES (?, ?)", test_users)
    conn.commit()
    conn.close()


if __name__ == "__main__":
    setup_database()
    print("Database setup complete")
