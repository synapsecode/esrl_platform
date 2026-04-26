"""
Logic Gate Master — a pygame educational game for learning logic gates.

Run:  python logic_gate_master.py
Requires: pygame  (pip install pygame)
"""

import math
import random
import sys

import pygame

pygame.init()

WIDTH, HEIGHT = 1200, 750
FPS = 60

BG          = (15, 18, 30)
BG_PANEL    = (28, 32, 52)
BG_PANEL_2  = (38, 44, 70)
WHITE       = (240, 240, 255)
GRAY        = (90, 100, 125)
LIGHT_GRAY  = (180, 185, 210)
GREEN       = (80, 220, 120)
RED         = (235, 80, 95)
BLUE        = (90, 160, 255)
YELLOW      = (255, 220, 80)
PURPLE      = (180, 120, 255)
ORANGE      = (255, 150, 60)
CYAN        = (80, 220, 230)
WIRE_OFF    = (95, 105, 135)
WIRE_ON     = (255, 220, 80)

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Logic Gate Master")
clock = pygame.time.Clock()

FONT_HUGE  = pygame.font.SysFont("Arial", 64, bold=True)
FONT_BIG   = pygame.font.SysFont("Arial", 40, bold=True)
FONT_MED   = pygame.font.SysFont("Arial", 28, bold=True)
FONT_SMALL = pygame.font.SysFont("Arial", 22)
FONT_TINY  = pygame.font.SysFont("Arial", 18)
FONT_MONO  = pygame.font.SysFont("Courier New", 24, bold=True)

# ---------- Gate logic ----------

GATES_2IN = ["AND", "OR", "NAND", "NOR", "XOR", "XNOR"]
GATES_1IN = ["NOT"]
ALL_GATES = GATES_2IN + GATES_1IN

def gate_eval(gate, a, b=0):
    if gate == "AND":  return a & b
    if gate == "OR":   return a | b
    if gate == "NAND": return 1 - (a & b)
    if gate == "NOR":  return 1 - (a | b)
    if gate == "XOR":  return a ^ b
    if gate == "XNOR": return 1 - (a ^ b)
    if gate == "NOT":  return 1 - a
    return 0

GATE_INFO = {
    "AND":  ("Output is 1 only when BOTH inputs are 1.",  "A · B"),
    "OR":   ("Output is 1 if at LEAST ONE input is 1.",   "A + B"),
    "NOT":  ("Inverts the input (1 -> 0, 0 -> 1).",       "¬A"),
    "NAND": ("Inverted AND. Output is 0 only when both inputs are 1.", "¬(A · B)"),
    "NOR":  ("Inverted OR. Output is 1 only when both inputs are 0.",  "¬(A + B)"),
    "XOR":  ("Output is 1 when inputs are DIFFERENT.",   "A ⊕ B"),
    "XNOR": ("Output is 1 when inputs are the SAME.",    "¬(A ⊕ B)"),
}

# ---------- Drawing primitives ----------

def draw_text(text, font, color, x, y, center=True, surf=None):
    surf = surf or screen
    img = font.render(text, True, color)
    rect = img.get_rect()
    if center:
        rect.center = (x, y)
    else:
        rect.topleft = (x, y)
    surf.blit(img, rect)
    return rect

def draw_panel(rect, fill=BG_PANEL, border=GRAY, radius=14, border_w=2):
    pygame.draw.rect(screen, fill, rect, border_radius=radius)
    if border_w:
        pygame.draw.rect(screen, border, rect, border_w, border_radius=radius)

# ---------- Gate shapes ----------

def _and_outline(cx, cy, w, h):
    left   = cx - w / 2
    top    = cy - h / 2
    bottom = cy + h / 2
    pts = [(left, bottom), (left, top), (cx, top)]
    for i in range(33):
        ang = -math.pi / 2 + math.pi * i / 32
        pts.append((cx + math.cos(ang) * (w / 2), cy + math.sin(ang) * (h / 2)))
    pts.append((cx, bottom))
    return pts

def _or_outline(cx, cy, w, h):
    left = cx - w / 2
    top = cy - h / 2
    bottom = cy + h / 2
    pts = []
    # Curved back
    for i in range(0, 17):
        t = i / 16
        x = left + 0.18 * w * math.sin(math.pi * t)
        y = top + h * t
        pts.append((x, y))
    # Curved upper to point
    for i in range(0, 17):
        t = i / 16
        ang = math.pi * (1 - t) / 2
        x = left + 0.2 * w + math.cos(ang) * w * 0.85
        y = cy - math.sin(ang) * (h / 2)
        pts.append((x, y))
    # Curved lower from point
    for i in range(0, 17):
        t = i / 16
        ang = math.pi * t / 2
        x = left + 0.2 * w + math.cos(ang) * w * 0.85
        y = cy + math.sin(ang) * (h / 2)
        pts.append((x, y))
    return pts

def _not_outline(cx, cy, w, h):
    left = cx - w / 2
    top = cy - h / 2
    bottom = cy + h / 2
    return [(left, top), (left + w * 0.85, cy), (left, bottom)]

def draw_gate(cx, cy, gate, scale=1.0, color=WHITE, fill=BG_PANEL_2, thick=3, label=True):
    w = 110 * scale
    h = 75 * scale
    out_x = cx + w / 2
    bubble = False
    base_gate = gate

    if gate in ("NAND",):
        base_gate = "AND"; bubble = True
    elif gate in ("NOR",):
        base_gate = "OR"; bubble = True
    elif gate == "XNOR":
        base_gate = "XOR"; bubble = True

    if base_gate in ("AND",):
        pts = _and_outline(cx, cy, w, h)
    elif base_gate in ("OR", "XOR"):
        pts = _or_outline(cx, cy, w, h)
    elif base_gate == "NOT":
        pts = _not_outline(cx, cy, w, h)
    else:
        pts = _and_outline(cx, cy, w, h)

    pygame.draw.polygon(screen, fill, pts)
    pygame.draw.polygon(screen, color, pts, thick)

    if base_gate == "XOR":
        # Extra back curve for XOR
        left = cx - w / 2
        back_pts = []
        for i in range(0, 17):
            t = i / 16
            x = left - 8 * scale + 0.18 * w * math.sin(math.pi * t)
            y = cy - h / 2 + h * t
            back_pts.append((x, y))
        if len(back_pts) >= 2:
            pygame.draw.lines(screen, color, False, back_pts, thick)

    # Bubble for inverted gates
    if bubble:
        br = int(7 * scale)
        bx = out_x + br + 1
        pygame.draw.circle(screen, fill, (int(bx), int(cy)), br)
        pygame.draw.circle(screen, color, (int(bx), int(cy)), br, thick)
        out_x = bx + br

    # Output line stub
    pygame.draw.line(screen, color, (out_x, cy), (out_x + 22 * scale, cy), thick)

    # Input line stubs
    if gate == "NOT":
        pygame.draw.line(screen, color, (cx - w / 2 - 22 * scale, cy), (cx - w / 2, cy), thick)
        in_pts = [(cx - w / 2 - 22 * scale, cy)]
    else:
        y1 = cy - h * 0.28
        y2 = cy + h * 0.28
        pygame.draw.line(screen, color, (cx - w / 2 - 22 * scale, y1), (cx - w / 2 + 4, y1), thick)
        pygame.draw.line(screen, color, (cx - w / 2 - 22 * scale, y2), (cx - w / 2 + 4, y2), thick)
        in_pts = [(cx - w / 2 - 22 * scale, y1), (cx - w / 2 - 22 * scale, y2)]

    if label:
        draw_text(gate, FONT_TINY, color, cx + 4, cy + h / 2 + 14)

    return {"out": (out_x + 22 * scale, cy), "ins": in_pts}

def draw_signal(pos, value, label=None):
    color = WIRE_ON if value else WIRE_OFF
    pygame.draw.circle(screen, color, (int(pos[0]), int(pos[1])), 16)
    pygame.draw.circle(screen, WHITE, (int(pos[0]), int(pos[1])), 16, 2)
    draw_text(str(value), FONT_MED, BG, int(pos[0]), int(pos[1]))
    if label:
        draw_text(label, FONT_SMALL, LIGHT_GRAY, int(pos[0]) - 35, int(pos[1]))

def draw_wire(p1, p2, on):
    color = WIRE_ON if on else WIRE_OFF
    pygame.draw.line(screen, color, p1, p2, 4)

# ---------- Particles ----------

class Particle:
    def __init__(self, x, y, color):
        ang = random.uniform(0, math.tau)
        spd = random.uniform(2, 7)
        self.x, self.y = x, y
        self.vx = math.cos(ang) * spd
        self.vy = math.sin(ang) * spd
        self.life = random.randint(30, 60)
        self.color = color
        self.size = random.randint(3, 6)

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vy += 0.18
        self.life -= 1

    def draw(self):
        if self.life > 0:
            a = max(0, min(255, self.life * 6))
            s = pygame.Surface((self.size * 2, self.size * 2), pygame.SRCALPHA)
            pygame.draw.circle(s, (*self.color, a), (self.size, self.size), self.size)
            screen.blit(s, (self.x - self.size, self.y - self.size))

# ---------- Buttons ----------

class Button:
    def __init__(self, x, y, w, h, label, value=None, color=BG_PANEL_2, font=FONT_MED):
        self.rect = pygame.Rect(x, y, w, h)
        self.label = label
        self.value = value if value is not None else label
        self.color = color
        self.font = font
        self.hover = False
        self.locked = False
        self.flash_color = None
        self.flash_t = 0

    def draw(self):
        c = self.color
        if self.flash_t > 0:
            c = self.flash_color
        elif self.hover and not self.locked:
            c = tuple(min(255, x + 25) for x in self.color)
        pygame.draw.rect(screen, c, self.rect, border_radius=12)
        pygame.draw.rect(screen, WHITE if self.hover and not self.locked else GRAY,
                         self.rect, 2, border_radius=12)
        draw_text(self.label, self.font, WHITE, self.rect.centerx, self.rect.centery)

    def update(self, mouse):
        self.hover = self.rect.collidepoint(mouse) and not self.locked
        if self.flash_t > 0:
            self.flash_t -= 1

    def click(self, mouse):
        return (not self.locked) and self.rect.collidepoint(mouse)

    def flash(self, color, frames=20):
        self.flash_color = color
        self.flash_t = frames

# ---------- Question generation ----------

def truth_table(gate):
    if gate == "NOT":
        return [(0, gate_eval(gate, 0)), (1, gate_eval(gate, 1))]
    return [((a, b), gate_eval(gate, a, b)) for a in (0, 1) for b in (0, 1)]

def make_question(level):
    """Generate a question dict.
    Types:
      'output'   – given gate + inputs, choose output (0 or 1)
      'identify' – given truth table, choose gate
      'inputs'   – given gate and desired output, choose input pair
      'chain'    – two-gate circuit; compute final output
    """
    pool = ["output", "identify", "inputs"]
    if level >= 3:
        pool.append("chain")
    if level >= 5:
        pool += ["chain", "identify"]  # weight harder questions

    qtype = random.choice(pool)

    # restrict gate variety by level
    if level == 1:
        gates_allowed = ["AND", "OR", "NOT"]
    elif level == 2:
        gates_allowed = ["AND", "OR", "NOT", "NAND", "NOR"]
    else:
        gates_allowed = ALL_GATES

    if qtype == "output":
        gate = random.choice(gates_allowed)
        if gate == "NOT":
            a = random.randint(0, 1)
            ans = gate_eval(gate, a)
            return {
                "type": "output",
                "gate": gate, "a": a, "b": None,
                "prompt": "What is the output of this gate?",
                "options": ["0", "1"],
                "answer": str(ans),
            }
        a, b = random.randint(0, 1), random.randint(0, 1)
        ans = gate_eval(gate, a, b)
        return {
            "type": "output",
            "gate": gate, "a": a, "b": b,
            "prompt": "What is the output of this gate?",
            "options": ["0", "1"],
            "answer": str(ans),
        }

    if qtype == "identify":
        gate = random.choice([g for g in gates_allowed if g != "NOT"])
        # Build options: correct + 3 random distractors
        opts = [gate]
        pool_g = [g for g in GATES_2IN if g != gate]
        random.shuffle(pool_g)
        opts += pool_g[:3]
        random.shuffle(opts)
        return {
            "type": "identify",
            "gate": gate,
            "table": truth_table(gate),
            "prompt": "Which gate matches this truth table?",
            "options": opts,
            "answer": gate,
        }

    if qtype == "inputs":
        gate = random.choice([g for g in gates_allowed if g != "NOT"])
        target = random.randint(0, 1)
        # Make sure target is achievable (it always is for these gates)
        return {
            "type": "inputs",
            "gate": gate,
            "target": target,
            "prompt": f"Pick inputs A,B that make output = {target}",
            "options": ["0,0", "0,1", "1,0", "1,1"],
            "answer": next(
                f"{a},{b}" for a in (0, 1) for b in (0, 1)
                if gate_eval(gate, a, b) == target
            ),
        }

    if qtype == "chain":
        g1 = random.choice([g for g in gates_allowed if g != "NOT"])
        g2 = random.choice([g for g in gates_allowed if g != "NOT"])
        a, b, c = (random.randint(0, 1) for _ in range(3))
        mid = gate_eval(g1, a, b)
        out = gate_eval(g2, mid, c)
        return {
            "type": "chain",
            "g1": g1, "g2": g2, "a": a, "b": b, "c": c,
            "mid": mid, "out": out,
            "prompt": "Trace the circuit. What is the final output?",
            "options": ["0", "1"],
            "answer": str(out),
        }

# ---------- Drawing the question ----------

def draw_question_visual(q, area):
    """Draw the gate/circuit visualization inside area rect."""
    cx, cy = area.center

    if q["type"] in ("output", "inputs"):
        gate = q["gate"]
        ports = draw_gate(cx, cy, gate, scale=1.6)
        if q["type"] == "output":
            if gate == "NOT":
                draw_signal(ports["ins"][0], q["a"], "A")
            else:
                draw_signal(ports["ins"][0], q["a"], "A")
                draw_signal(ports["ins"][1], q["b"], "B")
            # Output unknown
            ox, oy = ports["out"]
            pygame.draw.circle(screen, BG_PANEL, (int(ox), int(oy)), 18)
            pygame.draw.circle(screen, ORANGE, (int(ox), int(oy)), 18, 3)
            draw_text("?", FONT_MED, ORANGE, int(ox), int(oy))
            draw_text("OUT", FONT_SMALL, LIGHT_GRAY, int(ox) + 55, int(oy))
        else:
            # 'inputs' question: show ? on inputs, target on output
            for i, p in enumerate(ports["ins"]):
                pygame.draw.circle(screen, BG_PANEL, (int(p[0]), int(p[1])), 16)
                pygame.draw.circle(screen, CYAN, (int(p[0]), int(p[1])), 16, 3)
                draw_text("?", FONT_MED, CYAN, int(p[0]), int(p[1]))
                lbl = "A" if i == 0 else "B"
                draw_text(lbl, FONT_SMALL, LIGHT_GRAY, int(p[0]) - 35, int(p[1]))
            draw_signal(ports["out"], q["target"], None)
            draw_text("OUT", FONT_SMALL, LIGHT_GRAY, int(ports["out"][0]) + 55, int(ports["out"][1]))

    elif q["type"] == "identify":
        # Render the truth table
        tx = area.centerx - 130
        ty = area.top + 30
        draw_text("Truth Table", FONT_MED, YELLOW, area.centerx, ty)
        ty += 40
        header = "  A   B  |  OUT"
        draw_text(header, FONT_MONO, WHITE, area.centerx, ty)
        pygame.draw.line(screen, GRAY, (area.centerx - 110, ty + 18),
                         (area.centerx + 110, ty + 18), 2)
        ty += 36
        for (a, b), o in q["table"]:
            line = f"  {a}   {b}  |   {o}"
            draw_text(line, FONT_MONO, CYAN if o == 1 else LIGHT_GRAY,
                      area.centerx, ty)
            ty += 30

    elif q["type"] == "chain":
        # Two gate chain
        scale = 1.1
        g1 = draw_gate(cx - 170, cy - 40, q["g1"], scale=scale)
        # Inputs to g1
        in1 = (g1["ins"][0][0] - 30, g1["ins"][0][1])
        in2 = (g1["ins"][1][0] - 30, g1["ins"][1][1])
        draw_wire(in1, g1["ins"][0], q["a"])
        draw_wire(in2, g1["ins"][1], q["b"])
        draw_signal(in1, q["a"], "A")
        draw_signal(in2, q["b"], "B")

        # Second gate
        g2 = draw_gate(cx + 130, cy + 30, q["g2"], scale=scale)
        # Wire from g1 out -> g2 first input
        mid_pt = (g1["out"][0] + 30, g1["out"][1])
        draw_wire(g1["out"], mid_pt, q["mid"])
        # routed wire down to g2 input
        draw_wire(mid_pt, (mid_pt[0], g2["ins"][0][1]), q["mid"])
        draw_wire((mid_pt[0], g2["ins"][0][1]), g2["ins"][0], q["mid"])
        # Input C
        in3 = (g2["ins"][1][0] - 50, g2["ins"][1][1])
        draw_wire(in3, g2["ins"][1], q["c"])
        draw_signal(in3, q["c"], "C")

        # Output unknown
        ox, oy = g2["out"]
        pygame.draw.circle(screen, BG_PANEL, (int(ox), int(oy)), 18)
        pygame.draw.circle(screen, ORANGE, (int(ox), int(oy)), 18, 3)
        draw_text("?", FONT_MED, ORANGE, int(ox), int(oy))
        draw_text("OUT", FONT_SMALL, LIGHT_GRAY, int(ox) + 55, int(oy))

# ---------- Game ----------

class Game:
    STATE_INSTRUCTIONS = "instructions"
    STATE_PLAY         = "play"
    STATE_FEEDBACK     = "feedback"
    STATE_LEVEL_UP     = "level_up"
    STATE_GAME_OVER    = "game_over"

    def __init__(self):
        self.state = Game.STATE_INSTRUCTIONS
        self.score = 0
        self.lives = 3
        self.level = 1
        self.streak = 0
        self.best_streak = 0
        self.correct_this_level = 0
        self.required_per_level = 4
        self.time_left = 0
        self.timer_max = 18 * FPS  # 18 seconds per question
        self.particles = []
        self.shake = 0
        self.q = None
        self.buttons = []
        self.feedback_timer = 0
        self.last_correct = False
        self.last_explanation = ""
        self.start_btn = Button(WIDTH // 2 - 130, HEIGHT - 110, 260, 70,
                                "START GAME  ▶", color=(40, 120, 70))
        self.restart_btn = Button(WIDTH // 2 - 130, HEIGHT - 130, 260, 70,
                                  "PLAY AGAIN", color=(60, 90, 160))

    def new_question(self):
        self.q = make_question(self.level)
        self.time_left = self.timer_max
        # Layout option buttons
        self.buttons = []
        opts = self.q["options"]
        n = len(opts)
        bw, bh = 200, 70
        gap = 30
        total_w = n * bw + (n - 1) * gap
        start_x = WIDTH // 2 - total_w // 2
        y = HEIGHT - 160
        for i, opt in enumerate(opts):
            color = (60, 80, 130)
            self.buttons.append(Button(start_x + i * (bw + gap), y, bw, bh, opt, value=opt, color=color))

    def emit_particles(self, x, y, color, n=40):
        for _ in range(n):
            self.particles.append(Particle(x, y, color))

    def submit(self, choice):
        correct = (choice == self.q["answer"])
        self.last_correct = correct
        if correct:
            base = 100
            time_bonus = int(50 * (self.time_left / self.timer_max))
            streak_bonus = self.streak * 25
            level_bonus = self.level * 20
            gained = base + time_bonus + streak_bonus + level_bonus
            self.score += gained
            self.streak += 1
            self.best_streak = max(self.best_streak, self.streak)
            self.correct_this_level += 1
            self.last_explanation = f"+{gained} points  (streak x{self.streak})"
            self.emit_particles(WIDTH // 2, HEIGHT // 2, GREEN, 60)
            for b in self.buttons:
                if b.value == choice:
                    b.flash(GREEN, 25)
                b.locked = True
        else:
            self.lives -= 1
            self.streak = 0
            self.shake = 18
            self.last_explanation = self._explain_answer()
            for b in self.buttons:
                if b.value == choice:
                    b.flash(RED, 25)
                if b.value == self.q["answer"]:
                    b.flash(GREEN, 25)
                b.locked = True
        self.feedback_timer = 90
        self.state = Game.STATE_FEEDBACK

    def _explain_answer(self):
        q = self.q
        if q["type"] == "output":
            g = q["gate"]
            if g == "NOT":
                return f"NOT({q['a']}) = {q['answer']}.  {GATE_INFO[g][0]}"
            return f"{q['a']} {g} {q['b']} = {q['answer']}.  {GATE_INFO[g][0]}"
        if q["type"] == "identify":
            return f"That table is the {q['gate']} gate. {GATE_INFO[q['gate']][0]}"
        if q["type"] == "inputs":
            return f"E.g. {q['answer']} -> {q['target']}.  {GATE_INFO[q['gate']][0]}"
        if q["type"] == "chain":
            return (f"{q['g1']}({q['a']},{q['b']})={q['mid']}, "
                    f"then {q['g2']}({q['mid']},{q['c']})={q['out']}.")
        return ""

    def advance(self):
        if self.lives <= 0:
            self.state = Game.STATE_GAME_OVER
            return
        if self.correct_this_level >= self.required_per_level:
            self.level += 1
            self.correct_this_level = 0
            self.required_per_level = min(8, 3 + self.level)
            self.state = Game.STATE_LEVEL_UP
            self.feedback_timer = 110
            return
        self.new_question()
        self.state = Game.STATE_PLAY

    # ---------------- rendering ----------------

    def draw_hud(self):
        # Top bar
        pygame.draw.rect(screen, BG_PANEL, (0, 0, WIDTH, 60))
        pygame.draw.line(screen, GRAY, (0, 60), (WIDTH, 60), 2)
        draw_text(f"SCORE  {self.score}", FONT_MED, WHITE, 110, 30)
        draw_text(f"LEVEL  {self.level}", FONT_MED, YELLOW, 300, 30)
        # Lives as hearts (circles)
        draw_text("LIVES", FONT_SMALL, LIGHT_GRAY, 460, 30)
        for i in range(3):
            cx = 510 + i * 30
            col = RED if i < self.lives else GRAY
            pygame.draw.circle(screen, col, (cx, 30), 11)
            pygame.draw.circle(screen, WHITE, (cx, 30), 11, 2)
        draw_text(f"STREAK x{self.streak}", FONT_MED, ORANGE, 700, 30)
        draw_text(f"BEST x{self.best_streak}", FONT_SMALL, LIGHT_GRAY, 850, 30)
        # progress bar
        prog_x, prog_y, prog_w = 950, 22, 200
        pygame.draw.rect(screen, GRAY, (prog_x, prog_y, prog_w, 18), border_radius=8)
        fill_w = int(prog_w * (self.correct_this_level / self.required_per_level))
        pygame.draw.rect(screen, GREEN, (prog_x, prog_y, fill_w, 18), border_radius=8)
        draw_text(f"{self.correct_this_level}/{self.required_per_level}",
                  FONT_TINY, WHITE, prog_x + prog_w // 2, prog_y + 9)

    def draw_timer(self):
        # bar across top of question area
        x, y, w, h = 100, 80, WIDTH - 200, 12
        pygame.draw.rect(screen, BG_PANEL_2, (x, y, w, h), border_radius=6)
        ratio = self.time_left / self.timer_max
        col = GREEN if ratio > 0.5 else (YELLOW if ratio > 0.25 else RED)
        pygame.draw.rect(screen, col, (x, y, int(w * ratio), h), border_radius=6)

    def draw_instructions(self):
        screen.fill(BG)
        # Title
        draw_text("LOGIC GATE MASTER", FONT_HUGE, YELLOW, WIDTH // 2, 80)
        draw_text("Learn digital logic by playing!", FONT_MED, LIGHT_GRAY, WIDTH // 2, 140)

        # Sample gates row
        sample_y = 230
        samples = ["AND", "OR", "NOT", "NAND", "NOR", "XOR", "XNOR"]
        gap = (WIDTH - 80) // len(samples)
        for i, g in enumerate(samples):
            cx = 60 + gap // 2 + i * gap
            draw_gate(cx, sample_y, g, scale=0.9, color=CYAN)

        # Instructions panel
        panel = pygame.Rect(120, 320, WIDTH - 240, 320)
        draw_panel(panel)
        lines = [
            ("HOW TO PLAY", FONT_BIG, YELLOW),
            ("", FONT_SMALL, WHITE),
            ("• You'll be shown a logic gate or a small circuit.", FONT_SMALL, WHITE),
            ("• Yellow wires/dots = signal 1 (HIGH).   Dim wires = signal 0 (LOW).", FONT_SMALL, WHITE),
            ("• Question types you'll see:", FONT_SMALL, WHITE),
            ("     ◦  Compute the output of a gate from its inputs.", FONT_SMALL, LIGHT_GRAY),
            ("     ◦  Identify the gate from its truth table.", FONT_SMALL, LIGHT_GRAY),
            ("     ◦  Pick inputs that produce a target output.", FONT_SMALL, LIGHT_GRAY),
            ("     ◦  Trace a 2-gate circuit (level 3+).", FONT_SMALL, LIGHT_GRAY),
            ("• Click an answer button.  Faster answers = more points.", FONT_SMALL, WHITE),
            ("• 3 lives.  Build a streak for bonus score.  Levels add harder gates.", FONT_SMALL, WHITE),
            ("", FONT_SMALL, WHITE),
            ("Controls:  Mouse to click  •  1-4 keys for options  •  ESC to quit", FONT_SMALL, ORANGE),
        ]
        ty = panel.top + 24
        for text, font, color in lines:
            draw_text(text, font, color, panel.centerx, ty)
            ty += font.get_height() + 4

        self.start_btn.draw()
        draw_text("Press SPACE or click START to begin", FONT_TINY, LIGHT_GRAY,
                  WIDTH // 2, HEIGHT - 25)

    def draw_play(self):
        screen.fill(BG)
        self.draw_hud()
        self.draw_timer()

        # Prompt
        draw_text(self.q["prompt"], FONT_BIG, WHITE, WIDTH // 2, 130)

        # Visualization area
        area = pygame.Rect(150, 180, WIDTH - 300, 360)
        draw_panel(area, fill=BG_PANEL, border=GRAY)
        draw_question_visual(self.q, area)

        # Answer buttons
        for b in self.buttons:
            b.draw()

        # Hotkey hints
        for i, b in enumerate(self.buttons):
            draw_text(str(i + 1), FONT_TINY, LIGHT_GRAY, b.rect.left + 14, b.rect.top + 14)

    def draw_feedback(self):
        self.draw_play()
        # Banner
        banner = pygame.Rect(WIDTH // 2 - 460, 540, 920, 70)
        col = GREEN if self.last_correct else RED
        draw_panel(banner, fill=(*col, 50) if False else BG_PANEL_2, border=col, border_w=3)
        head = "CORRECT!" if self.last_correct else "WRONG!"
        draw_text(head, FONT_MED, col, banner.left + 80, banner.centery)
        draw_text(self.last_explanation, FONT_SMALL, WHITE,
                  banner.left + 250, banner.centery, center=False)

    def draw_level_up(self):
        screen.fill(BG)
        self.draw_hud()
        draw_text("LEVEL UP!", FONT_HUGE, YELLOW, WIDTH // 2, HEIGHT // 2 - 80)
        draw_text(f"Welcome to Level {self.level}", FONT_BIG, WHITE,
                  WIDTH // 2, HEIGHT // 2)
        if self.level == 2:
            tip = "New gates unlocked: NAND, NOR"
        elif self.level == 3:
            tip = "New gates unlocked: XOR, XNOR  •  Multi-gate circuits begin"
        elif self.level == 4:
            tip = "Harder mix of all gates"
        else:
            tip = "Keep going — your circuit-fu is strong!"
        draw_text(tip, FONT_MED, CYAN, WIDTH // 2, HEIGHT // 2 + 60)

    def draw_game_over(self):
        screen.fill(BG)
        draw_text("GAME OVER", FONT_HUGE, RED, WIDTH // 2, 180)
        draw_text(f"Final Score:  {self.score}", FONT_BIG, WHITE, WIDTH // 2, 280)
        draw_text(f"Best Streak:  x{self.best_streak}", FONT_MED, ORANGE, WIDTH // 2, 340)
        draw_text(f"Reached Level {self.level}", FONT_MED, YELLOW, WIDTH // 2, 390)

        # Show a brief gate cheatsheet
        cheat = pygame.Rect(150, 430, WIDTH - 300, 220)
        draw_panel(cheat)
        draw_text("Gate Cheatsheet", FONT_MED, CYAN, cheat.centerx, cheat.top + 22)
        ty = cheat.top + 60
        for g in ["AND", "OR", "NOT", "NAND", "NOR", "XOR", "XNOR"]:
            desc, sym = GATE_INFO[g]
            draw_text(f"{g:<5}  {sym:<10}", FONT_MONO, YELLOW, cheat.left + 200, ty, center=False)
            draw_text(desc, FONT_SMALL, WHITE, cheat.left + 420, ty + 2, center=False)
            ty += 22

        self.restart_btn.draw()

    # ---------------- main loop pieces ----------------

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            pygame.quit(); sys.exit()
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            pygame.quit(); sys.exit()

        if self.state == Game.STATE_INSTRUCTIONS:
            if event.type == pygame.KEYDOWN and event.key in (pygame.K_SPACE, pygame.K_RETURN):
                self.start()
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.start_btn.click(event.pos):
                    self.start()

        elif self.state == Game.STATE_PLAY:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for b in self.buttons:
                    if b.click(event.pos):
                        self.submit(b.value)
                        break
            if event.type == pygame.KEYDOWN:
                if pygame.K_1 <= event.key <= pygame.K_9:
                    idx = event.key - pygame.K_1
                    if 0 <= idx < len(self.buttons):
                        self.submit(self.buttons[idx].value)

        elif self.state == Game.STATE_GAME_OVER:
            if event.type == pygame.KEYDOWN and event.key in (pygame.K_SPACE, pygame.K_RETURN):
                self.__init__()
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.restart_btn.click(event.pos):
                    self.__init__()

    def start(self):
        self.state = Game.STATE_PLAY
        self.new_question()

    def update(self, dt):
        mouse = pygame.mouse.get_pos()
        if self.state == Game.STATE_INSTRUCTIONS:
            self.start_btn.update(mouse)
        elif self.state == Game.STATE_PLAY:
            for b in self.buttons:
                b.update(mouse)
            self.time_left -= 1
            if self.time_left <= 0:
                self.submit("__timeout__")  # always wrong
        elif self.state == Game.STATE_FEEDBACK:
            for b in self.buttons:
                b.update(mouse)
            self.feedback_timer -= 1
            if self.feedback_timer <= 0:
                self.advance()
        elif self.state == Game.STATE_LEVEL_UP:
            self.feedback_timer -= 1
            if self.feedback_timer <= 0:
                self.new_question()
                self.state = Game.STATE_PLAY
        elif self.state == Game.STATE_GAME_OVER:
            self.restart_btn.update(mouse)

        for p in self.particles:
            p.update()
        self.particles = [p for p in self.particles if p.life > 0]
        if self.shake > 0:
            self.shake -= 1

    def render(self):
        if self.state == Game.STATE_INSTRUCTIONS:
            self.draw_instructions()
        elif self.state == Game.STATE_PLAY:
            self.draw_play()
        elif self.state == Game.STATE_FEEDBACK:
            self.draw_feedback()
        elif self.state == Game.STATE_LEVEL_UP:
            self.draw_level_up()
        elif self.state == Game.STATE_GAME_OVER:
            self.draw_game_over()

        for p in self.particles:
            p.draw()

        # Apply shake by blitting the screen offset
        if self.shake > 0:
            offset = (random.randint(-6, 6), random.randint(-6, 6))
            snapshot = screen.copy()
            screen.fill(BG)
            screen.blit(snapshot, offset)


def main():
    game = Game()
    while True:
        for event in pygame.event.get():
            game.handle_event(event)
        game.update(1 / FPS)
        game.render()
        pygame.display.flip()
        clock.tick(FPS)


if __name__ == "__main__":
    main()
