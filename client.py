import socket
import threading
import intel_jtag_uart
import json
import sys

# this will be our ec2 ip address (store as an environment variable?)
HOST = "ec2-3-94-82-163.compute-1.amazonaws.com"
PORT = 12000  # this will be our ec2 port


def receive_messages(client_socket):
    while True:
        try:
            data = client_socket.recv(1024).decode("utf-8")
            if not data:
                break
            print(f"Server: {data}")

            # Can do some funky implementation on the data we get from the server here

        except:
            print("\nDisconnected from server.")
            break

def query_game_info(client_socket, game_id):
    
    client_socket.send(str(game_id).encode()) #send game ID
    data = client_socket.recv(1024).decode() # receive response 

    return json.loads(data) #returns parsed JSON respone 


def start_client():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
        client_socket.connect((HOST, PORT))
        print(f"Connected to server at {HOST}:{PORT}")

    #query game info function call 
        threading.Thread(
            target=receive_messages, args=(client_socket,), daemon=True
        ).start()

        while True:
            try:
                ju = intel_jtag_uart.intel_jtag_uart(
                    cable_name="Altera USB-Blaster",
                    )

            except Exception as e:
                print(e)
                sys.exit(0)

            msg = ju.read()
            
            game_id = input("Enter Game ID to query (or 'exit' to quit): ")

            if game_id.lower() == "exit":
                print("Exiting...")
                client_socket.send("exit".encode())
                break
            
            try:
                response = query_game_info(client_socket, game_id)
                print("Game Info:", response)

            except Exception as e:
                print(f"Error querying game info: {e}")
                break


if __name__ == "__main__":
    start_client()
