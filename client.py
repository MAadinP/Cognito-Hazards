import socket
import threading
import intel_jtag_uart

# this will be our ec2 ip address (store as an environment variable?)
HOST = "3.120.45.67"
PORT = 12345  # this will be our ec2 port


def receive_messages(client_socket):
    while True:
        try:
            data = client_socket.recv(1024).decode("utf-8")
            if not data:
                break

            # Can do some funky implementation on the data we get from the server here

        except:
            break


def start_client():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
        client_socket.connect((HOST, PORT))
        print(f"Connected to server at {HOST}:{PORT}")

        threading.Thread(
            target=receive_messages, args=(client_socket,), daemon=True
        ).start()

        while True:
            try:
                ju = intel_jtag_uart.intel_jtag_uart(
                    cable_name="USB-Blaster",
                )

            except Exception as e:
                print(e)
                sys.exit(0)

            msg = ju.read()
            client_socket.sendall(msg.encode("utf-8"))


if __name__ == "__main__":
    start_client()
