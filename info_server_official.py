import socket
import threading
import random
import time
import boto3
import datetime
import json
from decimal import Decimal

# Server setup for TCP connections
TCP_HOST = "0.0.0.0"  #Change this to the local DNS IPv4 address
TCP_PORT = 12000  # Port for TCP connections
TCP_BUFFER_SIZE = 1024

# Server setup
UDP_HOST = "0.0.0.0" #Change this to the local DNS IPv4 address
UDP_PORT = 12345
UDP_BUFFER_SIZE = 1024

server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server_socket.bind((UDP_HOST, UDP_PORT))
print(f"UDP Game Server started on {UDP_HOST}:{UDP_PORT}")

clients = {}  # Stores player IDs and their addresses
TCP_clients = [] # Stores TCP client sockets
players_ready = set()
boss_hp = 3000
overlay_angle = random.randint(-45, 45)
scores = {1: 0, 2: 0}  # Player scores
game_running = False
final_health = {1: 100, 2: 100}

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
    return game_id  # Return the game ID of the latest game

def convert_decimal(obj):
    if isinstance(obj, Decimal):
        return int(obj)
    elif isinstance(obj, dict):
        return {k: convert_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_decimal(i) for i in obj]
    return obj

def get_high_scores(latest_game_id):
    table = dynamodb.Table(table_name)
    response = table.scan()
    scores_list = response.get("Items", [])
    scores_list = convert_decimal(scores_list)
    sorted_scores = sorted(scores_list, key=lambda x: max(x["player_1_score"], x["player_2_score"]), reverse=True)
    
    # Get top 5 scores
    top_5_scores = sorted_scores[:5]
    
    # Find the latest game's ranking if it is not in the top 5
    latest_game_rank = next((i + 1 for i, game in enumerate(sorted_scores) if game["game_id"] == latest_game_id), None)
    latest_game_score = next((game for game in sorted_scores if game["game_id"] == latest_game_id), None)
    
    if latest_game_rank and latest_game_rank > 5:
        latest_game_score["rank"] = latest_game_rank
        return top_5_scores + [latest_game_score]
    else:
        return top_5_scores

def send_to_all_clients(message):
    print(f"Sending to clients: {message[:100]}...")  # Debug print

    for addr in clients.keys():  # Use stored (IP, Port) tuples
        if isinstance(addr, tuple):  # Ensure it's a valid address tuple
            server_socket.sendto(message.encode(), addr)
        else:
            print(f"Error: Invalid address {addr} in clients dictionary")


def UDP_handle_client():
    global boss_hp, game_running, players_ready
    while True:
        try:
            data, addr = server_socket.recvfrom(UDP_BUFFER_SIZE)
            message = data.decode()

            if message.startswith("PLAYER_ID"):
                _, player_id = message.split(",")
                player_id = int(player_id)

                clients[addr] = player_id  # Store player's network address as key
                players_ready.add(player_id)

                print(f"Player {player_id} joined from {addr}. Clients mapping: {clients}")

                if len(players_ready) == 2:
                    game_running = True
                    print("Game started!")
                    send_to_all_clients("GAME_START")

            elif message.startswith("GAME_OVER"):
                # Message format: GAME_OVER,player_id,remaining_health
                try:
                    _, pid, remaining_health = message.split(",")
                    pid = int(pid)
                    remaining_health = int(remaining_health)
                    final_health[pid] = remaining_health
                    # End the game when any player sends a GAME_OVER
                    game_running = False
                    # Compute final scores: final score = attack score + remaining health
                    final_score1 = scores[1] + final_health.get(1, 0)
                    final_score2 = scores[2] + final_health.get(2, 0)
                    scores[1] = final_score1
                    scores[2] = final_score2
                    latest_game_id = save_game_result()
                    high_scores = get_high_scores(latest_game_id)
                    send_to_all_clients(f"HIGH_SCORES,{json.dumps(high_scores)}")
                    players_ready.clear()
                except Exception as e:
                    print("Error processing GAME_OVER message:", e)

            
            elif game_running and message.startswith("SCORE"):
                _, player_id = message.split(",")
                player_id = int(player_id)
                scores[player_id] += 1
                
                if boss_hp > 0:
                    boss_hp -= 10
                    send_to_all_clients(f"SCORE_UPDATE,{player_id},{scores[player_id]},{boss_hp}")
                    print(f"Player {player_id} scored! Boss HP: {boss_hp}")
                
                if boss_hp <= 0:
                    boss_hp = 0
                    print("Boss defeated! Saving scores and showing high scores.")
                    game_running = False
                    latest_game_id = save_game_result()
                    high_scores = get_high_scores(latest_game_id)
                    send_to_all_clients(f"HIGH_SCORES,{json.dumps(high_scores)}")
                    players_ready.clear()
            
            elif message.startswith("PLAY_AGAIN"):
                _, player_id = message.split(",")
                player_id = int(player_id)

                # Find the actual player ID based on the sender's address
                actual_player_id = clients.get(addr, None)

                if actual_player_id is None:
                    print(f"Unknown address {addr} tried to play again.")
                    continue

                print(f"Player {actual_player_id} wants to play again from {addr}")

                players_ready.add(actual_player_id)

                if len(players_ready) == 1:
                    send_to_all_clients(f"WAITING,{actual_player_id}")
                elif len(players_ready) == 2:
                    send_to_all_clients("GAME_START")
                    boss_hp = 3000
                    scores[1] = scores[2] = 0
                    game_running = True
                    players_ready.clear()

        
        except Exception as e:
            print(f"Error: {e}")
            continue

threading.Thread(target=UDP_handle_client, daemon=True).start()

def handle_tcp_client(conn, addr):
    print(f"Client {addr} connected.")
    TCP_clients.append(conn)

    try: 
        with conn:
            print(f"Connected by {addr}")

            #receiving data from clients
            while True:
                data = conn.recv(1024).decode("utf-8")
                print(f"Receiving")
                #the data is currently in JSON string, convert it back to a list (same format shown as client)
                coordinates = json.loads(data)
                send_fpga_data(coordinates[0],coordinates[1],coordinates[2])
                print(coordinates)
                if not data:
                    break
                    
                # print(f"Data is coming through: {data}")
                # try:
                #     game_id = int(data)
                #     response = fetch_game_info(data)
                #     conn.send(response.encode())
                                            
                # except ValueError:
                #     #Its FPGA Data
                #     print(f"FPGA Data from {addr}: {data}")

                if data.lower() == "exit":
                    print(f"Client {addr} requested exit.")
                    break
                            
    except Exception as e:
        print(f"Error handling client {addr}: {e}")

    finally:
        print(f"Client {addr} disconnected.")
        clients.remove(conn)
        conn.close()



def start_tcp_server():
    """Start the TCP server for web/client connections."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as tcp_server_socket:
        tcp_server_socket.bind((TCP_HOST, TCP_PORT))
        tcp_server_socket.listen(5)
        print(f"TCP Server listening on {TCP_HOST}:{TCP_PORT}")

        while True:
            connection_socket, client_addr = tcp_server_socket.accept()
            print(f"TCP Connection from {client_addr}")
            threading.Thread(
                target=handle_tcp_client, 
                args=(connection_socket, client_addr), 
                daemon=True
            ).start()

def update_overlay():
    global overlay_angle
    while True:
        if game_running:
            overlay_angle = random.randint(-45, 45)
            overlay_message = f"OVERLAY,{overlay_angle}"
            send_to_all_clients(overlay_message)
            print(f"Sent overlay angle: {overlay_angle}")
        time.sleep(1)

threading.Thread(target=update_overlay, daemon=True).start()

create_table()

threading.Thread(target=start_tcp_server, daemon=True).start()

def send_fpga_data(x,y,player_no):
    message = f"{x},{y},{player_no}"
    send_to_all_clients(message)
    print(f"Sent: {message}") #debugging 

while True:
    time.sleep(1)  # Keeps the main thread alive


server_socket.close()
