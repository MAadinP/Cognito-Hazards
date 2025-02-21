import socket
import threading

HOST = "0.0.0.0"
PORT = 12345

clients = []


def handle_client(conn, addr):
    print(f"Client {addr} connected.")
    clients.append(conn)

    while True:
        try:
            data = conn.recv(1024).decode("utf-8")
            if not data:
                break
            if data == "end":
                sys.exit(0)

            # funky server side processing for the accelerometer data we receive

            for client in clients:
                if client != conn:
                    client.sendall(f"Client {addr}: {data}".encode("utf-8"))
        except:
            break

    print(f"Client {addr} disconnected.")
    clients.remove(conn)
    conn.close()


def start_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.bind((HOST, PORT))
        server_socket.listen(2)
        print(f"Server listening on {HOST}:{PORT}")

        while len(clients) < 2:
            conn, addr = server_socket.accept()
            threading.Thread(
                target=handle_client, args=(conn, addr), daemon=True
            ).start()

        # funky server side code to send something to the clients -> store game variables here. Ronnie might set up database here


if __name__ == "__main__":
    start_server()
