import socket

def check_port(port):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            result = s.connect_ex(('127.0.0.1', port))
            return result == 0
    except Exception as e:
        return False

backend = check_port(8000)
frontend = check_port(5173)

print(f"Backend (8000): {'OPEN' if backend else 'CLOSED'}")
print(f"Frontend (5173): {'OPEN' if frontend else 'CLOSED'}")
