import socket
import threading
import random
import time
import boto3
import datetime
import json
from decimal import Decimal

#Known Issues:
# Game doesn't reset after boss is defeated
# High scores are not displayed after game over

# Server setup
SERVER_IP = "0.0.0.0"
SERVER_PORT = 12345
BUFFER_SIZE = 1024

server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server_socket.bind((SERVER_IP, SERVER_PORT))
print(f"UDP Game Server started on {SERVER_IP}:{SERVER_PORT}")

clients = {}  # Stores player IDs and their addresses
players_ready = set()
MAXBOSSHP = 10000
boss_hp = MAXBOSSHP
overlay_angle = random.randint(-45, 45)
scores = {1: 0, 2: 0}  # Player scores
game_running = False

# AWS DynamoDB Setup
dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
table_name = "GameScores"

def create_table():
    existing_tables = [table.name for table in dynamodb.tables.all()]
    if table_name not in existing_tables:
        table = dynamodb.create_table(
            TableName=table_name,
            KeySchema=[{'AttributeName': 'game_id', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'game_id', 'AttributeType': 'N'}],
            ProvisionedThroughput={'ReadCapacityUnits': 10, 'WriteCapacityUnits': 10}
        )
        table.wait_until_exists()
        print("GameScores table created successfully!")

# Store game results
def save_game_result():
    table = dynamodb.Table(table_name)
    game_id = int(time.time())  # Unique game ID based on timestamp
    timestamp = datetime.datetime.now().isoformat()
    item = {
        "game_id": game_id,
        "player_1_score": scores[1],
        "player_2_score": scores[2],
        "timestamp": timestamp
    }
    table.put_item(Item=item)
    print("Game results saved to database.")

# Convert DynamoDB's Decimal values to int
def convert_decimal(obj):
    if isinstance(obj, Decimal):
        return int(obj)  # Convert to integer
    elif isinstance(obj, dict):
        return {k: convert_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_decimal(i) for i in obj]
    return obj

# Retrieve high scores and fix Decimal issue
def get_high_scores():
    table = dynamodb.Table(table_name)
    response = table.scan()
    scores_list = response.get("Items", [])
    scores_list = convert_decimal(scores_list)  # Convert Decimals to int
    return sorted(scores_list, key=lambda x: max(x["player_1_score"], x["player_2_score"]), reverse=True)

# Load Simulated Data
num_samples = 1000000  # Ensure data doesn't run out
simulated_data = [
    (random.randint(100, 700), random.randint(100, 500), random.choice([1, 2])) 
    for _ in range(num_samples)
]
data_index = 0

def send_to_all_clients(message):
    """Sends a message to all connected clients."""
    for addr in clients.values():
        server_socket.sendto(message.encode(), addr)

def handle_client():
    """Handles incoming client messages and game logic."""
    global boss_hp, overlay_angle, game_running, scores
    while True:
        try:
            data, addr = server_socket.recvfrom(BUFFER_SIZE)
            message = data.decode().strip()

            if not message:
                continue  # Ignore empty messages
            
            print(f"Received message: {message}")  # 🔍 Debugging

            parts = message.split(",")

            if parts[0] == "PLAYER_ID" and len(parts) == 2:
                player_id = int(parts[1])
                clients[player_id] = addr
                print(f"Player {player_id} joined: {addr}")
                send_to_all_clients(f"PLAYER_CONNECTED,{player_id}")

            elif parts[0] == "PLAYER_READY":
                print(f"Player {addr} is ready.")
                players_ready.add(addr)
            
                if len(players_ready) == 2:
                    game_running = True
                    print("Game started!")
                    send_to_all_clients("GAME_START")
            
            elif parts[0] == "RESET_GAME":
                print("Resetting game state...")
                boss_hp = MAXBOSSHP  # Reset boss HP
                scores = {1: 0, 2: 0}  # Reset scores
                game_running = False  # Ensure fresh start
                players_ready.clear()  # Ensure players re-enter start screen


            elif game_running and parts[0] == "SCORE":
                if len(parts) < 2:
                    print(f"Warning: Malformed SCORE message: {message}")
                    continue

                player_id = int(parts[1])
                scores[player_id] += 1

                if boss_hp > 0:
                    boss_hp -= 10  # Damage per hit
                    send_to_all_clients(f"SCORE_UPDATE,{player_id},{scores[player_id]},{boss_hp}")
                    print(f"Player {player_id} scored! Boss HP: {boss_hp}")

                if boss_hp <= 0:
                    boss_hp = 0
                    send_to_all_clients("GAME_OVER")
                    print("Boss defeated! Game over.")
                    game_running = False
                    save_game_result()
                    time.sleep(7)  # Delay before sending high scores
                    high_scores = get_high_scores()
                    send_to_all_clients(f"HIGH_SCORES,{json.dumps(high_scores)}")
                    break
            else:
                print(f"Warning: Received malformed message: {message}")

        except Exception as e:
            print(f"Error: {e}")
            continue

threading.Thread(target=handle_client, daemon=True).start()

def update_overlay():
    """Thread function to update overlay rectangle and send to clients."""
    global overlay_angle
    while True:
        if game_running:
            overlay_angle = random.randint(-45, 45)
            overlay_message = f"OVERLAY,{overlay_angle}"
            send_to_all_clients(overlay_message)
            print(f"Sent overlay angle: {overlay_angle}")
        time.sleep(1)  # Update every second

# Start a thread for overlay updates
threading.Thread(target=update_overlay, daemon=True).start()

create_table()

while True:
    try:
        if game_running and data_index < len(simulated_data):
            xpos, ypos, player_no = simulated_data[data_index]
            message = f"{xpos},{ypos},{player_no}"
            data_index += 1

            send_to_all_clients(message)
            print(f"Sent: {message}")

        time.sleep(0.05)  # 50ms per update (~20 updates per second)
    except KeyboardInterrupt:
        print("Server shutting down...")
        break

server_socket.close()
