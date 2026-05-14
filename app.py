import os
import sqlite3
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, g
)
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

DATABASE = os.path.join(app.instance_path, 'security_demo.db')


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass
    db = sqlite3.connect(DATABASE)
    db.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username VARCHAR(80) UNIQUE NOT NULL,
            password_hash VARCHAR(256) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS phishing_captures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username VARCHAR(80) NOT NULL,
            password VARCHAR(128) NOT NULL,
            ip_address VARCHAR(45),
            user_agent TEXT,
            captured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    db.commit()
    db.close()


app.teardown_appcontext(close_db)


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('请先登录后再访问此页面。', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


# ── Home ──────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


# ── Auth Routes ───────────────────────────────────────────────────────

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        confirm = request.form.get('confirm', '').strip()

        if not username or not password:
            flash('用户名和密码不能为空。', 'danger')
            return render_template('register.html')

        if password != confirm:
            flash('两次输入的密码不一致。', 'danger')
            return render_template('register.html')

        if len(password) < 4:
            flash('密码长度不能少于4位。', 'danger')
            return render_template('register.html')

        db = get_db()
        existing = db.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
        if existing:
            flash('该用户名已被注册。', 'danger')
            return render_template('register.html')

        password_hash = generate_password_hash(password)
        db.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)',
                   (username, password_hash))
        db.commit()
        flash('注册成功！请使用你的账号登录。', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if not username or not password:
            flash('请输入用户名和密码。', 'danger')
            return render_template('login.html')

        db = get_db()
        user = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()

        if user and check_password_hash(user['password_hash'], password):
            session.clear()
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash(f'欢迎回来，{username}！', 'success')
            return redirect(url_for('dashboard'))

        flash('用户名或密码错误。', 'danger')
        return render_template('login.html')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('你已成功退出登录。', 'info')
    return redirect(url_for('index'))


# ── Dashboard ─────────────────────────────────────────────────────────

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')


# ── TLS Demo ──────────────────────────────────────────────────────────

@app.route('/tls-demo')
def tls_demo():
    return render_template('tls_demo.html')


# ── Phishing Module ───────────────────────────────────────────────────

@app.route('/phishing')
def phishing_index():
    return render_template('phishing_index.html')


@app.route('/phishing/attack', methods=['GET', 'POST'])
def phishing_attack():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if username or password:
            ip = request.headers.get('X-Forwarded-For', request.remote_addr)
            ua = request.user_agent.string if request.user_agent else ''
            db = get_db()
            db.execute(
                'INSERT INTO phishing_captures (username, password, ip_address, user_agent) VALUES (?, ?, ?, ?)',
                (username, password, ip, ua)
            )
            db.commit()

        return render_template('phishing_captured.html', username=username)

    return render_template('phishing_attack.html')


@app.route('/phishing/captures')
def phishing_captures():
    db = get_db()
    captures = db.execute(
        'SELECT * FROM phishing_captures ORDER BY captured_at DESC'
    ).fetchall()
    return render_template('phishing_captures.html', captures=captures)


@app.route('/phishing/captures/clear', methods=['POST'])
def phishing_captures_clear():
    db = get_db()
    db.execute('DELETE FROM phishing_captures')
    db.commit()
    flash('所有捕获数据已清空。', 'info')
    return redirect(url_for('phishing_captures'))


@app.route('/phishing/education')
def phishing_education():
    return render_template('phishing_education.html')


# ── Startup ───────────────────────────────────────────────────────────

with app.app_context():
    init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
