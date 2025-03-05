import socket
import threading
import intel_jtag_uart
import json
import sys
import time
import queue

# Server connection details
HOST = "ec2-54-161-208-12.compute-1.amazonaws.com"
PORT = 12000

# Queue for sharing accelerometer data between threads
accel_data_queue = queue.Queue()

def receive_messages(client_socket):
    while True:
        try:
            data = client_socket.recv(1024).decode("utf-8")
            if not data:
                break
            print(f"Server: {data}")
        except:
            print("\nDisconnected from server.")
            break

def query_game_info(client_socket, game_id):
    client_socket.send(str(game_id).encode()) 
    data = client_socket.recv(1024).decode() 
    return json.loads(data)

def send_to_server(data, client_socket):
    try:
        client_socket.sendall(data.encode("utf-8"))
    except Exception as e:
        print(f"Error sending data to server: {e}")
    

def accelerometer_reader(stop_event, client_socket):
    """Thread function to read accelerometer data from FPGA via JTAG UART"""
    # Try different cable names, including the one that worked for you
    cable_names = [
        "USB-Blaster [USB-0]",  # Try this first since it worked for you
        "Altera USB-Blaster",
        "USB-Blaster",
        "Intel FPGA Download Cable",
        "USB-BlasterII"
    ]
    
    ju = None
    connected = False
    
    while not stop_event.is_set():
        # If not connected, try to connect
        if not connected:
            for cable in cable_names:
                try:
                    print(f"Trying to connect to JTAG: {cable}")
                    ju = intel_jtag_uart.intel_jtag_uart(cable_name=cable)
                    print(f"Successfully connected to {cable}")
                    connected = True
                    break
                except Exception as e:
                    print(f"Failed to connect to {cable}: {e}")
            
            if not connected:
                print("Could not connect to any JTAG cable. Retrying in 5 seconds...")
                time.sleep(5)
                continue
        
        # Read data if connected
        try:
            data = ju.read()
            if data and data.strip():
                # Put data in queue and also print immediately
                timestamp = time.strftime("%H:%M:%S", time.localtime())
                formatted_data = f"[{timestamp}] ACCEL: {data.strip()}"

                #print on the client-side 
                print(formatted_data)

                #send to server
                send_to_server(formatted_data, client_socket)
                print(f"CHECKING IF WE PASS THIS MULTIPLE TIMES")

                #put data in queue
                accel_data_queue.put((timestamp, data.strip()))
            
            # Small delay to avoid hammering the JTAG interface
            time.sleep(0.1)
            
            
        except Exception as e:
            print(f"Error reading from JTAG: {e}")
            connected = False
            time.sleep(1)  # Wait before retrying
            

def start_client():
    # Connect to server
    try:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((HOST, PORT))
        print(f"Connected to server at {HOST}:{PORT}")
    except Exception as e:
        print(f"Error connecting to server: {e}")
        return

    # Start message receiving thread
    threading.Thread(
        target=receive_messages, args=(client_socket,), daemon=True
    ).start()

    # Create stop event for accelerometer thread
    stop_event = threading.Event()
    
    # Start accelerometer reader thread
    accel_thread = threading.Thread(
        target=accelerometer_reader, 
        args=(stop_event,client_socket),
        daemon=True
    )
    accel_thread.start()
    print("Accelerometer reader started. Data will display automatically.")
    
    # Main client loop
    try:
        while True:
            print("\nOptions:")
            print("1. Query game info")
            print("2. View recent accelerometer readings")
            print("3. Exit")
            choice = input("Enter your choice (1-3): ")
            
            if choice == "1":
                game_id = input("Enter Game ID to query: ")
                try:
                    response = query_game_info(client_socket, game_id)
                    print("Game Info:", response)
                except Exception as e:
                    print(f"Error querying game info: {e}")
            
            elif choice == "2":
                # Display recent accelerometer readings from queue
                print("\nRecent Accelerometer Readings:")
                # Get all items from queue without blocking
                readings = []
                try:
                    while True:
                        readings.append(accel_data_queue.get_nowait())
                        accel_data_queue.task_done()
                except queue.Empty:
                    pass
                
                # Display last 10 readings
                if readings:
                    for timestamp, data in readings[-10:]:
                        print(f"[{timestamp}] {data}")
                else:
                    print("No accelerometer readings available yet.")
            
            elif choice == "3":
                print("Exiting...")
                client_socket.send("exit".encode())
                break
                
            else:
                print("Invalid choice. Please enter 1, 2, or 3.")
    
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        # Signal accelerometer thread to stop
        stop_event.set()
        # Close socket
        try:
            client_socket.send("exit".encode())
        except:
            pass
        client_socket.close()
        print("Client shut down successfully")

if __name__ == "__main__":
    start_client()
