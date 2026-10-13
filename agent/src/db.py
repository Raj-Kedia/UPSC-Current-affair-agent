import sqlite3
import os
import hashlib
import secrets
import datetime
from src.config import DATA_DIR, logger

DB_PATH = os.path.join(DATA_DIR, 'agent_users.db')

def get_db_connection():
    """Create and return a database connection with row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password: str, salt: str = None) -> tuple[str, str]:
    """Hash password using PBKDF2-HMAC-SHA256."""
    if salt is None:
        salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    )
    return key.hex(), salt

def verify_password(password: str, password_hash: str, salt: str) -> bool:
    """Verify provided password matches stored hash."""
    test_hash, _ = hash_password(password, salt)
    return test_hash == password_hash

def init_db():
    """Initialize database tables and create default admin account if not present."""
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = get_db_connection()
    cursor = conn.cursor()

    # Users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        salt TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'user',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Subscriptions table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS subscriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        email TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending', -- 'pending', 'active', 'cancelled'
        frequency TEXT NOT NULL DEFAULT 'weekly',
        requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        activated_at TIMESTAMP,
        cancelled_at TIMESTAMP,
        notes TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    # Active sessions table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        token TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expires_at TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    conn.commit()

    # Ensure default Admin exists
    cursor.execute("SELECT id FROM users WHERE role = 'admin'")
    admin_user = cursor.fetchone()
    if not admin_user:
        admin_email = "admin@upscagent.com"
        admin_pass = "admin123"
        pwd_hash, salt = hash_password(admin_pass)
        try:
            cursor.execute(
                "INSERT INTO users (name, email, password_hash, salt, role) VALUES (?, ?, ?, ?, ?)",
                ("System Administrator", admin_email, pwd_hash, salt, "admin")
            )
            conn.commit()
            logger.info(f"Default admin initialized: {admin_email}")
        except sqlite3.IntegrityError:
            pass

    conn.close()

def register_user(name: str, email: str, password: str, role: str = 'user'):
    """Register a new user."""
    conn = get_db_connection()
    cursor = conn.cursor()
    email_clean = email.strip().lower()
    
    # Check if user already exists
    cursor.execute("SELECT id FROM users WHERE email = ?", (email_clean,))
    if cursor.fetchone():
        conn.close()
        return None, "An account with this email already exists."

    pwd_hash, salt = hash_password(password)
    try:
        cursor.execute(
            "INSERT INTO users (name, email, password_hash, salt, role) VALUES (?, ?, ?, ?, ?)",
            (name.strip(), email_clean, pwd_hash, salt, role)
        )
        user_id = cursor.lastrowid
        conn.commit()
        
        # Create session
        token = create_session(user_id)
        user = get_user_by_id(user_id)
        conn.close()
        return {"user": user, "token": token}, None
    except Exception as e:
        conn.close()
        return None, str(e)

def authenticate_user(email: str, password: str):
    """Authenticate user credentials and return user info with session token."""
    conn = get_db_connection()
    cursor = conn.cursor()
    email_clean = email.strip().lower()
    
    cursor.execute("SELECT * FROM users WHERE email = ?", (email_clean,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return None, "Invalid email or password."
        
    user_dict = dict(row)
    if not verify_password(password, user_dict['password_hash'], user_dict['salt']):
        return None, "Invalid email or password."
        
    token = create_session(user_dict['id'])
    safe_user = {
        "id": user_dict['id'],
        "name": user_dict['name'],
        "email": user_dict['email'],
        "role": user_dict['role'],
        "created_at": user_dict['created_at']
    }
    return {"user": safe_user, "token": token}, None

def create_session(user_id: int) -> str:
    """Create a persistent session token."""
    conn = get_db_connection()
    cursor = conn.cursor()
    token = secrets.token_hex(32)
    # Session expires in 30 days
    expires_at = datetime.datetime.now() + datetime.timedelta(days=30)
    cursor.execute(
        "INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
        (token, user_id, expires_at.isoformat())
    )
    conn.commit()
    conn.close()
    return token

def get_user_by_token(token: str):
    """Fetch user by valid session token."""
    if not token:
        return None
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.id, u.name, u.email, u.role, u.created_at 
        FROM sessions s
        JOIN users u ON s.user_id = u.id
        WHERE s.token = ?
    """, (token,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def get_user_by_id(user_id: int):
    """Fetch safe user dict by ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, email, role, created_at FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def delete_session(token: str):
    """Log out / invalidate session."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sessions WHERE token = ?", (token,))
    conn.commit()
    conn.close()

# Subscription operations

def request_weekly_subscription(user_id: int, email: str, notes: str = ""):
    """Request weekly newsletter activation for given user and email."""
    conn = get_db_connection()
    cursor = conn.cursor()
    email_clean = email.strip().lower()
    
    # Check if a subscription already exists for this user
    cursor.execute("SELECT id, status FROM subscriptions WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    
    now_str = datetime.datetime.now().isoformat()
    if row:
        sub_id = row['id']
        cursor.execute("""
            UPDATE subscriptions 
            SET email = ?, status = 'pending', requested_at = ?, notes = ?
            WHERE id = ?
        """, (email_clean, now_str, notes, sub_id))
    else:
        cursor.execute("""
            INSERT INTO subscriptions (user_id, email, status, frequency, requested_at, notes)
            VALUES (?, ?, 'pending', 'weekly', ?, ?)
        """, (user_id, email_clean, now_str, notes))
        sub_id = cursor.lastrowid
        
    conn.commit()
    cursor.execute("SELECT * FROM subscriptions WHERE id = ?", (sub_id,))
    updated_sub = dict(cursor.fetchone())
    conn.close()
    return updated_sub

def get_user_subscription(user_id: int):
    """Retrieve subscription record for specific user."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM subscriptions WHERE user_id = ? ORDER BY id DESC LIMIT 1", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def get_all_subscriptions(status_filter: str = None):
    """Retrieve all subscriptions with user details for admin management."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = """
        SELECT s.*, u.name as user_name, u.email as user_account_email
        FROM subscriptions s
        JOIN users u ON s.user_id = u.id
    """
    params = []
    if status_filter:
        query += " WHERE s.status = ?"
        params.append(status_filter)
        
    query += " ORDER BY s.requested_at DESC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_subscription_status(subscription_id: int, new_status: str, notes: str = None):
    """Update subscription status (e.g. 'active', 'cancelled', 'pending')."""
    conn = get_db_connection()
    cursor = conn.cursor()
    now_str = datetime.datetime.now().isoformat()
    
    if new_status == 'active':
        cursor.execute("""
            UPDATE subscriptions 
            SET status = 'active', activated_at = ?, notes = COALESCE(?, notes)
            WHERE id = ?
        """, (now_str, notes, subscription_id))
    elif new_status == 'cancelled':
        cursor.execute("""
            UPDATE subscriptions 
            SET status = 'cancelled', cancelled_at = ?, notes = COALESCE(?, notes)
            WHERE id = ?
        """, (now_str, notes, subscription_id))
    else:
        cursor.execute("""
            UPDATE subscriptions 
            SET status = ?, notes = COALESCE(?, notes)
            WHERE id = ?
        """, (new_status, notes, subscription_id))
        
    conn.commit()
    cursor.execute("""
        SELECT s.*, u.name as user_name, u.email as user_account_email
        FROM subscriptions s
        JOIN users u ON s.user_id = u.id
        WHERE s.id = ?
    """, (subscription_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_active_subscriber_emails():
    """Get list of unique emails for all active subscribers."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT email FROM subscriptions WHERE status = 'active'")
    rows = cursor.fetchall()
    conn.close()
    return [r['email'] for r in rows if r['email']]

def get_overview_stats():
    """Retrieve overview metrics for admin dashboard."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'user'")
    total_users = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM subscriptions WHERE status = 'pending'")
    pending_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM subscriptions WHERE status = 'active'")
    active_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM subscriptions WHERE status = 'cancelled'")
    cancelled_count = cursor.fetchone()[0]
    
    conn.close()
    return {
        "total_users": total_users,
        "pending_requests": pending_count,
        "active_subscribers": active_count,
        "cancelled_subscribers": cancelled_count
    }

# Run init on module load
init_db()
