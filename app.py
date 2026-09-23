from flask import Flask, request, redirect, url_for, session, render_template, flash
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "sairler-efendisi-secret"
)

DB = "sairler.db"


def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init():
    conn = db()

    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT UNIQUE,
        email TEXT UNIQUE,
        password TEXT,
        premium INTEGER DEFAULT 0,
        admin INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS poems (
        id INTEGER PRIMARY KEY,
        title TEXT,
        body TEXT,
        author_id INTEGER,
        likes INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    conn.commit()
    conn.close()


# Uygulama başlarken veritabanını hazırla
init()


@app.context_processor
def context():
    user = None

    if session.get("uid"):
        user = db().execute(
            "SELECT * FROM users WHERE id=?",
            (session["uid"],)
        ).fetchone()

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

    return render_template("home.html", poems=poems)


@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        try:
            conn = db()

            conn.execute(
                "INSERT INTO users(username,email,password) VALUES(?,?,?)",
                (
                    request.form["username"],
                    request.form["email"],
                    generate_password_hash(
                        request.form["password"]
                    )
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

        user = db().execute(
            "SELECT * FROM users WHERE email=?",
            (request.form["email"],)
        ).fetchone()

        if user and check_password_hash(
            user["password"],
            request.form["password"]
        ):
            session["uid"] = user["id"]
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

    user = db().execute(
        "SELECT * FROM users WHERE id=?",
        (session["uid"],)
    ).fetchone()

    if request.method == "POST":

        conn = db()

        conn.execute(
            """
            INSERT INTO poems(title, body, author_id)
            VALUES(?,?,?)
            """,
            (
                request.form["title"],
                request.form["body"],
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

    poem_data = db().execute(
        """
        SELECT poems.*, users.username
        FROM poems
        JOIN users ON users.id = poems.author_id
        WHERE poems.id=?
        """,
        (id,)
    ).fetchone()

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

    user = db().execute(
        "SELECT * FROM users WHERE id=?",
        (session["uid"],)
    ).fetchone()

    if not user["admin"]:
        return "Yetkisiz erişim", 403

    conn = db()

    users = conn.execute(
        "SELECT * FROM users ORDER BY id DESC"
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
