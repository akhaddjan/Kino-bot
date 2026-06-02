import sqlite3
from config import DATABASE


def get_conn():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def create_tables():
    conn = get_conn()
    c = conn.cursor()

    # Kinolar
    c.execute("""
        CREATE TABLE IF NOT EXISTS kinolar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kod TEXT UNIQUE NOT NULL,
            nomi TEXT NOT NULL,
            file_id TEXT NOT NULL,
            izoh TEXT,
            qoshilgan TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Foydalanuvchilar
    c.execute("""
        CREATE TABLE IF NOT EXISTS foydalanuvchilar (
            user_id INTEGER PRIMARY KEY,
            ism TEXT,
            username TEXT,
            birinchi_kirilgan TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            oxirgi_faollik TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            bloklagan INTEGER DEFAULT 0
        )
    """)

    # Majburiy kanallar
    c.execute("""
        CREATE TABLE IF NOT EXISTS kanallar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kanal_id TEXT UNIQUE NOT NULL,
            kanal_nomi TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


# ── Kinolar ──────────────────────────────────

def kino_qosh(kod, nomi, file_id, izoh=""):
    try:
        conn = get_conn()
        conn.execute(
            "INSERT INTO kinolar (kod, nomi, file_id, izoh) VALUES (?, ?, ?, ?)",
            (kod, nomi, file_id, izoh)
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False


def kino_olish(kod):
    conn = get_conn()
    kino = conn.execute("SELECT * FROM kinolar WHERE kod = ?", (kod,)).fetchone()
    conn.close()
    return kino


def kino_ochir(kod):
    conn = get_conn()
    affected = conn.execute("DELETE FROM kinolar WHERE kod = ?", (kod,)).rowcount
    conn.commit()
    conn.close()
    return affected > 0


def barcha_kinolar():
    conn = get_conn()
    kinolar = conn.execute("SELECT kod, nomi FROM kinolar ORDER BY kod").fetchall()
    conn.close()
    return kinolar


def kinolar_soni():
    conn = get_conn()
    soni = conn.execute("SELECT COUNT(*) FROM kinolar").fetchone()[0]
    conn.close()
    return soni


# ── Foydalanuvchilar ──────────────────────────

def foydalanuvchi_qosh(user_id, ism, username):
    conn = get_conn()
    conn.execute("""
        INSERT INTO foydalanuvchilar (user_id, ism, username)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            ism = excluded.ism,
            username = excluded.username,
            oxirgi_faollik = CURRENT_TIMESTAMP,
            bloklagan = 0
    """, (user_id, ism, username))
    conn.commit()
    conn.close()


def bloklagan_belgi(user_id):
    conn = get_conn()
    conn.execute(
        "UPDATE foydalanuvchilar SET bloklagan = 1 WHERE user_id = ?", (user_id,)
    )
    conn.commit()
    conn.close()


def faollik_yangilab(user_id):
    conn = get_conn()
    conn.execute(
        "UPDATE foydalanuvchilar SET oxirgi_faollik = CURRENT_TIMESTAMP, bloklagan = 0 WHERE user_id = ?",
        (user_id,)
    )
    conn.commit()
    conn.close()


def statistika():
    conn = get_conn()
    jami = conn.execute("SELECT COUNT(*) FROM foydalanuvchilar").fetchone()[0]
    bloklagan = conn.execute("SELECT COUNT(*) FROM foydalanuvchilar WHERE bloklagan = 1").fetchone()[0]
    faol = conn.execute("""
        SELECT COUNT(*) FROM foydalanuvchilar
        WHERE bloklagan = 0
        AND oxirgi_faollik >= datetime('now', '-7 days')
    """).fetchone()[0]
    conn.close()
    return {"jami": jami, "bloklagan": bloklagan, "faol": faol}


def barcha_user_idlar():
    conn = get_conn()
    idlar = [r[0] for r in conn.execute(
        "SELECT user_id FROM foydalanuvchilar WHERE bloklagan = 0"
    ).fetchall()]
    conn.close()
    return idlar


# ── Kanallar ─────────────────────────────────

def kanal_qosh(kanal_id, kanal_nomi):
    try:
        conn = get_conn()
        conn.execute(
            "INSERT INTO kanallar (kanal_id, kanal_nomi) VALUES (?, ?)",
            (kanal_id, kanal_nomi)
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False


def kanal_ochir(kanal_id):
    conn = get_conn()
    affected = conn.execute("DELETE FROM kanallar WHERE kanal_id = ?", (kanal_id,)).rowcount
    conn.commit()
    conn.close()
    return affected > 0


def barcha_kanallar():
    conn = get_conn()
    kanallar = conn.execute("SELECT kanal_id, kanal_nomi FROM kanallar").fetchall()
    conn.close()
    return kanallar
