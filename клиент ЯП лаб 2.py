import socket
import threading
import sys


# Глобальные переменные клиента
sock = None
nickname = None
running = True

def recv_line():
    """Получение строки от сервера"""
    global sock
    data = b''
    while True:
        try:
            chunk = sock.recv(1)
            if not chunk:
                return None
            if chunk == b'\n':
                return data.decode('utf-8')
            data += chunk
        except socket.error:
            return None

def send_command(cmd):
    """Отправка команды на сервер"""
    global sock
    try:
        sock.sendall((cmd + '\n').encode())
    except Exception as e:
        print(f"Ошибка отправки: {e}")
        return False
    return True

def receive_messages():
    """Поток для приёма сообщений от сервера"""
    global running
    while running:
        msg = recv_line()
        if msg is None:
            if running:
                print("\nСоединение с сервером потеряно.")
                running = False
            break
        if msg.startswith("FROM "):
            print(f"\n[ЛИЧНОЕ] {msg}", end='')
        elif msg.startswith("USERS:"):
            print(f"\n{msg}", end='')
        # Игнорируем OK/ERROR — они выводятся в основном потоке

def connect(host, port):
    """Подключение к серверу"""
    global sock
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, port))
        print(f"Подключено к серверу {host}:{port}")
    except Exception as e:
        print(f"Не удалось подключиться: {e}")
        sys.exit(1)

def register():
    """Регистрация ника"""
    global nickname
    welcome = recv_line()
    if welcome:
        print(welcome, end='')

    while True:
        nick = input("Введите ваш ник: ").strip()
        if not nick:
            continue
        send_command(f"REGISTER {nick}")
        response = recv_line()
        if response == "OK":
            nickname = nick
            print("Регистрация успешна!")
            break
        else:
            print(f"Ошибка регистрации: {response}")

def run_client(host, port):
    """Основная функция клиента"""
    global running, nickname
    connect(host, port)
    register()

    # Запуск потока для приёма сообщений
    receiver = threading.Thread(target=receive_messages)
    receiver.daemon = True
    receiver.start()

    print("\nДоступные команды:")
    print("  /msg <ник> <сообщение> - отправить личное сообщение")
    print("  /list - показать список пользователей")
    print("  /quit - выйти")
    print("Для отправки сообщения введите команду.\n")

    try:
        while running:
            cmd_line = input().strip()
            if not cmd_line:
                continue

            if cmd_line == "/quit":
                send_command("QUIT")
                running = False
                break
            elif cmd_line.startswith("/msg "):
                parts = cmd_line.split(maxsplit=2)
                if len(parts) < 3:
                    print("Использование: /msg <ник> <сообщение>")
                    continue
                _, target, msg = parts
                send_command(f"SEND {target} {msg}")
                # Ждём OK/ERROR (но они придут в receive_messages, но мы их не видим)
                # Можно добавить краткое ожидание или просто выводить, что сообщение отправлено.
            elif cmd_line == "/list":
                send_command("LIST")
            else:
                print("Неизвестная команда.")
    except (KeyboardInterrupt, EOFError):
        print("\nВыход...")
        send_command("QUIT")
    finally:
        running = False
        if sock:
            sock.close()
        print("Клиент завершил работу.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Chat Client (functional)")
    parser.add_argument("--host", default="127.0.0.1", help="IP сервера")
    parser.add_argument("--port", type=int, default=8888, help="Порт сервера")
    args = parser.parse_args()
    run_client(args.host, args.port)