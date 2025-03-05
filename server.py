import socket
import threading
import boto3
import json
import decimal

HOST = "0.0.0.0" #listens to all available networks interfaces
PORT = 12000 #port number where the server listens for incoming connections - changed from 12345

clients = [] #list of connected clients

# AWS DynamoDB Setup
dynamodb = boto3.resource('dynamodb', region_name="us-east-1")
table_name = "GameInfo"

def create_sample_table():
    existing_tables = [table.name for table in dynamodb.tables.all()]
    
    if table_name not in existing_tables:
        table = dynamodb.create_table(
            TableName=table_name,
            KeySchema=[
                {'AttributeName': 'game_id', 'KeyType': 'HASH'}  # Partition key
            ],
            AttributeDefinitions=[
                {'AttributeName': 'game_id', 'AttributeType': 'N'}
            ],
            ProvisionedThroughput={'ReadCapacityUnits': 10, 'WriteCapacityUnits': 10}
        )
        table.wait_until_exists()
        print("Table created successfully!")

# Insert sample data
def insert_sample_data():
    table = dynamodb.Table(table_name)
    sample_data = [
        {"game_id": 1, "name": "Block Blast", "players": 1, "genre": "Puszzle"},
        {"game_id": 2, "name": "Dragon Quest", "players": 1, "genre": "RPG"},
        {"game_id": 3, "name": "CSGO", "players": 10, "genre": "FPS"}
    ]

    for game in sample_data:
        table.put_item(Item=game)

    print("Sample data inserted.")

#converting decimal to int or float since python is not compatible with decimal for JSON
def decimal_converter(obj):
    if isinstance(obj, decimal.Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)

# Fetch game info
def fetch_game_info(game_id):
    table = dynamodb.Table(table_name)
    try:
        response = table.get_item(Key={'game_id': int(game_id)})
        if 'Item' in response:
            return json.dumps(response['Item'], default=decimal_converter)
        else:
            return json.dumps({"error": "Game ID not found"})
    except Exception as e:
        return json.dumps({"error": str(e)})

#threaded function that manages communicate with a client
def handle_client(conn, addr):
    print(f"Client {addr} connected.")
    clients.append(conn)

    try: 
        with conn:
            print(f"Connected by {addr}")

            #receiving data from clients
            while True:
                data = conn.recv(1024).decode("utf-8")
                print(f"Receiving")
                print(data)
                if not data:
                    break
                    
                print(f"Data is coming through: {data}")
                try:
                    game_id = int(data)
                    response = fetch_game_info(data)
                    conn.send(response.encode())
                                            
                except ValueError:
                    #Its FPGA Data
                    print(f"FPGA Data from {addr}: {data}")
                        
                

                if data.lower() == "exit":
                    print(f"Client {addr} requested exit.")
                    break

                    #broadcasting messages to other clients
                    #for client in clients:
                        #if client != conn:
                            #client.sendall(f"Client {addr}: {data}".encode("utf-8"))
                            
    except Exception as e:
        print(f"Error handling client {addr}: {e}")
        

    finally:
        print(f"Client {addr} disconnected.")
        clients.remove(conn)
        conn.close()


def start_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.bind((HOST, PORT))
        server_socket.listen(2)
        print(f"Server listening on {HOST}:{PORT}")

        create_sample_table()
        insert_sample_data()   

        while True:
            connection_socket, caddr = server_socket.accept()
            print(f"Connection from {caddr}")
            threading.Thread(
                target=handle_client, args=(connection_socket, caddr), daemon=True
            ).start()


if __name__ == "__main__":
    start_server()
