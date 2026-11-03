import pygame
import math
import random
import sys

pygame.init()
WIDTH, HEIGHT = 1000, 700
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Break-Even Express: The Contribution Tank")
clock = pygame.time.Clock()
FPS = 60

# Colors
WHITE=(255,255,255); BLACK=(0,0,0); RED=(220,60,60); DARK_RED=(140,30,30)
LIGHT_RED=(240,150,150); GREEN=(80,200,100); DARK_GREEN=(40,130,60)
BLUE=(70,140,220); LIGHT_BLUE=(130,190,240); YELLOW=(240,210,80)
ORANGE=(240,150,60); GRAY=(140,140,140); DARK_GRAY=(60,60,60)
LIGHT_GRAY=(200,200,200); ROAD=(80,80,90); GRASS=(110,160,90)
BROWN=(140,90,60); TANK_BG=(220,235,245); BG=(28,38,60)

font_lg = pygame.font.SysFont("arial", 32, bold=True)
font_md = pygame.font.SysFont("arial", 20, bold=True)
font_sm = pygame.font.SysFont("arial", 15)
font_xs = pygame.font.SysFont("arial", 12)

GAME_AREA = pygame.Rect(0, 60, 760, 640)
TANK_AREA = pygame.Rect(790, 100, 180, 520)

# Road rectangles (drawn). Top, middle, and bottom horizontals + one vertical.
ROAD_RECTS = [
    pygame.Rect(GAME_AREA.left, 160, GAME_AREA.width, 70),  # top horizontal
    pygame.Rect(GAME_AREA.left, 350, GAME_AREA.width, 70),  # middle horizontal
    pygame.Rect(GAME_AREA.left, 540, GAME_AREA.width, 70),  # bottom horizontal
    pygame.Rect(370, GAME_AREA.top, 70, GAME_AREA.height),  # vertical
]
# Drivable bands = road rects shrunk by van half-size (van is ~44x28, so 22 / 14).
DRIVABLE = [
    pygame.Rect(GAME_AREA.left + 22, 174, GAME_AREA.width - 44, 43),
    pygame.Rect(GAME_AREA.left + 22, 364, GAME_AREA.width - 44, 43),
    pygame.Rect(GAME_AREA.left + 22, 554, GAME_AREA.width - 44, 43),
    pygame.Rect(392, GAME_AREA.top + 14, 27, GAME_AREA.height - 28),
]

MENU, INSTRUCTIONS, LEVEL_INTRO, PLAYING, END_SCREEN = 0,1,2,3,4

class Particle:
    def __init__(self, x, y, vx, vy, color, life, size=3, gravity=0.1):
        self.x=x; self.y=y; self.vx=vx; self.vy=vy
        self.color=color; self.life=life; self.max_life=life
        self.size=size; self.gravity=gravity
    def update(self):
        self.x += self.vx; self.y += self.vy
        self.vy += self.gravity
        self.life -= 1
    def draw(self, surf):
        if self.life > 0:
            ratio = self.life / self.max_life
            s = max(1, int(self.size * ratio))
            pygame.draw.circle(surf, self.color, (int(self.x), int(self.y)), s)

class Van:
    def __init__(self, x, y):
        self.x=x; self.y=y; self.speed=3.8
        self.crates=0; self.capacity=12
    def update(self, keys):
        dx=dy=0
        if keys[pygame.K_LEFT] or keys[pygame.K_a]: dx -= self.speed
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]: dx += self.speed
        if keys[pygame.K_UP] or keys[pygame.K_w]: dy -= self.speed
        if keys[pygame.K_DOWN] or keys[pygame.K_s]: dy += self.speed
        nx = self.x + dx; ny = self.y + dy
        # Move x and y independently so the van slides along road edges.
        if any(d.collidepoint(nx, self.y) for d in DRIVABLE):
            self.x = nx
        if any(d.collidepoint(self.x, ny) for d in DRIVABLE):
            self.y = ny
    def draw(self, surf):
        # Shadow
        pygame.draw.ellipse(surf, (40,40,40), (self.x-22, self.y+12, 44, 8))
        # Body
        pygame.draw.rect(surf, BLUE, (self.x-22, self.y-14, 44, 26), border_radius=4)
        # Cab window
        pygame.draw.rect(surf, LIGHT_BLUE, (self.x+4, self.y-10, 14, 18), border_radius=2)
        # Side stripe
        pygame.draw.rect(surf, WHITE, (self.x-22, self.y-2, 44, 3))
        # Wheels
        for wx, wy in [(-13,12),(13,12),(-13,-14),(13,-14)]:
            pygame.draw.circle(surf, BLACK, (int(self.x+wx), int(self.y+wy)), 4)
        # Crate count
        if self.crates > 0:
            t = font_xs.render(str(self.crates), True, WHITE)
            surf.blit(t, (self.x-19, self.y-7))

class Market:
    def __init__(self, x, y):
        self.x=x; self.y=y
        self.rect = pygame.Rect(x-45, y-45, 90, 90)
    def draw(self, surf):
        pygame.draw.rect(surf, ORANGE, self.rect, border_radius=6)
        pygame.draw.rect(surf, BROWN, self.rect, 3, border_radius=6)
        # Awning
        for i in range(0, 90, 14):
            pygame.draw.line(surf, RED, (self.rect.left+i, self.rect.top),
                             (self.rect.left+i+7, self.rect.top+10), 4)
        # Crates icon
        for cx, cy in [(-15,5),(0,5),(15,5),(-7,-12),(8,-12)]:
            pygame.draw.rect(surf, BROWN, (self.x+cx-6, self.y+cy-6, 12, 12))
            pygame.draw.line(surf, BLACK, (self.x+cx-6,self.y+cy), (self.x+cx+6,self.y+cy),1)
        t = font_sm.render("MARKET", True, BLACK)
        surf.blit(t, (self.rect.centerx-t.get_width()//2, self.rect.bottom-18))

class House:
    def __init__(self, x, y):
        self.x=x; self.y=y
        self.rect = pygame.Rect(x-25, y-22, 50, 44)
        self.active = True
        self.cooldown = 0
        self.permanent_off = False
    def update(self, base_cd):
        if self.permanent_off:
            self.active = False
            return
        if not self.active:
            self.cooldown -= 1
            if self.cooldown <= 0:
                self.active = True
    def draw(self, surf):
        if self.permanent_off:
            color = (90,90,90); rcolor = (70,70,70)
        elif self.active:
            color = (220,200,160); rcolor = (180,60,60)
        else:
            color = (160,150,130); rcolor = (130,80,80)
        pygame.draw.rect(surf, color, self.rect)
        pygame.draw.polygon(surf, rcolor,
            [(self.rect.left-4, self.rect.top),
             (self.rect.right+4, self.rect.top),
             (self.rect.centerx, self.rect.top-18)])
        # Door
        pygame.draw.rect(surf, BROWN, (self.rect.centerx-6, self.rect.centery, 12, 22))
        # Window
        pygame.draw.rect(surf, LIGHT_BLUE, (self.rect.left+5, self.rect.top+7, 10, 10))
        if self.active and not self.permanent_off:
            pygame.draw.circle(surf, YELLOW, (self.rect.right+5, self.rect.top-8), 9)
            pygame.draw.circle(surf, BLACK, (self.rect.right+5, self.rect.top-8), 9, 2)
            t = font_xs.render("!", True, BLACK)
            surf.blit(t, (self.rect.right+2, self.rect.top-15))
        if self.permanent_off:
            t = font_xs.render("CLOSED", True, RED)
            surf.blit(t, (self.rect.centerx-t.get_width()//2, self.rect.top-14))

class Game:
    def __init__(self, level_num):
        self.level_num = level_num
        self.variable_cost = 250
        self.selling_price = 400
        self.contribution = 150
        self.fixed_cost = 1500
        self.duration = 25 if level_num == 1 else 30

        self.bep_line = self.fixed_cost
        self.mos_line = self.fixed_cost + 500  # ~3 boxes above BEP
        self.profit_target = 250  # for level 3
        self.tank_max = self.fixed_cost * 2
        
        self.tank_value = self.bep_line
        self.drain_per_sec = self.fixed_cost / self.duration
        
        self.time_left = self.duration
        self.boxes_sold = 0
        self.crates_bought = 0
        self.money_spent_var = 0
        
        self.van = Van(400, 380)
        self.market = Market(80, 380)
        self.houses = [
            House(220, 130), House(450, 130), House(680, 130),
            House(220, 620), House(450, 620), House(680, 620),
            House(700, 380),
        ]
        
        self.particles = []
        self.message = ""
        self.message_time = 0
        self.popup = None
        self.event_triggered = False
        self.discount_offered = False
        self.discount_decided = False
        self.discount_accepted = False
        self.house_cooldown_frames = 180
        self.tutorial_step = 0 if level_num == 1 else -1
        self.tutorial_messages = [
            "Drive to the orange MARKET and press SPACE to BUY crates.",
            "Now drive to a HOUSE (yellow !) and press SPACE to DELIVER.",
            "Watch: only the CONTRIBUTION (Rs 150) fills the tank!",
            "The DRAIN is fixed cost — it leaks no matter what. Sell ≥ 10 boxes to break even!"
        ]
        self.end_state = None  # "win" or "lose"
        self.end_msg = ""
    
    def update(self, dt, keys):
        if self.popup:
            return
        self.van.update(keys)
        self.tank_value -= self.drain_per_sec * dt
        for h in self.houses:
            h.update(self.house_cooldown_frames)
        self.particles = [p for p in self.particles if p.life > 0]
        for p in self.particles:
            p.update()
        self.time_left -= dt
        if self.message_time > 0:
            self.message_time -= dt
        
        # Tutorial advancement
        if self.level_num == 1 and self.tutorial_step < len(self.tutorial_messages):
            if self.tutorial_step == 0 and self.crates_bought > 0:
                self.tutorial_step = 1
            elif self.tutorial_step == 1 and self.boxes_sold >= 1:
                self.tutorial_step = 2
            elif self.tutorial_step == 2 and self.boxes_sold >= 3:
                self.tutorial_step = 3
        
        # Level 2 mid-month event
        if self.level_num == 2 and not self.event_triggered:
            if self.time_left <= self.duration * 0.5:
                self.event_triggered = True
                self.fixed_cost += 500
                self.bep_line = self.fixed_cost
                self.mos_line = self.bep_line + 500
                rt = max(1, self.time_left)
                self.drain_per_sec += 500 / rt
                self.popup = ("event", "DIESEL PRICE UP!",
                    "Fixed costs rose by Rs 500.\n"
                    "Notice: your DRAIN got FASTER, not your splash.\n"
                    "Diesel & loan are FIXED costs (per month),\n"
                    "not variable (per trip)!\n"
                    "New BEP target ≈ 14 boxes.")
        
        # Level 3 discount offer
        if self.level_num == 3 and not self.discount_offered:
            if self.time_left <= self.duration * 0.65:
                self.discount_offered = True
                self.popup = ("discount", "CUSTOMER OFFER!",
                    "A buyer wants to pay Rs 350 instead of Rs 400.\n"
                    "ACCEPT: Contribution drops to Rs 100.\n"
                    "  New BEP = 1500/100 = 15 boxes (faster customers).\n"
                    "REFUSE: Contribution stays Rs 150.\n"
                    "  But 2 customers go elsewhere.")
        
        # End conditions
        if self.tank_value <= 0:
            self.end_state = "lose"
            self.end_msg = "BANKRUPT! Tank emptied to zero."
        elif self.time_left <= 0:
            self.evaluate_end()
    
    def evaluate_end(self):
        profit = self.tank_value - self.bep_line
        if self.level_num == 1:
            if self.tank_value >= self.bep_line:
                self.end_state = "win"
                self.end_msg = f"You broke even! ({self.boxes_sold} boxes)"
            else:
                self.end_state = "lose"
                self.end_msg = "Below the Break-Even Line. Loss declared."
        elif self.level_num == 2:
            if self.tank_value >= self.mos_line:
                self.end_state = "win"
                self.end_msg = "In the GREEN Margin-of-Safety zone!"
            elif self.tank_value >= self.bep_line:
                self.end_state = "lose"
                self.end_msg = "Broke even, but no margin of safety."
            else:
                self.end_state = "lose"
                self.end_msg = "Below BEP. Loss declared."
        else:
            if profit >= self.profit_target:
                self.end_state = "win"
                self.end_msg = f"Profit Rs {int(profit)} hit target Rs {self.profit_target}!"
            elif profit >= 0:
                self.end_state = "lose"
                self.end_msg = f"Profit only Rs {int(profit)} (need Rs {self.profit_target})."
            else:
                self.end_state = "lose"
                self.end_msg = f"Loss of Rs {int(-profit)}."
    
    def handle_action(self):
        if self.popup or self.end_state:
            return
        # Market?
        if math.hypot(self.van.x - self.market.x, self.van.y - self.market.y) < 70:
            slots = self.van.capacity - self.van.crates
            if slots > 0:
                self.van.crates += slots
                self.crates_bought += slots
                self.money_spent_var += slots * self.variable_cost
                self.message = f"Bought {slots} crates  (-Rs {slots*self.variable_cost} variable cost)"
                self.message_time = 2.0
                # market particles
                for _ in range(10):
                    self.particles.append(Particle(
                        self.van.x, self.van.y, random.uniform(-1,1), random.uniform(-2,-0.5),
                        ORANGE, 25, 3))
            else:
                self.message = "Van is full!"
                self.message_time = 1.5
            return
        # House?
        for h in self.houses:
            if h.active and not h.permanent_off and math.hypot(self.van.x-h.x, self.van.y-h.y) < 55:
                if self.van.crates > 0:
                    self.van.crates -= 1
                    self.boxes_sold += 1
                    self.tank_value += self.contribution
                    h.active = False
                    h.cooldown = self.house_cooldown_frames
                    # Splash (blue) toward tank
                    for _ in range(14):
                        self.particles.append(Particle(
                            h.x, h.y - 10,
                            random.uniform(-1.5, 1.5), random.uniform(-3.5, -1.5),
                            BLUE, 35, 4, gravity=0.12))
                    # Variable cost steam
                    for _ in range(10):
                        self.particles.append(Particle(
                            h.x, h.y - 15,
                            random.uniform(-1, 1), random.uniform(-2.5, -0.8),
                            (180,180,180), 28, 4, gravity=-0.05))
                    self.message = f"Delivered! +Rs {self.contribution} contribution (Rs {self.variable_cost} cost evaporates)"
                    self.message_time = 2.0
                else:
                    self.message = "No crates! Visit the market first."
                    self.message_time = 1.5
                return
    
    def handle_popup_click(self, pos):
        if not self.popup:
            return
        kind = self.popup[0]
        if kind == "event":
            ok_rect = pygame.Rect(WIDTH//2-50, HEIGHT//2+90, 100, 40)
            if ok_rect.collidepoint(pos):
                self.popup = None
        elif kind == "discount":
            yes_rect = pygame.Rect(WIDTH//2-160, HEIGHT//2+90, 130, 40)
            no_rect = pygame.Rect(WIDTH//2+30, HEIGHT//2+90, 130, 40)
            if yes_rect.collidepoint(pos):
                self.discount_accepted = True
                self.discount_decided = True
                self.selling_price = 350
                self.contribution = 100
                self.house_cooldown_frames = 90
                self.popup = None
                self.message = "Accepted! Contribution Rs 100. New BEP = 15 boxes."
                self.message_time = 3.0
            elif no_rect.collidepoint(pos):
                self.discount_accepted = False
                self.discount_decided = True
                cnt = 0
                for h in self.houses:
                    if not h.permanent_off and cnt < 2:
                        h.permanent_off = True
                        h.active = False
                        cnt += 1
                self.popup = None
                self.message = "Refused. 2 customers gone, but contribution stays Rs 150."
                self.message_time = 3.0
    
    def draw(self, surf):
        surf.fill(BG)
        # Game area
        pygame.draw.rect(surf, GRASS, GAME_AREA)
        # Roads (three horizontals + one vertical so every building has road access)
        for r in ROAD_RECTS:
            pygame.draw.rect(surf, ROAD, r)
        # Lane markers — horizontal roads at y=193, 383, 573; vertical road at x=403
        for x in range(GAME_AREA.left+10, GAME_AREA.right, 32):
            pygame.draw.rect(surf, YELLOW, (x, 193, 18, 3))
            pygame.draw.rect(surf, YELLOW, (x, 383, 18, 3))
            pygame.draw.rect(surf, YELLOW, (x, 573, 18, 3))
        for y in range(GAME_AREA.top+10, GAME_AREA.bottom, 32):
            pygame.draw.rect(surf, YELLOW, (403, y, 3, 18))
        
        self.market.draw(surf)
        for h in self.houses:
            h.draw(surf)
        self.van.draw(surf)
        for p in self.particles:
            p.draw(surf)
        
        # Interaction hint
        self.draw_interaction_hint(surf)
        
        self.draw_tank(surf)
        self.draw_hud(surf)
        
        if self.message_time > 0 and self.message:
            t = font_md.render(self.message, True, WHITE)
            bg = pygame.Rect(GAME_AREA.centerx - t.get_width()//2 - 12,
                             GAME_AREA.bottom - 40, t.get_width()+24, 30)
            s = pygame.Surface((bg.width, bg.height))
            s.set_alpha(200); s.fill(BLACK)
            surf.blit(s, bg.topleft)
            surf.blit(t, (bg.x+12, bg.y+5))
        
        # Tutorial
        if self.level_num == 1 and 0 <= self.tutorial_step < len(self.tutorial_messages):
            msg = self.tutorial_messages[self.tutorial_step]
            t = font_md.render(msg, True, BLACK)
            bg = pygame.Rect(GAME_AREA.centerx-t.get_width()//2-12, GAME_AREA.top+8,
                             t.get_width()+24, 30)
            pygame.draw.rect(surf, YELLOW, bg, border_radius=6)
            pygame.draw.rect(surf, BLACK, bg, 2, border_radius=6)
            surf.blit(t, (bg.x+12, bg.y+5))
        
        if self.popup:
            self.draw_popup(surf)
    
    def draw_interaction_hint(self, surf):
        near = None
        if math.hypot(self.van.x-self.market.x, self.van.y-self.market.y) < 70:
            near = "[SPACE] BUY"
        else:
            for h in self.houses:
                if h.active and not h.permanent_off and math.hypot(self.van.x-h.x, self.van.y-h.y) < 55:
                    near = "[SPACE] DELIVER"
                    break
        if near:
            t = font_sm.render(near, True, YELLOW)
            bg = pygame.Rect(self.van.x-t.get_width()//2-6, self.van.y-50,
                             t.get_width()+12, 20)
            s = pygame.Surface((bg.width, bg.height))
            s.set_alpha(220); s.fill(BLACK)
            surf.blit(s, bg.topleft)
            surf.blit(t, (bg.x+6, bg.y+3))
    
    def draw_tank(self, surf):
        pygame.draw.rect(surf, TANK_BG, TANK_AREA)
        pygame.draw.rect(surf, DARK_GRAY, TANK_AREA, 4)
        
        def val_to_y(val):
            v = max(0, min(self.tank_max, val))
            r = v / self.tank_max
            return TANK_AREA.bottom - r * TANK_AREA.height
        
        # Zone backgrounds
        bep_y = val_to_y(self.bep_line)
        mos_y = val_to_y(self.mos_line)
        # Loss zone (light red below BEP)
        loss_rect = pygame.Rect(TANK_AREA.left+4, bep_y, TANK_AREA.width-8, TANK_AREA.bottom-bep_y-4)
        if loss_rect.height > 0:
            s = pygame.Surface((loss_rect.width, loss_rect.height))
            s.set_alpha(70); s.fill(RED)
            surf.blit(s, loss_rect.topleft)
        # MoS zone
        mos_rect = pygame.Rect(TANK_AREA.left+4, TANK_AREA.top+4, TANK_AREA.width-8, mos_y-TANK_AREA.top-4)
        if mos_rect.height > 0:
            s = pygame.Surface((mos_rect.width, mos_rect.height))
            s.set_alpha(70); s.fill(GREEN)
            surf.blit(s, mos_rect.topleft)
        
        # Water level
        water_y = val_to_y(self.tank_value)
        if self.tank_value >= self.mos_line:
            wcolor = GREEN
        elif self.tank_value >= self.bep_line:
            wcolor = LIGHT_BLUE
        else:
            wcolor = LIGHT_RED
        wrect = pygame.Rect(TANK_AREA.left+4, water_y, TANK_AREA.width-8, TANK_AREA.bottom-water_y-4)
        if wrect.height > 0:
            pygame.draw.rect(surf, wcolor, wrect)
            # Wave line
            pygame.draw.line(surf, WHITE, (wrect.left, water_y), (wrect.right, water_y), 2)
        
        # BEP line
        pygame.draw.line(surf, RED, (TANK_AREA.left, bep_y), (TANK_AREA.right, bep_y), 3)
        t = font_xs.render("BEP", True, RED)
        surf.blit(t, (TANK_AREA.right+5, bep_y-7))
        # MoS line
        pygame.draw.line(surf, DARK_GREEN, (TANK_AREA.left, mos_y), (TANK_AREA.right, mos_y), 3)
        t = font_xs.render("MoS", True, DARK_GREEN)
        surf.blit(t, (TANK_AREA.right+5, mos_y-7))
        
        # Drain icon
        pygame.draw.rect(surf, DARK_GRAY, (TANK_AREA.left-15, TANK_AREA.bottom-25, 15, 25))
        pygame.draw.polygon(surf, GRAY, [(TANK_AREA.left-15, TANK_AREA.bottom-25),
                                          (TANK_AREA.left, TANK_AREA.bottom-25),
                                          (TANK_AREA.left-7, TANK_AREA.bottom-15)])
        # Title
        t = font_md.render("COST TANK", True, WHITE)
        surf.blit(t, (TANK_AREA.centerx-t.get_width()//2, TANK_AREA.top-30))
        
        # Value
        diff = self.tank_value - self.bep_line
        if diff >= 0:
            vt = font_sm.render(f"+Rs {int(diff)} (profit)", True, GREEN)
        else:
            vt = font_sm.render(f"-Rs {int(-diff)} (loss)", True, LIGHT_RED)
        surf.blit(vt, (TANK_AREA.centerx-vt.get_width()//2, TANK_AREA.bottom+10))
        # Drain rate
        dt = font_xs.render(f"Drain: Rs {int(self.drain_per_sec)}/sec", True, WHITE)
        surf.blit(dt, (TANK_AREA.centerx-dt.get_width()//2, TANK_AREA.bottom+30))
    
    def draw_hud(self, surf):
        pygame.draw.rect(surf, DARK_GRAY, (0, 0, WIDTH, 60))
        items = [
            f"LEVEL {self.level_num}",
            f"Time: {max(0,int(self.time_left))}s",
            f"Boxes: {self.boxes_sold}",
            f"BEP: {int(self.fixed_cost/self.contribution)}",
            f"Crates: {self.van.crates}/{self.van.capacity}",
            f"Contrib: Rs {self.contribution}",
            f"Fixed: Rs {self.fixed_cost}",
        ]
        x = 10
        for it in items:
            t = font_sm.render(it, True, WHITE)
            surf.blit(t, (x, 8))
            x += t.get_width() + 18
        # P/V Ratio
        pv = self.contribution / self.selling_price * 100
        pvc = GREEN if pv >= 35 else (YELLOW if pv >= 25 else ORANGE)
        t = font_sm.render(f"P/V Ratio: {pv:.1f}%", True, pvc)
        surf.blit(t, (10, 32))
        # Controls
        hint = font_xs.render("WASD/Arrows: Drive | SPACE: Buy/Deliver", True, LIGHT_GRAY)
        surf.blit(hint, (220, 36))
        # P/V bar
        pv_x = 700
        pygame.draw.rect(surf, BLACK, (pv_x, 32, 60, 12), 1)
        pygame.draw.rect(surf, pvc, (pv_x+1, 33, int(58*pv/100), 10))
    
    def draw_popup(self, surf):
        overlay = pygame.Surface((WIDTH, HEIGHT))
        overlay.set_alpha(180); overlay.fill(BLACK)
        surf.blit(overlay, (0,0))
        kind, title, msg = self.popup
        box = pygame.Rect(WIDTH//2-300, HEIGHT//2-150, 600, 300)
        pygame.draw.rect(surf, WHITE, box, border_radius=10)
        pygame.draw.rect(surf, ORANGE, box, 4, border_radius=10)
        t = font_lg.render(title, True, RED)
        surf.blit(t, (box.centerx-t.get_width()//2, box.top+15))
        y = box.top+70
        for line in msg.split('\n'):
            t = font_sm.render(line, True, BLACK)
            surf.blit(t, (box.centerx-t.get_width()//2, y))
            y += 22
        if kind == "event":
            ok = pygame.Rect(WIDTH//2-50, HEIGHT//2+90, 100, 40)
            pygame.draw.rect(surf, BLUE, ok, border_radius=6)
            t = font_md.render("OK", True, WHITE)
            surf.blit(t, (ok.centerx-t.get_width()//2, ok.centery-t.get_height()//2))
        elif kind == "discount":
            yes = pygame.Rect(WIDTH//2-160, HEIGHT//2+90, 130, 40)
            no = pygame.Rect(WIDTH//2+30, HEIGHT//2+90, 130, 40)
            pygame.draw.rect(surf, GREEN, yes, border_radius=6)
            pygame.draw.rect(surf, RED, no, border_radius=6)
            t = font_md.render("ACCEPT", True, WHITE)
            surf.blit(t, (yes.centerx-t.get_width()//2, yes.centery-t.get_height()//2))
            t = font_md.render("REFUSE", True, WHITE)
            surf.blit(t, (no.centerx-t.get_width()//2, no.centery-t.get_height()//2))


def draw_menu():
    screen.fill(BG)
    # Title
    t = font_lg.render("BREAK-EVEN EXPRESS", True, YELLOW)
    screen.blit(t, (WIDTH//2-t.get_width()//2, 60))
    t = font_md.render("The Contribution Tank", True, WHITE)
    screen.blit(t, (WIDTH//2-t.get_width()//2, 105))
    t = font_sm.render("A pygame mini-game on Break-Even, Contribution & Margin of Safety", True, LIGHT_GRAY)
    screen.blit(t, (WIDTH//2-t.get_width()//2, 140))
    # Tank icon
    pygame.draw.rect(screen, DARK_GRAY, (WIDTH//2-60, 175, 120, 100), 4)
    pygame.draw.rect(screen, LIGHT_BLUE, (WIDTH//2-56, 215, 112, 56))
    pygame.draw.line(screen, RED, (WIDTH//2-60, 220), (WIDTH//2+60, 220), 3)
    pygame.draw.line(screen, GREEN, (WIDTH//2-60, 195), (WIDTH//2+60, 195), 3)
    
    buttons = []
    labels = ["Level 1: Fill the Tank",
              "Level 2: Cost Classification",
              "Level 3: The Discount Trap",
              "How to Play"]
    colors = [BLUE, ORANGE, RED, DARK_GREEN]
    for i, (label, c) in enumerate(zip(labels, colors)):
        rect = pygame.Rect(WIDTH//2-160, 320+i*65, 320, 55)
        pygame.draw.rect(screen, c, rect, border_radius=8)
        pygame.draw.rect(screen, WHITE, rect, 2, border_radius=8)
        t = font_md.render(label, True, WHITE)
        screen.blit(t, (rect.centerx-t.get_width()//2, rect.centery-t.get_height()//2))
        buttons.append((label, rect))
    return buttons

def draw_instructions():
    screen.fill(BG)
    t = font_lg.render("HOW TO PLAY", True, YELLOW)
    screen.blit(t, (WIDTH//2-t.get_width()//2, 30))
    
    lines = [
        "You run a fresh-fruit delivery van. Your COST TANK shows your money status.",
        "",
        "ECONOMICS (per box):",
        "  Selling Price = Rs 400  |  Variable Cost = Rs 250  |  Contribution = Rs 150",
        "  Fixed Cost (loan, wages, insurance) = Rs 1,500 per month — DRAINS the tank.",
        "  Break-Even Point = Fixed Cost / Contribution = 1500 / 150 = 10 boxes.",
        "",
        "CONTROLS:",
        "  WASD / ARROW KEYS  -  Drive the van",
        "  SPACE              -  Buy crates at MARKET, or deliver to a HOUSE (yellow !)",
        "  LEFT MOUSE CLICK   -  Menu navigation, popup choices",
        "",
        "TANK ZONES:",
        "  Below RED line  =  LOSS",
        "  At RED line     =  Break-Even",
        "  Above GREEN line=  Margin of Safety (profit zone)",
        "",
        "WIN: end the month at or above the level's target line.",
        "LOSE: tank reaches zero (bankrupt) OR ends below BEP.",
        "",
        "TIP: Each delivery adds only the CONTRIBUTION (Rs 150) — the variable Rs 250",
        "evaporates as 'steam'. Revenue is NOT profit!",
        "",
        "Click anywhere to return to menu.",
    ]
    y = 80
    for line in lines:
        t = font_sm.render(line, True, WHITE)
        screen.blit(t, (60, y))
        y += 22

def draw_level_intro(level_num):
    screen.fill(BG)
    titles = {
        1: ("LEVEL 1: Fill the Tank", "Learn the Drain, Feel the Splash"),
        2: ("LEVEL 2: Cost Classification Crunch", "Margin of Safety Matters"),
        3: ("LEVEL 3: The Discount Trap", "Price, Contribution, and the Shifting BEP"),
    }
    descs = {
        1: ["Sell at least 10 boxes to reach the BEP line.",
            "Fixed Cost = Rs 1,500  |  Contribution = Rs 150 / box",
            "BEP = 1,500 / 150 = 10 boxes",
            "Time: 25 seconds"],
        2: ["Finish in the GREEN Margin-of-Safety zone (~14 boxes).",
            "Fixed Cost = Rs 1,500. A mid-month event will hit!",
            "Watch carefully: it changes the DRAIN, not the splash.",
            "Time: 30 seconds"],
        3: ["Profit at least Rs 250 above BEP to win!",
            "Mid-month a customer will request a discount.",
            "Accept = lower contribution, more demand.",
            "Refuse = full contribution, fewer customers.",
            "Time: 30 seconds"],
    }
    title, sub = titles[level_num]
    t = font_lg.render(title, True, YELLOW)
    screen.blit(t, (WIDTH//2-t.get_width()//2, 130))
    t = font_md.render(sub, True, WHITE)
    screen.blit(t, (WIDTH//2-t.get_width()//2, 180))
    y = 270
    for line in descs[level_num]:
        t = font_md.render(line, True, WHITE)
        screen.blit(t, (WIDTH//2-t.get_width()//2, y))
        y += 32
    btn = pygame.Rect(WIDTH//2-120, 540, 240, 60)
    pygame.draw.rect(screen, GREEN, btn, border_radius=10)
    pygame.draw.rect(screen, WHITE, btn, 3, border_radius=10)
    t = font_lg.render("START", True, WHITE)
    screen.blit(t, (btn.centerx-t.get_width()//2, btn.centery-t.get_height()//2))
    return btn

def draw_end_screen(game):
    screen.fill(BG)
    won = game.end_state == "win"
    color = GREEN if won else RED
    title = "MONTH COMPLETE — YOU WON!" if won else "MONTH ENDED — TRY AGAIN"
    t = font_lg.render(title, True, color)
    screen.blit(t, (WIDTH//2-t.get_width()//2, 50))
    t = font_md.render(game.end_msg, True, WHITE)
    screen.blit(t, (WIDTH//2-t.get_width()//2, 100))
    
    revenue = game.boxes_sold * game.selling_price
    var_costs_used = game.boxes_sold * game.variable_cost
    contribution_total = game.boxes_sold * game.contribution
    profit = contribution_total - game.fixed_cost
    bep_b = int(game.fixed_cost / game.contribution)
    mos_boxes = max(0, game.boxes_sold - bep_b)
    
    lines = [
        ("Boxes Sold:", f"{game.boxes_sold}"),
        ("Selling Price:", f"Rs {game.selling_price} per box"),
        ("Revenue (Boxes x Price):", f"Rs {revenue}"),
        ("- Variable Cost (sold):", f"Rs {var_costs_used}"),
        ("= Total Contribution:", f"Rs {contribution_total}"),
        ("- Fixed Cost:", f"Rs {game.fixed_cost}"),
        ("= Profit / Loss:", f"Rs {profit}"),
        ("", ""),
        ("BEP Boxes:", f"{bep_b}"),
        ("Margin of Safety:", f"{mos_boxes} boxes"),
        ("P/V Ratio:", f"{game.contribution/game.selling_price*100:.1f}%"),
    ]
    y = 160
    for label, val in lines:
        if label == "":
            y += 10; continue
        t = font_md.render(label, True, WHITE)
        screen.blit(t, (WIDTH//2-220, y))
        c = GREEN if (label=="= Profit / Loss:" and profit>=0) else (RED if label=="= Profit / Loss:" else WHITE)
        t = font_md.render(val, True, c)
        screen.blit(t, (WIDTH//2+80, y))
        y += 30
    
    btn = pygame.Rect(WIDTH//2-100, HEIGHT-70, 200, 50)
    pygame.draw.rect(screen, BLUE, btn, border_radius=10)
    pygame.draw.rect(screen, WHITE, btn, 2, border_radius=10)
    t = font_md.render("BACK TO MENU", True, WHITE)
    screen.blit(t, (btn.centerx-t.get_width()//2, btn.centery-t.get_height()//2))
    return btn


def main():
    state = MENU
    game = None
    selected_level = 1
    
    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        mouse_pos = pygame.mouse.get_pos()
        click_event = False
        space_event = False
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                click_event = True
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                space_event = True
        
        if state == MENU:
            buttons = draw_menu()
            if click_event:
                for label, rect in buttons:
                    if rect.collidepoint(mouse_pos):
                        if "Level 1" in label:
                            selected_level = 1; state = LEVEL_INTRO
                        elif "Level 2" in label:
                            selected_level = 2; state = LEVEL_INTRO
                        elif "Level 3" in label:
                            selected_level = 3; state = LEVEL_INTRO
                        elif "How to Play" in label:
                            state = INSTRUCTIONS
        elif state == INSTRUCTIONS:
            draw_instructions()
            if click_event:
                state = MENU
        elif state == LEVEL_INTRO:
            btn = draw_level_intro(selected_level)
            if click_event and btn.collidepoint(mouse_pos):
                game = Game(selected_level)
                state = PLAYING
        elif state == PLAYING:
            keys = pygame.key.get_pressed()
            game.update(dt, keys)
            if space_event:
                game.handle_action()
            if click_event and game.popup:
                game.handle_popup_click(mouse_pos)
            game.draw(screen)
            if game.end_state is not None:
                state = END_SCREEN
        elif state == END_SCREEN:
            btn = draw_end_screen(game)
            if click_event and btn.collidepoint(mouse_pos):
                state = MENU
        
        pygame.display.flip()
    
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()