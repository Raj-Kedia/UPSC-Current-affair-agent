import argparse
import sys
import os

# Ensure agent directory is in path
AGENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if AGENT_DIR not in sys.path:
    sys.path.insert(0, AGENT_DIR)

from src.db import init_db, get_db_connection, hash_password, get_user_by_id

def reset_admin(email, password, name="System Administrator"):
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    clean_email = email.strip().lower()
    clean_pass = password.strip()
    
    if len(clean_pass) < 6:
        print("Error: Password must be at least 6 characters.")
        conn.close()
        sys.exit(1)
        
    pwd_hash, salt = hash_password(clean_pass)
    
    # Check if admin user exists
    cursor.execute("SELECT id FROM users WHERE role = 'admin' LIMIT 1")
    admin_row = cursor.fetchone()
    
    if admin_row:
        admin_id = admin_row['id']
        cursor.execute(
            "UPDATE users SET name = ?, email = ?, password_hash = ?, salt = ? WHERE id = ?",
            (name.strip(), clean_email, pwd_hash, salt, admin_id)
        )
        conn.commit()
        print(f"SUCCESS: Admin credentials updated!")
        print(f"  - Admin ID: {admin_id}")
        print(f"  - Email (Username): {clean_email}")
        print(f"  - Password: {'*' * len(clean_pass)}")
    else:
        cursor.execute(
            "INSERT INTO users (name, email, password_hash, salt, role) VALUES (?, ?, ?, ?, 'admin')",
            (name.strip(), clean_email, pwd_hash, salt)
        )
        conn.commit()
        print(f"SUCCESS: New Admin user created!")
        print(f"  - Email (Username): {clean_email}")
        print(f"  - Password: {'*' * len(clean_pass)}")
        
    conn.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Reset or change UPSC Agent admin username and password")
    parser.add_argument('--email', required=True, help="New admin email address (username)")
    parser.add_argument('--password', required=True, help="New admin password")
    parser.add_argument('--name', default="System Administrator", help="Admin display name")
    
    args = parser.parse_args()
    reset_admin(args.email, args.password, args.name)
