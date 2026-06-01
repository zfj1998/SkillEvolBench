"""Database query module."""
import sqlite3

DB_PATH = "app.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_user_by_id(user_id):
<<<<<<< HEAD
    """Get user by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")
    user = cursor.fetchone()
    conn.close()
    return dict(user) if user else None


def search_users(query):
    """Search users by name. NEW FEATURE."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM users WHERE name LIKE '%{query}%'")
    users = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return users
=======
    """Get user by ID - improved query."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return dict(user) if user else None
>>>>>>> security/fix-sql-injection


def get_all_users():
    conn = get_connection()
    cursor = conn.cursor()
<<<<<<< HEAD
    cursor.execute("SELECT * FROM users")
=======
    cursor.execute("SELECT * FROM users")
>>>>>>> security/fix-sql-injection
    users = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return users


def create_user(name, email):
    conn = get_connection()
    cursor = conn.cursor()
<<<<<<< HEAD
    cursor.execute(f"INSERT INTO users (name, email) VALUES ('{name}', '{email}')")
=======
    cursor.execute("INSERT INTO users (name, email) VALUES (?, ?)", (name, email))
>>>>>>> security/fix-sql-injection
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()
    return user_id
