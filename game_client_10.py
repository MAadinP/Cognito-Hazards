import pygame
import socket
import threading
import math
import os
import json

#Known Issues:
# Game doesn't reset after boss is defeated
# High scores are not displayed after game over

os.environ['SDL_AUDIODRIVER'] = 'dummy'  # Prevent pygame from initializing the audio driver

# Pygame setup
pygame.init()
WIDTH, HEIGHT = 800, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
clock = pygame.time.Clock()
font = pygame.font.Font(None, 36)

game_state = "player_select"  # Possible states: player_select, start_screen, playing, game_over, high_scores
player_id = None
players_ready = set()
high_scores = []

# Network setup
SERVER_IP = "54.80.2.56"  # Replace with your server IP
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
boss_hp = 10000  # Boss health points
boss_hp_max = 10000
boss_hp_bar_length = 400
boss_hp_ratio = boss_hp_max / boss_hp_bar_length

# Adjust boss size and position
BOSS_SIZE = (500, 500)  # Bigger boss
BOSS_Y_OFFSET = -80  # Move boss downward

# Load boss animations
ANIMATION_PATHS = {
    "idle": "individual_sprites/01_demon_idle",
    "take_hit": "individual_sprites/04_demon_take_hit",
    "die": "individual_sprites/05_demon_death"
}

def load_animation_frames(folder, flip=False, scale_size=(128, 128)):
    frames = []
    if not os.path.exists(folder):
        return [pygame.Surface(scale_size, pygame.SRCALPHA)]  # Placeholder frame
    
    for filename in sorted(os.listdir(folder)):
        if filename.endswith(".png"):
            frame = pygame.image.load(os.path.join(folder, filename)).convert_alpha()
            frame = pygame.transform.scale(frame, scale_size)  # Scale size
            if flip:
                frame = pygame.transform.flip(frame, True, False)  # Flip for player 2
            frames.append(frame)
    
    return frames if frames else [pygame.Surface(scale_size, pygame.SRCALPHA)]

# Load animations for swords
SWORD_PATH = "sword_sprites"
sword_idle = {
    1: load_animation_frames(os.path.join(SWORD_PATH, "sword_idle"), scale_size=(200, 200)),
    2: load_animation_frames(os.path.join(SWORD_PATH, "sword_idle"), flip=True, scale_size=(200, 200))
}
sword_combo = {
    1: load_animation_frames(os.path.join(SWORD_PATH, "sword_combo"), scale_size=(200, 200)),
    2: load_animation_frames(os.path.join(SWORD_PATH, "sword_combo"), flip=True, scale_size=(200, 200))
}

sword_states = {1: "idle", 2: "idle"}
sword_frame_index = {1: 0, 2: 0}
sword_last_update = {1: pygame.time.get_ticks(), 2: pygame.time.get_ticks()}
sword_animation_speed = 100

# Boss animation setup
animation_frames = {name: load_animation_frames(path, scale_size=BOSS_SIZE) for name, path in ANIMATION_PATHS.items()}
current_animation = "idle"
frame_index = 0
ANIMATION_SPEED = 100
last_update = pygame.time.get_ticks()
hit_timer = 0

def send_message(message):
    client_socket.sendto(message.encode(), (SERVER_IP, SERVER_PORT))

def draw_player_select():
    screen.fill((0, 0, 0))
    title = font.render("Select Player 1 or 2", True, (255, 255, 255))
    screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 200))
    start_text = font.render("Press 1 or 2 to select your player", True, (200, 200, 200))
    screen.blit(start_text, (WIDTH // 2 - start_text.get_width() // 2, 250))
    pygame.display.flip()

def draw_start_screen():
    screen.fill((0, 0, 0))
    title = font.render("Press ENTER to start", True, (255, 255, 255))
    screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 200))
    pygame.display.flip()

def draw_game_over():
    screen.fill((0, 0, 0))
    game_over_text = font.render("Game Over!", True, (255, 0, 0))
    score_text_1 = font.render(f"Player 1: {scores[1]}", True, (255, 255, 255))
    score_text_2 = font.render(f"Player 2: {scores[2]}", True, (255, 255, 255))
    continue_text = font.render("Press ENTER to continue", True, (200, 200, 200))
    screen.blit(game_over_text, (WIDTH // 2 - game_over_text.get_width() // 2, 200))
    screen.blit(score_text_1, (WIDTH // 2 - 100, 250))
    screen.blit(score_text_2, (WIDTH // 2 + 100, 250))
    screen.blit(continue_text, (WIDTH // 2 - continue_text.get_width() // 2, 300))
    pygame.display.flip()

def draw_high_scores():
    screen.fill((0, 0, 0))
    title = font.render("High Scores", True, (255, 255, 255))
    screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 100))
    
    y_offset = 150
    for score_entry in high_scores[:5]:  # Show top 5 scores
        score_text = font.render(f"{score_entry['timestamp']}: P1-{score_entry['player_1_score']} P2-{score_entry['player_2_score']}", True, (200, 200, 200))
        screen.blit(score_text, (WIDTH // 2 - score_text.get_width() // 2, y_offset))
        y_offset += 40
    
    continue_text = font.render("Press ENTER to continue", True, (200, 200, 200))
    screen.blit(continue_text, (WIDTH // 2 - continue_text.get_width() // 2, y_offset + 40))
    pygame.display.flip()

def receive_data():
    global game_state, boss_hp, high_scores, players_ready, current_animation
    while True:
        try:
            data, _ = client_socket.recvfrom(BUFFER_SIZE)
            decoded_data = data.decode()
            if decoded_data.startswith("GAME_START"):
                game_state = "playing"
            elif decoded_data.startswith("GAME_OVER"):
                game_state = "game_over"
            elif decoded_data.startswith("HIGH_SCORES"):
                game_state = "high_scores"
                _, scores_json = decoded_data.split(",", 1)
                high_scores = json.loads(scores_json)
            elif decoded_data.startswith("PLAYER_READY"):
                players_ready.add(decoded_data.split(",")[1])
                if len(players_ready) == 2:
                    send_message("GAME_START")
                    game_state = "playing"
            
            if game_state == "playing":
                if decoded_data.startswith("OVERLAY"):
                    _, angle = decoded_data.split(",")
                    global overlay_angle
                    overlay_angle = int(angle)
                elif decoded_data.startswith("SCORE_UPDATE"):
                    _, player_id, score, boss_health = decoded_data.split(",")
                    scores[int(player_id)] = int(score)
                    boss_hp = int(boss_health)  # Sync boss HP from server
                    sword_states[int(player_id)] = "combo"
                    sword_frame_index[int(player_id)] = 0
                    if boss_hp <= 0:
                        current_animation = "die"
                        frame_index = 0
                    else:
                        current_animation = "take_hit"
                        frame_index = 0
                        hit_timer = pygame.time.get_ticks()
                else:
                    xpos, ypos, player_id = map(float, decoded_data.split(","))
                    angle = ((xpos - X_MID) / (X_MAX - X_MIN)) * 90  # Scale to -45 to 45
                    color = (0, 255, 0) if ypos > Y_MID else (255, 0, 0)
                    players[int(player_id)]["angle"] = angle
                    players[int(player_id)]["color"] = color
        except ValueError:
            pass
        except socket.timeout:
            continue

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
    boss_rect = boss_image.get_rect(center=(WIDTH // 2, HEIGHT // 2 + BOSS_Y_OFFSET))
    screen.blit(boss_image, boss_rect.topleft)
    
def draw_boss_health():
    health_bar_width = int(boss_hp / boss_hp_ratio)
    pygame.draw.rect(screen, (255, 0, 0), (200, 20, health_bar_width, 25))
    pygame.draw.rect(screen, (255, 255, 255), (200, 20, boss_hp_bar_length, 25), 4)

def draw_sword(player_id, pivot):
    now = pygame.time.get_ticks()
    if now - sword_last_update[player_id] > sword_animation_speed:
        sword_last_update[player_id] = now
        if sword_states[player_id] == "combo":
            sword_frame_index[player_id] += 1
            if sword_frame_index[player_id] >= len(sword_combo[player_id]):
                sword_states[player_id] = "idle"
                sword_frame_index[player_id] = 0
    
    current_sword_frames = sword_combo if sword_states[player_id] == "combo" else sword_idle
    sword_image = current_sword_frames[player_id][sword_frame_index[player_id]]
    sword_rect = sword_image.get_rect(center=(pivot[0], pivot[1] + 130)) # Move sword downward
    screen.blit(sword_image, sword_rect.topleft)

running = True
while running:
    screen.fill((0, 0, 0))
    if game_state == "player_select":
        draw_player_select()
    elif game_state == "start_screen":
        draw_start_screen()
    elif game_state == "playing":
        draw_boss_health()
        draw_boss()
        draw_overlay_rectangle(PIVOT_1, overlay_angle)
        draw_overlay_rectangle(PIVOT_2, overlay_angle)
        draw_tilting_rectangle(PIVOT_1, players[1]["angle"], players[1]["color"])
        draw_tilting_rectangle(PIVOT_2, players[2]["angle"], players[2]["color"])
        draw_sword(1, PIVOT_1)
        draw_sword(2, PIVOT_2)

        # Check for scoring condition
        for player_id, pivot in [(1, PIVOT_1), (2, PIVOT_2)]:
            if abs(players[player_id]["angle"] - overlay_angle) < 5 and players[player_id]["color"] == (0, 255, 0):
                send_score(player_id)

        # Display scores
        score_text_1 = font.render(f"Player 1: {scores[1]}", True, (255, 255, 255))
        screen.blit(score_text_1, (20, 20))
        score_text_2 = font.render(f"Player 2: {scores[2]}", True, (255, 255, 255))
        screen.blit(score_text_2, (WIDTH - 150, 20))
    
    elif game_state == "game_over":
        draw_game_over()
    elif game_state == "high_scores":
        draw_high_scores()
    
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif game_state == "player_select" and event.type == pygame.KEYDOWN:
            if event.key == pygame.K_1:
                send_message("PLAYER_ID,1")
                game_state = "start_screen"
            elif event.key == pygame.K_2:
                send_message("PLAYER_ID,2")
                game_state = "start_screen"
        elif game_state == "start_screen" and event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                send_message("PLAYER_READY")
        elif game_state == "game_over" and event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                game_state = "high_scores"
        elif game_state == "high_scores" and event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                game_state = "start_screen"
                players_ready.clear()  # Ensure players must press ENTER again
                boss_hp = boss_hp_max  # Reset boss HP
                scores = {1: 0, 2: 0}  # Reset scores
                current_animation = "idle"  # Reset animations
                send_message("RESET_GAME")  # Notify server to fully reset

    
    pygame.display.flip()
    clock.tick(60)
pygame.quit()
