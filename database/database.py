import sqlite3
import json
from datetime import datetime
from pathlib import Path
from config import Config

def get_db_connection():
    db_path = Path(Config.DATABASE_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(Config.DATABASE_PATH, timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Documents table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            stored_filename TEXT NOT NULL,
            extracted_text TEXT NOT NULL,
            file_size INTEGER DEFAULT 0,
            page_count INTEGER DEFAULT 0,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')

    # Study content table (summary, questions, flashcards, mcqs)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS study_content (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            content_type TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
            UNIQUE(document_id, content_type)
        )
    ''')

    # Chat history table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            document_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
        )
    ''')

    # Quiz results table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS quiz_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            document_id INTEGER NOT NULL,
            score INTEGER NOT NULL,
            total_questions INTEGER NOT NULL,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
        )
    ''')

    conn.commit()
    conn.close()

# ----------------- User Helpers -----------------
def create_user(name, email, password_hash):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name.strip(), email.strip().lower(), password_hash)
        )
        conn.commit()
        user_id = cursor.lastrowid
        return user_id
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()

def get_user_by_email(email):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE lower(email) = ?", (email.strip().lower(),))
    user = cursor.fetchone()
    conn.close()
    return user

def get_user_by_id(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def update_user_name(user_id, name):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET name = ? WHERE id = ?", (name.strip(), user_id))
    conn.commit()
    conn.close()
    return True

def update_user_password(user_id, password_hash):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id))
    conn.commit()
    conn.close()
    return True

# ----------------- Document Helpers -----------------
def create_document(user_id, filename, stored_filename, extracted_text, file_size=0, page_count=0):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO documents (user_id, filename, stored_filename, extracted_text, file_size, page_count)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, filename, stored_filename, extracted_text, file_size, page_count))
    conn.commit()
    doc_id = cursor.lastrowid
    conn.close()
    return doc_id

def get_document(doc_id, user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM documents WHERE id = ? AND user_id = ?", (doc_id, user_id))
    doc = cursor.fetchone()
    conn.close()
    return doc

def get_user_documents(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM documents WHERE user_id = ? ORDER BY uploaded_at DESC", (user_id,))
    docs = cursor.fetchall()
    conn.close()
    return docs

def delete_document(doc_id, user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT stored_filename FROM documents WHERE id = ? AND user_id = ?", (doc_id, user_id))
    doc = cursor.fetchone()
    if not doc:
        conn.close()
        return False
    
    # Delete from DB (cascading foreign keys will clean up study_content, chat_history, quiz_results)
    cursor.execute("DELETE FROM documents WHERE id = ? AND user_id = ?", (doc_id, user_id))
    conn.commit()
    conn.close()

    # Also remove stored physical PDF if exists
    if doc["stored_filename"]:
        file_path = Path(Config.UPLOAD_FOLDER) / doc["stored_filename"]
        if file_path.exists():
            try:
                file_path.unlink()
            except Exception:
                pass
    return True

# ----------------- Study Content Helpers -----------------
def save_study_content(document_id, content_type, content):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO study_content (document_id, content_type, content, created_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(document_id, content_type) DO UPDATE SET
            content = excluded.content,
            created_at = CURRENT_TIMESTAMP
    ''', (document_id, content_type, content))
    conn.commit()
    conn.close()

def get_study_content(document_id, content_type):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM study_content WHERE document_id = ? AND content_type = ?",
        (document_id, content_type)
    )
    row = cursor.fetchone()
    conn.close()
    return row

def get_all_study_content_for_doc(document_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM study_content WHERE document_id = ?", (document_id,))
    rows = cursor.fetchall()
    conn.close()
    return {row["content_type"]: row["content"] for row in rows}

# ----------------- Chat History Helpers -----------------
def add_chat_message(user_id, document_id, role, message):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO chat_history (user_id, document_id, role, message) VALUES (?, ?, ?, ?)",
        (user_id, document_id, role, message)
    )
    conn.commit()
    msg_id = cursor.lastrowid
    conn.close()
    return msg_id

def get_chat_history(user_id, document_id, limit=50):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM chat_history 
        WHERE user_id = ? AND document_id = ? 
        ORDER BY created_at ASC, id ASC
        LIMIT ?
    ''', (user_id, document_id, limit))
    rows = cursor.fetchall()
    conn.close()
    return rows

def clear_chat_history(user_id, document_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM chat_history WHERE user_id = ? AND document_id = ?", (user_id, document_id))
    conn.commit()
    conn.close()
    return True

# ----------------- Quiz Helpers -----------------
def save_quiz_result(user_id, document_id, score, total_questions, details=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    details_str = json.dumps(details) if details else None
    cursor.execute('''
        INSERT INTO quiz_results (user_id, document_id, score, total_questions, details)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, document_id, score, total_questions, details_str))
    conn.commit()
    quiz_id = cursor.lastrowid
    conn.close()
    return quiz_id

def get_user_quiz_results(user_id, document_id=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    if document_id:
        cursor.execute('''
            SELECT qr.*, d.filename 
            FROM quiz_results qr
            JOIN documents d ON qr.document_id = d.id
            WHERE qr.user_id = ? AND qr.document_id = ?
            ORDER BY qr.created_at DESC
        ''', (user_id, document_id))
    else:
        cursor.execute('''
            SELECT qr.*, d.filename 
            FROM quiz_results qr
            JOIN documents d ON qr.document_id = d.id
            WHERE qr.user_id = ?
            ORDER BY qr.created_at DESC
        ''', (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

# ----------------- Dashboard & History Analytics -----------------
def get_dashboard_stats(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Total Materials
    cursor.execute("SELECT COUNT(*) AS total FROM documents WHERE user_id = ?", (user_id,))
    total_materials = cursor.fetchone()["total"]
    
    # 2. Summaries Created
    cursor.execute('''
        SELECT COUNT(sc.id) AS total
        FROM study_content sc
        JOIN documents d ON sc.document_id = d.id
        WHERE d.user_id = ? AND sc.content_type = 'summary'
    ''', (user_id,))
    summaries_created = cursor.fetchone()["total"]

    # 3. Questions Generated (questions + flashcards + mcqs)
    cursor.execute('''
        SELECT COUNT(sc.id) AS total
        FROM study_content sc
        JOIN documents d ON sc.document_id = d.id
        WHERE d.user_id = ? AND sc.content_type IN ('questions', 'flashcards', 'mcqs')
    ''', (user_id,))
    questions_generated = cursor.fetchone()["total"]

    # 4. Quiz Attempts
    cursor.execute("SELECT COUNT(*) AS total FROM quiz_results WHERE user_id = ?", (user_id,))
    quiz_attempts = cursor.fetchone()["total"]
    
    conn.close()
    return {
        "total_materials": total_materials,
        "summaries_created": summaries_created,
        "questions_generated": questions_generated,
        "quiz_attempts": quiz_attempts
    }

def get_user_activity_history(user_id, limit=50):
    conn = get_db_connection()
    cursor = conn.cursor()

    activities = []

    # Documents uploaded
    cursor.execute('''
        SELECT id, filename, uploaded_at
        FROM documents
        WHERE user_id = ?
        ORDER BY uploaded_at DESC LIMIT ?
    ''', (user_id, limit))
    for row in cursor.fetchall():
        activities.append({
            "doc_id": row["id"],
            "filename": row["filename"],
            "activity_type": "Upload",
            "title": f"Uploaded \"{row['filename']}\"",
            "details": "Extracted text & indexed for AI study workspace",
            "created_at": row["uploaded_at"],
            "badge": "badge-primary"
        })

    # Study content generated
    cursor.execute('''
        SELECT sc.content_type, sc.created_at, d.id as doc_id, d.filename
        FROM study_content sc
        JOIN documents d ON sc.document_id = d.id
        WHERE d.user_id = ?
        ORDER BY sc.created_at DESC LIMIT ?
    ''', (user_id, limit))
    for row in cursor.fetchall():
        ctype = row["content_type"].capitalize()
        badge = "badge-success" if row["content_type"] == "summary" else "badge-info"
        activities.append({
            "doc_id": row["doc_id"],
            "filename": row["filename"],
            "activity_type": ctype,
            "title": f"Generated {ctype}",
            "details": f"Created AI study material for \"{row['filename']}\"",
            "created_at": row["created_at"],
            "badge": badge
        })

    # Quiz results
    cursor.execute('''
        SELECT qr.score, qr.total_questions, qr.created_at, d.id as doc_id, d.filename
        FROM quiz_results qr
        JOIN documents d ON qr.document_id = d.id
        WHERE qr.user_id = ?
        ORDER BY qr.created_at DESC LIMIT ?
    ''', (user_id, limit))
    for row in cursor.fetchall():
        pct = round((row["score"] / row["total_questions"]) * 100) if row["total_questions"] > 0 else 0
        activities.append({
            "doc_id": row["doc_id"],
            "filename": row["filename"],
            "activity_type": "Quiz",
            "title": f"Completed MCQ Quiz: {row['score']}/{row['total_questions']} ({pct}%)",
            "details": f"Tested knowledge on \"{row['filename']}\"",
            "created_at": row["created_at"],
            "badge": "badge-warning"
        })

    # Sort all combined activities by date descending
    activities.sort(key=lambda x: str(x["created_at"]), reverse=True)
    conn.close()
    return activities[:limit]
