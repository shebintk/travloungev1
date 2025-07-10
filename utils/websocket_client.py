import socketio
import json

sio = socketio.Client()

@sio.event
def connect():
    print('Connected to server')
    
@sio.event
def disconnect():
    print('Disconnected from server')


def connect_to_server(server_url="http://127.0.0.1:8000"):
    sio.connect(server_url)

    
def send_room_numbers(room_numbers,namespace):
    print(f"Sending to namespace: {namespace}")
    sio.emit(namespace,'room_numbers', json.dumps(room_numbers))
    
def disconnect_from_server():
    sio.disconnect()

@sio.event     
def exit():
    disconnect_from_server()
    
def start_client(server_url):
    connect_to_server(server_url)