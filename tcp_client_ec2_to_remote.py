import socket
import json

print("Starting the Game Info Client...")

server_name = "54.242.180.145"  # Replace with EC2 instance Public IP
server_port = 12000

def query_game_info(game_id):
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect((server_name, server_port))

    client_socket.send(str(game_id).encode())

    data = client_socket.recv(1024).decode()
    client_socket.close()

    return json.loads(data)

if __name__ == "__main__":
    while True:
        game_id = input("Enter Game ID to query (or 'exit' to quit): ")
        if game_id.lower() == 'exit':
            break

        response = query_game_info(game_id)
        print("Game Info:", response)
