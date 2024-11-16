import os
import sqlite3

# اسم ملف قاعدة البيانات
db_file = 'points.db'

# حذف قاعدة البيانات إذا كانت موجودة
if os.path.exists(db_file):
    os.remove(db_file)
    print(f"{db_file} has been deleted.")

# إعداد قاعدة بيانات SQLite
conn = sqlite3.connect('points.db')
cursor = conn.cursor()

# إنشاء جدول لتخزين المستخدمين
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id TEXT UNIQUE,
    points INTEGER DEFAULT 0,
    ad_code TEXT,
    invited_by TEXT,
    invite_count INTEGER DEFAULT 0,
    has_received_invite_points BOOLEAN DEFAULT FALSE,
    last_rewarded INTEGER DEFAULT 0,
    invite_link_used BOOLEAN DEFAULT FALSE,
    gift_link_active BOOLEAN DEFAULT FALSE
)
''')

# إنشاء جدول لتخزين روابط الهدايا
cursor.execute('''
CREATE TABLE IF NOT EXISTS gift_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gift_code TEXT UNIQUE,
    points_per_user INTEGER,
    remaining_uses INTEGER,
    active BOOLEAN DEFAULT TRUE
)
''')

# إنشاء جدول لتسجيل الدعوات
cursor.execute('''
CREATE TABLE IF NOT EXISTS invitations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    inviter_id TEXT NOT NULL,
    invited_id TEXT NOT NULL,
    UNIQUE(inviter_id, invited_id)
)
''')

conn.commit()
conn.close()

print("Database and tables created successfully.")
