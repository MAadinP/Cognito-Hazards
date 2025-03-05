import socket
import time
import random
import threading

#On ec2 create a new security group custom udp on port 12345 from all Ip's or won't work

# Server settings
SERVER_IP = "0.0.0.0"  # Binds to all available network interfaces
SERVER_PORT = 12345
BUFFER_SIZE = 1024

# Create UDP socket
server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server_socket.bind((SERVER_IP, SERVER_PORT))

print(f"UDP Game Server started on {SERVER_IP}:{SERVER_PORT}")

clients = set()  # Store connected clients
scores = {1: 0, 2: 0}  # Player scores
boss_hp = 10000  # Boss health points

# Load Simulated Data
num_samples = 1000000  # Ensure data doesn't run out
simulated_data = [
    (random.randint(100, 700), random.randint(100, 500), random.choice([1, 2])) 
    for _ in range(num_samples)
]

data_index = 0
overlay_angle = random.randint(-45, 45)

def receive_client_messages():
    """Thread function to receive client messages (score updates)."""
    global boss_hp
    while True:
        try:
            data, addr = server_socket.recvfrom(BUFFER_SIZE)
            decoded_data = data.decode()
            print(f"Received from {addr}: {decoded_data}")
            
            if addr not in clients:
                clients.add(addr)
                print(f"New client connected: {addr}")

            # Handle score updates
            if decoded_data.startswith("SCORE"):
                _, player_id = decoded_data.split(",")
                player_id = int(player_id)
                scores[player_id] += 1
                boss_hp -= 10  # Deduct boss HP per score event
                if boss_hp < 0:
                    boss_hp = 0  # Ensure HP doesn't go negative
                print(f"Player {player_id} scored! New score: {scores[player_id]}, Boss HP: {boss_hp}")

                # Send updated scores and boss HP to all clients
                for client in clients:
                    score_message = f"SCORE_UPDATE,{player_id},{scores[player_id]},{boss_hp}"
                    server_socket.sendto(score_message.encode(), client)
        except socket.timeout:
            continue  # No data received, continue listening

# Start a thread for receiving client messages
threading.Thread(target=receive_client_messages, daemon=True).start()

def update_overlay():
    """Thread function to update overlay rectangle and send to clients."""
    global overlay_angle
    while True:
        overlay_angle = random.randint(-45, 45)
        overlay_message = f"OVERLAY,{overlay_angle}"
        for client in clients:
            server_socket.sendto(overlay_message.encode(), client)
        print(f"Sent overlay angle: {overlay_angle}")
        time.sleep(1)  # Update every second

# Start a thread for overlay updates
threading.Thread(target=update_overlay, daemon=True).start()

while True:
    try:
        # Send simulated player data to all clients
        if data_index < len(simulated_data):
            xpos, ypos, player_no = simulated_data[data_index]
            message = f"{xpos},{ypos},{player_no}"
            data_index += 1

            for client in clients:
                server_socket.sendto(message.encode(), client)

            print(f"Sent: {message}")

        time.sleep(0.05)  # 50ms per update (~20 updates per second)

    except KeyboardInterrupt:
        print("Server shutting down...")
        break

server_socket.close()
