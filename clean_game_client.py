import pygame
import socket
import threading
import json
import os


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


def send_player_id(selected_id):
    global player_id
    player_id = selected_id
    message = f"PLAYER_ID,{player_id}"
    client_socket.sendto(message.encode(), (SERVER_IP, SERVER_PORT))


def draw_text(text, x, y, color=(255, 255, 255)):
    text_surface = font.render(text, True, color)
    screen.blit(text_surface, (x - text_surface.get_width() // 2, y))


def draw_menu():
    screen.fill((0, 0, 0))
    draw_text("Select Player 1 or 2", WIDTH // 2, 200)
    draw_text("Press 1 or 2 to select your player", WIDTH // 2, 250, (200, 200, 200))
    pygame.display.flip()


def draw_high_scores():
    screen.fill((0, 0, 0))
    draw_text("High Scores", WIDTH // 2, 100)
    y_offset = 150
    for score_entry in high_scores:
        color = (255, 255, 0) if score_entry == latest_game else (200, 200, 200)
        score_text = f"{score_entry['timestamp']}: P1-{score_entry['player_1_score']} P2-{score_entry['player_2_score']}"
        if "rank" in score_entry:
            score_text += f" (Rank: {score_entry['rank']})"
        draw_text(score_text, WIDTH // 2, y_offset, color)
        y_offset += 40
    draw_text("Press ENTER to play again", WIDTH // 2, y_offset + 40, (200, 200, 200))
    pygame.display.flip()


def request_play_again():
    global player_id, waiting_for_other
    if player_id is not None:
        client_socket.sendto(
            f"PLAY_AGAIN,{player_id}".encode(), (SERVER_IP, SERVER_PORT)
        )
        waiting_for_other = False  # Ensure it resets after sending request


def receive_data():
    global game_state, high_scores, latest_game, waiting_for_other, boss_hp
    while True:
        try:
            data, _ = client_socket.recvfrom(BUFFER_SIZE)
            decoded_data = data.decode()

            if decoded_data.startswith("GAME_START"):
                print("Received GAME_START from server. Resetting game state.")
                game_state = "playing"
                waiting_for_other = False
                boss_hp = 3000
                scores[1] = 0
                scores[2] = 0
                player_health = {1: 100, 2: 100}  # Reset player HP
                enemy_attack = {1: False, 2: False}  # Reset enemy attack flags
                enemy_attack_timer = {1: 0, 2: 0}  # Reset timers
                game_over_sent = False
                pygame.event.post(
                    pygame.event.Event(pygame.USEREVENT, {"type": "game_reset"})
                )

            elif decoded_data.startswith("HIGH_SCORES"):
                _, scores_json = decoded_data.split(",", 1)
                print("Received High Scores JSON:", scores_json[:100])
                high_scores = json.loads(scores_json)
                latest_game = high_scores[-1] if "rank" in high_scores[-1] else None
                if boss_hp <= 0:
                    game_state = "high_scores"
            elif decoded_data.startswith("WAITING"):
                print(f"Player {player_id} is waiting...")
                _, other_player = decoded_data.split(",")
                if game_state != "playing":  # Only wait if the game hasn't started
                    waiting_for_other = True

            elif decoded_data.startswith("SCORE_UPDATE"):
                _, p_id, score, boss_health = decoded_data.split(",")
                p_id = int(p_id)
                scores[p_id] = int(score)
                boss_hp = int(boss_health)  # Sync boss HP from server
                sword_states[p_id] = "combo"
                sword_frame_index[p_id] = 0
                if scores[p_id] % 6 == 0 and scores[p_id] != 0:
                    enemy_attack[p_id] = True
                    enemy_attack_timer[p_id] = pygame.time.get_ticks()
                    if current_animation != "cleave":
                        update_boss_animation("cleave")
                elif boss_hp <= 0:
                    boss_hp = 0
                    update_boss_animation("die")
                else:
                    if current_animation != "take_hit":
                        update_boss_animation("hit")

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
                        boss_hp = 0
                        update_boss_animation("die")
                    else:
                        update_boss_animation("hit")
                else:
                    xpos, ypos, player_id = map(float, decoded_data.split(","))
                    angle = (
                        (xpos - X_MID) / (X_MAX - X_MIN)
                    ) * 90  # Scale to -45 to 45
                    color = (0, 255, 0) if ypos > Y_MID else (255, 0, 0)
                    players[int(player_id)]["angle"] = angle
                    players[int(player_id)]["color"] = color
        except ValueError:
            pass
        except socket.timeout:
            continue


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


def draw_overlay_rectangle(pivot, angle, color=(255, 255, 255, 50)):
    overlay_surf = pygame.Surface((RECT_WIDTH + 10, RECT_HEIGHT + 10), pygame.SRCALPHA)
    overlay_surf.fill(color)
    rotated_surf = pygame.transform.rotate(overlay_surf, angle)
    rotated_rect = rotated_surf.get_rect(center=pivot)
    screen.blit(rotated_surf, rotated_rect.topleft)


def draw_boss():
    global last_update, frame_index, current_animation, hit_timer, game_state
    now = pygame.time.get_ticks()

    # If cleave or take_hit animation has finished its set duration, switch to idle
    if (current_animation == "take_hit" and now - hit_timer > 500) or (
        current_animation == "cleave" and now - hit_timer > 700
    ):
        current_animation = "idle"
        frame_index = 0  # Reset frame index when switching to idle

    elif (
        current_animation == "die"
        and frame_index == len(animation_frames[current_animation]) - 1
    ):
        game_state = "high_scores"  # Show high scores once animation completes

    if now - last_update > ANIMATION_SPEED:
        if current_animation == "idle":
            frame_index = (frame_index + 1) % len(animation_frames[current_animation])
        else:
            frame_index = min(
                frame_index + 1, len(animation_frames[current_animation]) - 1
            )
        last_update = now

    if frame_index >= len(animation_frames[current_animation]):
        frame_index = len(animation_frames[current_animation]) - 1

    boss_image = animation_frames[current_animation][frame_index]
    boss_rect = boss_image.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 80))
    screen.blit(boss_image, boss_rect.topleft)


def update_boss_animation(state):
    global current_animation, frame_index, hit_timer
    # Give cleave animation priority: if already in cleave, ignore other states.
    if current_animation == "cleave" and state != "cleave":
        return
    if state == "hit":
        if current_animation != "take_hit":
            current_animation = "take_hit"
            frame_index = 0
            hit_timer = pygame.time.get_ticks()
    elif state == "cleave":
        if current_animation != "cleave":
            current_animation = "cleave"
            frame_index = 0
            hit_timer = pygame.time.get_ticks()
    elif state == "die":
        current_animation = "die"
        frame_index = 0
    else:
        # When switching to idle, reset the frame index.
        current_animation = "idle"
        frame_index = 0


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

    current_sword_frames = (
        sword_combo if sword_states[player_id] == "combo" else sword_idle
    )
    sword_image = current_sword_frames[player_id][sword_frame_index[player_id]]
    sword_rect = sword_image.get_rect(center=(pivot[0], pivot[1] + 130))
    screen.blit(sword_image, sword_rect.topleft)

    # Draw health bar
    hp_bar_width = 100
    hp_bar_height = 10
    max_health = 100
    hp_ratio = player_health[player_id] / max_health
    current_hp_width = int(hp_bar_width * hp_ratio)
    hp_bar_x = pivot[0] - hp_bar_width // 2
    # Position the bar
    hp_bar_y = pivot[1] + 130 + sword_image.get_height() // 2 + 5
    pygame.draw.rect(
        screen, (255, 0, 0), (hp_bar_x, hp_bar_y, hp_bar_width, hp_bar_height)
    )
    pygame.draw.rect(
        screen, (0, 255, 0), (hp_bar_x, hp_bar_y, current_hp_width, hp_bar_height)
    )


if __name__ == "__main__":

    os.environ["SDL_AUDIODRIVER"] = "dummy"

    # Pygame setup
    pygame.init()
    WIDTH, HEIGHT = 800, 600
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    clock = pygame.time.Clock()
    font = pygame.font.Font(None, 36)

    game_state = "menu"
    player_id = None
    high_scores = []
    latest_game = None
    waiting_for_other = False

    # Network setup
    SERVER_IP = "ec2-3-88-178-208.compute-1.amazonaws.com"
    SERVER_PORT = 12345
    BUFFER_SIZE = 1024

    client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client_socket.settimeout(0.1)
    client_socket.sendto(b"HELLO", (SERVER_IP, SERVER_PORT))

    # Define pivot points and rotation range
    X_MIN, X_MAX = 0, 7000  # X range
    Y_MIN, Y_MAX = 0, 7000  # Y range
    X_MID = (X_MIN + X_MAX) / 2
    Y_MID = (Y_MIN + Y_MAX) / 2

    PIVOT_1 = (WIDTH // 4, HEIGHT // 2)  # Player 1 pivot (Left side)
    PIVOT_2 = (3 * WIDTH // 4, HEIGHT // 2)  # Player 2 pivot (Right side)
    RECT_WIDTH, RECT_HEIGHT = 120, 20  # Rectangle dimensions

    players = {
        1: {"angle": 0, "color": (255, 0, 0)},
        2: {"angle": 0, "color": (255, 0, 0)},
    }
    scores = {1: 0, 2: 0}
    overlay_angle = 0  # Updated from the server
    boss_hp = 3000
    boss_hp_max = 3000
    boss_hp_bar_length = 400
    boss_hp_ratio = boss_hp_max / boss_hp_bar_length

    player_health = {1: 100, 2: 100}
    enemy_attack = {1: False, 2: False}
    enemy_attack_timer = {1: 0, 2: 0}
    ATTACK_WINDOW = 1000  # milliseconds during which a block is attempted
    DAMAGE_AMOUNT = 20
    game_over_sent = False  # To ensure we only send GAME_OVER once

    # Adjust boss size and position
    BOSS_SIZE = (500, 500)  # Bigger boss
    BOSS_Y_OFFSET = -80  # Move boss downward

    # Load boss animations
    ANIMATION_PATHS = {
        "idle": "individual_sprites/01_demon_idle",
        "cleave": "individual_sprites/03_demon_cleave",
        "take_hit": "individual_sprites/04_demon_take_hit",
        "die": "individual_sprites/05_demon_death",
    }

    # Load animations for swords
    SWORD_PATH = "sword_sprites"
    sword_idle = {
        1: load_animation_frames(
            os.path.join(SWORD_PATH, "sword_idle"), scale_size=(300, 300)
        ),
        2: load_animation_frames(
            os.path.join(SWORD_PATH, "sword_idle"), flip=True, scale_size=(300, 300)
        ),
    }
    sword_combo = {
        1: load_animation_frames(
            os.path.join(SWORD_PATH, "sword_combo"), scale_size=(300, 300)
        ),
        2: load_animation_frames(
            os.path.join(SWORD_PATH, "sword_combo"), flip=True, scale_size=(300, 300)
        ),
    }

    sword_states = {1: "idle", 2: "idle"}
    sword_frame_index = {1: 0, 2: 0}
    sword_last_update = {1: pygame.time.get_ticks(), 2: pygame.time.get_ticks()}
    sword_animation_speed = 100

    # Boss animation setup
    animation_frames = {
        name: load_animation_frames(path, scale_size=BOSS_SIZE)
        for name, path in ANIMATION_PATHS.items()
    }
    current_animation = "idle"
    frame_index = 0
    ANIMATION_SPEED = 100
    last_update = pygame.time.get_ticks()
    hit_timer = 0

    player_id = None

    threading.Thread(target=receive_data, daemon=True).start()

    running = True
    while running:
        screen.fill((0, 0, 0))
        if game_state == "menu":
            draw_menu()
        elif game_state == "high_scores":
            draw_high_scores()
        elif game_state == "waiting":
            draw_text(f"Waiting for Player {player_id}...", WIDTH // 2, 300)
        elif game_state == "playing":
            screen.fill((0, 0, 0))  # Clear screen for game start
            draw_boss_health()
            draw_boss()
            draw_overlay_rectangle(PIVOT_1, overlay_angle)
            draw_overlay_rectangle(PIVOT_2, overlay_angle)
            draw_tilting_rectangle(PIVOT_1, players[1]["angle"], players[1]["color"])
            draw_tilting_rectangle(PIVOT_2, players[2]["angle"], players[2]["color"])
            draw_sword(1, PIVOT_1)
            draw_sword(2, PIVOT_2)

            # Check for scoring condition only if player is alive
            for p_id, pivot in [(1, PIVOT_1), (2, PIVOT_2)]:
                if (
                    player_health[p_id] > 0
                    and abs(players[p_id]["angle"] - overlay_angle) < 5
                    and players[p_id]["color"] == (0, 255, 0)
                ):
                    send_score(p_id)

            # Display scores
            score_text_1 = font.render(f"Player 1: {scores[1]}", True, (255, 255, 255))
            screen.blit(score_text_1, (20, 20))
            score_text_2 = font.render(f"Player 2: {scores[2]}", True, (255, 255, 255))
            screen.blit(score_text_2, (WIDTH - 150, 20))

            # For each player, draw only if health > 0
            if player_health[1] > 0:
                draw_tilting_rectangle(
                    PIVOT_1, players[1]["angle"], players[1]["color"]
                )
                # Use a red overlay if enemy attack is active
                if enemy_attack[1]:
                    draw_overlay_rectangle(
                        PIVOT_1, overlay_angle, color=(255, 0, 0, 100)
                    )
                else:
                    draw_overlay_rectangle(PIVOT_1, overlay_angle)
                draw_sword(1, PIVOT_1)
            if player_health[2] > 0:
                draw_tilting_rectangle(
                    PIVOT_2, players[2]["angle"], players[2]["color"]
                )
                if enemy_attack[2]:
                    draw_overlay_rectangle(
                        PIVOT_2, overlay_angle, color=(255, 0, 0, 100)
                    )
                else:
                    draw_overlay_rectangle(PIVOT_2, overlay_angle)
                draw_sword(2, PIVOT_2)

            # Process enemy attack resolution
            for pid in [1, 2]:
                if enemy_attack[pid]:
                    if (
                        pygame.time.get_ticks() - enemy_attack_timer[pid]
                        > ATTACK_WINDOW
                    ):
                        # If player's current angle is within tolerance of overlay_angle, they block the attack.
                        if abs(players[pid]["angle"] - overlay_angle) < 5:
                            # Successful block – no damage taken
                            pass
                        else:
                            # Attack not blocked – subtract damage if still alive
                            if player_health[pid] > 0:
                                player_health[pid] -= DAMAGE_AMOUNT
                                if player_health[pid] < 0:
                                    player_health[pid] = 0
                        enemy_attack[pid] = False  # Reset attack flag

                    if not game_over_sent:
                        if player_health[1] <= 0 and player_health[2] <= 0:
                            # Send GAME_OVER for each player and transition to high scores
                            if player_health[1] <= 0:
                                client_socket.sendto(
                                    f"GAME_OVER,1,{player_health[1]}".encode(),
                                    (SERVER_IP, SERVER_PORT),
                                )
                            if player_health[2] <= 0:
                                client_socket.sendto(
                                    f"GAME_OVER,2,{player_health[2]}".encode(),
                                    (SERVER_IP, SERVER_PORT),
                                )
                            game_over_sent = True
                            game_state = "high_scores"

                        # Send GAME_OVER for each player that is now out.
                        if player_health[1] <= 0:
                            client_socket.sendto(
                                f"GAME_OVER,1,{player_health[1]}".encode(),
                                (SERVER_IP, SERVER_PORT),
                            )
                        if player_health[2] <= 0:
                            client_socket.sendto(
                                f"GAME_OVER,2,{player_health[2]}".encode(),
                                (SERVER_IP, SERVER_PORT),
                            )
                        game_over_sent = True
                        game_state = "high_scores"  # Transition locally to high scores

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif game_state == "menu" and event.type == pygame.KEYDOWN:
                if event.key == pygame.K_1:
                    send_player_id(1)
                elif event.key == pygame.K_2:
                    send_player_id(2)
                print(f"Joining as {player_id}")
            elif game_state == "high_scores" and event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:
                    request_play_again()
                    waiting_for_other = True
                    game_state = "waiting"

        pygame.display.flip()
        clock.tick(60)
    pygame.quit()
