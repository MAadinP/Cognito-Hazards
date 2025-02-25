import socket
import boto3
import json

print("Starting the Game Info Server...")

# AWS DynamoDB Setup
dynamodb = boto3.resource('dynamodb', region_name="us-east-1")
table_name = "GameInfo"

# Create sample table if it doesn't exist
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

# Fetch game info
def fetch_game_info(game_id):
    table = dynamodb.Table(table_name)
    try:
        response = table.get_item(Key={'game_id': int(game_id)})
        if 'Item' in response:
            return json.dumps(response['Item'])
        else:
            return json.dumps({"error": "Game ID not found"})
    except Exception as e:
        return json.dumps({"error": str(e)})

# Set up TCP Server
server_port = 12000
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.bind(('0.0.0.0', server_port))
server_socket.listen(5)

print(f"Server running on port {server_port}")

# Ensure DB is set up
create_sample_table()
insert_sample_data()

while True:
    connection_socket, caddr = server_socket.accept()
    print(f"Connection from {caddr}")

    # Receive the game ID
    game_id = connection_socket.recv(1024).decode().strip()
    print(f"Client requested Game ID: {game_id}")

    # Fetch data and send it back
    response = fetch_game_info(game_id)
    connection_socket.send(response.encode())

    connection_socket.close()
