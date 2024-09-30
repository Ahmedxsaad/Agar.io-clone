import pygame
import random
import math
import sys
import os

# Initialize Pygame
pygame.init()

# Screen dimensions
SCREEN_WIDTH, SCREEN_HEIGHT = 1200, 800

# Game world dimensions
WORLD_WIDTH, WORLD_HEIGHT = 2000, 2000  # Adjusted back to previous size

# Create the display surface
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Agar.io Clone with Weapons and Teams")

# Clock object to control the frame rate
clock = pygame.time.Clock()

# Define colors
WHITE = (255, 255, 255)
GRAY = (200, 200, 200)
GREEN = (0, 255, 0)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
BLUE = (0, 0, 255)
FORTNITE_STORM_COLOR = (86, 44, 116, 100)  # RGBA color similar to Fortnite storm

TEAM_COLORS = {
    'red': (255, 0, 0),
    'blue': (0, 0, 255),
    'green': (0, 255, 0),
    'yellow': (255, 255, 0)
}

# Fonts
font_large = pygame.font.SysFont(None, 72)
font_small = pygame.font.SysFont(None, 36)
font_mini = pygame.font.SysFont(None, 24)

# Game state
game_state = "menu"  # Can be "menu", "team_select", "mode_select", "running", "game_over", "won"

# Camera position
camera_pos = [0, 0]

# Load flag images
flag_images = {}
def load_flags():
    flags_folder = 'flags'
    for filename in os.listdir(flags_folder):
        if filename.endswith('.png'):
            country_name = filename[:-4]  # Remove '.png' extension
            image = pygame.image.load(os.path.join(flags_folder, filename)).convert_alpha()
            flag_images[country_name.lower()] = image

# Load flags
load_flags()

# Weapon configurations
WEAPONS = {
    'none': {'cost': 0, 'damage': 0, 'rate': 0},
    'gun': {'cost': 2000, 'damage': 150, 'rate': 0.2},
    'rpg': {'cost': 3000, 'damage': 400, 'rate': 0.8}
}

# Grid settings for spatial partitioning
GRID_SIZE = 100  # Adjust based on performance
cell_grid = {}
food_grid = {}
bullet_grid = {}

# Maximum number of cells allowed for player and bots
MAX_CELLS = 16
MAX_BOT_CELLS = 4

# Bullet class
class Bullet:
    def __init__(self, x, y, dx, dy, damage, owner, type='gun', team=None):
        self.pos = [x, y]
        self.vel = [dx, dy]
        self.damage = damage
        self.owner = owner  # 'player' or 'enemy'
        self.type = type  # 'gun' or 'rpg'
        self.radius = 5 if type == 'gun' else 10
        self.color = (255, 255, 0) if type == 'gun' else (255, 165, 0)
        self.team = team

    def update(self, dt):
        self.pos[0] += self.vel[0] * dt
        self.pos[1] += self.vel[1] * dt

    def draw(self, surface):
        screen_x = self.pos[0] - camera_pos[0]
        screen_y = self.pos[1] - camera_pos[1]
        if 0 <= screen_x <= SCREEN_WIDTH and 0 <= screen_y <= SCREEN_HEIGHT:
            pygame.draw.circle(surface, self.color, (int(screen_x), int(screen_y)), self.radius)

# Cell class
class Cell:
    def __init__(self, x, y, radius, mass, speed, name, flag_image, team=None):
        self.pos = [x, y]
        self.radius = radius
        self.mass = mass
        self.speed = speed
        self.direction = [0, 0]
        self.split_cooldown = 0
        self.flag_image_original = flag_image
        self.flag_image_scaled = None
        self.scaled_radius = None
        self.name = name
        self.weapon = 'none'
        self.weapon_cooldown = 0
        self.weapon_level = 0  # 0: none, 1: gun, 2: dual gun
        self.bullets = []
        self.movement_locked = False  # For movement lock
        self.locked_direction = [0, 0]
        self.team = team  # Team assignment
        self.collided = False  # For collision flag

    def draw(self, surface):
        screen_x = self.pos[0] - camera_pos[0]
        screen_y = self.pos[1] - camera_pos[1]

        # Only scale the image if the radius has changed
        if self.scaled_radius != self.radius:
            self.flag_image_scaled = pygame.transform.smoothscale(
                self.flag_image_original, (int(self.radius * 2), int(self.radius * 2))
            )
            self.scaled_radius = self.radius

        rect = self.flag_image_scaled.get_rect(center=(int(screen_x), int(screen_y)))
        surface.blit(self.flag_image_scaled, rect)

        # Draw name
        text_surface = font_mini.render(self.name, True, WHITE)
        text_rect = text_surface.get_rect(center=(int(screen_x), int(screen_y + self.radius + 10)))
        surface.blit(text_surface, text_rect)

        # Draw weapon as a small circle
        if self.weapon != 'none':
            angle = math.atan2(self.direction[1], self.direction[0])
            weapon_distance = self.radius + 10  # Distance from center
            weapon_x = screen_x + math.cos(angle) * weapon_distance
            weapon_y = screen_y + math.sin(angle) * weapon_distance
            weapon_radius = 5 if self.weapon == 'gun' else 8
            pygame.draw.circle(surface, WHITE, (int(weapon_x), int(weapon_y)), weapon_radius)
            if self.weapon_level == 2:
                # Draw second weapon
                angle += math.pi / 6
                weapon_x = screen_x + math.cos(angle) * weapon_distance
                weapon_y = screen_y + math.sin(angle) * weapon_distance
                pygame.draw.circle(surface, WHITE, (int(weapon_x), int(weapon_y)), weapon_radius)
        # Draw team color border
        if self.team:
            pygame.draw.circle(surface, TEAM_COLORS[self.team], (int(screen_x), int(screen_y)), int(self.radius), 2)

    def update(self, dt):
        # Apply movement
        if self.movement_locked:
            # Continue in locked direction
            dx, dy = self.locked_direction
            speed = self.speed * (20 / self.radius)  # Slower when larger
            self.pos[0] += dx * speed * dt * 60  # Multiply by 60 to normalize speed
            self.pos[1] += dy * speed * dt * 60
        else:
            # Apply split movement
            self.pos[0] += self.direction[0] * dt
            self.pos[1] += self.direction[1] * dt

            # Friction to slow down split cells
            self.direction[0] *= 0.90
            self.direction[1] *= 0.90

        # Decrease split cooldown
        if self.split_cooldown > 0:
            self.split_cooldown -= dt
        else:
            self.split_cooldown = 0

        # Decrease weapon cooldown
        if self.weapon_cooldown > 0:
            self.weapon_cooldown -= dt
        else:
            self.weapon_cooldown = 0

        # Keep cells within world bounds
        self.pos[0] = max(self.radius, min(WORLD_WIDTH - self.radius, self.pos[0]))
        self.pos[1] = max(self.radius, min(WORLD_HEIGHT - self.radius, self.pos[1]))

    def shoot(self, target_x, target_y):
        if self.weapon == 'none' or self.weapon_cooldown > 0:
            return
        weapon_info = WEAPONS[self.weapon]
        # Create bullet
        dx, dy = target_x - self.pos[0], target_y - self.pos[1]
        dist = math.hypot(dx, dy)
        if dist != 0:
            dx /= dist
            dy /= dist
        else:
            dx, dy = 0, 0
        speed = 500  # Bullet speed
        bullet = Bullet(
            self.pos[0] + dx * self.radius,
            self.pos[1] + dy * self.radius,
            dx * speed,
            dy * speed,
            weapon_info['damage'],
            'player' if isinstance(self, PlayerCell) else 'enemy',
            type=self.weapon,
            team=self.team
        )
        self.bullets.append(bullet)
        # Set weapon cooldown
        self.weapon_cooldown = weapon_info['rate']
        # Reduce mass as cost
        self.mass = max(0, self.mass - 10)
        self.radius = math.sqrt(self.mass) if self.mass > 0 else 0

# Player cell subclass
class PlayerCell(Cell):
    def __init__(self, x, y, radius, mass, speed, name, flag_image, team=None):
        super().__init__(x, y, radius, mass, speed, name, flag_image, team)

    def move_towards(self, target_x, target_y):
        if self.movement_locked:
            # Direction is locked; movement handled in update()
            return
        dx, dy = target_x - self.pos[0], target_y - self.pos[1]
        dist = math.hypot(dx, dy)
        if dist > 5:  # Movement threshold to prevent shaking
            dx, dy = dx / dist, dy / dist  # Normalize
            speed = self.speed * (20 / self.radius)  # Slower when larger
            self.pos[0] += dx * speed
            self.pos[1] += dy * speed
            self.direction = [dx, dy]

# Enemy cell subclass
class EnemyCell(Cell):
    id_counter = 0  # Class variable to assign unique IDs

    def __init__(self, x, y, radius, mass, speed, name, flag_image, team=None):
        super().__init__(x, y, radius, mass, speed, name, flag_image, team)
        self.id = EnemyCell.id_counter
        EnemyCell.id_counter += 1
        angle = random.uniform(0, 2 * math.pi)
        self.direction = [math.cos(angle), math.sin(angle)]

    def ai_move(self, dt, targets):
        # Simplified AI to reduce lag
        if battle_royale_mode:
            dist_to_safe_zone = math.hypot(self.pos[0] - safe_zone_center[0], self.pos[1] - safe_zone_center[1])
            if dist_to_safe_zone > safe_zone_radius - self.radius:
                # Move towards the safe zone center
                dx = safe_zone_center[0] - self.pos[0]
                dy = safe_zone_center[1] - self.pos[1]
                self.direction = [dx, dy]
            else:
                # Random movement
                if random.random() < 0.005:
                    angle = random.uniform(0, 2 * math.pi)
                    self.direction = [math.cos(angle), math.sin(angle)]
        else:
            # Random movement
            if random.random() < 0.005:
                angle = random.uniform(0, 2 * math.pi)
                self.direction = [math.cos(angle), math.sin(angle)]

        # Normalize direction
        dx, dy = self.direction
        dist = math.hypot(dx, dy)
        if dist != 0:
            dx /= dist
            dy /= dist

        # Smooth direction changes
        self.direction[0] += (dx - self.direction[0]) * 0.1
        self.direction[1] += (dy - self.direction[1]) * 0.1

        speed = self.speed * (20 / self.radius)  # Slower when larger
        self.pos[0] += dx * speed
        self.pos[1] += dy * speed

        # Update direction
        self.direction = [dx, dy]

        # Simplify shooting decision
        if self.weapon != 'none' and self.weapon_cooldown <= 0:
            # Shoot in the current direction
            target_x = self.pos[0] + dx * 100
            target_y = self.pos[1] + dy * 100
            self.shoot(target_x, target_y)

        # Weapon selection when mass >= threshold
        if self.mass >= 5000 and self.weapon == 'none':
            self.weapon = random.choice(['gun', 'rpg'])
            self.weapon_level = 1
            self.mass -= WEAPONS[self.weapon]['cost']
            if self.mass < 0:
                self.mass = 0  # Prevent negative mass
            self.radius = math.sqrt(self.mass) if self.mass > 0 else 0

        # Simplify split decision
        if (self.mass >= 400 and self.split_cooldown <= 0 and
            random.random() < 0.005 and len(enemy_cells_by_team[self.team]) < MAX_BOT_CELLS):
            self.split()

    def split(self):
        # Split the cell
        if (self.mass >= 400 and self.split_cooldown <= 0 and
            len(enemy_cells_by_team[self.team]) < MAX_BOT_CELLS):
            mass1 = self.mass / 2
            mass2 = self.mass / 2
            radius1 = math.sqrt(mass1)
            radius2 = math.sqrt(mass2)
            angle = random.uniform(0, 2 * math.pi)
            dx, dy = math.cos(angle), math.sin(angle)
            dist = math.hypot(dx, dy)
            if dist != 0:
                dx /= dist
                dy /= dist
            else:
                dx, dy = 0, 0
            speed = 300  # Speed of the ejected cell
            new_cell = EnemyCell(
                self.pos[0] + dx * self.radius,
                self.pos[1] + dy * self.radius,
                radius2,
                mass2,
                self.speed,
                self.name,
                self.flag_image_original,
                self.team
            )
            new_cell.direction = [dx * speed, dy * speed]
            new_cell.split_cooldown = 2
            # Adjust original cell
            self.mass = mass1
            if self.mass < 0:
                self.mass = 0
            self.radius = math.sqrt(self.mass) if self.mass > 0 else 0
            self.direction[0] -= new_cell.direction[0] * 0.1
            self.direction[1] -= new_cell.direction[1] * 0.1
            self.split_cooldown = 2  # 2 seconds cooldown
            enemy_list.append(new_cell)
            enemy_cells_by_team[self.team].append(new_cell)

# Food class
class Food:
    def __init__(self, x, y):
        self.pos = [x, y]
        self.radius = 4
        self.mass = self.radius ** 2
        self.respawn_timer = 0  # Timer to manage respawn

# Global variables
player_cells = []
player_name = "Player"
player_flag_image = None

food_list = []
FOOD_COUNT = 200  # Adjusted for performance
FOOD_RESPAWN_TIME = 5  # Time in seconds to respawn food
respawning_food = []

enemy_list = []
enemy_cells_by_team = {'red': [], 'blue': [], 'green': [], 'yellow': []}
ENEMY_COUNT = 15  # Adjusted for performance
cool_names = [
    "Shadow", "Ghost", "Blaze", "Storm", "Viper", "Phantom", "Ranger",
    "Hunter", "Predator", "Maverick", "Titan", "Zephyr", "Nova", "Falcon",
    "Spectre", "Vortex", "Blizzard", "Phoenix", "Nebula", "Inferno",
    "Cyclone", "Kraken", "Bullet", "Reaper", "Serpent", "Golem"
]
available_names = cool_names.copy()

bullets = []

# Battle Royale specific variables
safe_zone_radius = None
safe_zone_shrink_time = None
safe_zone_stage = 0
SAFE_ZONE_SHRINK_INTERVAL = 20  # Time in seconds between shrinks
SAFE_ZONE_MIN_RADIUS = 300
safe_zone_center = [WORLD_WIDTH // 2, WORLD_HEIGHT // 2]
battle_royale_mode = False

# Teams mode specific variables
teams_mode = False
team_scores = {'red': 0, 'blue': 0, 'green': 0, 'yellow': 0}
teams = ['red', 'blue', 'green', 'yellow']
team_selection_active = False
selected_team = None
GAME_DURATION = 300  # 5 minutes in seconds
game_timer = GAME_DURATION

def initialize_battle_royale():
    global safe_zone_radius, safe_zone_shrink_time, safe_zone_stage, battle_royale_mode
    safe_zone_radius = max(WORLD_WIDTH, WORLD_HEIGHT) // 2
    safe_zone_shrink_time = SAFE_ZONE_SHRINK_INTERVAL
    safe_zone_stage = 1
    battle_royale_mode = True

def update_safe_zone(dt):
    global safe_zone_radius, safe_zone_shrink_time, safe_zone_stage, safe_zone_center
    if safe_zone_radius > SAFE_ZONE_MIN_RADIUS:
        safe_zone_shrink_time -= dt
        if safe_zone_shrink_time <= 0:
            safe_zone_radius -= 300  # Decrease radius
            safe_zone_shrink_time = SAFE_ZONE_SHRINK_INTERVAL
            safe_zone_stage += 1
            # Randomly move the safe zone center
            safe_zone_center[0] += random.randint(-100, 100)
            safe_zone_center[1] += random.randint(-100, 100)
            # Keep center within bounds
            safe_zone_center[0] = max(0, min(WORLD_WIDTH, safe_zone_center[0]))
            safe_zone_center[1] = max(0, min(WORLD_HEIGHT, safe_zone_center[1]))
    else:
        safe_zone_radius = SAFE_ZONE_MIN_RADIUS

def draw_safe_zone():
    # Create a full-screen storm overlay
    storm_overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    storm_overlay.fill(FORTNITE_STORM_COLOR)

    # Create a mask for the safe zone
    safe_zone_mask = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    safe_zone_mask.fill((0, 0, 0, 0))  # Transparent

    # Draw the safe zone area onto the mask
    screen_x = safe_zone_center[0] - camera_pos[0]
    screen_y = safe_zone_center[1] - camera_pos[1]
    pygame.draw.circle(safe_zone_mask, (0, 0, 0, 255), (int(screen_x), int(screen_y)), int(safe_zone_radius))

    # Apply the mask to the storm overlay
    storm_overlay.blit(safe_zone_mask, (0, 0), special_flags=pygame.BLEND_RGBA_SUB)

    # Blit the storm overlay onto the screen
    screen.blit(storm_overlay, (0, 0))

    # Draw safe zone border
    pygame.draw.circle(screen, BLUE, (int(screen_x), int(screen_y)), int(safe_zone_radius), 2)

def apply_safe_zone_damage(dt):
    damage = 5 * safe_zone_stage * dt  # Damage increases with each stage
    for cell in player_cells + enemy_list:
        dist = math.hypot(cell.pos[0] - safe_zone_center[0], cell.pos[1] - safe_zone_center[1])
        if dist > safe_zone_radius:
            cell.mass -= damage
            if cell.mass <= 0:
                cell.mass = 0
                if cell in player_cells:
                    player_cells.remove(cell)
                    if not player_cells:
                        global game_state
                        game_state = "game_over"
                elif cell in enemy_list:
                    enemy_list.remove(cell)
                    if cell.team and cell in enemy_cells_by_team[cell.team]:
                        enemy_cells_by_team[cell.team].remove(cell)
            else:
                cell.radius = math.sqrt(cell.mass)

def spawn_food():
    while len(food_list) < FOOD_COUNT:
        x = random.randint(0, WORLD_WIDTH)
        y = random.randint(0, WORLD_HEIGHT)
        food_list.append(Food(x, y))

def draw_food(surface):
    for food in food_list:
        if is_on_screen(food.pos[0], food.pos[1], food.radius):
            screen_x = food.pos[0] - camera_pos[0]
            screen_y = food.pos[1] - camera_pos[1]
            pygame.draw.circle(surface, GREEN, (int(screen_x), int(screen_y)), food.radius)

def update_food(dt):
    # Update respawn timers
    for food in respawning_food[:]:
        food.respawn_timer -= dt
        if food.respawn_timer <= 0:
            # Respawn food at a new random position
            x = random.randint(0, WORLD_WIDTH)
            y = random.randint(0, WORLD_HEIGHT)
            food.pos = [x, y]
            food_list.append(food)
            respawning_food.remove(food)

def spawn_enemy(team=None):
    global available_names
    if not available_names:
        available_names = cool_names.copy()
    name = random.choice(available_names)
    available_names.remove(name)
    x = random.randint(0, WORLD_WIDTH)
    y = random.randint(0, WORLD_HEIGHT)
    radius = random.randint(15, 40)
    mass = radius ** 2
    # Randomly assign a country flag to the enemy
    flag = random.choice(list(flag_images.values()))
    if not team:
        team = random.choice(teams)
    enemy = EnemyCell(x, y, radius, mass, 5, name, flag, team)
    enemy_list.append(enemy)
    enemy_cells_by_team[team].append(enemy)

def spawn_enemies(count=ENEMY_COUNT):
    if teams_mode:
        team_counts = {team: 0 for team in teams}
        # Distribute enemies equally among teams
        for _ in range(count):
            team = min(team_counts, key=team_counts.get)
            spawn_enemy(team=team)
            team_counts[team] += 1
    else:
        for _ in range(count):
            spawn_enemy()

def respawn_enemies(dt):
    if battle_royale_mode:
        return  # Do not respawn enemies in battle royale mode
    if teams_mode:
        # Maintain enemy counts per team
        desired_count = ENEMY_COUNT // len(teams)
        for team in teams:
            current_count = len(enemy_cells_by_team[team])
            if current_count < desired_count:
                spawn_enemy(team=team)
    else:
        # In classic mode, maintain total enemy count
        while len(enemy_list) < ENEMY_COUNT:
            spawn_enemy()

def is_on_screen(x, y, radius):
    return (
        x + radius >= camera_pos[0] - radius and
        x - radius <= camera_pos[0] + SCREEN_WIDTH + radius and
        y + radius >= camera_pos[1] - radius and
        y - radius <= camera_pos[1] + SCREEN_HEIGHT + radius
    )

def get_grid_cell(x, y):
    return int(x // GRID_SIZE), int(y // GRID_SIZE)

def add_to_grid(obj, grid):
    grid_cell = get_grid_cell(obj.pos[0], obj.pos[1])
    if grid_cell not in grid:
        grid[grid_cell] = []
    grid[grid_cell].append(obj)

def get_nearby_cells(cell, grid):
    grid_cell = get_grid_cell(cell.pos[0], cell.pos[1])
    nearby_cells = []
    for dx in [-1, 0, 1]:
        for dy in [-1, 0, 1]:
            neighbor_cell = (grid_cell[0] + dx, grid_cell[1] + dy)
            if neighbor_cell in grid:
                nearby_cells.extend(grid[neighbor_cell])
    return nearby_cells

def check_collisions():
    global game_state, team_scores
    cell_grid.clear()
    food_grid.clear()

    # Add cells to grid
    for cell in player_cells + enemy_list:
        add_to_grid(cell, cell_grid)

    # Add food to grid
    for food in food_list:
        add_to_grid(food, food_grid)

    # Prepare lists to remove cells and food
    player_cells_to_remove = []
    enemy_cells_to_remove = []
    food_to_remove = []

    # Check collision with food
    for cell in player_cells + enemy_list:
        nearby_food = get_nearby_cells(cell, food_grid)
        for food in nearby_food:
            dist = math.hypot(food.pos[0] - cell.pos[0], food.pos[1] - cell.pos[1])
            if dist < cell.radius:
                food_to_remove.append(food)
                cell.mass += food.mass
                cell.radius = math.sqrt(cell.mass)
                if teams_mode and cell.team:
                    team_scores[cell.team] += food.mass

    # Remove eaten food
    for food in food_to_remove:
        if food in food_list:
            food_list.remove(food)
            # Start respawn timer
            food.respawn_timer = FOOD_RESPAWN_TIME
            # Add to respawn list
            respawning_food.append(food)

    # Check collisions among cells
    for cell in player_cells + enemy_list:
        nearby_cells = get_nearby_cells(cell, cell_grid)
        for other in nearby_cells:
            if other is cell or (cell.team == other.team):
                continue  # Skip self and teammates
            if cell.collided or other.collided:
                continue
            dist = math.hypot(cell.pos[0] - other.pos[0], cell.pos[1] - other.pos[1])
            if dist < cell.radius + other.radius:
                # Handle collision
                if cell.radius > other.radius * 1.1:
                    cell.mass += other.mass
                    cell.radius = math.sqrt(cell.mass)
                    other.collided = True
                    if other in player_cells:
                        player_cells_to_remove.append(other)
                        if not teams_mode:
                            game_state = "game_over"
                    elif other in enemy_list:
                        enemy_cells_to_remove.append(other)
                        if other.team and other in enemy_cells_by_team[other.team]:
                            enemy_cells_by_team[other.team].remove(other)
                        if teams_mode and cell.team:
                            team_scores[cell.team] += other.mass
                elif other.radius > cell.radius * 1.1:
                    other.mass += cell.mass
                    other.radius = math.sqrt(other.mass)
                    cell.collided = True
                    if cell in player_cells:
                        player_cells_to_remove.append(cell)
                        if not teams_mode:
                            game_state = "game_over"
                    elif cell in enemy_list:
                        enemy_cells_to_remove.append(cell)
                        if cell.team and cell in enemy_cells_by_team[cell.team]:
                            enemy_cells_by_team[cell.team].remove(cell)
                        if teams_mode and other.team:
                            team_scores[other.team] += cell.mass

    # Remove cells after iteration
    for cell in player_cells_to_remove:
        if cell in player_cells:
            player_cells.remove(cell)
    for cell in enemy_cells_to_remove:
        if cell in enemy_list:
            enemy_list.remove(cell)

    # Reset collision flags
    for cell in player_cells + enemy_list:
        cell.collided = False

    # Check collision between player's own cells for merging
    for cell in player_cells:
        nearby_cells = get_nearby_cells(cell, cell_grid)
        for other in nearby_cells:
            if other is cell or other not in player_cells:
                continue
            dist = math.hypot(cell.pos[0] - other.pos[0], cell.pos[1] - other.pos[1])
            if dist < cell.radius + other.radius:
                if cell.split_cooldown <= 0 and other.split_cooldown <= 0:
                    total_mass = cell.mass + other.mass
                    new_radius = math.sqrt(total_mass)
                    cell.mass = total_mass
                    cell.radius = new_radius
                    player_cells.remove(other)
                    break

def handle_bullets(dt):
    bullet_grid.clear()
    # Add bullets to grid
    for bullet in bullets:
        add_to_grid(bullet, bullet_grid)

    for bullet in bullets[:]:
        bullet.update(dt)
        # Only draw bullets if they are on-screen
        if is_on_screen(bullet.pos[0], bullet.pos[1], bullet.radius):
            bullet.draw(screen)

        # Determine potential targets
        nearby_cells = get_nearby_cells(bullet, cell_grid)
        for target in nearby_cells:
            if target.team == bullet.team:
                continue  # Skip teammates
            dist = math.hypot(target.pos[0] - bullet.pos[0], target.pos[1] - bullet.pos[1])
            if dist < target.radius:
                # Deal damage
                target.mass -= bullet.damage
                if target.mass <= 0:
                    target.mass = 0
                    if target in player_cells:
                        player_cells.remove(target)
                        if not player_cells:
                            global game_state
                            game_state = "game_over"
                    elif target in enemy_list:
                        enemy_list.remove(target)
                        if target.team and target in enemy_cells_by_team[target.team]:
                            enemy_cells_by_team[target.team].remove(target)
                else:
                    target.radius = math.sqrt(target.mass)
                if bullet in bullets:
                    bullets.remove(bullet)
                break

        # Remove bullet if out of bounds
        if bullet.pos[0] < 0 or bullet.pos[0] > WORLD_WIDTH or bullet.pos[1] < 0 or bullet.pos[1] > WORLD_HEIGHT:
            if bullet in bullets:
                bullets.remove(bullet)

def display_game_over():
    screen.fill(GRAY)
    text = font_large.render("Game Over", True, RED)
    rect = text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 50))
    screen.blit(text, rect)

    play_again_text = font_small.render("Press 'R' to Play Again or 'Q' to Quit", True, WHITE)
    play_again_rect = play_again_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 20))
    screen.blit(play_again_text, play_again_rect)

def display_winning_screen():
    screen.fill(GRAY)
    if teams_mode:
        # Display winning team
        winning_team = max(team_scores, key=team_scores.get)
        text = font_large.render(f"{winning_team.capitalize()} Team Wins!", True, TEAM_COLORS[winning_team])
    else:
        text = font_large.render("You Win!", True, (0, 255, 0))
    rect = text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 50))
    screen.blit(text, rect)

    play_again_text = font_small.render("Press 'R' to Play Again or 'Q' to Quit", True, WHITE)
    play_again_rect = play_again_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 20))
    screen.blit(play_again_text, play_again_rect)

def display_battle_royale_info():
    # Count unique enemy IDs
    unique_enemy_ids = set(enemy.id for enemy in enemy_list)
    players_left = len(unique_enemy_ids)
    # Add 1 if player is alive
    if player_cells:
        players_left += 1
    info_text = font_small.render(f"Players Left: {players_left}", True, WHITE)
    screen.blit(info_text, (10, 10))

def display_score():
    # Calculate player's total mass
    total_mass = sum(cell.mass for cell in player_cells)
    score_text = font_small.render(f"Score: {int(total_mass)}", True, WHITE)
    screen.blit(score_text, (10, SCREEN_HEIGHT - 40))

def display_leaderboard():
    # Get top 5 players by mass
    all_cells = player_cells + enemy_list
    leaderboard = sorted(all_cells, key=lambda c: c.mass, reverse=True)[:5]
    x = SCREEN_WIDTH - 200
    y = 10
    leaderboard_title = font_small.render("Leaderboard", True, WHITE)
    screen.blit(leaderboard_title, (x, y))
    y += 30
    for i, cell in enumerate(leaderboard):
        name = cell.name if cell in enemy_list else player_name
        entry_text = font_mini.render(f"{i+1}. {name}: {int(cell.mass)}", True, WHITE)
        screen.blit(entry_text, (x, y))
        y += 20

def draw_minimap():
    minimap_width = 200
    minimap_height = 200
    minimap_surface = pygame.Surface((minimap_width, minimap_height))
    minimap_surface.fill(BLACK)
    scale_x = minimap_width / WORLD_WIDTH
    scale_y = minimap_height / WORLD_HEIGHT

    # Draw safe zone
    if battle_royale_mode:
        zone_x = int(safe_zone_center[0] * scale_x)
        zone_y = int(safe_zone_center[1] * scale_y)
        zone_radius = int(safe_zone_radius * scale_x)
        pygame.draw.circle(minimap_surface, BLUE, (zone_x, zone_y), zone_radius, 1)

    # Draw enemies
    for enemy in enemy_list:
        x = int(enemy.pos[0] * scale_x)
        y = int(enemy.pos[1] * scale_y)
        color = TEAM_COLORS[enemy.team] if teams_mode else RED
        pygame.draw.circle(minimap_surface, color, (x, y), max(2, int(enemy.radius * scale_x)))

    # Draw player
    for cell in player_cells:
        x = int(cell.pos[0] * scale_x)
        y = int(cell.pos[1] * scale_y)
        pygame.draw.circle(minimap_surface, (0, 0, 255), (x, y), max(2, int(cell.radius * scale_x)))

    # Blit minimap to screen
    screen.blit(minimap_surface, (SCREEN_WIDTH - minimap_width - 10, SCREEN_HEIGHT - minimap_height - 10))

def display_menu():
    screen.fill(GRAY)
    title_text = font_large.render("Select Your Country", True, WHITE)
    title_rect = title_text.get_rect(center=(SCREEN_WIDTH // 2, 50))
    screen.blit(title_text, title_rect)

    instruction_text = font_small.render("Enter your name and choose a country flag", True, WHITE)
    instruction_rect = instruction_text.get_rect(center=(SCREEN_WIDTH // 2, 100))
    screen.blit(instruction_text, instruction_rect)

    # Display the available flags
    y_offset = 150
    x_offset = 100
    x_spacing = 150
    y_spacing = 150
    flags_per_row = 6
    index = 0
    flag_keys = list(flag_images.keys())
    for i in range((len(flag_keys) + flags_per_row - 1) // flags_per_row):
        for j in range(flags_per_row):
            if index >= len(flag_keys):
                break
            country = flag_keys[index]
            flag_image = pygame.transform.scale(flag_images[country], (100, 100))
            rect = flag_image.get_rect()
            rect.topleft = (x_offset + j * x_spacing, y_offset + i * y_spacing)
            screen.blit(flag_image, rect)
            # Draw country name
            country_text = font_mini.render(country.capitalize(), True, WHITE)
            country_rect = country_text.get_rect(center=(rect.centerx, rect.bottom + 10))
            screen.blit(country_text, country_rect)
            index += 1

    # Display input box for name
    name_text = font_small.render(f"Name: {player_name_input}", True, WHITE)
    name_rect = name_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 100))
    screen.blit(name_text, name_rect)

def display_team_selection():
    global team_buttons
    team_buttons = []
    screen.fill(GRAY)
    title_text = font_large.render("Select Your Team", True, WHITE)
    title_rect = title_text.get_rect(center=(SCREEN_WIDTH // 2, 100))
    screen.blit(title_text, title_rect)

    x_spacing = 200
    y_position = SCREEN_HEIGHT // 2
    x_start = (SCREEN_WIDTH - (len(teams) - 1) * x_spacing) // 2

    for i, team in enumerate(teams):
        team_text = font_small.render(team.capitalize(), True, TEAM_COLORS[team])
        team_rect = team_text.get_rect(center=(x_start + i * x_spacing, y_position))
        team_button_rect = pygame.Rect(team_rect.left - 10, team_rect.top - 10, team_rect.width + 20, team_rect.height + 20)
        pygame.draw.rect(screen, TEAM_COLORS[team], team_button_rect, 2)
        screen.blit(team_text, team_rect)
        team_buttons.append((team, team_button_rect))

def display_mode_selection():
    global classic_mode_rect, battle_royale_rect, teams_mode_rect
    # Draw semi-transparent overlay
    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    overlay.set_alpha(180)
    overlay.fill((0, 0, 0))
    screen.blit(overlay, (0, 0))

    # Draw the selection box
    box_width = 600
    box_height = 400
    box_x = (SCREEN_WIDTH - box_width) // 2
    box_y = (SCREEN_HEIGHT - box_height) // 2
    pygame.draw.rect(screen, GRAY, (box_x, box_y, box_width, box_height))

    # Draw title
    title_text = font_large.render("Choose Game Mode", True, WHITE)
    title_rect = title_text.get_rect(center=(SCREEN_WIDTH // 2, box_y + 50))
    screen.blit(title_text, title_rect)

    # Draw mode options
    classic_text = font_small.render("Classic Mode", True, WHITE)
    classic_rect = classic_text.get_rect(center=(SCREEN_WIDTH // 2 - 150, SCREEN_HEIGHT // 2))
    classic_mode_rect = pygame.Rect(classic_rect.left - 10, classic_rect.top - 10, classic_rect.width + 20, classic_rect.height + 20)
    pygame.draw.rect(screen, WHITE, classic_mode_rect, 2)
    screen.blit(classic_text, classic_rect)

    battle_royale_text = font_small.render("Battle Royale", True, WHITE)
    battle_rect = battle_royale_text.get_rect(center=(SCREEN_WIDTH // 2 + 150, SCREEN_HEIGHT // 2))
    battle_royale_rect = pygame.Rect(battle_rect.left - 10, battle_rect.top - 10, battle_rect.width + 20, battle_rect.height + 20)
    pygame.draw.rect(screen, WHITE, battle_royale_rect, 2)
    screen.blit(battle_royale_text, battle_rect)

    teams_text = font_small.render("Teams Mode", True, WHITE)
    teams_rect = teams_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 100))
    teams_mode_rect = pygame.Rect(teams_rect.left - 10, teams_rect.top - 10, teams_rect.width + 20, teams_rect.height + 20)
    pygame.draw.rect(screen, WHITE, teams_mode_rect, 2)
    screen.blit(teams_text, teams_rect)
    return teams_mode_rect

def display_weapon_selection():
    global gun_button_rect, rpg_button_rect
    # Draw semi-transparent overlay
    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    overlay.set_alpha(180)
    overlay.fill((0, 0, 0))
    screen.blit(overlay, (0, 0))

    # Draw the selection box
    box_width = 600
    box_height = 400
    box_x = (SCREEN_WIDTH - box_width) // 2
    box_y = (SCREEN_HEIGHT - box_height) // 2
    pygame.draw.rect(screen, GRAY, (box_x, box_y, box_width, box_height))

    # Draw title
    title_text = font_large.render("Choose Your Weapon", True, WHITE)
    title_rect = title_text.get_rect(center=(SCREEN_WIDTH // 2, box_y + 50))
    screen.blit(title_text, title_rect)

    # Draw weapon options
    gun_text = font_small.render("Gun", True, WHITE)
    gun_rect = gun_text.get_rect(center=(SCREEN_WIDTH // 2 - 150, SCREEN_HEIGHT // 2))
    gun_button_rect = pygame.Rect(gun_rect.left - 10, gun_rect.top - 10, gun_rect.width + 20, gun_rect.height + 20)
    pygame.draw.rect(screen, WHITE, gun_button_rect, 2)
    screen.blit(gun_text, gun_rect)

    rpg_text = font_small.render("RPG", True, WHITE)
    rpg_rect = rpg_text.get_rect(center=(SCREEN_WIDTH // 2 + 150, SCREEN_HEIGHT // 2))
    rpg_button_rect = pygame.Rect(rpg_rect.left - 10, rpg_rect.top - 10, rpg_rect.width + 20, rpg_rect.height + 20)
    pygame.draw.rect(screen, WHITE, rpg_button_rect, 2)
    screen.blit(rpg_text, rpg_rect)

def main():
    global game_state, player_cells, enemy_list, food_list, respawning_food, camera_pos
    global player_name, player_flag_image, player_name_input
    global weapon_selection_active, gun_button_rect, rpg_button_rect
    global classic_mode_rect, battle_royale_rect, battle_royale_mode, teams_mode
    global team_buttons, selected_team, team_selection_active, game_timer
    player_name_input = ""
    weapon_selection_active = False
    gun_button_rect = None
    rpg_button_rect = None
    mode_selection_active = False
    classic_mode_rect = None
    battle_royale_rect = None
    teams_mode_rect = None
    team_selection_active = False
    team_buttons = []
    selected_team = None
    game_timer = GAME_DURATION

    running = True
    while running:
        dt = clock.tick(60) / 1000  # Delta time in seconds, capped at 60 FPS

        # Event handling
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            if game_state == "menu":
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_BACKSPACE:
                        player_name_input = player_name_input[:-1]
                    elif event.key == pygame.K_RETURN:
                        if player_flag_image and player_name_input:
                            player_name = player_name_input
                            game_state = "mode_select"
                    else:
                        player_name_input += event.unicode
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    mx, my = pygame.mouse.get_pos()
                    # Check if a flag was clicked
                    y_offset = 150
                    x_offset = 100
                    x_spacing = 150
                    y_spacing = 150
                    flags_per_row = 6
                    index = 0
                    flag_keys = list(flag_images.keys())
                    for i in range((len(flag_keys) + flags_per_row - 1) // flags_per_row):
                        for j in range(flags_per_row):
                            if index >= len(flag_keys):
                                break
                            country = flag_keys[index]
                            rect = pygame.Rect(x_offset + j * x_spacing, y_offset + i * y_spacing, 100, 100)
                            if rect.collidepoint(mx, my):
                                player_flag_image = flag_images[country]
                            index += 1

            elif game_state == "mode_select":
                teams_mode_rect = display_mode_selection()
                if event.type == pygame.MOUSEBUTTONDOWN:
                    mx, my = pygame.mouse.get_pos()
                    if classic_mode_rect and classic_mode_rect.collidepoint(mx, my):
                        # Initialize player cell
                        initial_cell = PlayerCell(
                            WORLD_WIDTH // 2,
                            WORLD_HEIGHT // 2,
                            40,
                            1600,
                            5,
                            player_name,
                            player_flag_image
                        )
                        player_cells.append(initial_cell)
                        spawn_food()
                        spawn_enemies()
                        game_state = "running"
                    elif battle_royale_rect and battle_royale_rect.collidepoint(mx, my):
                        # Initialize player cell
                        initial_cell = PlayerCell(
                            random.randint(0, WORLD_WIDTH),
                            random.randint(0, WORLD_HEIGHT),
                            40,
                            1600,
                            5,
                            player_name,
                            player_flag_image
                        )
                        player_cells.append(initial_cell)
                        spawn_food()
                        spawn_enemies(count=49)  # 50 players in total
                        initialize_battle_royale()
                        game_state = "running"
                    elif teams_mode_rect and teams_mode_rect.collidepoint(mx, my):
                        game_state = "team_select"

            elif game_state == "team_select":
                display_team_selection()
                if event.type == pygame.MOUSEBUTTONDOWN:
                    mx, my = pygame.mouse.get_pos()
                    for team, button_rect in team_buttons:
                        if button_rect.collidepoint(mx, my):
                            selected_team = team
                            # Initialize player cell
                            initial_cell = PlayerCell(
                                random.randint(0, WORLD_WIDTH),
                                random.randint(0, WORLD_HEIGHT),
                                40,
                                1600,
                                5,
                                player_name,
                                player_flag_image,
                                team=selected_team
                            )
                            player_cells.append(initial_cell)
                            teams_mode = True
                            spawn_food()
                            spawn_enemies(count=40)  # Adjust number as needed
                            game_state = "running"
                            break

            elif game_state == "running":
                if weapon_selection_active:
                    display_weapon_selection()
                    if event.type == pygame.MOUSEBUTTONDOWN:
                        mx, my = pygame.mouse.get_pos()
                        if gun_button_rect and gun_button_rect.collidepoint(mx, my):
                            for cell in player_cells:
                                cell.weapon = 'gun'
                                cell.weapon_level = 1
                                # Deduct cost
                                cell.mass -= WEAPONS['gun']['cost']
                                if cell.mass < 0:
                                    cell.mass = 0
                                cell.radius = math.sqrt(cell.mass) if cell.mass > 0 else 0
                            weapon_selection_active = False
                        elif rpg_button_rect and rpg_button_rect.collidepoint(mx, my):
                            for cell in player_cells:
                                cell.weapon = 'rpg'
                                cell.weapon_level = 1
                                # Deduct cost
                                cell.mass -= WEAPONS['rpg']['cost']
                                if cell.mass < 0:
                                    cell.mass = 0
                                cell.radius = math.sqrt(cell.mass) if cell.mass > 0 else 0
                            weapon_selection_active = False
                else:
                    # Split action
                    if event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_SPACE:
                            new_cells = []
                            for cell in player_cells[:]:
                                if (cell.mass >= 400 and cell.split_cooldown <= 0 and
                                    len(player_cells) + len(new_cells) < MAX_CELLS):
                                    # Split the cell
                                    mass1 = cell.mass / 2
                                    mass2 = cell.mass / 2
                                    radius1 = math.sqrt(mass1)
                                    radius2 = math.sqrt(mass2)
                                    # Eject towards mouse cursor
                                    mx, my = pygame.mouse.get_pos()
                                    world_mx = mx + camera_pos[0]
                                    world_my = my + camera_pos[1]
                                    dx, dy = world_mx - cell.pos[0], world_my - cell.pos[1]
                                    dist = math.hypot(dx, dy)
                                    if dist != 0:
                                        dx /= dist
                                        dy /= dist
                                    else:
                                        dx, dy = 0, 0
                                    speed = 300  # Speed of the ejected cell
                                    new_cell = PlayerCell(
                                        cell.pos[0] + dx * cell.radius,
                                        cell.pos[1] + dy * cell.radius,
                                        radius2,
                                        mass2,
                                        cell.speed,
                                        cell.name,
                                        cell.flag_image_original,
                                        team=cell.team
                                    )
                                    new_cell.direction = [dx * speed, dy * speed]
                                    new_cell.split_cooldown = 2
                                    new_cell.weapon = cell.weapon
                                    new_cell.weapon_level = cell.weapon_level
                                    new_cell.movement_locked = cell.movement_locked
                                    new_cell.locked_direction = cell.locked_direction[:]
                                    # Adjust original cell
                                    cell.mass = mass1
                                    cell.radius = radius1
                                    cell.direction[0] += dx * speed * 0.1
                                    cell.direction[1] += dy * speed * 0.1
                                    cell.split_cooldown = 2  # 2 seconds cooldown
                                    new_cells.append(new_cell)
                            player_cells.extend(new_cells)
                        elif event.key == pygame.K_LSHIFT:
                            # Toggle movement lock for all cells
                            movement_locked = not all(cell.movement_locked for cell in player_cells)
                            for cell in player_cells:
                                cell.movement_locked = movement_locked
                                if cell.movement_locked:
                                    dx, dy = cell.direction
                                    cell.locked_direction = dx, dy
                        elif event.key == pygame.K_ESCAPE:
                            running = False

                    if event.type == pygame.MOUSEBUTTONDOWN:
                        if event.button == 1:  # Left click to shoot
                            for cell in player_cells:
                                mx, my = pygame.mouse.get_pos()
                                world_mx = mx + camera_pos[0]
                                world_my = my + camera_pos[1]
                                cell.shoot(world_mx, world_my)
                        elif event.button == 3:  # Right click to lock movement
                            movement_locked = not all(cell.movement_locked for cell in player_cells)
                            for cell in player_cells:
                                cell.movement_locked = movement_locked
                                if cell.movement_locked:
                                    dx, dy = cell.direction
                                    cell.locked_direction = dx, dy

                # Update camera to follow the player
                if player_cells:
                    camera_pos[0] = player_cells[0].pos[0] - SCREEN_WIDTH // 2
                    camera_pos[1] = player_cells[0].pos[1] - SCREEN_HEIGHT // 2

                    # Keep camera within world bounds
                    camera_pos[0] = max(0, min(camera_pos[0], WORLD_WIDTH - SCREEN_WIDTH))
                    camera_pos[1] = max(0, min(camera_pos[1], WORLD_HEIGHT - SCREEN_HEIGHT))

                # Player movement towards mouse
                mx, my = pygame.mouse.get_pos()
                world_mx = mx + camera_pos[0]
                world_my = my + camera_pos[1]
                for cell in player_cells:
                    cell.move_towards(world_mx, world_my)
                    cell.update(dt)

                # Draw and move elements
                screen.fill(GRAY)
                update_food(dt)
                draw_food(screen)

                # Update and draw enemies
                for enemy in enemy_list:
                    enemy.ai_move(dt, player_cells + enemy_list)
                    enemy.update(dt)
                    if is_on_screen(enemy.pos[0], enemy.pos[1], enemy.radius):
                        enemy.draw(screen)

                for cell in player_cells:
                    if is_on_screen(cell.pos[0], cell.pos[1], cell.radius):
                        cell.draw(screen)

                # Handle bullets
                bullets.extend([bullet for cell in player_cells for bullet in cell.bullets])
                bullets.extend([bullet for enemy in enemy_list for bullet in enemy.bullets])
                for cell in player_cells:
                    cell.bullets.clear()
                for enemy in enemy_list:
                    enemy.bullets.clear()
                handle_bullets(dt)

                # Check for collisions
                check_collisions()

                if battle_royale_mode:
                    update_safe_zone(dt)
                    draw_safe_zone()
                    apply_safe_zone_damage(dt)
                    if len(enemy_list) == 0 and player_cells:
                        game_state = "won"
                    # Display battle royale info
                    display_battle_royale_info()
                elif teams_mode:
                    game_timer -= dt
                    if game_timer <= 0:
                        game_state = "won"
                    # Display teams info
                    # Implement if needed
                else:
                    # Display score and leaderboard
                    display_score()
                    display_leaderboard()

                draw_minimap()
                respawn_enemies(dt)
                update_food(dt)

                # Check if player can choose weapon
                if player_cells:
                    total_mass = sum(cell.mass for cell in player_cells)
                    if total_mass >= 5000 and player_cells[0].weapon == 'none' and not weapon_selection_active:
                        weapon_selection_active = True

            elif game_state in ["game_over", "won"]:
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_r:
                        # Reset the game
                        player_cells = []
                        enemy_list = []
                        food_list = []
                        respawning_food = []
                        bullets.clear()
                        enemy_cells_by_team = {team: [] for team in teams}
                        team_scores = {team: 0 for team in teams}
                        available_names = cool_names.copy()
                        battle_royale_mode = False
                        teams_mode = False
                        game_state = "menu"
                        game_timer = GAME_DURATION
                    elif event.key == pygame.K_q:
                        running = False

        if game_state == "menu":
            display_menu()
        elif game_state == "mode_select":
            teams_mode_rect = display_mode_selection()
        elif game_state == "team_select":
            display_team_selection()
        elif game_state == "running":
            if weapon_selection_active:
                display_weapon_selection()
        elif game_state == "game_over":
            display_game_over()
        elif game_state == "won":
            display_winning_screen()

        # Update the display
        pygame.display.flip()

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
 