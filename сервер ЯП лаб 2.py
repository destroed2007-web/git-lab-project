import socket
import threading
import signal
import sys

# Глобальные переменные сервера
server_socket = None
clients = {}               # ник -> (соединение, адрес)
clients_lock = threading.Lock()
running = True

def recv_line(conn):
    """Получение строки от клиента до символа \\n"""
    data = b''
    while True:
        try:
            chunk = conn.recv(1)
            if not chunk:
                return None
            if chunk == b'\n':
                return data.decode('utf-8')
            data += chunk
        except socket.error:
            return None

def handle_send(sender_nick, target_nick, message, conn):
    """Отправка личного сообщения от sender к target"""
    with clients_lock:
        if target_nick not in clients:
            conn.sendall(f"ERROR User '{target_nick}' not found\n".encode())
            return
        target_conn, _ = clients[target_nick]

    try:
        target_conn.sendall(f"FROM {sender_nick}: {message}\n".encode())
        conn.sendall(b"OK\n")
    except Exception as e:
        conn.sendall(b"ERROR Failed to deliver message\n")
        print(f"Ошибка отправки от {sender_nick} к {target_nick}: {e}")

def handle_list(conn):
    """Отправка списка активных пользователей"""
    with clients_lock:
        nicknames = list(clients.keys())
    user_list = ", ".join(nicknames) if nicknames else "No users online"
    conn.sendall(f"USERS: {user_list}\n".encode())

def handle_client(conn, addr):
    """Обработка одного клиента"""
    nickname = None
    try:
        # Приветствие
        conn.sendall(b"Welcome to the chat server. Please register with: REGISTER <nickname>\n")

        # Регистрация
        data = recv_line(conn)
        if not data:
            return

        parts = data.strip().split()
        if len(parts) == 2 and parts[0].upper() == "REGISTER":
            nickname = parts[1]
            with clients_lock:
                if nickname in clients:
                    conn.sendall(f"ERROR Nickname '{nickname}' is already taken\n".encode())
                    return
                clients[nickname] = (conn, addr)
            conn.sendall(b"OK\n")
            print(f"Клиент {nickname} зарегистрирован")
        else:
            conn.sendall(b"ERROR Invalid registration command\n")
            return

        # Основной цикл команд
        while True:
            data = recv_line(conn)
            if not data:
                break

            cmd = data.strip().split()
            if not cmd:
                continue

            command = cmd[0].upper()

            if command == "SEND":
                if len(cmd) < 3:
                    conn.sendall(b"ERROR Usage: SEND <target_nick> <message>\n")
                    continue
                target_nick = cmd[1]
                message = ' '.join(cmd[2:])
                handle_send(nickname, target_nick, message, conn)

            elif command == "LIST":
                handle_list(conn)

            elif command == "QUIT":
                conn.sendall(b"OK\n")
                break

            else:
                conn.sendall(b"ERROR Unknown command\n")

    except (ConnectionResetError, BrokenPipeError):
        print(f"Клиент {nickname} аварийно отключился")
    except Exception as e:
        print(f"Ошибка при обработке {nickname}: {e}")
    finally:
        if nickname:
            with clients_lock:
                if nickname in clients:
                    del clients[nickname]
            print(f"Клиент {nickname} отключён")
        conn.close()

def shutdown_handler(signum, frame):
    """Обработчик сигналов для корректного завершения"""
    global running
    print("\nПолучен сигнал завершения. Останавливаем сервер...")
    running = False
    if server_socket:
        server_socket.close()  # вызовет исключение в accept
    # Закрываем все клиентские соединения
    with clients_lock:
        for nick, (conn, addr) in list(clients.items()):
            try:
                conn.close()
            except:
                pass
    sys.exit(0)

def start_server(host='127.0.0.1', port=8888):
    """Запуск сервера"""
    global server_socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server_socket.bind((host, port))
        server_socket.listen(5)
        print(f"Сервер запущен на {host}:{port}")
    except Exception as e:
        print(f"Ошибка запуска: {e}")
        sys.exit(1)

    # Установка обработчиков сигналов
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    global running
    while running:
        try:
            client_socket, client_addr = server_socket.accept()
            print(f"Новое подключение: {client_addr}")
            thread = threading.Thread(target=handle_client, args=(client_socket, client_addr))
            thread.daemon = True
            thread.start()
        except socket.error:
            # Возникает при закрытии сервера (server_socket.close())
            break
        except Exception as e:
            print(f"Ошибка accept: {e}")
            break

    print("Сервер завершил работу.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Chat Server (functional)")
    parser.add_argument("--host", default="127.0.0.1", help="IP адрес")
    parser.add_argument("--port", type=int, default=8888, help="Порт")
    args = parser.parse_args()
    start_server(args.host, args.port)