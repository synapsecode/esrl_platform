"""
Lemonade Ledger -- a break-even visualisation game.

The whole point is that you SEE where every dollar goes:
- Customer arrives, pays the Price.
- The coin splits at the stand: Variable Cost slides to "Suppliers"; the
  Contribution Margin slides to your "Profit Bucket".
- Meanwhile a Fixed Costs bar (Rent + Wages + Power) drains continuously.
- Profit = total CM collected - total fixed costs drained.

Three days (levels):
  Day 1 (Watch & Learn)  - price locked, see the whole income statement form.
  Day 2 (Set Your Price) - high price = fewer customers; find the sweet spot.
  Day 3 (Surprise Bill)  - midway through, fixed costs jump. Survive.
"""

import math
import random
from dataclasses import dataclass
from typing import Callable, List, Optional

import pygame

pygame.init()

WIDTH, HEIGHT = 1100, 720
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Lemonade Ledger -- Where the Money Goes")
clock = pygame.time.Clock()
FPS = 60

# Palette: warm, cozy lemonade-stand vibe.
BG = (252, 244, 219)
PANEL = (255, 252, 240)
PANEL_DARK = (240, 232, 205)
INK = (60, 50, 40)
INK_SOFT = (110, 100, 85)
LEMON = (255, 215, 75)
LEMON_DARK = (220, 175, 50)
GREEN = (90, 175, 95)
GREEN_SOFT = (200, 235, 200)
RED = (215, 85, 75)
RED_SOFT = (245, 210, 205)
ORANGE = (240, 155, 80)
ORANGE_SOFT = (250, 220, 190)
BLUE = (95, 140, 200)
SHADOW = (200, 190, 170)
WHITE = (255, 255, 255)

font_xs = pygame.font.SysFont("arial", 13)
font_sm = pygame.font.SysFont("arial", 16)
font_md = pygame.font.SysFont("arial", 20, bold=True)
font_lg = pygame.font.SysFont("arial", 28, bold=True)
font_xl = pygame.font.SysFont("arial", 44, bold=True)


# ----------------------------- helpers ------------------------------------

def draw_text(surf, text, font, color, x, y, *, center=False, right=False):
    img = font.render(text, True, color)
    rect = img.get_rect()
    if center:
        rect.center = (x, y)
    elif right:
        rect.topright = (x, y)
    else:
        rect.topleft = (x, y)
    surf.blit(img, rect)


def panel(surf, x, y, w, h, fill=PANEL, border=INK_SOFT, radius=10, border_w=2):
    pygame.draw.rect(surf, SHADOW, (x + 3, y + 3, w, h), border_radius=radius)
    pygame.draw.rect(surf, fill, (x, y, w, h), border_radius=radius)
    pygame.draw.rect(surf, border, (x, y, w, h), border_w, border_radius=radius)


# ----------------------------- entities -----------------------------------

CUSTOMER_COLORS = [
    (220, 130, 140), (130, 175, 220), (160, 200, 130),
    (210, 165, 110), (180, 145, 215), (235, 175, 110),
]


@dataclass
class Customer:
    x: float
    y: float
    target_x: float
    color: tuple
    speed: float = 70.0           # px/sec walking in
    state: str = "approaching"    # approaching | paying | leaving
    pay_timer: float = 0.0
    on_pay: Optional[Callable] = None

    def update(self, dt):
        if self.state == "approaching":
            self.x += self.speed * dt
            if self.x >= self.target_x:
                self.x = self.target_x
                self.state = "paying"
                self.pay_timer = 0.35
        elif self.state == "paying":
            self.pay_timer -= dt
            if self.pay_timer <= 0:
                if self.on_pay:
                    self.on_pay(self)
                self.state = "leaving"
        else:
            self.x += (self.speed * 1.6) * dt

    def alive(self):
        return self.x < WIDTH + 40

    def draw(self, surf):
        pygame.draw.circle(surf, self.color, (int(self.x), int(self.y)), 11)
        pygame.draw.circle(surf, INK, (int(self.x), int(self.y)), 11, 1)
        pygame.draw.circle(surf, (245, 215, 180), (int(self.x), int(self.y - 14)), 7)
        pygame.draw.circle(surf, INK, (int(self.x), int(self.y - 14)), 7, 1)
        leg_y = int(self.y + 9)
        pygame.draw.line(surf, INK, (int(self.x - 4), leg_y), (int(self.x - 4), leg_y + 8), 2)
        pygame.draw.line(surf, INK, (int(self.x + 4), leg_y), (int(self.x + 4), leg_y + 8), 2)


@dataclass
class FlowCoin:
    """A labeled coin that animates from (x,y) to (tx,ty) on an eased arc."""
    x: float
    y: float
    tx: float
    ty: float
    label: str
    color: tuple
    duration: float = 0.9
    arc_height: float = 60.0
    elapsed: float = 0.0
    on_arrive: Optional[Callable] = None
    arrived: bool = False
    radius: int = 14
    cur_x: float = 0.0
    cur_y: float = 0.0

    def __post_init__(self):
        self.cur_x = self.x
        self.cur_y = self.y

    def update(self, dt):
        if self.arrived:
            return
        self.elapsed += dt
        t = min(1.0, self.elapsed / self.duration)
        e = 1 - (1 - t) ** 2  # ease-out
        self.cur_x = self.x + (self.tx - self.x) * e
        self.cur_y = self.y + (self.ty - self.y) * e - self.arc_height * math.sin(math.pi * t)
        if t >= 1.0:
            self.arrived = True
            if self.on_arrive:
                self.on_arrive()

    def draw(self, surf):
        if self.arrived:
            return
        cx, cy = int(self.cur_x), int(self.cur_y)
        pygame.draw.circle(surf, self.color, (cx, cy), self.radius)
        pygame.draw.circle(surf, INK, (cx, cy), self.radius, 2)
        draw_text(surf, self.label, font_xs, INK, cx, cy, center=True)


@dataclass
class DrainParticle:
    """A small red coin escaping the fixed-costs bar (one of: Rent/Wages/Power)."""
    x: float
    y: float
    vy: float
    vx: float
    label: str
    life: float = 1.6
    age: float = 0.0

    def update(self, dt):
        self.age += dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vy += 80 * dt

    def alive(self):
        return self.age < self.life

    def draw(self, surf):
        r = max(3, int(8 * (1 - self.age / self.life * 0.5)))
        pygame.draw.circle(surf, RED, (int(self.x), int(self.y)), r)
        if self.age / self.life < 0.6:
            draw_text(surf, self.label, font_xs, INK, int(self.x), int(self.y - 14), center=True)


@dataclass
class Pulse:
    """A short coloured flash anchored to a rect, used to highlight events."""
    rect: pygame.Rect
    color: tuple
    life: float = 0.5
    age: float = 0.0

    def update(self, dt):
        self.age += dt

    def alive(self):
        return self.age < self.life

    def draw(self, surf):
        alpha = max(0, 1 - self.age / self.life)
        s = pygame.Surface((self.rect.w, self.rect.h), pygame.SRCALPHA)
        s.fill((self.color[0], self.color[1], self.color[2], int(120 * alpha)))
        surf.blit(s, (self.rect.x, self.rect.y))


# ----------------------------- regions ------------------------------------

STAND = pygame.Rect(WIDTH // 2 - 70, 230, 140, 130)
QUEUE_Y = STAND.centery
SUPPLIERS = pygame.Rect(70, 430, 230, 160)
PROFIT_BUCKET = pygame.Rect(WIDTH - 300, 430, 230, 200)
FIXED_BAR = pygame.Rect(340, 470, 420, 50)
PRICE_PANEL = pygame.Rect(340, 555, 420, 110)


FIXED_LINE_ITEMS = [
    ("Rent", 0.45),
    ("Wages", 0.40),
    ("Power", 0.15),
]


# ----------------------------- the game -----------------------------------

class Game:
    def __init__(self):
        self.state = "menu"
        self.day = 1
        self._reset_day()

    def _reset_day(self):
        if self.day == 1:
            self.price = 5
            self.vc = 2
            # Day 1 is a 15s tutorial; scale the fixed-cost budget down so the
            # drain rate per second feels the same as Days 2 and 3.
            self.duration = 15.0
            self.fixed_total_target = 8
            self.fixed_per_sec = self.fixed_total_target / self.duration
            self.profit_target = 0
            self.price_locked = True
        elif self.day == 2:
            self.price = 5
            self.vc = 2
            self.duration = 30.0
            self.fixed_total_target = 25      # was 50 over 60s; same drain rate
            self.fixed_per_sec = self.fixed_total_target / self.duration
            self.profit_target = 10           # was 20; scaled to match
            self.price_locked = False
        else:  # day 3
            self.price = 6
            self.vc = 3
            self.duration = 30.0
            self.fixed_total_target = 30      # was 60 over 60s; same drain rate
            self.fixed_per_sec = self.fixed_total_target / self.duration
            self.profit_target = 15           # was 30; scaled to match
            self.price_locked = False
            self.shock_at = 15.0              # halfway through, like before
            self.shock_warn_at = 13.0
            self.shock_amount = 12            # was 25 on $60; scaled
            self.shock_announced = False

        self.time_left = self.duration
        self.elapsed = 0.0
        self.customers: List[Customer] = []
        self.coins: List[FlowCoin] = []
        self.drains: List[DrainParticle] = []
        self.pulses: List[Pulse] = []
        self.spawn_timer = 0.0
        self.drain_timer = 0.0

        self.cust_count = 0
        self.revenue = 0.0
        self.var_cost = 0.0
        self.cm_total = 0.0
        self.fixed_drained = 0.0

        self.crossed_be_once = False
        self.flash_break_even = 0.0
        self.shock_text = ""
        self.shock_timer = 0.0
        self.lock_nag_timer = 0.0  # flashes when player tries to change locked price

    @property
    def cm(self):
        return max(0, self.price - self.vc)

    @property
    def profit(self):
        return self.cm_total - self.fixed_drained

    def customer_interval(self):
        """Higher price -> slower arrivals."""
        base = 0.6 + max(0, (self.price - 3)) * 0.45
        return max(0.5, base)

    def _spawn_customer(self):
        c = Customer(
            x=-30,
            y=QUEUE_Y,
            target_x=STAND.left - 18,
            color=random.choice(CUSTOMER_COLORS),
            on_pay=self._on_customer_pays,
        )
        self.customers.append(c)

    def _on_customer_pays(self, c: Customer):
        self.cust_count += 1
        self.revenue += self.price
        sx, sy = STAND.centerx, STAND.centery - 10
        # price coin (yellow) flies from customer to stand for visual context
        self.coins.append(FlowCoin(
            x=c.x + 5, y=c.y - 10,
            tx=sx, ty=sy + 10,
            label=f"${self.price}",
            color=LEMON,
            duration=0.55,
            arc_height=30,
            radius=12,
        ))
        # variable cost coin (orange) -> Suppliers
        if self.vc > 0:
            vc_amt = self.vc

            def add_vc(_amt=vc_amt):
                self.var_cost += _amt
                self.pulses.append(Pulse(SUPPLIERS.copy(), ORANGE))

            self.coins.append(FlowCoin(
                x=sx, y=sy,
                tx=SUPPLIERS.centerx, ty=SUPPLIERS.top + 30,
                label=f"-${vc_amt}",
                color=ORANGE,
                duration=0.85,
                on_arrive=add_vc,
            ))
        # contribution margin coin (green) -> Profit Bucket
        cm_amt = self.cm
        if cm_amt > 0:
            def add_cm(_amt=cm_amt):
                prev = self.profit
                self.cm_total += _amt
                self.pulses.append(Pulse(PROFIT_BUCKET.copy(), GREEN))
                if not self.crossed_be_once and prev < 0 <= self.profit:
                    self.crossed_be_once = True
                    self.flash_break_even = 1.6

            self.coins.append(FlowCoin(
                x=sx, y=sy,
                tx=PROFIT_BUCKET.centerx, ty=PROFIT_BUCKET.top + 40,
                label=f"+${cm_amt}",
                color=GREEN,
                duration=0.9,
                on_arrive=add_cm,
            ))

    def _emit_drain(self):
        r = random.random()
        cum = 0.0
        label = "Rent"
        for name, share in FIXED_LINE_ITEMS:
            cum += share
            if r <= cum:
                label = name
                break
        x = random.uniform(FIXED_BAR.left + 20, FIXED_BAR.right - 20)
        y = FIXED_BAR.bottom - 4
        self.drains.append(DrainParticle(
            x=x, y=y,
            vy=60 + random.uniform(-10, 20),
            vx=random.uniform(-30, 30),
            label=label,
        ))

    def update(self, dt):
        if self.state != "playing":
            return

        self.time_left = max(0.0, self.time_left - dt)
        self.elapsed += dt

        # spawn customers
        self.spawn_timer -= dt
        if self.spawn_timer <= 0:
            if self.cm > 0:
                self._spawn_customer()
            self.spawn_timer = self.customer_interval()

        # continuous fixed cost drain
        drain = min(self.fixed_per_sec * dt,
                    max(0.0, self.fixed_total_target - self.fixed_drained))
        self.fixed_drained += drain

        # drain particles every ~0.65s while there's fixed cost left
        self.drain_timer -= dt
        if self.drain_timer <= 0 and self.fixed_drained < self.fixed_total_target:
            self._emit_drain()
            self.drain_timer = 0.65

        # day-3 shock
        if self.day == 3:
            t_in = self.elapsed
            if not self.shock_announced:
                if t_in >= self.shock_warn_at and t_in < self.shock_at:
                    sec_left = max(0, int(self.shock_at - t_in) + 1)
                    self.shock_text = f"WARNING: Bill arriving in {sec_left}s..."
                    self.shock_timer = max(self.shock_timer, 1.2)
                if t_in >= self.shock_at:
                    self.shock_announced = True
                    remaining_time = max(1.0, self.duration - t_in)
                    self.fixed_total_target += self.shock_amount
                    self.fixed_per_sec += self.shock_amount / remaining_time
                    self.shock_text = f"BILL: Equipment repair! +${self.shock_amount} fixed cost"
                    self.shock_timer = 3.0
                    self.pulses.append(Pulse(FIXED_BAR.copy(), RED))

        if self.shock_timer > 0:
            self.shock_timer -= dt

        if self.flash_break_even > 0:
            self.flash_break_even -= dt
        if self.lock_nag_timer > 0:
            self.lock_nag_timer -= dt

        # update entities
        for c in self.customers:
            c.update(dt)
        self.customers = [c for c in self.customers if c.alive()]
        for fc in self.coins:
            fc.update(dt)
        self.coins = [fc for fc in self.coins if not fc.arrived]
        for d in self.drains:
            d.update(dt)
        self.drains = [d for d in self.drains if d.alive()]
        for p in self.pulses:
            p.update(dt)
        self.pulses = [p for p in self.pulses if p.alive()]

        # end of day -- only resolve once all coin animations have landed so
        # the final ledger isn't off by one
        if self.time_left <= 0 and not self.coins:
            self.state = "win" if self.profit >= self.profit_target else "lose"

    # --------- input ---------
    def handle_key(self, key):
        if self.state == "menu":
            if key == pygame.K_SPACE:
                self.day = 1
                self._reset_day()
                self.state = "playing"
            elif key == pygame.K_i:
                self.state = "instructions"
            elif key == pygame.K_ESCAPE:
                pygame.event.post(pygame.event.Event(pygame.QUIT))
        elif self.state == "instructions":
            if key in (pygame.K_SPACE, pygame.K_ESCAPE, pygame.K_RETURN):
                self.state = "menu"
        elif self.state == "playing":
            if key in (pygame.K_UP, pygame.K_w, pygame.K_DOWN, pygame.K_s):
                if self.price_locked:
                    self.lock_nag_timer = 1.4
                elif key in (pygame.K_UP, pygame.K_w):
                    self.price = min(15, self.price + 1)
                else:
                    self.price = max(self.vc, self.price - 1)
            if key == pygame.K_r:
                self._reset_day()
            elif key == pygame.K_ESCAPE:
                self.state = "menu"
        elif self.state in ("win", "lose"):
            if key == pygame.K_SPACE:
                if self.state == "win" and self.day < 3:
                    self.day += 1
                    self._reset_day()
                    self.state = "playing"
                elif self.state == "win" and self.day == 3:
                    self.state = "finished"
                else:
                    self._reset_day()
                    self.state = "playing"
            elif key == pygame.K_r:
                self._reset_day()
                self.state = "playing"
            elif key == pygame.K_ESCAPE:
                self.state = "menu"
        elif self.state == "finished":
            if key in (pygame.K_SPACE, pygame.K_ESCAPE, pygame.K_RETURN):
                self.day = 1
                self._reset_day()
                self.state = "menu"

    # --------- drawing widgets ---------

    def _draw_stand(self):
        panel(screen, STAND.x, STAND.y, STAND.w, STAND.h, fill=LEMON)
        pygame.draw.rect(screen, LEMON_DARK, STAND.inflate(-12, -12).move(0, 8), border_radius=8)
        for i in range(7):
            cx = STAND.left + 10 + i * 20
            pygame.draw.polygon(screen, RED, [(cx, STAND.top - 5),
                                              (cx + 20, STAND.top - 5),
                                              (cx + 10, STAND.top + 12)])
        draw_text(screen, "LEMONADE", font_md, INK, STAND.centerx, STAND.top + 38, center=True)
        draw_text(screen, f"${self.price}", font_lg, INK, STAND.centerx, STAND.top + 75, center=True)
        pygame.draw.ellipse(screen, LEMON, (STAND.centerx - 14, STAND.bottom - 30, 28, 22))
        pygame.draw.ellipse(screen, INK, (STAND.centerx - 14, STAND.bottom - 30, 28, 22), 1)

    def _draw_suppliers(self):
        panel(screen, SUPPLIERS.x, SUPPLIERS.y, SUPPLIERS.w, SUPPLIERS.h, fill=ORANGE_SOFT)
        draw_text(screen, "VARIABLE COSTS", font_md, INK,
                  SUPPLIERS.centerx, SUPPLIERS.top + 18, center=True)
        draw_text(screen, "(Lemons, Sugar, Cups)", font_xs, INK_SOFT,
                  SUPPLIERS.centerx, SUPPLIERS.top + 38, center=True)
        draw_text(screen, f"-${int(self.var_cost)}", font_xl, ORANGE,
                  SUPPLIERS.centerx, SUPPLIERS.top + 90, center=True)
        draw_text(screen, f"${self.vc} per cup", font_sm, INK_SOFT,
                  SUPPLIERS.centerx, SUPPLIERS.bottom - 22, center=True)

    def _draw_profit_bucket(self):
        panel(screen, PROFIT_BUCKET.x, PROFIT_BUCKET.y,
              PROFIT_BUCKET.w, PROFIT_BUCKET.h, fill=GREEN_SOFT)
        draw_text(screen, "PROFIT BUCKET", font_md, INK,
                  PROFIT_BUCKET.centerx, PROFIT_BUCKET.top + 18, center=True)
        draw_text(screen, "Contribution Margin per cup", font_xs, INK_SOFT,
                  PROFIT_BUCKET.centerx, PROFIT_BUCKET.top + 38, center=True)
        draw_text(screen, f"+${int(self.cm_total)}", font_xl, GREEN,
                  PROFIT_BUCKET.centerx, PROFIT_BUCKET.top + 92, center=True)
        draw_text(screen, f"CM = ${self.price} - ${self.vc} = ${self.cm}",
                  font_sm, INK, PROFIT_BUCKET.centerx, PROFIT_BUCKET.top + 130, center=True)
        prof = self.profit
        col = GREEN if prof >= 0 else RED
        sign = "+" if prof >= 0 else "-"
        draw_text(screen, f"NET: {sign}${abs(int(round(prof)))}", font_md, col,
                  PROFIT_BUCKET.centerx, PROFIT_BUCKET.bottom - 22, center=True)

    def _draw_fixed_bar(self):
        panel(screen, FIXED_BAR.x - 6, FIXED_BAR.y - 28,
              FIXED_BAR.w + 12, FIXED_BAR.h + 60, fill=RED_SOFT)
        draw_text(screen, "FIXED COSTS (drain continuously)", font_md, INK,
                  FIXED_BAR.centerx, FIXED_BAR.y - 12, center=True)

        pygame.draw.rect(screen, PANEL_DARK, FIXED_BAR, border_radius=6)
        remaining = max(0.0, self.fixed_total_target - self.fixed_drained)
        ratio = remaining / max(1.0, self.fixed_total_target)
        fill_w = int(FIXED_BAR.w * ratio)
        if fill_w > 0:
            seg_x = FIXED_BAR.x
            for name, share in FIXED_LINE_ITEMS:
                seg_w = int(FIXED_BAR.w * share)
                visible_left = max(seg_x, FIXED_BAR.x + (FIXED_BAR.w - fill_w))
                visible_right = min(seg_x + seg_w, FIXED_BAR.right)
                if visible_right > visible_left:
                    color = {"Rent": (210, 110, 110),
                             "Wages": (220, 145, 110),
                             "Power": (180, 130, 95)}[name]
                    pygame.draw.rect(screen, color,
                                     (visible_left, FIXED_BAR.y,
                                      visible_right - visible_left, FIXED_BAR.h))
                seg_x += seg_w
        pygame.draw.rect(screen, INK, FIXED_BAR, 2, border_radius=6)

        seg_x = FIXED_BAR.x
        for name, share in FIXED_LINE_ITEMS:
            seg_w = int(FIXED_BAR.w * share)
            draw_text(screen, name, font_xs, INK,
                      seg_x + seg_w // 2, FIXED_BAR.bottom + 6, center=True)
            seg_x += seg_w
        draw_text(screen,
                  f"Drained: ${int(self.fixed_drained)} / ${int(self.fixed_total_target)}",
                  font_sm, INK, FIXED_BAR.centerx, FIXED_BAR.bottom + 24, center=True)

    def _draw_price_panel(self):
        # Tint the whole panel red briefly if the player tried to change a locked price.
        nag_active = self.price_locked and self.lock_nag_timer > 0
        fill_col = RED_SOFT if nag_active else PANEL_DARK
        panel(screen, PRICE_PANEL.x, PRICE_PANEL.y, PRICE_PANEL.w, PRICE_PANEL.h,
              fill=fill_col)
        draw_text(screen, "PRICE & DEMAND", font_md, INK,
                  PRICE_PANEL.centerx, PRICE_PANEL.top + 16, center=True)

        col = INK_SOFT if self.price_locked else INK
        draw_text(screen, f"Price: ${self.price}",
                  font_lg, col, PRICE_PANEL.x + 20, PRICE_PANEL.top + 38)
        if self.price_locked:
            # Big red LOCKED badge so it can't be missed.
            badge = pygame.Rect(PRICE_PANEL.x + 160, PRICE_PANEL.top + 40, 110, 32)
            pygame.draw.rect(screen, RED, badge, border_radius=6)
            draw_text(screen, "LOCKED", font_md, WHITE,
                      badge.centerx, badge.centery, center=True)
            hint = ("Day 1: just watch the flow. Price unlocks on Day 2."
                    if not nag_active else
                    "Price is LOCKED on Day 1 -- finish the day to unlock!")
            hint_col = RED if nag_active else INK_SOFT
            draw_text(screen, hint, font_xs, hint_col,
                      PRICE_PANEL.x + 20, PRICE_PANEL.top + 80)
        else:
            draw_text(screen, "UP / DOWN  (or W / S) to change",
                      font_xs, INK_SOFT, PRICE_PANEL.x + 20, PRICE_PANEL.top + 76)

        meter_x = PRICE_PANEL.right - 200
        meter_y = PRICE_PANEL.top + 50
        meter_w = 170
        meter_h = 16
        pygame.draw.rect(screen, PANEL, (meter_x, meter_y, meter_w, meter_h), border_radius=6)
        pygame.draw.rect(screen, INK, (meter_x, meter_y, meter_w, meter_h), 2, border_radius=6)
        demand = max(0.0, min(1.0, 1.0 - (self.price - 3) * 0.12))
        fill_w = int((meter_w - 4) * demand)
        if fill_w > 0:
            bar_col = GREEN if demand > 0.5 else (240, 200, 90) if demand > 0.25 else RED
            pygame.draw.rect(screen, bar_col,
                             (meter_x + 2, meter_y + 2, fill_w, meter_h - 4), border_radius=4)
        draw_text(screen, "Customer Demand", font_xs, INK_SOFT, meter_x, meter_y - 16)
        label = "few" if demand < 0.4 else ("ok" if demand < 0.7 else "lots")
        draw_text(screen, label, font_xs, INK_SOFT,
                  meter_x + meter_w - 4, meter_y + meter_h + 4, right=True)

    def _draw_hud(self):
        pygame.draw.rect(screen, PANEL, (0, 0, WIDTH, 56))
        pygame.draw.line(screen, INK_SOFT, (0, 56), (WIDTH, 56), 2)
        draw_text(screen, "LEMONADE LEDGER", font_md, INK, 16, 16)
        draw_text(screen, f"Day {self.day} / 3", font_md, INK_SOFT, 220, 16)
        time_col = RED if self.time_left < 10 else INK
        draw_text(screen, f"{int(self.time_left)}s left", font_md, time_col, 340, 16)
        draw_text(screen, f"Cups sold: {self.cust_count}", font_md, INK, 460, 16)
        draw_text(screen, f"Goal: profit >= ${self.profit_target}", font_md, BLUE, 640, 16)
        draw_text(screen, "ESC menu  |  R restart day", font_xs, INK_SOFT,
                  WIDTH - 16, 22, right=True)

        # mini income statement, top-right
        ix, iy = WIDTH - 250, 64
        panel(screen, ix - 4, iy - 4, 246, 110, fill=PANEL_DARK)
        draw_text(screen, "Live income statement", font_xs, INK_SOFT, ix + 8, iy + 4)
        rows = [
            ("Revenue",         f"+${int(self.revenue)}",      GREEN),
            ("- Variable Cost", f"-${int(self.var_cost)}",     ORANGE),
            ("= Contribution",  f"${int(self.cm_total)}",      INK),
            ("- Fixed Cost",    f"-${int(self.fixed_drained)}", RED),
        ]
        y = iy + 20
        for name, val, color in rows:
            draw_text(screen, name, font_xs, INK, ix + 10, y)
            draw_text(screen, val, font_xs, color, ix + 230, y, right=True)
            y += 14
        prof = self.profit
        col = GREEN if prof >= 0 else RED
        draw_text(screen, "= PROFIT", font_sm, INK, ix + 10, y + 2)
        sign = "" if prof >= 0 else "-"
        draw_text(screen, f"{sign}${abs(int(round(prof)))}", font_sm, col,
                  ix + 230, y + 2, right=True)

    def _draw_arrows_and_labels(self):
        # arrow over the customer lane
        pygame.draw.line(screen, INK_SOFT, (60, QUEUE_Y - 28), (STAND.left - 24, QUEUE_Y - 28), 2)
        pygame.draw.polygon(screen, INK_SOFT,
                            [(STAND.left - 24, QUEUE_Y - 28),
                             (STAND.left - 32, QUEUE_Y - 33),
                             (STAND.left - 32, QUEUE_Y - 23)])
        draw_text(screen, "Customers walk in", font_xs, INK_SOFT, 70, QUEUE_Y - 50)

        # split arrows from stand
        sx, sy = STAND.centerx, STAND.bottom + 4
        pygame.draw.line(screen, ORANGE, (sx - 6, sy),
                         (SUPPLIERS.centerx + 30, SUPPLIERS.top - 6), 3)
        pygame.draw.line(screen, GREEN, (sx + 6, sy),
                         (PROFIT_BUCKET.centerx - 30, PROFIT_BUCKET.top - 6), 3)
        draw_text(screen, "VC out", font_xs, ORANGE, sx - 90, sy + 30)
        draw_text(screen, "CM in", font_xs, GREEN, sx + 50, sy + 30)

    # --------- screen states ---------
    def draw_menu(self):
        screen.fill(BG)
        draw_text(screen, "LEMONADE LEDGER", font_xl, INK, WIDTH // 2, 160, center=True)
        draw_text(screen, "See where every dollar goes.", font_md, INK_SOFT,
                  WIDTH // 2, 215, center=True)
        rect = pygame.Rect(WIDTH // 2 - 90, 270, 180, 130)
        panel(screen, rect.x, rect.y, rect.w, rect.h, fill=LEMON)
        for i in range(9):
            cx = rect.left + 10 + i * 20
            pygame.draw.polygon(screen, RED, [(cx, rect.top - 5),
                                              (cx + 20, rect.top - 5),
                                              (cx + 10, rect.top + 12)])
        draw_text(screen, "LEMONADE", font_md, INK, rect.centerx, rect.centery - 4, center=True)
        draw_text(screen, "Press SPACE to start", font_md, GREEN,
                  WIDTH // 2, 460, center=True)
        draw_text(screen, "Press I for instructions", font_sm, INK_SOFT,
                  WIDTH // 2, 495, center=True)
        draw_text(screen, "Press ESC to quit", font_xs, INK_SOFT,
                  WIDTH // 2, 525, center=True)

    def draw_instructions(self):
        screen.fill(BG)
        draw_text(screen, "HOW TO PLAY", font_xl, INK, WIDTH // 2, 60, center=True)
        lines = [
            "You run a lemonade stand. Watch every dollar's journey:",
            "",
            "  1. A customer walks up and pays the PRICE (yellow coin).",
            "  2. The price splits at the stand:",
            "       - VARIABLE COST (orange) goes to Suppliers (lemons, sugar, cups).",
            "       - CONTRIBUTION MARGIN (green) goes into your Profit Bucket.",
            "  3. FIXED COSTS (rent, wages, power) drain continuously, regardless of sales.",
            "",
            "  PROFIT = total Contribution Margin   -   total Fixed Costs",
            "  BREAK-EVEN is the moment Profit first reaches $0.",
            "",
            "Day 1: price is locked. Just watch the flow.",
            "Day 2: set the price. Higher price = bigger CM, but fewer customers.",
            "Day 3: a surprise bill hits mid-day. Build a buffer above break-even.",
            "",
            "Controls:  UP/DOWN (or W/S) to change price  |  R restart  |  ESC menu",
            "",
            "Press SPACE or ESC to return.",
        ]
        y = 130
        for line in lines:
            draw_text(screen, line, font_sm, INK, 90, y)
            y += 24

    def draw_playing(self):
        screen.fill(BG)
        # subtle profit-tinted background
        if self.profit > 0:
            tint = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            alpha = min(50, int(self.profit * 1.5))
            tint.fill((GREEN_SOFT[0], GREEN_SOFT[1], GREEN_SOFT[2], alpha))
            screen.blit(tint, (0, 0))
        elif self.profit < -5:
            tint = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            alpha = min(50, int(-self.profit * 1.2))
            tint.fill((RED_SOFT[0], RED_SOFT[1], RED_SOFT[2], alpha))
            screen.blit(tint, (0, 0))

        self._draw_hud()
        # dotted ground line under the customer lane
        for x in range(0, WIDTH, 18):
            pygame.draw.line(screen, SHADOW, (x, QUEUE_Y + 22), (x + 8, QUEUE_Y + 22), 2)
        self._draw_arrows_and_labels()
        self._draw_stand()
        self._draw_suppliers()
        self._draw_profit_bucket()
        self._draw_fixed_bar()
        self._draw_price_panel()

        for c in self.customers:
            c.draw(screen)
        for d in self.drains:
            d.draw(screen)
        for fc in self.coins:
            fc.draw(screen)
        for p in self.pulses:
            p.draw(screen)

        if self.flash_break_even > 0:
            t = self.flash_break_even / 1.6
            scale = 1.0 + 0.2 * (1 - t)
            txt = "BROKE EVEN!  Every $ from here is profit."
            img = font_lg.render(txt, True, GREEN)
            img = pygame.transform.rotozoom(img, 0, scale)
            rect = img.get_rect(center=(WIDTH // 2, 130))
            screen.blit(img, rect)

        if self.shock_text and self.shock_timer > 0:
            banner = pygame.Rect(WIDTH // 2 - 260, 70, 520, 44)
            pygame.draw.rect(screen, RED, banner, border_radius=8)
            draw_text(screen, self.shock_text, font_md, WHITE,
                      banner.centerx, banner.centery, center=True)

    def draw_end(self, won):
        self.draw_playing()
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        screen.blit(overlay, (0, 0))
        title = "DAY COMPLETE!" if won else "DAY OVER"
        col = GREEN if won else RED
        draw_text(screen, title, font_xl, col, WIDTH // 2, 130, center=True)

        bx = WIDTH // 2 - 240
        by = 200
        panel(screen, bx, by, 480, 280, fill=PANEL)
        draw_text(screen, f"Day {self.day} -- the books", font_md, INK,
                  WIDTH // 2, by + 22, center=True)

        rows = [
            ("Revenue",
             f"{self.cust_count} cups x ${self.price} = ${int(self.revenue)}", GREEN),
            ("- Variable Cost",
             f"{self.cust_count} cups x ${self.vc} = -${int(self.var_cost)}", ORANGE),
            ("= Contribution", f"${int(self.cm_total)}", INK),
            ("- Fixed Cost", f"-${int(self.fixed_drained)}", RED),
        ]
        y = by + 60
        for name, val, color in rows:
            draw_text(screen, name, font_sm, INK, bx + 24, y)
            draw_text(screen, val, font_sm, color, bx + 460, y, right=True)
            y += 28
        pygame.draw.line(screen, INK, (bx + 24, y + 4), (bx + 460, y + 4), 2)
        prof = int(round(self.profit))
        sign = "" if prof >= 0 else "-"
        draw_text(screen, "= PROFIT", font_md, INK, bx + 24, y + 16)
        col2 = GREEN if prof >= 0 else RED
        draw_text(screen, f"{sign}${abs(prof)}", font_md, col2, bx + 460, y + 16, right=True)
        draw_text(screen, f"(needed >= ${self.profit_target})", font_xs, INK_SOFT,
                  bx + 460, y + 44, right=True)

        if won:
            if self.day < 3:
                draw_text(screen, "SPACE -> next day    R -> replay this day",
                          font_md, INK, WIDTH // 2, HEIGHT - 80, center=True)
            else:
                draw_text(screen, "SPACE -> finale", font_md, INK,
                          WIDTH // 2, HEIGHT - 80, center=True)
        else:
            draw_text(screen, "SPACE or R -> try again", font_md, INK,
                      WIDTH // 2, HEIGHT - 80, center=True)

    def draw_finished(self):
        screen.fill(BG)
        draw_text(screen, "YOU MADE IT!", font_xl, GREEN, WIDTH // 2, 200, center=True)
        draw_text(screen, "You can read an income statement now.",
                  font_md, INK, WIDTH // 2, 270, center=True)
        bullets = [
            "  PROFIT = (Price - Variable Cost) x Volume - Fixed Cost",
            "  Break-even = where total CM finally covers Fixed Cost.",
            "  Margin of safety = the green buffer above break-even.",
        ]
        y = 330
        for b in bullets:
            draw_text(screen, b, font_md, INK, WIDTH // 2, y, center=True)
            y += 38
        draw_text(screen, "Press SPACE to return to the menu", font_sm, INK_SOFT,
                  WIDTH // 2, HEIGHT - 80, center=True)


# ----------------------------- main loop ----------------------------------

def main():
    game = Game()
    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                game.handle_key(event.key)
        game.update(dt)

        if game.state == "menu":
            game.draw_menu()
        elif game.state == "instructions":
            game.draw_instructions()
        elif game.state == "playing":
            game.draw_playing()
        elif game.state == "win":
            game.draw_end(True)
        elif game.state == "lose":
            game.draw_end(False)
        elif game.state == "finished":
            game.draw_finished()

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
