import pygame
import math
import random
import sys

pygame.init()
WIDTH, HEIGHT = 1000, 700
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Chopstick Crisis: Dining Philosophers Deadlock")
clock = pygame.time.Clock()
FPS = 60

# Colors
WHITE=(245,245,245); BLACK=(10,10,12); BG=(26,30,42)
RED=(230,70,70); DARK_RED=(140,30,30); LIGHT_RED=(240,150,150)
GREEN=(90,200,120); DARK_GREEN=(40,130,60)
BLUE=(100,160,240); LIGHT_BLUE=(160,200,255)
YELLOW=(240,210,80); ORANGE=(240,150,60)
GRAY=(140,140,145); DARK_GRAY=(60,60,70); DIM=(110,110,120)
PURPLE=(180,110,220); BROWN=(140,90,60); TAN=(220,200,170)
TABLE=(135,90,60); TABLE_EDGE=(85,55,35); TABLE_TOP=(170,120,80)
RICE=(245,235,210); SAUCE=(200,90,60); PLATE=(235,235,240)
SKIN=(225,190,150); ROBE=(70,90,140)
CHOP_LIGHT=(235,215,170); CHOP_DARK=(170,130,80)

font_xl = pygame.font.SysFont("arial", 44, bold=True)
font_lg = pygame.font.SysFont("arial", 30, bold=True)
font_md = pygame.font.SysFont("arial", 20, bold=True)
font_sm = pygame.font.SysFont("arial", 15)
font_xs = pygame.font.SysFont("arial", 12, bold=True)

MENU, INSTRUCTIONS, LEVEL_INTRO, PLAYING, END_SCREEN = range(5)

# Layout
TABLE_CX, TABLE_CY = 360, 370
TABLE_R = 140
PHIL_R = 230
CHOP_R = 185
HUD_X = 740

# Philosopher states
THINKING, HUNGRY, HOLDING_ONE, EATING = range(4)
STATE_LABELS = {THINKING:"thinking", HUNGRY:"hungry",
                HOLDING_ONE:"waiting", EATING:"eating"}
STATE_COLORS = {THINKING:BLUE, HUNGRY:YELLOW,
                HOLDING_ONE:ORANGE, EATING:GREEN}

PHIL_COLORS = [
    (110, 160, 230),  # blue
    (220, 150, 80),   # orange
    (130, 200, 130),  # green
    (220, 130, 180),  # pink
    (200, 175, 95),   # gold
]
PHIL_NAMES = ["Plato", "Kant", "Laozi", "Hypatia", "Confucius"]

LEVELS = {
    1: {
        "n": 3,
        "hunger_rate": 2.2,
        "eat_time": 1.6,
        "duration": 45,
        "goal": 5,
        "title": "LEVEL 1: Three at the Table",
        "sub": "Learn the rules. Deadlock is unlikely with only three.",
        "desc": [
            "3 philosophers sit at a round table. There are 3 chopsticks.",
            "Each philosopher needs BOTH their left and right chopstick to eat.",
            "LEFT-CLICK a philosopher to wake them up to grab chopsticks.",
            "Goal: serve 5 meals in 45 seconds. Nobody starves.",
        ],
    },
    2: {
        "n": 5,
        "hunger_rate": 3.4,
        "eat_time": 2.0,
        "duration": 60,
        "goal": 10,
        "title": "LEVEL 2: Classic Deadlock",
        "sub": "Five philosophers, five chopsticks. The trap is real.",
        "desc": [
            "If every philosopher grabs their LEFT chopstick at once,",
            "no right chopstick is free — they all wait forever.",
            "That circular wait is called DEADLOCK. The red ring warns you.",
            "RIGHT-CLICK a waiting philosopher to drop their chopstick.",
            "Goal: serve 10 meals in 60s without anyone starving.",
        ],
    },
    3: {
        "n": 5,
        "hunger_rate": 5.0,
        "eat_time": 1.4,
        "duration": 75,
        "goal": 18,
        "title": "LEVEL 3: The Hungry Crowd",
        "sub": "Faster hunger, less margin. Be the scheduler.",
        "desc": [
            "Hunger ticks faster. Meals finish quicker.",
            "Stagger your wake-ups so chopsticks are never all held at once.",
            "Goal: serve 18 meals in 75 seconds. Nobody starves.",
        ],
    },
}

HUNGER_MAX = 100.0


class Particle:
    def __init__(self, x, y, vx, vy, color, life, size=3, gravity=0.08):
        self.x=x; self.y=y; self.vx=vx; self.vy=vy
        self.color=color; self.life=life; self.max_life=life
        self.size=size; self.gravity=gravity
    def update(self):
        self.x += self.vx; self.y += self.vy
        self.vy += self.gravity
        self.life -= 1
    def draw(self, surf):
        if self.life <= 0: return
        r = max(1, int(self.size * (self.life / self.max_life)))
        pygame.draw.circle(surf, self.color, (int(self.x), int(self.y)), r)


class Philosopher:
    def __init__(self, i, n):
        self.i = i
        self.n = n
        angle = -math.pi / 2 + i * (2 * math.pi / n)
        self.angle = angle
        self.x = TABLE_CX + PHIL_R * math.cos(angle)
        self.y = TABLE_CY + PHIL_R * math.sin(angle)
        self.state = THINKING
        self.hunger = random.uniform(8, 22)
        self.think_timer = random.uniform(1.5, 3.0)
        self.eat_timer = 0
        self.left_chop = i
        self.right_chop = (i + 1) % n
        self.holds = set()
        self.meals = 0
        self.color = PHIL_COLORS[i % len(PHIL_COLORS)]
        self.name = PHIL_NAMES[i % len(PHIL_NAMES)]
        self.pulse = 0

    def wants(self):
        return {self.left_chop, self.right_chop} - self.holds


def chop_pos(i, n):
    angle = -math.pi / 2 + (i + 0.5) * (2 * math.pi / n)
    return (TABLE_CX + CHOP_R * math.cos(angle),
            TABLE_CY + CHOP_R * math.sin(angle), angle)


class Game:
    def __init__(self, level):
        self.level = level
        self.cfg = LEVELS[level]
        self.n = self.cfg["n"]
        self.phils = [Philosopher(i, self.n) for i in range(self.n)]
        self.chops = [None] * self.n  # owner index or None
        self.time_left = self.cfg["duration"]
        self.elapsed = 0
        self.particles = []
        self.cycle = set()
        self.deadlock_grace = 0.0
        self.deadlock_resolved = 0
        self.deadlock_explained = False
        self.popup = None
        self.message = ""
        self.message_time = 0
        self.tutorial_step = 0 if level == 1 else -1
        self.tutorial_messages = [
            "Click a YELLOW (hungry) philosopher to make them grab chopsticks.",
            "They need BOTH adjacent chopsticks. Orange = waiting for the second.",
            "Right-click a waiting philosopher to drop their chopstick.",
            "Keep everyone fed — green = eating. Each meal counts toward the goal.",
        ]
        self.end_state = None
        self.end_msg = ""
        self.starved = None
        self.flash = 0  # deadlock visual flash timer

    # ---- mechanics ----
    def try_grab(self, i):
        p = self.phils[i]
        if p.state not in (HUNGRY, HOLDING_ONE):
            return
        # Prefer left then right
        for c in (p.left_chop, p.right_chop):
            if c in p.holds:
                continue
            if self.chops[c] is None:
                self.chops[c] = i
                p.holds.add(c)
        if len(p.holds) == 2:
            p.state = EATING
            p.eat_timer = self.cfg["eat_time"]
            # rice splash
            for _ in range(10):
                self.particles.append(Particle(
                    p.x, p.y, random.uniform(-1.5, 1.5), random.uniform(-2.5, -0.5),
                    RICE, 28, 3))
        elif len(p.holds) == 1:
            p.state = HOLDING_ONE

    def release_all(self, i):
        p = self.phils[i]
        for c in list(p.holds):
            self.chops[c] = None
        p.holds.clear()

    def request_eat(self, i):
        p = self.phils[i]
        if p.state == THINKING:
            p.state = HUNGRY
        self.try_grab(i)
        # advance tutorial
        if self.level == 1 and self.tutorial_step == 0:
            self.tutorial_step = 1

    def force_release(self, i):
        p = self.phils[i]
        if p.state == EATING:
            return  # don't interrupt eating
        if p.holds:
            self.release_all(i)
            p.state = HUNGRY
            self.message = f"{p.name} dropped their chopsticks."
            self.message_time = 1.6
            if self.level == 1 and self.tutorial_step == 2:
                self.tutorial_step = 3

    # ---- deadlock detection (wait-for cycle) ----
    def detect_cycle(self):
        wait_for = {}
        for i, p in enumerate(self.phils):
            if p.state == HOLDING_ONE:
                for c in p.wants():
                    holder = self.chops[c]
                    if holder is not None and holder != i:
                        wait_for[i] = holder
                        break
        in_cycle = set()
        for start in list(wait_for):
            seen = []
            cur = start
            while cur in wait_for and cur not in seen:
                seen.append(cur)
                cur = wait_for[cur]
            if cur in seen:
                idx = seen.index(cur)
                in_cycle.update(seen[idx:])
        return in_cycle

    # ---- main update ----
    def update(self, dt):
        if self.popup or self.end_state:
            return
        cfg = self.cfg
        for p in self.phils:
            if p.state == THINKING:
                p.think_timer -= dt
                p.hunger += cfg["hunger_rate"] * 0.4 * dt
                if p.think_timer <= 0 or p.hunger > 55:
                    p.state = HUNGRY
            elif p.state == HUNGRY:
                p.hunger += cfg["hunger_rate"] * dt
                # In level 1, philosophers also auto-try; in higher levels you control
                if self.level == 1:
                    self.try_grab(p.i)
            elif p.state == HOLDING_ONE:
                p.hunger += cfg["hunger_rate"] * 1.2 * dt
                self.try_grab(p.i)
                p.pulse = (p.pulse + dt * 4) % (2 * math.pi)
                # tutorial advance when a philosopher is stuck
                if self.level == 1 and self.tutorial_step == 1:
                    self.tutorial_step = 2
            elif p.state == EATING:
                p.eat_timer -= dt
                p.hunger = max(0, p.hunger - 55 * dt)
                if p.eat_timer <= 0:
                    p.meals += 1
                    self.release_all(p.i)
                    p.state = THINKING
                    p.think_timer = random.uniform(2.2, 4.2)
                    # eating particles already added at grab
            if p.hunger >= HUNGER_MAX:
                self.end_state = "lose"
                self.starved = p.i
                self.end_msg = f"{p.name} starved! Hunger ran out."
                return

        # particles
        self.particles = [pt for pt in self.particles if pt.life > 0]
        for pt in self.particles:
            pt.update()

        # time
        self.elapsed += dt
        self.time_left -= dt
        total = sum(p.meals for p in self.phils)
        if self.time_left <= 0:
            if total >= cfg["goal"]:
                self.end_state = "win"
                self.end_msg = f"Served {total} meals — goal {cfg['goal']} met!"
            else:
                self.end_state = "lose"
                self.end_msg = f"Only {total} of {cfg['goal']} meals. Try staggering wake-ups."
            return

        # deadlock
        prev_cycle = self.cycle
        self.cycle = self.detect_cycle()
        if self.cycle:
            self.deadlock_grace += dt
            self.flash = (self.flash + dt * 6) % (2 * math.pi)
            if (self.level >= 2 and not self.deadlock_explained
                    and self.deadlock_grace > 1.3 and len(self.cycle) >= 2):
                self.popup = ("deadlock",
                    "DEADLOCK DETECTED",
                    [
                        "Every philosopher in the red ring holds one chopstick",
                        "and is waiting for the next one — a CIRCULAR WAIT.",
                        "No one can proceed. This is a classic deadlock.",
                        "",
                        "TO BREAK IT: right-click someone in the cycle so they",
                        "drop their chopstick. That frees a neighbour to eat.",
                    ])
                self.deadlock_explained = True
        else:
            if prev_cycle and not self.cycle:
                self.deadlock_resolved += 1
                self.message = "Deadlock resolved!"
                self.message_time = 2.0
            self.deadlock_grace = max(0, self.deadlock_grace - dt * 2)

        if self.message_time > 0:
            self.message_time -= dt

    # ---- input ----
    def handle_click(self, pos, button):
        if self.popup or self.end_state:
            return
        for p in self.phils:
            if math.hypot(pos[0] - p.x, pos[1] - p.y) < 42:
                if button == 1:
                    self.request_eat(p.i)
                elif button == 3:
                    self.force_release(p.i)
                return

    def handle_popup_click(self, pos):
        if not self.popup:
            return
        ok = pygame.Rect(WIDTH // 2 - 90, HEIGHT // 2 + 130, 180, 44)
        if ok.collidepoint(pos):
            self.popup = None

    # ---- drawing ----
    def draw(self, surf):
        surf.fill(BG)
        self.draw_table(surf)
        self.draw_chopsticks(surf)
        for p in self.phils:
            self.draw_philosopher(surf, p)
        for pt in self.particles:
            pt.draw(surf)
        self.draw_wait_arrows(surf)
        self.draw_hud(surf)
        if self.cycle:
            self.draw_deadlock_warning(surf)
        self.draw_message(surf)
        if self.level == 1 and 0 <= self.tutorial_step < len(self.tutorial_messages):
            self.draw_tutorial(surf)
        if self.popup:
            self.draw_popup(surf)

    def draw_table(self, surf):
        # Table shadow
        pygame.draw.circle(surf, (10, 12, 18), (TABLE_CX + 4, TABLE_CY + 6), TABLE_R + 8)
        # Table edge
        pygame.draw.circle(surf, TABLE_EDGE, (TABLE_CX, TABLE_CY), TABLE_R + 8)
        # Table top
        pygame.draw.circle(surf, TABLE, (TABLE_CX, TABLE_CY), TABLE_R)
        pygame.draw.circle(surf, TABLE_TOP, (TABLE_CX, TABLE_CY), TABLE_R - 6)
        # Wood grain rings
        for r in (TABLE_R - 20, TABLE_R - 60):
            pygame.draw.circle(surf, TABLE, (TABLE_CX, TABLE_CY), r, 2)
        # Title centred on table
        title = font_md.render("CHOPSTICK CRISIS", True, (90, 60, 40))
        surf.blit(title, (TABLE_CX - title.get_width() // 2, TABLE_CY - 14))
        sub = font_xs.render(f"Level {self.level}", True, (90, 60, 40))
        surf.blit(sub, (TABLE_CX - sub.get_width() // 2, TABLE_CY + 8))

    def draw_chopsticks(self, surf):
        for i in range(self.n):
            cx, cy, angle = chop_pos(i, self.n)
            held = self.chops[i] is not None
            # The chopstick is laid perpendicular to the radial axis
            tx, ty = math.cos(angle + math.pi / 2), math.sin(angle + math.pi / 2)
            # If held, draw a small offset showing it's with the holder
            if held:
                holder = self.phils[self.chops[i]]
                # Move chopstick partway toward the holder
                cx = (cx + holder.x) * 0.5
                cy = (cy + holder.y) * 0.5
            length = 30
            color = CHOP_DARK if held else CHOP_LIGHT
            # Two parallel sticks for "chopstick" look
            for offset in (-3, 3):
                ox = -ty * offset
                oy = tx * offset
                p1 = (cx - tx * length / 2 + ox, cy - ty * length / 2 + oy)
                p2 = (cx + tx * length / 2 + ox, cy + ty * length / 2 + oy)
                pygame.draw.line(surf, color, p1, p2, 4)
                pygame.draw.circle(surf, color, (int(p2[0]), int(p2[1])), 3)
            if not held:
                idx = font_xs.render(f"C{i}", True, DIM)
                surf.blit(idx, (cx - idx.get_width() // 2, cy + 14))

    def draw_philosopher(self, surf, p):
        x, y = int(p.x), int(p.y)
        # Hover ring
        mx, my = pygame.mouse.get_pos()
        hover = math.hypot(mx - p.x, my - p.y) < 42
        if hover and not self.popup and not self.end_state:
            pygame.draw.circle(surf, WHITE, (x, y), 44, 2)
        # Cycle alarm ring
        if p.i in self.cycle:
            r = 46 + int(3 * math.sin(self.flash))
            pygame.draw.circle(surf, RED, (x, y), r, 3)
        # Plate behind philosopher (closer to table)
        plate_x = int((p.x + TABLE_CX) * 0.5 + (TABLE_CX - p.x) * 0.05)
        plate_y = int((p.y + TABLE_CY) * 0.5 + (TABLE_CY - p.y) * 0.05)
        pygame.draw.ellipse(surf, PLATE, (plate_x - 22, plate_y - 12, 44, 24))
        pygame.draw.ellipse(surf, (200, 200, 205), (plate_x - 22, plate_y - 12, 44, 24), 2)
        # Rice on plate (more rice when state=eating)
        if p.state == EATING:
            for _ in range(6):
                rx = plate_x + random.randint(-10, 10)
                ry = plate_y + random.randint(-4, 4)
                pygame.draw.circle(surf, RICE, (rx, ry), 2)
        else:
            for dx, dy in [(-8, 0), (0, -2), (8, 0), (-4, 3), (4, 3)]:
                pygame.draw.circle(surf, RICE, (plate_x + dx, plate_y + dy), 2)

        # Body (robe)
        body_color = p.color
        pygame.draw.circle(surf, BLACK, (x, y + 2), 34)
        pygame.draw.circle(surf, body_color, (x, y), 32)
        # Inner highlight
        pygame.draw.circle(surf, (
            min(255, body_color[0] + 30),
            min(255, body_color[1] + 30),
            min(255, body_color[2] + 30)), (x - 8, y - 8), 12)
        # State dot
        sc = STATE_COLORS[p.state]
        pygame.draw.circle(surf, sc, (x, y - 22), 8)
        pygame.draw.circle(surf, BLACK, (x, y - 22), 8, 2)
        # Face: simple eyes + mouth
        eye_y = y - 4
        pygame.draw.circle(surf, BLACK, (x - 8, eye_y), 3)
        pygame.draw.circle(surf, BLACK, (x + 8, eye_y), 3)
        if p.state == EATING:
            pygame.draw.arc(surf, BLACK, (x - 10, y + 2, 20, 12), math.pi, 2 * math.pi, 2)
        elif p.state == HUNGRY:
            pygame.draw.line(surf, BLACK, (x - 6, y + 10), (x + 6, y + 10), 2)
        elif p.state == HOLDING_ONE:
            pygame.draw.line(surf, BLACK, (x - 6, y + 11), (x + 6, y + 8), 2)
        else:
            pygame.draw.line(surf, BLACK, (x - 5, y + 9), (x + 5, y + 9), 2)

        # Name label
        nm = font_xs.render(p.name, True, WHITE)
        bg = pygame.Rect(x - nm.get_width() // 2 - 4, y + 38, nm.get_width() + 8, 16)
        pygame.draw.rect(surf, (0, 0, 0, 150), bg, border_radius=4)
        surf.blit(nm, (bg.x + 4, bg.y + 1))

        # Hunger bar
        bw, bh = 60, 7
        bx = x - bw // 2
        by = y + 58
        pygame.draw.rect(surf, (40, 40, 50), (bx, by, bw, bh), border_radius=2)
        h_ratio = p.hunger / HUNGER_MAX
        hc = GREEN if h_ratio < 0.5 else (YELLOW if h_ratio < 0.8 else RED)
        pygame.draw.rect(surf, hc, (bx, by, int(bw * h_ratio), bh), border_radius=2)
        pygame.draw.rect(surf, (20, 20, 25), (bx, by, bw, bh), 1, border_radius=2)

        # State label (small)
        lbl = font_xs.render(STATE_LABELS[p.state], True, sc)
        surf.blit(lbl, (x - lbl.get_width() // 2, by + 9))

    def draw_wait_arrows(self, surf):
        # Faint arrows from waiter to the chopstick they want (and its holder)
        for p in self.phils:
            if p.state == HOLDING_ONE:
                for c in p.wants():
                    holder = self.chops[c]
                    if holder is None:
                        continue
                    h = self.phils[holder]
                    color = RED if p.i in self.cycle else (180, 180, 90)
                    # Draw a short arrow
                    sx, sy = p.x, p.y
                    ex, ey = h.x, h.y
                    dx, dy = ex - sx, ey - sy
                    L = math.hypot(dx, dy) or 1
                    dx, dy = dx / L, dy / L
                    sx += dx * 42; sy += dy * 42
                    ex -= dx * 42; ey -= dy * 42
                    pygame.draw.line(surf, color, (sx, sy), (ex, ey), 2)
                    # Arrowhead
                    perp = (-dy, dx)
                    ax1 = ex - dx * 10 + perp[0] * 5
                    ay1 = ey - dy * 10 + perp[1] * 5
                    ax2 = ex - dx * 10 - perp[0] * 5
                    ay2 = ey - dy * 10 - perp[1] * 5
                    pygame.draw.polygon(surf, color,
                        [(ex, ey), (ax1, ay1), (ax2, ay2)])

    def draw_hud(self, surf):
        # Side panel
        panel = pygame.Rect(HUD_X - 10, 20, WIDTH - HUD_X - 10, HEIGHT - 40)
        pygame.draw.rect(surf, (38, 42, 58), panel, border_radius=10)
        pygame.draw.rect(surf, (60, 68, 90), panel, 2, border_radius=10)

        x = HUD_X
        y = 36
        t = font_lg.render(f"Level {self.level}", True, WHITE)
        surf.blit(t, (x, y)); y += 38

        # Time
        t = font_sm.render("TIME LEFT", True, DIM)
        surf.blit(t, (x, y)); y += 18
        col = RED if self.time_left < 10 else WHITE
        t = font_lg.render(f"{max(0, self.time_left):.1f}s", True, col)
        surf.blit(t, (x, y)); y += 38

        # Meals served
        total = sum(p.meals for p in self.phils)
        goal = self.cfg["goal"]
        t = font_sm.render("MEALS SERVED", True, DIM)
        surf.blit(t, (x, y)); y += 18
        t = font_lg.render(f"{total} / {goal}", True, GREEN if total >= goal else WHITE)
        surf.blit(t, (x, y)); y += 38

        # Deadlocks resolved
        t = font_sm.render("DEADLOCKS BROKEN", True, DIM)
        surf.blit(t, (x, y)); y += 18
        t = font_md.render(str(self.deadlock_resolved), True, WHITE)
        surf.blit(t, (x, y)); y += 30

        # Legend
        y += 10
        t = font_sm.render("STATES", True, DIM)
        surf.blit(t, (x, y)); y += 20
        for st in (THINKING, HUNGRY, HOLDING_ONE, EATING):
            pygame.draw.circle(surf, STATE_COLORS[st], (x + 8, y + 8), 7)
            pygame.draw.circle(surf, BLACK, (x + 8, y + 8), 7, 2)
            t = font_sm.render(STATE_LABELS[st], True, WHITE)
            surf.blit(t, (x + 24, y + 1))
            y += 22

        # Controls reminder
        y += 6
        t = font_sm.render("CONTROLS", True, DIM)
        surf.blit(t, (x, y)); y += 20
        for line in ("L-click: wake / grab", "R-click: force drop",
                     "ESC: back to menu"):
            t = font_sm.render(line, True, WHITE)
            surf.blit(t, (x, y)); y += 18

    def draw_deadlock_warning(self, surf):
        text = "CYCLE FORMING — break it!" if self.deadlock_grace < 1.3 else "DEADLOCK!"
        col = ORANGE if self.deadlock_grace < 1.3 else RED
        t = font_md.render(text, True, col)
        bg = pygame.Rect(TABLE_CX - t.get_width() // 2 - 16, 30,
                         t.get_width() + 32, 32)
        pygame.draw.rect(surf, (40, 20, 20), bg, border_radius=8)
        pygame.draw.rect(surf, col, bg, 2, border_radius=8)
        surf.blit(t, (bg.x + 16, bg.y + 5))

    def draw_message(self, surf):
        if self.message_time > 0 and self.message:
            t = font_md.render(self.message, True, WHITE)
            bg = pygame.Rect(TABLE_CX - t.get_width() // 2 - 12, HEIGHT - 60,
                             t.get_width() + 24, 30)
            s = pygame.Surface((bg.width, bg.height), pygame.SRCALPHA)
            s.fill((0, 0, 0, 180))
            surf.blit(s, bg.topleft)
            surf.blit(t, (bg.x + 12, bg.y + 5))

    def draw_tutorial(self, surf):
        msg = self.tutorial_messages[self.tutorial_step]
        t = font_md.render(msg, True, BLACK)
        bg = pygame.Rect(TABLE_CX - t.get_width() // 2 - 12, 70,
                         t.get_width() + 24, 32)
        pygame.draw.rect(surf, YELLOW, bg, border_radius=8)
        pygame.draw.rect(surf, BLACK, bg, 2, border_radius=8)
        surf.blit(t, (bg.x + 12, bg.y + 6))
        # Step indicator
        s = font_xs.render(f"Step {self.tutorial_step + 1} / {len(self.tutorial_messages)}",
                           True, BLACK)
        surf.blit(s, (bg.right - s.get_width() - 6, bg.bottom + 2))

    def draw_popup(self, surf):
        s = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        s.fill((0, 0, 0, 180))
        surf.blit(s, (0, 0))
        box = pygame.Rect(WIDTH // 2 - 320, HEIGHT // 2 - 170, 640, 360)
        pygame.draw.rect(surf, (40, 44, 60), box, border_radius=12)
        pygame.draw.rect(surf, RED, box, 3, border_radius=12)
        kind, title, lines = self.popup
        t = font_lg.render(title, True, RED)
        surf.blit(t, (box.centerx - t.get_width() // 2, box.y + 24))
        y = box.y + 80
        for line in lines:
            t = font_md.render(line, True, WHITE)
            surf.blit(t, (box.centerx - t.get_width() // 2, y))
            y += 28
        ok = pygame.Rect(WIDTH // 2 - 90, HEIGHT // 2 + 130, 180, 44)
        pygame.draw.rect(surf, GREEN, ok, border_radius=8)
        pygame.draw.rect(surf, WHITE, ok, 2, border_radius=8)
        t = font_md.render("GOT IT", True, BLACK)
        surf.blit(t, (ok.centerx - t.get_width() // 2,
                      ok.centery - t.get_height() // 2))


# ----- Screens -----
def draw_menu():
    screen.fill(BG)
    # Decorative chopsticks
    for i, off in enumerate((-30, 0, 30)):
        pygame.draw.line(screen, CHOP_LIGHT,
                         (WIDTH // 2 - 200 + off, 80), (WIDTH // 2 + 200 + off, 100), 4)
    title = font_xl.render("CHOPSTICK CRISIS", True, WHITE)
    screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 70))
    sub = font_md.render("Dining Philosophers — A Deadlock Puzzle", True, YELLOW)
    screen.blit(sub, (WIDTH // 2 - sub.get_width() // 2, 130))

    blurb = font_sm.render(
        "Keep the philosophers fed. Don't let them deadlock waiting for chopsticks.",
        True, DIM)
    screen.blit(blurb, (WIDTH // 2 - blurb.get_width() // 2, 170))

    buttons = []
    y0 = 230
    for level in (1, 2, 3):
        rect = pygame.Rect(WIDTH // 2 - 220, y0, 440, 70)
        pygame.draw.rect(screen, (50, 56, 80), rect, border_radius=10)
        pygame.draw.rect(screen, BLUE, rect, 2, border_radius=10)
        cfg = LEVELS[level]
        t = font_md.render(cfg["title"], True, WHITE)
        screen.blit(t, (rect.x + 18, rect.y + 10))
        t = font_sm.render(cfg["sub"], True, DIM)
        screen.blit(t, (rect.x + 18, rect.y + 38))
        buttons.append((f"Level {level}", rect))
        y0 += 84

    # How to play
    rect = pygame.Rect(WIDTH // 2 - 110, y0 + 8, 220, 44)
    pygame.draw.rect(screen, (60, 80, 60), rect, border_radius=8)
    pygame.draw.rect(screen, GREEN, rect, 2, border_radius=8)
    t = font_md.render("How to Play", True, WHITE)
    screen.blit(t, (rect.centerx - t.get_width() // 2,
                    rect.centery - t.get_height() // 2))
    buttons.append(("How to Play", rect))

    foot = font_xs.render("LEFT-click to start a level. ESC quits.", True, DIM)
    screen.blit(foot, (WIDTH // 2 - foot.get_width() // 2, HEIGHT - 30))
    return buttons


def draw_instructions():
    screen.fill(BG)
    title = font_xl.render("HOW TO PLAY", True, WHITE)
    screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 40))

    sections = [
        ("THE SETUP", YELLOW, [
            "Philosophers sit around a round table. Between each pair lies",
            "one chopstick. To eat, a philosopher needs BOTH the chopstick",
            "on their LEFT and the one on their RIGHT.",
            "Each chopstick can only be held by one philosopher at a time.",
        ]),
        ("WHAT YOU DO", GREEN, [
            "LEFT-CLICK a philosopher: wake them up and grab any free chopstick",
            "  - they keep waiting until both chopsticks are in hand.",
            "RIGHT-CLICK a philosopher: force them to put their chopstick down",
            "  - use this to break a deadlock cycle.",
        ]),
        ("THE DEADLOCK TRAP", ORANGE, [
            "If every philosopher grabs their LEFT chopstick at once,",
            "every RIGHT chopstick is taken. Nobody can finish. That's a",
            "CIRCULAR WAIT — the textbook example of DEADLOCK.",
            "A red ring appears around the cycle. Right-click someone in",
            "the ring to free a chopstick and unblock a neighbour.",
        ]),
        ("WIN / LOSE", BLUE, [
            "WIN: serve the level's meal goal before time runs out.",
            "LOSE: any philosopher's hunger bar fills to 100%.",
        ]),
    ]

    y = 110
    for heading, color, lines in sections:
        t = font_md.render(heading, True, color)
        screen.blit(t, (80, y))
        y += 28
        for line in lines:
            t = font_sm.render(line, True, WHITE)
            screen.blit(t, (100, y))
            y += 19
        y += 8

    back = pygame.Rect(WIDTH // 2 - 110, HEIGHT - 60, 220, 44)
    pygame.draw.rect(screen, BLUE, back, border_radius=8)
    pygame.draw.rect(screen, WHITE, back, 2, border_radius=8)
    t = font_md.render("BACK TO MENU", True, WHITE)
    screen.blit(t, (back.centerx - t.get_width() // 2,
                    back.centery - t.get_height() // 2))
    return back


def draw_level_intro(level):
    screen.fill(BG)
    cfg = LEVELS[level]
    title = font_xl.render(cfg["title"], True, YELLOW)
    screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 90))
    sub = font_md.render(cfg["sub"], True, WHITE)
    screen.blit(sub, (WIDTH // 2 - sub.get_width() // 2, 145))

    box = pygame.Rect(120, 210, WIDTH - 240, 280)
    pygame.draw.rect(screen, (40, 44, 60), box, border_radius=10)
    pygame.draw.rect(screen, BLUE, box, 2, border_radius=10)

    y = box.y + 30
    for line in cfg["desc"]:
        t = font_md.render(line, True, WHITE)
        screen.blit(t, (box.x + 30, y))
        y += 30

    y += 10
    stats = [
        ("Philosophers", str(cfg["n"])),
        ("Time", f"{cfg['duration']} seconds"),
        ("Meal goal", f"{cfg['goal']} meals"),
    ]
    for label, val in stats:
        t = font_sm.render(label, True, DIM)
        screen.blit(t, (box.x + 30, y))
        t = font_sm.render(val, True, WHITE)
        screen.blit(t, (box.x + 200, y))
        y += 20

    start = pygame.Rect(WIDTH // 2 - 130, HEIGHT - 90, 260, 50)
    pygame.draw.rect(screen, GREEN, start, border_radius=10)
    pygame.draw.rect(screen, WHITE, start, 2, border_radius=10)
    t = font_md.render("START LEVEL", True, BLACK)
    screen.blit(t, (start.centerx - t.get_width() // 2,
                    start.centery - t.get_height() // 2))
    return start


def draw_end_screen(game):
    screen.fill(BG)
    title_text = "VICTORY!" if game.end_state == "win" else "GAME OVER"
    title_color = GREEN if game.end_state == "win" else RED
    title = font_xl.render(title_text, True, title_color)
    screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 70))

    sub = font_md.render(game.end_msg, True, WHITE)
    screen.blit(sub, (WIDTH // 2 - sub.get_width() // 2, 130))

    # Stats
    total = sum(p.meals for p in game.phils)
    cfg = game.cfg
    stats = [
        ("Level", str(game.level)),
        ("Meals served", f"{total} / {cfg['goal']}"),
        ("Time used", f"{cfg['duration'] - max(0, game.time_left):.1f}s"),
        ("Deadlocks broken", str(game.deadlock_resolved)),
    ]
    box = pygame.Rect(WIDTH // 2 - 220, 200, 440, 200)
    pygame.draw.rect(screen, (40, 44, 60), box, border_radius=10)
    pygame.draw.rect(screen, BLUE, box, 2, border_radius=10)
    y = box.y + 24
    for label, val in stats:
        t = font_md.render(label, True, DIM)
        screen.blit(t, (box.x + 30, y))
        t = font_md.render(val, True, WHITE)
        screen.blit(t, (box.right - 30 - t.get_width(), y))
        y += 36

    # Per-philosopher
    y = box.bottom + 20
    t = font_sm.render("Per philosopher:", True, DIM)
    screen.blit(t, (WIDTH // 2 - 220, y))
    y += 22
    for p in game.phils:
        pygame.draw.circle(screen, p.color, (WIDTH // 2 - 210, y + 8), 7)
        t = font_sm.render(f"{p.name}: {p.meals} meals", True, WHITE)
        screen.blit(t, (WIDTH // 2 - 190, y))
        y += 20

    btn = pygame.Rect(WIDTH // 2 - 130, HEIGHT - 70, 260, 48)
    pygame.draw.rect(screen, BLUE, btn, border_radius=10)
    pygame.draw.rect(screen, WHITE, btn, 2, border_radius=10)
    t = font_md.render("BACK TO MENU", True, WHITE)
    screen.blit(t, (btn.centerx - t.get_width() // 2,
                    btn.centery - t.get_height() // 2))
    return btn


def main():
    state = MENU
    game = None
    selected_level = 1
    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        mouse_pos = pygame.mouse.get_pos()
        click_btn = None  # 1 left, 3 right
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                click_btn = event.button
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if state == PLAYING:
                        state = MENU
                    elif state == MENU:
                        running = False
                    else:
                        state = MENU

        if state == MENU:
            buttons = draw_menu()
            if click_btn == 1:
                for label, rect in buttons:
                    if rect.collidepoint(mouse_pos):
                        if label == "How to Play":
                            state = INSTRUCTIONS
                        elif label.startswith("Level"):
                            selected_level = int(label.split()[1])
                            state = LEVEL_INTRO
        elif state == INSTRUCTIONS:
            back = draw_instructions()
            if click_btn == 1 and back.collidepoint(mouse_pos):
                state = MENU
        elif state == LEVEL_INTRO:
            start = draw_level_intro(selected_level)
            if click_btn == 1 and start.collidepoint(mouse_pos):
                game = Game(selected_level)
                state = PLAYING
        elif state == PLAYING:
            game.update(dt)
            if click_btn in (1, 3):
                if game.popup:
                    if click_btn == 1:
                        game.handle_popup_click(mouse_pos)
                else:
                    game.handle_click(mouse_pos, click_btn)
            game.draw(screen)
            if game.end_state is not None:
                state = END_SCREEN
        elif state == END_SCREEN:
            btn = draw_end_screen(game)
            if click_btn == 1 and btn.collidepoint(mouse_pos):
                state = MENU

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
