from flask import Flask, request, redirect, url_for, session, render_template, flash
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# Render Environment Variables üzerinden alınır.
# Kodun içinde admin şifresi bulunmaz.
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")

DB = "sairler.db"


def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init():
    conn = db()

    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        premium INTEGER DEFAULT 0,
        admin INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS poems (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        body TEXT NOT NULL,
        author_id INTEGER NOT NULL,
        likes INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (author_id) REFERENCES users(id)
    );
    """)

    conn.commit()

    # Admin bilgileri Render Environment Variables'dan alınır.
    admin_email = os.environ.get("ADMIN_EMAIL")
    admin_password = os.environ.get("ADMIN_PASSWORD")

    if admin_email and admin_password:

        admin_username = os.environ.get(
            "ADMIN_USERNAME",
            "Kralderdo"
        )

        existing = conn.execute(
            "SELECT id FROM users WHERE email=?",
            (admin_email,)
        ).fetchone()

        if existing:
            # Hesap varsa admin yap ve şifreyi güncelle
            conn.execute(
                """
                UPDATE users
                SET admin=1,
                    username=?,
                    password=?
                WHERE email=?
                """,
                (
                    admin_username,
                    generate_password_hash(admin_password),
                    admin_email
                )
            )
        else:
            # Admin hesabı yoksa oluştur
            conn.execute(
                """
                INSERT INTO users
                (username, email, password, premium, admin)
                VALUES (?, ?, ?, 1, 1)
                """,
                (
                    admin_username,
                    admin_email,
                    generate_password_hash(admin_password)
                )
            )

        conn.commit()

    conn.close()


# Uygulama başlarken veritabanını hazırla
init()


@app.context_processor
def context():
    user = None

    if session.get("uid"):
        conn = db()

        user = conn.execute(
            "SELECT * FROM users WHERE id=?",
            (session["uid"],)
        ).fetchone()

        conn.close()

    return {"user": user}


@app.route("/")
def home():
    conn = db()

    poems = conn.execute("""
        SELECT poems.*, users.username
        FROM poems
        JOIN users ON users.id = poems.author_id
        ORDER BY poems.created_at DESC
    """).fetchall()

    conn.close()

    return render_template(
        "home.html",
        poems=poems
    )


@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not username or not email or not password:
            flash("Lütfen tüm alanları doldur.")
            return render_template("register.html")

        try:
            conn = db()

            conn.execute(
                """
                INSERT INTO users
                (username, email, password)
                VALUES (?, ?, ?)
                """,
                (
                    username,
                    email,
                    generate_password_hash(password)
                )
            )

            conn.commit()
            conn.close()

            flash("Kayıt başarılı. Şimdi giriş yapabilirsin.")

            return redirect(url_for("login"))

        except sqlite3.IntegrityError:
            flash("Bu kullanıcı adı veya e-posta zaten kayıtlı.")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        conn = db()

        user = conn.execute(
            "SELECT * FROM users WHERE email=?",
            (email,)
        ).fetchone()

        conn.close()

        if user and check_password_hash(
            user["password"],
            password
        ):
            session.clear()
            session["uid"] = user["id"]

            if user["admin"]:
                return redirect(url_for("admin"))

            return redirect(url_for("home"))

        flash("E-posta veya şifre hatalı.")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


@app.route("/premium")
def premium():
    return render_template("premium.html")


@app.route("/poem/new", methods=["GET", "POST"])
def new_poem():

    if not session.get("uid"):
        return redirect(url_for("login"))

    conn = db()

    user = conn.execute(
        "SELECT * FROM users WHERE id=?",
        (session["uid"],)
    ).fetchone()

    conn.close()

    if not user:
        session.clear()
        return redirect(url_for("login"))

    if request.method == "POST":

        title = request.form.get("title", "").strip()
        body = request.form.get("body", "").strip()

        if not title or not body:
            flash("Başlık ve şiir metni boş bırakılamaz.")
            return render_template("new_poem.html")

        conn = db()

        conn.execute(
            """
            INSERT INTO poems
            (title, body, author_id)
            VALUES (?, ?, ?)
            """,
            (
                title,
                body,
                user["id"]
            )
        )

        conn.commit()
        conn.close()

        flash("Şiirin başarıyla yayınlandı. ✍️")

        return redirect(url_for("home"))

    return render_template("new_poem.html")


@app.route("/poem/<int:id>")
def poem(id):

    conn = db()

    poem_data = conn.execute(
        """
        SELECT poems.*, users.username
        FROM poems
        JOIN users ON users.id = poems.author_id
        WHERE poems.id=?
        """,
        (id,)
    ).fetchone()

    conn.close()

    if not poem_data:
        return "Şiir bulunamadı", 404

    return render_template(
        "poem.html",
        poem=poem_data
    )


@app.route("/admin")
def admin():

    if not session.get("uid"):
        return redirect(url_for("login"))

    conn = db()

    user = conn.execute(
        "SELECT * FROM users WHERE id=?",
        (session["uid"],)
    ).fetchone()

    if not user:
        conn.close()
        session.clear()
        return redirect(url_for("login"))

    if not user["admin"]:
        conn.close()
        return "Yetkisiz erişim", 403

    users = conn.execute(
        """
        SELECT id, username, email, premium, admin
        FROM users
        ORDER BY id DESC
        """
    ).fetchall()

    poems = conn.execute(
        """
        SELECT poems.*, users.username
        FROM poems
        JOIN users ON users.id = poems.author_id
        ORDER BY poems.id DESC
        """
    ).fetchall()

    conn.close()

    return render_template(
        "admin.html",
        users=users,
        poems=poems
    )


if __name__ == "__main__":

    port = int(os.environ.get("PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=port
    )


