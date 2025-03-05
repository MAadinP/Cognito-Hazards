import pygame
import socket
import threading
import math
import os
os.environ['SDL_AUDIODRIVER'] = 'dummy' #prevent pygame from initializing audio driver and giving errors


# Pygame setup
pygame.init()
WIDTH, HEIGHT = 800, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
clock = pygame.time.Clock()
font = pygame.font.Font(None, 36)

# Network setup
SERVER_IP = "34.228.6.66"  
SERVER_PORT = 12345
BUFFER_SIZE = 1024

client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
client_socket.settimeout(0.1)  # Non-blocking receive

# Send initial handshake message
client_socket.sendto(b"HELLO", (SERVER_IP, SERVER_PORT))

# Define pivot points and rotation range
X_MIN, X_MAX = 100, 700  # X range
Y_MIN, Y_MAX = 100, 500  # Y range
X_MID = (X_MIN + X_MAX) / 2
Y_MID = (Y_MIN + Y_MAX) / 2

PIVOT_1 = (WIDTH // 4, HEIGHT // 2)  # Player 1 pivot (Left side)
PIVOT_2 = (3 * WIDTH // 4, HEIGHT // 2)  # Player 2 pivot (Right side)
RECT_WIDTH, RECT_HEIGHT = 120, 20  # Rectangle dimensions

players = {1: {"angle": 0, "color": (255, 0, 0)}, 2: {"angle": 0, "color": (255, 0, 0)}}
scores = {1: 0, 2: 0}
overlay_angle = 0  # Updated from the server
boss_hp = 10000  
boss_hp_max = 10000
boss_hp_bar_length = 400
boss_hp_ratio = boss_hp_max / boss_hp_bar_length

# Load boss animations
ANIMATION_PATHS = {
    "idle": "individual_sprites/01_demon_idle",
    "take_hit": "individual_sprites/04_demon_take_hit",
    "die": "individual_sprites/05_demon_death"
}

def load_animation_frames(folder):
    frames = []
    if not os.path.exists(folder):
        print(f"Warning: Animation folder {folder} not found.")
        return [pygame.Surface((100, 100), pygame.SRCALPHA)]  # Placeholder frame
    
    for filename in sorted(os.listdir(folder)):
        if filename.endswith(".png"):
            frame = pygame.image.load(os.path.join(folder, filename)).convert_alpha()
            frame = pygame.transform.scale(frame, (frame.get_width() * 2, frame.get_height() * 2))  # Scale up boss
            frames.append(frame)
    
    if not frames:
        print(f"Warning: No valid frames found in {folder}.")
        return [pygame.Surface((100, 100), pygame.SRCALPHA)]  # Placeholder frame
    
    return frames

animation_frames = {name: load_animation_frames(path) for name, path in ANIMATION_PATHS.items()}
current_animation = "idle"
frame_index = 0
ANIMATION_SPEED = 100  # Milliseconds per frame
last_update = pygame.time.get_ticks()
hit_timer = 0  # Timer for hit animation

def receive_data():
    """Thread function to listen for server updates."""
    global boss_hp, current_animation, frame_index, hit_timer
    while True:
        try:
            data, _ = client_socket.recvfrom(BUFFER_SIZE)
            decoded_data = data.decode()
            try:
                if decoded_data.startswith("OVERLAY"):
                    _, angle = decoded_data.split(",")
                    global overlay_angle
                    overlay_angle = int(angle)
                elif decoded_data.startswith("SCORE_UPDATE"):
                    _, player_id, score, boss_health = decoded_data.split(",")
                    scores[int(player_id)] = int(score)
                    boss_hp = int(boss_health)  # Sync boss HP from server
                    if boss_hp <= 0:
                        current_animation = "die"
                        frame_index = 0
                    else:
                        current_animation = "take_hit"
                        frame_index = 0
                        hit_timer = pygame.time.get_ticks()  # Start hit animation timer
                else:
                    xpos, ypos, player_id = map(float, decoded_data.split(","))
                    angle = ((xpos - X_MID) / (X_MAX - X_MIN)) * 90  # Scale to -45 to 45
                    color = (0, 255, 0) if ypos > Y_MID else (255, 0, 0)
                    players[int(player_id)]["angle"] = angle
                    players[int(player_id)]["color"] = color
            except ValueError:
                print(f"Received malformed data: {decoded_data}")
        except socket.timeout:
            continue

# Start receiving thread
threading.Thread(target=receive_data, daemon=True).start()

def send_score(player_id):
    message = f"SCORE,{player_id}"
    client_socket.sendto(message.encode(), (SERVER_IP, SERVER_PORT))

def draw_tilting_rectangle(pivot, angle, color):
    """Draws a rectangle tilted around a pivot point."""
    rect_surf = pygame.Surface((RECT_WIDTH, RECT_HEIGHT), pygame.SRCALPHA)
    rect_surf.fill(color)
    rotated_surf = pygame.transform.rotate(rect_surf, angle)
    rotated_rect = rotated_surf.get_rect(center=pivot)
    screen.blit(rotated_surf, rotated_rect.topleft)

def draw_overlay_rectangle(pivot, angle):
    """Draws the overlay rectangle faintly."""
    overlay_surf = pygame.Surface((RECT_WIDTH + 10, RECT_HEIGHT + 10), pygame.SRCALPHA)
    overlay_surf.fill((255, 255, 255, 50))  # Transparent white
    rotated_surf = pygame.transform.rotate(overlay_surf, angle)
    rotated_rect = rotated_surf.get_rect(center=pivot)
    screen.blit(rotated_surf, rotated_rect.topleft)

def draw_boss():
    """Draws the boss animation in the center of the screen."""
    global last_update, frame_index, current_animation, hit_timer
    now = pygame.time.get_ticks()
    
    if current_animation == "take_hit" and now - hit_timer > 500:
        current_animation = "idle"  # Return to idle after 500ms of hit animation
    
    if now - last_update > ANIMATION_SPEED:
        if current_animation == "die" and frame_index == len(animation_frames[current_animation]) - 1:
            pass  # Keep last frame of death animation
        else:
            frame_index = (frame_index + 1) % len(animation_frames[current_animation])
        last_update = now
    
    boss_image = animation_frames[current_animation][frame_index]
    boss_rect = boss_image.get_rect(center=(WIDTH // 2, HEIGHT // 2))
    screen.blit(boss_image, boss_rect.topleft)

def draw_boss_health():
    health_bar_width = int(boss_hp / boss_hp_ratio)
    pygame.draw.rect(screen, (255, 0, 0), (200, 20, health_bar_width, 25))
    pygame.draw.rect(screen, (255, 255, 255), (200, 20, boss_hp_bar_length, 25), 4)

running = True
while running:
    screen.fill((30, 30, 30))
    draw_boss_health()
    draw_boss()
    draw_overlay_rectangle(PIVOT_1, overlay_angle)
    draw_overlay_rectangle(PIVOT_2, overlay_angle)
    draw_tilting_rectangle(PIVOT_1, players[1]["angle"], players[1]["color"])
    draw_tilting_rectangle(PIVOT_2, players[2]["angle"], players[2]["color"])

    # Check for scoring condition
    for player_id, pivot in [(1, PIVOT_1), (2, PIVOT_2)]:
        if abs(players[player_id]["angle"] - overlay_angle) < 5 and players[player_id]["color"] == (0, 255, 0):
            send_score(player_id)

    # Display scores
    score_text_1 = font.render(f"Player 1: {scores[1]}", True, (255, 255, 255))
    screen.blit(score_text_1, (20, 20))
    score_text_2 = font.render(f"Player 2: {scores[2]}", True, (255, 255, 255))
    screen.blit(score_text_2, (WIDTH - 150, 20))

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
    pygame.display.flip()
    clock.tick(60)
pygame.quit()
