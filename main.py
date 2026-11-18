"""
ARCADE LAB - one program, one menu, four classic-style games
ENGR-126 Project 20a (Vibe Coding with AI, VCU College of Engineering)

  1. Viper Bite   - a snake game
  2. Brick Fall   - a falling-blocks game
  3. Chomp Maze   - a maze-chase game with four ghosts
  4. Paddle Duel  - a paddle-and-ball game

HOW TO RUN (PyCharm)
  pip install pygame          (once, in PyCharm's terminal)
  then run this file.

HOW TO PUBLISH ON THE WEB (pygbag)
  Put a copy of this file in its own folder, named main.py, then:
  pip install pygbag
  pygbag --build arcade_web     (arcade_web = that folder)
  The finished web page is in arcade_web/build/web.

CONTROLS EVERYWHERE
  Esc = back to the menu (quits from the menu on a laptop)
  P   = pause          M = sound on / off

The file is organized in sections, in this order:
  SECTION 1  shared settings, colors and helpers
  SECTION 2  shared parts: sounds, high scores, effects, game base class
  SECTION 3  game 1: Viper Bite
  SECTION 4  game 2: Brick Fall
  SECTION 5  game 3: Chomp Maze
  SECTION 6  game 4: Paddle Duel
  SECTION 7  player classes (the keys each game listens to)
  SECTION 8  the menu
  SECTION 9  the app and the main loop (async, so it also runs on the web)

Each game's settings are at the top of its section and use a prefix
(SN_, TE_, PM_, PO_) so names never clash.

NOTE: keep this file plain ASCII. Write special symbols in on-screen text
as codes like "\\u2190" (an arrow), or the web build on Windows can fail.
"""

import asyncio
import json
import math
import os
import random
import sys
from array import array

import pygame

# On the web (pygbag) Python runs inside the browser and sys.platform says so.
IS_WEB = sys.platform == "emscripten"
if IS_WEB:
    import platform  # pygbag's bridge to the browser (window, localStorage)


# =============================================================================
# SECTION 1 - SHARED SETTINGS, COLORS AND HELPERS
# =============================================================================

WINDOW_SCALE = 0          # 0 = fit the screen automatically; or a size such as 0.8
CANVAS_W, CANVAS_H = 960, 740   # everything is drawn on this surface, then scaled
FPS = 60
SOUND_VOLUME = 0.5        # 0.0 to 1.0
SCORE_FILE = "arcade_lab_scores.json"
TOP_BAR = 36              # height of the title bar above a game
BOTTOM_BAR = 28           # height of the help line below a game

BG = (10, 10, 22)
PANEL = (26, 26, 48)
PANEL_LIGHT = (44, 44, 78)
WHITE = (240, 240, 245)
GREY = (140, 140, 160)
DARK_GREY = (70, 70, 90)
ACCENT = (90, 220, 255)
GOLD = (255, 205, 60)
RED = (240, 70, 70)
GREEN = (90, 220, 110)

START_KEYS = (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER)

_font_cache = {}


def font(size):
    """Return the default pygame font at this size (cached, works on the web too)."""
    if size not in _font_cache:
        _font_cache[size] = pygame.font.Font(None, size)
    return _font_cache[size]


def draw_text(surf, text, size, color, pos, anchor="center"):
    """Draw text with one point of its box (center, midleft, topright...) at pos."""
    img = font(size).render(str(text), True, color)
    rect = img.get_rect()
    setattr(rect, anchor, (int(pos[0]), int(pos[1])))
    surf.blit(img, rect)
    return rect


def lighten(color, amount):
    return tuple(min(255, int(c + amount)) for c in color)


def darken(color, factor):
    return tuple(max(0, int(c * factor)) for c in color)


def mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def clamp(value, low, high):
    return max(low, min(high, value))


def irect(x, y, w, h):
    """A pygame.Rect from float numbers."""
    return pygame.Rect(int(round(x)), int(round(y)), int(round(w)), int(round(h)))


def shade_overlay(surf, alpha=170):
    """Darken a whole surface (used behind start / pause / game-over text)."""
    veil = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    veil.fill((0, 0, 0, alpha))
    surf.blit(veil, (0, 0))


# =============================================================================
# SECTION 2 - SHARED PARTS: SOUNDS, HIGH SCORES, EFFECTS, GAME BASE CLASS
# =============================================================================

# Every sound is a list of notes: (start frequency, end frequency, seconds).
# A frequency of 0 means silence. Waves: square, triangle, sine, noise.
SOUND_RECIPES = {
    "menu_move": ("square", 0.25, [(660, 660, 0.04)]),
    "menu_pick": ("square", 0.30, [(523, 523, 0.06), (784, 784, 0.09)]),
    "start":     ("square", 0.30, [(392, 392, 0.06), (523, 523, 0.06), (784, 784, 0.10)]),
    "pause":     ("triangle", 0.40, [(440, 330, 0.10)]),
    "over":      ("square", 0.30, [(392, 392, 0.12), (330, 330, 0.12), (262, 196, 0.30)]),
    "best":      ("square", 0.30, [(523, 523, 0.08), (659, 659, 0.08), (784, 784, 0.08), (1046, 1046, 0.20)]),
    # Viper Bite
    "sn_eat":    ("square", 0.30, [(600, 900, 0.07)]),
    "sn_gold":   ("square", 0.30, [(700, 700, 0.05), (900, 900, 0.05), (1200, 1200, 0.10)]),
    "sn_crash":  ("noise", 0.45, [(0, 0, 0.35)]),
    # Brick Fall
    "te_move":   ("square", 0.12, [(220, 220, 0.02)]),
    "te_rotate": ("square", 0.18, [(440, 520, 0.04)]),
    "te_lock":   ("triangle", 0.45, [(150, 90, 0.07)]),
    "te_drop":   ("noise", 0.30, [(0, 0, 0.08)]),
    "te_clear":  ("square", 0.28, [(523, 1046, 0.18)]),
    "te_four":   ("square", 0.28, [(523, 523, 0.07), (659, 659, 0.07), (784, 784, 0.07), (1046, 1318, 0.18)]),
    "te_level":  ("triangle", 0.45, [(392, 392, 0.08), (523, 523, 0.08), (659, 659, 0.08), (784, 784, 0.15)]),
    # Chomp Maze
    "pm_waka1":  ("triangle", 0.35, [(260, 480, 0.06)]),
    "pm_waka2":  ("triangle", 0.35, [(480, 260, 0.06)]),
    "pm_power":  ("square", 0.25, [(200, 600, 0.20)]),
    "pm_ghost":  ("square", 0.25, [(1200, 300, 0.25)]),
    "pm_death":  ("square", 0.28, [(700, 120, 0.9)]),
    "pm_ready":  ("triangle", 0.40, [(523, 523, 0.10), (0, 0, 0.04), (659, 659, 0.10), (0, 0, 0.04), (784, 784, 0.18)]),
    "pm_clear":  ("triangle", 0.40, [(523, 523, 0.08), (659, 659, 0.08), (784, 784, 0.08), (1046, 1046, 0.25)]),
    # Paddle Duel
    "po_paddle": ("square", 0.30, [(480, 480, 0.04)]),
    "po_wall":   ("square", 0.22, [(300, 300, 0.035)]),
    "po_score":  ("triangle", 0.45, [(600, 200, 0.25)]),
}


class SoundBank:
    """Makes every sound in code (no sound files) and plays it if sound is on."""

    def __init__(self):
        self.enabled = True   # M toggles this, in every game
        self.ready = False
        self.sounds = {}
        self.pending = []
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(22050, -16, 1, 512)
            self.rate, size, self.channels = pygame.mixer.get_init()
            self.bits = abs(size)
            if self.bits not in (16, 32):
                raise RuntimeError("unusual sound format %s" % size)
            # Sounds are built a few at a time by build_some(), called once per frame,
            # so the first picture shows right away (slow in the browser otherwise).
            self.pending = list(SOUND_RECIPES)
            self.ready = True
        except Exception as error:   # no sound card, or a browser that blocks it
            print("Sound is off:", error)

    def build(self, name):
        wave, volume, notes = SOUND_RECIPES[name]
        self.sounds[name] = self.make(wave, volume, notes)

    def build_some(self, count=1):
        """Build the next few sounds that are not made yet."""
        if not self.ready:
            return
        try:
            while self.pending and count > 0:
                name = self.pending.pop(0)
                if name not in self.sounds:
                    self.build(name)
                count -= 1
        except Exception as error:
            print("Sound is off:", error)
            self.ready = False

    def make(self, wave, volume, notes):
        """Build one sound from notes and return a pygame Sound."""
        if self.bits == 16:
            samples = array("h")
            peak = 32000 * volume * SOUND_VOLUME
        else:
            samples = array("f")
            peak = 0.98 * volume * SOUND_VOLUME
        attack = int(self.rate * 0.004) + 1
        for f_start, f_end, seconds in notes:
            count = max(1, int(self.rate * seconds))
            phase = 0.0
            for i in range(count):
                t = i / count
                freq = f_start + (f_end - f_start) * t
                phase += freq / self.rate
                p = phase % 1.0
                if f_start == 0 and f_end == 0 and wave != "noise":
                    value = 0.0
                elif wave == "square":
                    value = 1.0 if p < 0.5 else -1.0
                elif wave == "triangle":
                    value = 4.0 * abs(p - 0.5) - 1.0
                elif wave == "noise":
                    value = random.uniform(-1.0, 1.0)
                else:
                    value = math.sin(2 * math.pi * p)
                envelope = min(1.0, i / attack) * (1.0 - t) ** 0.7
                sample = value * envelope * peak
                if self.bits == 16:
                    sample = int(sample)
                for _ in range(self.channels):
                    samples.append(sample)
        return pygame.mixer.Sound(buffer=samples.tobytes())

    def play(self, name):
        if not (self.ready and self.enabled and name in SOUND_RECIPES):
            return
        if name not in self.sounds:      # asked for before build_some() got to it
            try:
                self.build(name)
            except Exception as error:
                print("Sound is off:", error)
                self.ready = False
                return
        self.sounds[name].play()

    def toggle(self):
        self.enabled = not self.enabled
        if not self.enabled and self.ready:
            pygame.mixer.stop()
        return self.enabled


class ScoreBook:
    """One score record for all games: a JSON file, or browser storage on the web."""

    STORAGE_KEY = "arcade_lab_scores"

    def __init__(self):
        self.data = {"snake": 0, "tetris": 0, "pacman": 0, "pong_wins": 0, "pong_losses": 0}
        if not IS_WEB:
            folder = os.path.dirname(os.path.abspath(__file__))
            self.path = os.path.join(folder, SCORE_FILE)
        self.load()

    def load(self):
        try:
            if IS_WEB:
                raw = platform.window.localStorage.getItem(self.STORAGE_KEY)
            elif os.path.exists(self.path):
                with open(self.path, "r", encoding="utf-8") as f:
                    raw = f.read()
            else:
                raw = None
            if raw:
                saved = json.loads(str(raw))
                for key in self.data:
                    if isinstance(saved.get(key), int):
                        self.data[key] = saved[key]
        except Exception as error:
            print("Could not read the scores:", error)

    def save(self):
        try:
            text = json.dumps(self.data)
            if IS_WEB:
                platform.window.localStorage.setItem(self.STORAGE_KEY, text)
            else:
                with open(self.path, "w", encoding="utf-8") as f:
                    f.write(text)
        except Exception as error:
            print("Could not save the scores:", error)

    def best(self, key):
        return self.data.get(key, 0)

    def submit(self, key, score):
        """Keep the score if it beats the best one. Returns True for a new best."""
        if score > self.data.get(key, 0):
            self.data[key] = score
            self.save()
            return True
        return False

    def add(self, key, amount=1):
        self.data[key] = self.data.get(key, 0) + amount
        self.save()


class Effects:
    """Small flying dots and floating text, shared by all games."""

    def __init__(self):
        self.dots = []    # [x, y, vx, vy, color, size, life, max_life, gravity]
        self.texts = []   # [x, y, text, color, size, life, max_life]

    def clear(self):
        self.dots = []
        self.texts = []

    def dot(self, x, y, vx, vy, color, size=4, life=0.7, gravity=0.0):
        self.dots.append([x, y, vx, vy, color, size, life, life, gravity])

    def burst(self, x, y, color, count=12, speed=160, size=4, life=0.6, gravity=0.0):
        for _ in range(count):
            angle = random.uniform(0, 2 * math.pi)
            power = random.uniform(0.3, 1.0) * speed
            self.dot(x, y, math.cos(angle) * power, math.sin(angle) * power, color,
                     size, life * random.uniform(0.7, 1.2), gravity)

    def text(self, x, y, message, color=WHITE, size=26, life=0.9):
        self.texts.append([x, y, message, color, size, life, life])

    def update(self, dt):
        for d in self.dots:
            d[3] += d[8] * dt
            d[0] += d[2] * dt
            d[1] += d[3] * dt
            d[6] -= dt
        self.dots = [d for d in self.dots if d[6] > 0]
        for t in self.texts:
            t[1] -= 40 * dt
            t[5] -= dt
        self.texts = [t for t in self.texts if t[5] > 0]

    def draw(self, surf):
        for x, y, vx, vy, color, size, life, max_life, gravity in self.dots:
            s = max(1, int(size * min(1.0, life / max_life * 1.5)))
            pygame.draw.rect(surf, color, (int(x - s / 2), int(y - s / 2), s, s))
        for x, y, message, color, size, life, max_life in self.texts:
            fade = min(1.0, life / max_life * 2)
            draw_text(surf, message, size, mix(BG, color, fade), (x, y))


class GameBase:
    """What every game shares: start screen, pause, game over, effects, score.

    A game sets NAME, KEY (its name in the score file), SIZE and HELP, and
    writes reset(), step(dt), draw_game(surface) and on_key(key).
    """

    NAME = "Game"
    KEY = "game"
    SIZE = (400, 300)
    HELP = []

    def __init__(self, app):
        self.app = app
        self.surface = pygame.Surface(self.SIZE)
        self.fx = Effects()
        self.state = "start"       # start, play, pause, over
        self.score = 0
        self.new_best = False
        self.shake = 0.0
        self.clock = 0.0           # seconds since the game was opened (for blinking)
        self.reset()

    # -- things every game can use --------------------------------------------
    def sound(self, name):
        self.app.sounds.play(name)

    def best_text(self):
        return "Best %d" % self.app.scores.best(self.KEY)

    # -- the life of a game ----------------------------------------------------
    def enter(self):
        """Called when the menu opens this game."""
        self.state = "start"
        self.reset()

    def leave(self):
        """Called when Esc goes back to the menu: keep a high score even if unfinished."""
        if self.state in ("play", "pause"):
            self.record()

    def start(self):
        self.reset()
        self.state = "play"
        self.new_best = False
        self.sound("start")

    def finish(self):
        self.state = "over"
        self.record()
        self.sound("best" if self.new_best else "over")

    def record(self):
        self.new_best = self.app.scores.submit(self.KEY, self.score)

    # -- input -------------------------------------------------------------------
    def handle_key(self, key):
        if self.state == "start":
            if key in START_KEYS:
                self.start()
        elif self.state == "play":
            if key == pygame.K_p:
                self.state = "pause"
                self.sound("pause")
            else:
                self.on_key(key)
        elif self.state == "pause":
            if key == pygame.K_p or key in START_KEYS:
                self.state = "play"
        elif self.state == "over":
            if key in START_KEYS:
                self.start()

    def handle_keyup(self, key):
        self.on_keyup(key)

    def on_key(self, key):
        pass

    def on_keyup(self, key):
        pass

    # -- every frame -------------------------------------------------------------
    def update(self, dt):
        self.clock += dt
        if self.state == "pause":
            return
        if self.state == "play":
            self.step(dt)
        self.fx.update(dt)
        self.shake = max(0.0, self.shake - dt)

    def shake_offset(self):
        if self.shake <= 0:
            return 0, 0
        power = int(self.shake * 25) + 1
        return random.randint(-power, power), random.randint(-power, power)

    def draw(self):
        s = self.surface
        self.draw_game(s)
        self.fx.draw(s)
        if self.state == "start":
            self.draw_start(s)
        elif self.state == "pause":
            shade_overlay(s, 140)
            w, h = self.SIZE
            draw_text(s, "PAUSED", 72, WHITE, (w / 2, h / 2 - 20))
            draw_text(s, "Press P to continue", 28, GREY, (w / 2, h / 2 + 30))
        elif self.state == "over":
            self.draw_over(s)
        return s

    def blink_on(self, speed=2.0):
        return int(self.clock * speed) % 2 == 0

    def draw_start(self, s):
        shade_overlay(s, 175)
        w, h = self.SIZE
        draw_text(s, self.NAME, 72, ACCENT, (w / 2, h * 0.22))
        for i, line in enumerate(self.HELP):
            draw_text(s, line, 26, WHITE, (w / 2, h * 0.36 + i * 32))
        draw_text(s, self.best_text(), 30, GOLD, (w / 2, h * 0.36 + len(self.HELP) * 32 + 24))
        if self.blink_on():
            draw_text(s, "Press Enter or Space to start", 32, WHITE, (w / 2, h * 0.84))

    def over_lines(self):
        return ["Score %d" % self.score]

    def draw_over(self, s):
        shade_overlay(s, 165)
        w, h = self.SIZE
        draw_text(s, "GAME OVER", 80, RED, (w / 2, h * 0.3))
        for i, line in enumerate(self.over_lines()):
            draw_text(s, line, 38, WHITE, (w / 2, h * 0.45 + i * 40))
        if self.new_best and self.blink_on(4):
            draw_text(s, "NEW BEST!", 44, GOLD, (w / 2, h * 0.6))
        draw_text(s, "Enter: play again     Esc: menu", 28, GREY, (w / 2, h * 0.75))


# =============================================================================
# SECTION 3 - GAME 1: VIPER BITE (a snake game)
# =============================================================================

SN_CELL = 24                 # size of one square, in pixels
SN_COLS = 28                 # board width in squares
SN_ROWS = 24                 # board height in squares
SN_HUD = 40                  # score bar height
SN_START_LENGTH = 4
SN_START_SPEED = 7.0         # squares per second at the start
SN_SPEED_STEP = 0.35         # extra speed for every apple
SN_MAX_SPEED = 20            # the fastest the snake can get
SN_WRAP_WALLS = False        # True = leave one side, come back on the other
SN_TURN_QUEUE = 3            # turns remembered between two moves
SN_WAVE_SPEED = 45.0         # how fast a new color runs from head to tail (squares/s)
SN_START_COLOR = (90, 220, 110)
SN_APPLE_COLORS = [          # the apple colors (the snake takes each one)
    (240, 60, 60),           # red
    (255, 140, 30),          # orange
    (200, 240, 60),          # lime
    (60, 210, 120),          # green
    (40, 210, 235),          # cyan
    (70, 120, 255),          # blue
    (170, 90, 255),          # purple
    (255, 110, 190),         # pink
]
SN_GOLDEN_COLOR = (255, 200, 0)
SN_GOLDEN_CHANCE = 0.12      # chance that the next apple is golden
SN_GOLDEN_POINTS = 5


class SnakeGame(GameBase):
    NAME = "Viper Bite"
    KEY = "snake"
    SIZE = (SN_COLS * SN_CELL, SN_ROWS * SN_CELL + SN_HUD)
    HELP = ["Arrow keys or WASD: steer",
            "Each apple paints the snake its color",
            "Golden apple = %d points" % SN_GOLDEN_POINTS,
            "Don't hit the walls or yourself"]

    def __init__(self, app):
        self.background = self.make_background()
        super().__init__(app)

    def make_background(self):
        bg = pygame.Surface(self.SIZE)
        bg.fill((16, 18, 30))
        for y in range(SN_ROWS):
            for x in range(SN_COLS):
                color = (24, 28, 44) if (x + y) % 2 == 0 else (20, 23, 38)
                pygame.draw.rect(bg, color, (x * SN_CELL, SN_HUD + y * SN_CELL, SN_CELL, SN_CELL))
        pygame.draw.rect(bg, PANEL, (0, 0, self.SIZE[0], SN_HUD))
        return bg

    def reset(self):
        self.player = SnakePlayer()
        cx, cy = SN_COLS // 2, SN_ROWS // 2
        self.body = [(cx - i, cy) for i in range(SN_START_LENGTH)]   # head first
        self.prev = list(self.body)     # where each square was before the last move
        self.direction = (1, 0)
        self.timer = 0.0                # 0..1 progress toward the next move
        self.score = 0
        self.apples = 0
        self.color = SN_START_COLOR
        self.new_color = None           # color running down the body as a wave
        self.wave = 0.0
        self.dead = False
        self.dead_timer = 0.0
        self.fx.clear()
        self.place_apple()

    def speed(self):
        return min(SN_MAX_SPEED, SN_START_SPEED + SN_SPEED_STEP * self.apples)

    def cell_center(self, cell):
        return cell[0] * SN_CELL + SN_CELL / 2, SN_HUD + cell[1] * SN_CELL + SN_CELL / 2

    def place_apple(self):
        taken = set(self.body)
        free = [(x, y) for x in range(SN_COLS) for y in range(SN_ROWS) if (x, y) not in taken]
        if not free:            # the board is full: you won!
            self.finish()
            return
        self.apple = random.choice(free)
        self.apple_age = 0.0
        self.apple_golden = random.random() < SN_GOLDEN_CHANCE
        if self.apple_golden:
            self.apple_color = SN_GOLDEN_COLOR
        else:
            current = self.new_color or self.color
            choices = [c for c in SN_APPLE_COLORS if c != current] or SN_APPLE_COLORS
            self.apple_color = random.choice(choices)

    def on_key(self, key):
        self.player.press(key, self.direction)

    def step(self, dt):
        self.apple_age += dt
        if self.new_color is not None:
            self.wave += SN_WAVE_SPEED * dt
            if self.wave >= len(self.body):
                self.color = self.new_color
                self.new_color = None
        if self.dead:
            self.dead_timer -= dt
            if self.dead_timer <= 0:
                self.finish()
            return
        self.timer += dt * self.speed()
        while self.timer >= 1.0 and not self.dead and self.state == "play":
            self.timer -= 1.0
            self.move()

    def move(self):
        turn = self.player.next_turn()
        if turn:
            self.direction = turn
        dx, dy = self.direction
        hx, hy = self.body[0]
        nx, ny = hx + dx, hy + dy
        if SN_WRAP_WALLS:
            nx %= SN_COLS
            ny %= SN_ROWS
        elif not (0 <= nx < SN_COLS and 0 <= ny < SN_ROWS):
            self.crash()
            return
        eating = (nx, ny) == self.apple
        blockers = self.body if eating else self.body[:-1]   # the tail moves away
        if (nx, ny) in blockers:
            self.crash()
            return
        old = self.body
        self.body = [(nx, ny)] + (old if eating else old[:-1])
        self.prev = old + ([old[-1]] if eating else [])
        if eating:
            self.eat()

    def eat(self):
        x, y = self.cell_center(self.apple)
        points = SN_GOLDEN_POINTS if self.apple_golden else 1
        self.score += points
        self.apples += 1
        if self.new_color is not None:   # finish the old wave first
            self.color = self.new_color
        self.new_color = self.apple_color
        self.wave = 0.0
        self.fx.burst(x, y, self.apple_color, count=22 if self.apple_golden else 12, speed=170)
        self.fx.text(x, y - 16, "+%d" % points, self.apple_color, 30)
        self.sound("sn_gold" if self.apple_golden else "sn_eat")
        self.place_apple()

    def crash(self):
        """The snake bursts: every body square becomes a small grid of dots."""
        self.dead = True
        self.dead_timer = 1.6
        self.shake = 0.35
        self.sound("sn_crash")
        third = SN_CELL / 3
        for i, cell in enumerate(self.body):
            px, py = self.cell_center(cell)
            color = self.segment_color(i)
            for gx in range(3):
                for gy in range(3):
                    x = px - SN_CELL / 2 + (gx + 0.5) * third
                    y = py - SN_CELL / 2 + (gy + 0.5) * third
                    vx = (x - px) * random.uniform(4, 9) + random.uniform(-50, 50)
                    vy = (y - py) * random.uniform(4, 9) - random.uniform(80, 200)
                    self.fx.dot(x, y, vx, vy, color, int(third) - 1, random.uniform(1.0, 1.6), 600)

    def segment_color(self, i):
        base = self.new_color if (self.new_color is not None and i < self.wave) else self.color
        shade = 1.0 - 0.35 * i / max(1, len(self.body) - 1)   # head brighter than tail
        return darken(base, shade)

    # -- drawing -----------------------------------------------------------------
    def draw_game(self, s):
        s.blit(self.background, (0, 0))
        w = self.SIZE[0]
        draw_text(s, "Score %d" % self.score, 30, WHITE, (14, SN_HUD / 2), "midleft")
        draw_text(s, self.best_text(), 30, GOLD, (w / 2, SN_HUD / 2))
        draw_text(s, "Speed %.1f" % self.speed(), 30, GREY, (w - 14, SN_HUD / 2), "midright")
        self.draw_apple(s)
        if not self.dead:
            self.draw_snake(s)

    def draw_apple(self, s):
        x, y = self.cell_center(self.apple)
        r = SN_CELL * 0.38 + math.sin(self.apple_age * 6) * 1.5
        if self.apple_golden:
            pygame.draw.circle(s, darken(SN_GOLDEN_COLOR, 0.4), (int(x), int(y)), int(r + 5))
        pygame.draw.circle(s, self.apple_color, (int(x), int(y)), int(r))
        pygame.draw.circle(s, lighten(self.apple_color, 90), (int(x - r / 3), int(y - r / 3)), max(2, int(r / 4)))
        pygame.draw.line(s, (120, 80, 40), (int(x), int(y - r)), (int(x + 2), int(y - r - 5)), 2)
        if self.apple_golden:
            for k in range(4):
                a = self.apple_age * 3 + k * math.pi / 2
                pygame.draw.circle(s, WHITE, (int(x + math.cos(a) * (r + 8)), int(y + math.sin(a) * (r + 8))), 2)

    def draw_snake(self, s):
        # Slide every square from where it was to where it is (smooth movement).
        t = clamp(self.timer, 0.0, 1.0)
        points = []
        for i, now in enumerate(self.body):
            before = self.prev[i] if i < len(self.prev) else now
            if abs(now[0] - before[0]) + abs(now[1] - before[1]) > 1:   # wrapped around
                before = now
            fx = before[0] + (now[0] - before[0]) * t
            fy = before[1] + (now[1] - before[1]) * t
            points.append((fx * SN_CELL + SN_CELL / 2, SN_HUD + fy * SN_CELL + SN_CELL / 2))
        size = SN_CELL - 4
        radius = size // 3
        # Draw tail to head, joining each square to the next: one continuous body.
        for i in range(len(points) - 1, -1, -1):
            color = self.segment_color(i)
            x, y = points[i]
            if i > 0:
                px, py = points[i - 1]
                if abs(px - x) + abs(py - y) < SN_CELL * 1.6:
                    joint = irect(min(x, px) - size / 2, min(y, py) - size / 2,
                                  abs(x - px) + size, abs(y - py) + size)
                    pygame.draw.rect(s, color, joint, border_radius=radius)
            pygame.draw.rect(s, color, irect(x - size / 2, y - size / 2, size, size), border_radius=radius)
        # Eyes on the head, looking where the snake is going.
        hx, hy = points[0]
        dx, dy = self.direction
        for side in (-1, 1):
            ex = hx + dx * 4 - dy * side * 5
            ey = hy + dy * 4 + dx * side * 5
            pygame.draw.circle(s, WHITE, (int(ex), int(ey)), 4)
            pygame.draw.circle(s, (10, 10, 10), (int(ex + dx * 1.5), int(ey + dy * 1.5)), 2)


# =============================================================================
# SECTION 4 - GAME 2: BRICK FALL (a falling-blocks game)
# =============================================================================

TE_COLS = 10
TE_ROWS = 20
TE_CELL = 30
TE_NEXT_COUNT = 1            # upcoming pieces shown
TE_SHOW_GHOST = False        # True = show where the piece will land
TE_USE_HOLD = False          # True = C or Shift keeps a piece for later
TE_START_FALL = 0.80         # seconds per row at level 1
TE_FALL_FACTOR = 0.83        # each level falls this much faster
TE_MIN_FALL = 0.05
TE_LINES_PER_LEVEL = 10      # speed rises every 10 rows
TE_LOCK_DELAY = 0.5          # seconds a landed piece can still slide
TE_LOCK_RESETS = 15          # moves allowed while landed before it locks anyway
TE_FLASH_TIME = 0.35         # full rows flash this long before they vanish
TE_DAS = 0.16                # hold left/right this long before it repeats
TE_ARR = 0.05                # then move one square this often
TE_SOFT_DROP = 0.035         # seconds per row while Down is held
TE_LINE_POINTS = [0, 100, 300, 500, 800]   # times the level
TE_SHAPES = {                # each piece inside its own box
    "I": ["....", "XXXX", "....", "...."],
    "O": ["XX", "XX"],
    "T": [".X.", "XXX", "..."],
    "S": [".XX", "XX.", "..."],
    "Z": ["XX.", ".XX", "..."],
    "J": ["X..", "XXX", "..."],
    "L": ["..X", "XXX", "..."],
}
TE_COLORS = {"I": (60, 220, 240), "O": (250, 220, 60), "T": (180, 90, 240), "S": (90, 220, 100),
             "Z": (240, 70, 70), "J": (70, 110, 250), "L": (250, 150, 40)}
TE_KICKS = [(0, 0), (-1, 0), (1, 0), (0, -1), (-2, 0), (2, 0)]   # wall kicks to try
TE_BOARD_X, TE_BOARD_Y = 20, 20


def te_make_rotations(shape):
    """The four turns of a piece, each turned inside its box."""
    n = len(shape)
    cells = [(x, y) for y, row in enumerate(shape) for x, ch in enumerate(row) if ch == "X"]
    turns = [cells]
    for _ in range(3):
        cells = [(n - 1 - y, x) for (x, y) in cells]    # turn clockwise
        turns.append(cells)
    return turns


TE_ROTATIONS = {kind: te_make_rotations(shape) for kind, shape in TE_SHAPES.items()}


class Brick:
    """The falling piece: its kind, turn and the top-left corner of its box."""

    def __init__(self, kind):
        self.kind = kind
        self.rot = 0
        size = len(TE_SHAPES[kind])
        self.x = (TE_COLS - size) // 2
        self.y = -1 if kind == "I" else 0

    def cells(self, dx=0, dy=0, rot=None):
        r = self.rot if rot is None else rot
        return [(self.x + cx + dx, self.y + cy + dy) for cx, cy in TE_ROTATIONS[self.kind][r % 4]]


class BlockGame(GameBase):
    NAME = "Brick Fall"
    KEY = "tetris"
    SIZE = (TE_BOARD_X * 2 + TE_COLS * TE_CELL + 200, TE_BOARD_Y * 2 + TE_ROWS * TE_CELL)
    HELP = ["Left / Right: move     Up or X: turn     Z: turn back",
            "Down: soft drop     Space: hard drop" + ("     C: hold" if TE_USE_HOLD else ""),
            "Fill a row to clear it",
            "Speed rises every %d rows" % TE_LINES_PER_LEVEL]

    def reset(self):
        self.player = TetrisPlayer()
        self.board = [[None] * TE_COLS for _ in range(TE_ROWS)]
        self.bag = []
        self.queue = []
        self.fill_queue()
        self.score = 0
        self.lines = 0
        self.level = 1
        self.hold = None
        self.hold_used = False
        self.flash_rows = []
        self.flash_timer = 0.0
        self.fall_timer = 0.0
        self.lock_timer = 0.0
        self.lock_resets = 0
        self.piece = None
        self.fx.clear()
        self.spawn()

    # -- pieces ------------------------------------------------------------------
    def next_kind(self):
        """7-bag: every 7 pieces contain each kind exactly once."""
        if not self.bag:
            self.bag = list(TE_SHAPES)
            random.shuffle(self.bag)
        return self.bag.pop()

    def fill_queue(self):
        while len(self.queue) < max(1, TE_NEXT_COUNT):
            self.queue.append(self.next_kind())

    def spawn(self, kind=None):
        if kind is None:
            kind = self.queue.pop(0)
            self.fill_queue()
        self.piece = Brick(kind)
        self.fall_timer = 0.0
        self.lock_timer = 0.0
        self.lock_resets = 0
        if not self.fits(self.piece.cells()):
            self.top_out()

    def fits(self, cells):
        for x, y in cells:
            if x < 0 or x >= TE_COLS or y >= TE_ROWS:
                return False
            if y >= 0 and self.board[y][x] is not None:
                return False
        return True

    def on_ground(self):
        return self.piece is not None and not self.fits(self.piece.cells(0, 1))

    def fall_interval(self):
        return max(TE_MIN_FALL, TE_START_FALL * TE_FALL_FACTOR ** (self.level - 1))

    # -- actions (the player class calls these) ---------------------------------
    def moved(self):
        """A move or turn while landed gives a little more time (a limited number of times)."""
        if self.on_ground() and self.lock_resets < TE_LOCK_RESETS:
            self.lock_timer = 0.0
            self.lock_resets += 1

    def shift(self, dx):
        if self.piece is None or self.flash_rows:
            return False
        if self.fits(self.piece.cells(dx, 0)):
            self.piece.x += dx
            self.moved()
            self.sound("te_move")
            return True
        return False

    def rotate(self, direction):
        if self.piece is None or self.flash_rows:
            return
        new_rot = (self.piece.rot + direction) % 4
        for kx, ky in TE_KICKS:
            if self.fits(self.piece.cells(kx, ky, new_rot)):
                self.piece.x += kx
                self.piece.y += ky
                self.piece.rot = new_rot
                self.moved()
                self.sound("te_rotate")
                return

    def drop_distance(self):
        d = 0
        while self.fits(self.piece.cells(0, d + 1)):
            d += 1
        return d

    def hard_drop(self):
        if self.piece is None or self.flash_rows:
            return
        d = self.drop_distance()
        for x, y in self.piece.cells():
            px = TE_BOARD_X + x * TE_CELL + TE_CELL / 2
            for k in range(0, d, 2):   # a short trail of dots above the piece
                py = TE_BOARD_Y + (y + k) * TE_CELL + TE_CELL / 2
                if py > TE_BOARD_Y:
                    self.fx.dot(px, py, 0, -30, darken(TE_COLORS[self.piece.kind], 0.6), 3, 0.25)
        self.piece.y += d
        self.score += 2 * d
        self.shake = 0.12
        self.sound("te_drop")
        self.lock()

    def hold_piece(self):
        if not TE_USE_HOLD or self.hold_used or self.piece is None or self.flash_rows:
            return
        kind = self.piece.kind
        if self.hold is None:
            self.hold = kind
            self.spawn()
        else:
            swap = self.hold
            self.hold = kind
            self.spawn(swap)
        self.hold_used = True

    def lock(self):
        above_top = False
        for x, y in self.piece.cells():
            if y < 0:
                above_top = True
            else:
                self.board[y][x] = self.piece.kind
        self.piece = None
        self.hold_used = False
        self.sound("te_lock")
        if above_top:
            self.top_out()
            return
        full = [y for y in range(TE_ROWS) if all(self.board[y])]
        if full:
            self.flash_rows = full
            self.flash_timer = TE_FLASH_TIME
            self.sound("te_four" if len(full) == 4 else "te_clear")
            for y in full:
                for x in range(TE_COLS):
                    cx = TE_BOARD_X + x * TE_CELL + TE_CELL / 2
                    cy = TE_BOARD_Y + y * TE_CELL + TE_CELL / 2
                    self.fx.burst(cx, cy, TE_COLORS[self.board[y][x]], count=3, speed=140, life=0.6, gravity=300)
        else:
            self.spawn()

    def remove_rows(self):
        count = len(self.flash_rows)
        for y in sorted(self.flash_rows):
            del self.board[y]
            self.board.insert(0, [None] * TE_COLS)
        old_level = self.level
        self.score += TE_LINE_POINTS[count] * self.level
        self.lines += count
        self.level = self.lines // TE_LINES_PER_LEVEL + 1
        names = ["", "SINGLE", "DOUBLE", "TRIPLE", "FOUR ROWS!"]
        mid_x = TE_BOARD_X + TE_COLS * TE_CELL / 2
        mid_y = TE_BOARD_Y + sum(self.flash_rows) / count * TE_CELL
        self.fx.text(mid_x, mid_y, names[count], WHITE, 40, 1.0)
        if self.level > old_level:
            self.fx.text(mid_x, mid_y + 45, "LEVEL %d" % self.level, GOLD, 40, 1.4)
            self.sound("te_level")
        if count == 4:
            self.shake = 0.3
        self.flash_rows = []
        self.spawn()

    def top_out(self):
        self.shake = 0.3
        self.finish()

    # -- every frame -------------------------------------------------------------
    def on_key(self, key):
        self.player.press(key, self)

    def on_keyup(self, key):
        self.player.release(key)

    def step(self, dt):
        if self.flash_rows:
            self.flash_timer -= dt
            if self.flash_timer <= 0:
                self.remove_rows()
            return
        if self.piece is None:
            return
        self.player.update(dt, self)
        if self.piece is None or self.flash_rows or self.state != "play":
            return
        interval = self.fall_interval()
        if self.player.soft:
            interval = min(interval, TE_SOFT_DROP)
        self.fall_timer += dt
        while self.fall_timer >= interval:
            self.fall_timer -= interval
            if self.fits(self.piece.cells(0, 1)):
                self.piece.y += 1
                if self.player.soft:
                    self.score += 1
            else:
                self.fall_timer = 0.0
                break
        if self.on_ground():
            self.lock_timer += dt
            if self.lock_timer >= TE_LOCK_DELAY:
                self.lock()
        else:
            self.lock_timer = 0.0

    # -- drawing -----------------------------------------------------------------
    def draw_cell(self, s, px, py, size, color):
        r = pygame.Rect(int(px) + 1, int(py) + 1, size - 2, size - 2)
        pygame.draw.rect(s, color, r)
        pygame.draw.line(s, lighten(color, 70), r.topleft, r.topright, 2)
        pygame.draw.line(s, lighten(color, 70), r.topleft, r.bottomleft, 2)
        pygame.draw.line(s, darken(color, 0.55), r.bottomleft, r.bottomright, 2)
        pygame.draw.line(s, darken(color, 0.55), r.topright, r.bottomright, 2)

    def draw_mini(self, s, kind, box):
        """Draw a piece centered in a small box (next / hold)."""
        cells = TE_ROTATIONS[kind][0]
        size = 22
        xs = [c[0] for c in cells]
        ys = [c[1] for c in cells]
        w = (max(xs) - min(xs) + 1) * size
        h = (max(ys) - min(ys) + 1) * size
        ox = box.centerx - w / 2 - min(xs) * size
        oy = box.centery - h / 2 - min(ys) * size
        for cx, cy in cells:
            self.draw_cell(s, ox + cx * size, oy + cy * size, size, TE_COLORS[kind])

    def draw_game(self, s):
        s.fill(BG)
        board_rect = pygame.Rect(TE_BOARD_X, TE_BOARD_Y, TE_COLS * TE_CELL, TE_ROWS * TE_CELL)
        pygame.draw.rect(s, (18, 18, 34), board_rect)
        for x in range(1, TE_COLS):
            px = TE_BOARD_X + x * TE_CELL
            pygame.draw.line(s, (28, 28, 48), (px, TE_BOARD_Y), (px, board_rect.bottom))
        for y in range(1, TE_ROWS):
            py = TE_BOARD_Y + y * TE_CELL
            pygame.draw.line(s, (28, 28, 48), (TE_BOARD_X, py), (board_rect.right, py))
        flash_white = int(self.flash_timer * 20) % 2 == 0
        for y, row in enumerate(self.board):
            for x, kind in enumerate(row):
                if kind:
                    color = TE_COLORS[kind]
                    if y in self.flash_rows and flash_white:
                        color = WHITE
                    self.draw_cell(s, TE_BOARD_X + x * TE_CELL, TE_BOARD_Y + y * TE_CELL, TE_CELL, color)
        if self.piece is not None:
            color = TE_COLORS[self.piece.kind]
            if TE_SHOW_GHOST:
                d = self.drop_distance()
                for x, y in self.piece.cells(0, d):
                    if y >= 0:
                        r = (TE_BOARD_X + x * TE_CELL + 2, TE_BOARD_Y + y * TE_CELL + 2, TE_CELL - 4, TE_CELL - 4)
                        pygame.draw.rect(s, darken(color, 0.7), r, 2)
            for x, y in self.piece.cells():
                if y >= 0:
                    self.draw_cell(s, TE_BOARD_X + x * TE_CELL, TE_BOARD_Y + y * TE_CELL, TE_CELL, color)
        pygame.draw.rect(s, PANEL_LIGHT, board_rect.inflate(4, 4), 2)

        # Side panel
        px = board_rect.right + 25
        draw_text(s, "NEXT", 30, GREY, (px, 30), "topleft")
        y = 58
        for i, kind in enumerate(self.queue[:max(1, TE_NEXT_COUNT)]):
            box = pygame.Rect(px, y, 150, 80)
            pygame.draw.rect(s, PANEL, box, border_radius=8)
            self.draw_mini(s, kind, box)
            y += 90
        if TE_USE_HOLD:
            draw_text(s, "HOLD (C)", 30, GREY, (px, y + 6), "topleft")
            box = pygame.Rect(px, y + 34, 150, 80)
            pygame.draw.rect(s, PANEL, box, border_radius=8)
            if self.hold:
                self.draw_mini(s, self.hold, box)
            y += 124
        y = max(y + 20, 300)
        for label, value, color in (("SCORE", self.score, WHITE), ("ROWS", self.lines, WHITE),
                                    ("LEVEL", self.level, ACCENT),
                                    ("BEST", self.app.scores.best(self.KEY), GOLD)):
            draw_text(s, label, 26, GREY, (px, y), "topleft")
            draw_text(s, value, 40, color, (px, y + 22), "topleft")
            y += 70


# =============================================================================
# SECTION 5 - GAME 3: CHOMP MAZE (a maze-chase game)
# =============================================================================

PM_CELL = 20
PM_HUD = 40
PM_PLAYER_SPEED = 5.0        # squares per second at level 1
PM_GHOST_SPEED = 4.6         # ghosts at level 1
PM_LEVEL_SPEEDUP = 0.06      # everyone gets 6% faster each level...
PM_MAX_SPEEDUP = 1.45        # ...up to this much
PM_FRIGHT_SPEED = 2.8        # blue ghosts
PM_EYES_SPEED = 11.0         # eaten ghosts going home
PM_HOUSE_SPEED = 3.0         # ghosts walking out of the house
PM_FRIGHT_TIME = 7.0         # seconds ghosts stay blue at level 1 (1 s less each level)
PM_FRIGHT_MIN = 2.0
PM_TURN_FORGIVENESS = 0.35   # a turn pressed this late (part of a square) still takes the corner
PM_TURN_MEMORY = 1.0         # a turn pressed early is remembered this long (seconds)
PM_LIVES = 3
PM_DOT_POINTS = 10
PM_POWER_POINTS = 50
PM_GHOST_POINTS = 200        # doubles for each ghost eaten on one big dot
PM_MODE_TIMES = [("scatter", 7), ("chase", 20), ("scatter", 7), ("chase", 20),
                 ("scatter", 5), ("chase", None)]   # None = forever
# letter in the maze, name, plan, color, scatter corner (column, row), seconds before leaving the house
PM_GHOSTS = [
    ("R", "Blaze", "chase", (255, 70, 70), (25, -3), 0.0),     # goes straight for you
    ("K", "Petal", "ahead", (255, 150, 210), (2, -3), 1.0),    # aims 4 squares ahead of you
    ("C", "Frost", "flank", (80, 230, 240), (27, 31), 4.0),    # teams up with Blaze to trap you
    ("E", "Sunny", "shy", (255, 170, 60), (0, 31), 8.0),       # chases, but runs off when close
]
# Draw your own maze! # wall   . dot   o big dot   = ghost door   (space) empty
# P = player start   R K C E = ghost starts. A row open at both ends is a tunnel.
# The game checks that every dot can be reached (unreachable dots are removed).
PM_MAZE = [
    "############################",
    "#o....##.....##.....##....o#",
    "#.###.##.###.##.###.##.###.#",
    "#.###.##.###.##.###.##.###.#",
    "#..........................#",
    "#.##.####.##.##.##.####.##.#",
    "#....####....##....####....#",
    "####.####.########.####.####",
    "####.####.########.####.####",
    "####.##......R.......##.####",
    "####.##.#####==#####.##.####",
    "####.##.#          #.##.####",
    "    ....#  C K  E  #....    ",
    "####.##.#          #.##.####",
    "####.##.############.##.####",
    "####.##..............##.####",
    "####.#######.##.#######.####",
    "#............##............#",
    "#.###.###.##.##.##.###.###.#",
    "#......#............#......#",
    "###.##.#.##########.#.##.###",
    "#......#.....##.....#......#",
    "#.##.####.##.##.##.####.##.#",
    "#o...##......P.......##...o#",
    "#.##.##.####.##.####.##.##.#",
    "#....##......##......##....#",
    "#.#####.####.##.####.#####.#",
    "#..........................#",
    "#.####.###.#.##.#.###.####.#",
    "#............##............#",
    "############################",
]
PM_DIRS = [(0, -1), (-1, 0), (0, 1), (1, 0)]   # up, left, down, right (ties go in this order)
PM_WALL_COLOR = (40, 70, 220)
PM_FRIGHT_COLOR = (40, 60, 220)


def pm_step(tile, d):
    return tile[0] + d[0], tile[1] + d[1]


class Mover:
    """Something that moves square to square: a tile, a direction and progress 0..1."""

    def __init__(self, tile, direction=(0, 0)):
        self.tile = tile
        self.dir = direction
        self.progress = 0.0

    def pos(self):
        """Position in squares (with fractions) - used for drawing and collisions."""
        return (self.tile[0] + self.dir[0] * self.progress,
                self.tile[1] + self.dir[1] * self.progress)

    def reverse(self, game):
        dx, dy = self.dir
        if (dx, dy) == (0, 0):
            return
        if self.progress <= 0.0:
            back = (-dx, -dy)
            if self.can_go(game, back):
                self.dir = back
            return
        self.tile = game.wrap(pm_step(self.tile, self.dir))
        self.dir = (-dx, -dy)
        self.progress = 1.0 - self.progress

    def can_go(self, game, d):
        return game.is_open(pm_step(self.tile, d))


class Ghost(Mover):
    def __init__(self, info, game):
        self.letter, self.name, self.plan, self.color, self.corner, self.release = info
        self.start = game.ghost_starts.get(self.letter, game.home_tile)
        super().__init__(self.start)
        self.reset(game)

    def reset(self, game):
        self.tile = self.start
        self.dir = (0, 0)
        self.progress = 0.0
        self.frightened = False
        self.bob = random.uniform(0, 3)
        if self.start in game.house_tiles:
            self.state = "house"         # waiting inside
            self.wait = self.release
        else:
            self.state = "active"
            self.dir = (-1, 0)

    def can_go(self, game, d):
        through_door = self.state in ("leave", "eyes")
        return game.is_open(pm_step(self.tile, d), through_door)

    def target(self, game):
        player = game.player
        px, py = player.tile
        dx, dy = player.dir
        if game.mode == "scatter":
            return self.corner
        if self.plan == "chase":
            return px, py
        if self.plan == "ahead":
            return px + 4 * dx, py + 4 * dy
        if self.plan == "flank":
            ax, ay = px + 2 * dx, py + 2 * dy
            partner = next((g for g in game.ghosts if g.plan == "chase"), self)
            bx, by = partner.tile
            return 2 * ax - bx, 2 * ay - by
        if self.plan == "shy":
            gx, gy = self.tile
            if (gx - px) ** 2 + (gy - py) ** 2 > 64:
                return px, py
            return self.corner
        return px, py

    def decide(self, game):
        """Pick a direction when standing on a square."""
        if self.state == "leave":
            return game.path_step(self.tile, game.exit_tile)
        if self.state == "eyes":
            return game.path_step(self.tile, game.home_tile)
        back = (-self.dir[0], -self.dir[1])
        options = [d for d in PM_DIRS if d != back and self.can_go(game, d)]
        if not options:
            options = [d for d in PM_DIRS if self.can_go(game, d)]
        if not options:
            return 0, 0
        if self.frightened:
            return random.choice(options)
        tx, ty = self.target(game)

        def distance(d):
            nx, ny = pm_step(self.tile, d)
            return (nx - tx) ** 2 + (ny - ty) ** 2

        return min(options, key=lambda d: (distance(d), PM_DIRS.index(d)))

    def arrived(self, game):
        if self.state == "leave" and self.tile == game.exit_tile:
            self.state = "active"
        elif self.state == "eyes" and self.tile == game.home_tile:
            self.state = "leave"
            self.frightened = False

    def update(self, dt, game):
        if self.state == "house":
            self.bob += dt
            self.wait -= dt
            if self.wait <= 0:
                self.state = "leave"
            return
        if self.state == "leave":
            speed = PM_HOUSE_SPEED
        elif self.state == "eyes":
            speed = PM_EYES_SPEED
        elif self.frightened:
            speed = PM_FRIGHT_SPEED
        else:
            speed = PM_GHOST_SPEED * game.speed_factor()
        if self.progress <= 0.0 and (self.dir == (0, 0) or not self.can_go(game, self.dir)):
            self.dir = self.decide(game)
            if self.dir == (0, 0):
                return
        self.progress += speed * dt
        while self.progress >= 1.0:
            self.progress -= 1.0
            self.tile = game.wrap(pm_step(self.tile, self.dir))
            self.arrived(game)
            self.dir = self.decide(game)
            if self.dir == (0, 0):
                self.progress = 0.0
                return


class MazeGame(GameBase):
    NAME = "Chomp Maze"
    KEY = "pacman"
    HELP = ["Arrow keys or WASD: move",
            "Eat every dot.  Big dots turn the ghosts blue",
            "Blue ghosts can be eaten - their eyes run home",
            "Blaze chases, Petal cuts ahead, Frost flanks, Sunny is shy"]

    def __init__(self, app):
        self.load_maze()
        self.SIZE = (self.W * PM_CELL, self.H * PM_CELL + PM_HUD)
        self.maze_image = self.render_maze(PM_WALL_COLOR)
        self.maze_flash = self.render_maze(WHITE)
        super().__init__(app)

    # -- the maze ----------------------------------------------------------------
    def load_maze(self):
        self.H = len(PM_MAZE)
        self.W = max(len(row) for row in PM_MAZE)
        rows = [row.ljust(self.W) for row in PM_MAZE]
        self.walls, self.doors = set(), set()
        self.dot_tiles, self.power_tiles = set(), set()
        self.ghost_starts = {}
        self.player_start = None
        letters = [g[0] for g in PM_GHOSTS]
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                if ch == "#":
                    self.walls.add((x, y))
                elif ch == "=":
                    self.doors.add((x, y))
                elif ch == ".":
                    self.dot_tiles.add((x, y))
                elif ch == "o":
                    self.power_tiles.add((x, y))
                elif ch == "P":
                    self.player_start = (x, y)
                elif ch in letters:
                    self.ghost_starts[ch] = (x, y)
        if self.player_start is None:
            self.player_start = min(self.dot_tiles)
        door = min(self.doors) if self.doors else (self.W // 2, self.H // 2)
        self.exit_tile = (door[0], door[1] - 1)     # just outside the door
        self.home_tile = (door[0], door[1] + 1)     # just inside the door
        # The house = squares joined to home without going through the door.
        self.house_tiles = self.flood(self.home_tile, through_door=False) if self.doors else set()
        # Check every dot can be reached from the player start.
        reachable = self.flood(self.player_start, through_door=False)
        lost = (self.dot_tiles | self.power_tiles) - reachable
        if lost:
            print("Chomp Maze: %d dots can't be reached and were removed: %s" % (len(lost), sorted(lost)[:8]))
            self.dot_tiles -= lost
            self.power_tiles -= lost

    def wrap(self, tile):
        return tile[0] % self.W, tile[1]

    def is_open(self, tile, through_door=False):
        x, y = tile
        if y < 0 or y >= self.H:
            return False
        x %= self.W
        if (x, y) in self.walls:
            return False
        if (x, y) in self.doors and not through_door:
            return False
        return True

    def flood(self, start, through_door):
        seen = {start}
        todo = [start]
        while todo:
            tile = todo.pop()
            for d in PM_DIRS:
                nxt = self.wrap(pm_step(tile, d))
                if nxt not in seen and self.is_open(nxt, through_door):
                    seen.add(nxt)
                    todo.append(nxt)
        return seen

    def path_step(self, start, goal):
        """First step of the shortest path (through the door) - for leaving and going home."""
        if start == goal:
            return 0, 0
        first = {start: None}
        queue = [start]
        i = 0
        while i < len(queue):
            tile = queue[i]
            i += 1
            for d in PM_DIRS:
                nxt = self.wrap(pm_step(tile, d))
                if nxt in first or not self.is_open(nxt, True):
                    continue
                first[nxt] = first[tile] or d
                if nxt == goal:
                    return first[nxt]
                queue.append(nxt)
        return 0, 0

    def render_maze(self, color):
        img = pygame.Surface((self.W * PM_CELL, self.H * PM_CELL))
        img.fill(BG)
        c = PM_CELL
        for (x, y) in self.walls:
            pygame.draw.rect(img, darken(color, 0.25), (x * c, y * c, c, c))
        for (x, y) in self.walls:   # bright edges where a wall meets a path
            px, py = x * c, y * c
            if (x, y - 1) not in self.walls and y > 0:
                pygame.draw.line(img, color, (px, py + 2), (px + c - 1, py + 2), 2)
            if (x, y + 1) not in self.walls and y < self.H - 1:
                pygame.draw.line(img, color, (px, py + c - 3), (px + c - 1, py + c - 3), 2)
            if (x - 1, y) not in self.walls and x > 0:
                pygame.draw.line(img, color, (px + 2, py), (px + 2, py + c - 1), 2)
            if (x + 1, y) not in self.walls and x < self.W - 1:
                pygame.draw.line(img, color, (px + c - 3, py), (px + c - 3, py + c - 1), 2)
        for (x, y) in self.doors:
            pygame.draw.rect(img, (255, 170, 200), (x * c, y * c + c // 2 - 2, c, 4))
        return img

    # -- game flow ---------------------------------------------------------------
    def reset(self):
        self.score = 0
        self.lives = PM_LIVES
        self.level = 1
        self.fx.clear()
        self.new_level()

    def new_level(self):
        self.dots = set(self.dot_tiles)
        self.power = set(self.power_tiles)
        self.reset_actors()

    def reset_actors(self):
        self.player = MazePlayer(self.player_start)
        self.ghosts = [Ghost(info, self) for info in PM_GHOSTS]
        self.mode_index = 0
        self.mode, self.mode_timer = PM_MODE_TIMES[0]
        self.fright = 0.0
        self.combo = 0
        self.freeze = 0.0
        self.phase = "ready"       # ready, run, dying, clear
        self.phase_timer = 1.6
        self.waka = 0

    def start(self):
        super().start()
        self.sound("pm_ready")

    def speed_factor(self):
        return min(PM_MAX_SPEEDUP, 1.0 + PM_LEVEL_SPEEDUP * (self.level - 1))

    def on_key(self, key):
        if self.phase in ("ready", "run"):
            self.player.press(key, self)

    def step(self, dt):
        if self.phase == "ready":
            self.phase_timer -= dt
            if self.phase_timer <= 0:
                self.phase = "run"
            return
        if self.phase == "dying":
            self.phase_timer -= dt
            if self.phase_timer <= 0:
                if self.lives <= 0:
                    self.finish()
                else:
                    self.reset_actors()
            return
        if self.phase == "clear":
            self.phase_timer -= dt
            if self.phase_timer <= 0:
                self.level += 1
                self.new_level()
            return
        if self.freeze > 0:         # short stop after eating a ghost
            self.freeze -= dt
            return
        if self.fright > 0:
            self.fright -= dt
            if self.fright <= 0:
                for g in self.ghosts:
                    g.frightened = False
        elif self.mode_timer is not None:
            self.mode_timer -= dt
            if self.mode_timer <= 0:
                self.mode_index = min(self.mode_index + 1, len(PM_MODE_TIMES) - 1)
                self.mode, self.mode_timer = PM_MODE_TIMES[self.mode_index]
                for g in self.ghosts:          # ghosts turn around when the mode changes
                    if g.state == "active":
                        g.reverse(self)
        self.player.update(dt, self, PM_PLAYER_SPEED * self.speed_factor())
        if self.phase != "run":
            return
        for g in self.ghosts:
            g.update(dt, self)
        self.check_hits()

    def player_arrived(self, tile):
        """Called by the player each time it reaches a square."""
        cx = tile[0] * PM_CELL + PM_CELL / 2
        cy = PM_HUD + tile[1] * PM_CELL + PM_CELL / 2
        if tile in self.dots:
            self.dots.discard(tile)
            self.score += PM_DOT_POINTS
            self.waka = 1 - self.waka
            self.sound("pm_waka1" if self.waka else "pm_waka2")
        elif tile in self.power:
            self.power.discard(tile)
            self.score += PM_POWER_POINTS
            self.fx.burst(cx, cy, WHITE, 10, 120)
            self.frighten()
        else:
            return
        if not self.dots and not self.power:
            self.phase = "clear"
            self.phase_timer = 2.2
            self.sound("pm_clear")

    def frighten(self):
        self.fright = max(PM_FRIGHT_MIN, PM_FRIGHT_TIME - (self.level - 1))
        self.combo = 0
        self.sound("pm_power")
        for g in self.ghosts:
            if g.state == "active":
                if not g.frightened:
                    g.reverse(self)
                g.frightened = True

    def check_hits(self):
        px, py = self.player.pos()
        for g in self.ghosts:
            if g.state not in ("active", "leave"):
                continue
            gx, gy = g.pos()
            dx = abs(gx - px)
            dx = min(dx, self.W - dx)     # the tunnel joins the two sides
            if dx * dx + (gy - py) ** 2 > 0.65 ** 2:
                continue
            cx = gx * PM_CELL + PM_CELL / 2
            cy = PM_HUD + gy * PM_CELL + PM_CELL / 2
            if g.frightened:
                g.state = "eyes"
                g.frightened = False
                self.combo += 1
                points = PM_GHOST_POINTS * 2 ** (self.combo - 1)
                self.score += points
                self.fx.text(cx, cy, str(points), ACCENT, 28, 1.0)
                self.fx.burst(cx, cy, PM_FRIGHT_COLOR, 14, 150)
                self.freeze = 0.45
                self.sound("pm_ghost")
            else:
                self.lives -= 1
                self.phase = "dying"
                self.phase_timer = 1.8
                self.shake = 0.3
                self.sound("pm_death")
                return

    # -- drawing -----------------------------------------------------------------
    def to_pixels(self, pos):
        return pos[0] * PM_CELL + PM_CELL / 2, PM_HUD + pos[1] * PM_CELL + PM_CELL / 2

    def draw_game(self, s):
        s.fill(BG)
        flashing = self.phase == "clear" and int(self.phase_timer * 6) % 2 == 0
        s.blit(self.maze_flash if flashing else self.maze_image, (0, PM_HUD))
        # HUD
        w = self.SIZE[0]
        draw_text(s, "Score %d" % self.score, 30, WHITE, (10, PM_HUD / 2), "midleft")
        draw_text(s, self.best_text(), 30, GOLD, (w / 2 - 30, PM_HUD / 2))
        draw_text(s, "Lv %d" % self.level, 28, ACCENT, (w / 2 + 75, PM_HUD / 2))
        for i in range(max(0, self.lives - (0 if self.phase == "dying" else 1))):
            self.draw_chomper(s, w - 18 - i * 24, PM_HUD / 2, 8, (1, 0), 0.6)
        # Dots
        for (x, y) in self.dots:
            cx, cy = self.to_pixels((x, y))
            pygame.draw.circle(s, (255, 200, 170), (int(cx), int(cy)), 2)
        if int(self.clock * 4) % 2 == 0 or self.state != "play":
            for (x, y) in self.power:
                cx, cy = self.to_pixels((x, y))
                pygame.draw.circle(s, (255, 200, 170), (int(cx), int(cy)), 6)
        # Player
        px, py = self.to_pixels(self.player.pos())
        if self.phase == "dying":
            opened = math.pi * clamp(1.0 - (self.phase_timer - 0.4) / 1.4, 0, 1)
            if opened < math.pi * 0.98:
                self.draw_chomper(s, px, py, 9, (0, -1), opened)
        else:
            self.draw_chomper(s, px, py, 9, self.player.dir, self.player.mouth_angle())
        # Ghosts
        if self.phase not in ("dying", "clear"):
            for g in self.ghosts:
                gx, gy = self.to_pixels(g.pos())
                if g.state == "house":
                    gy += math.sin(g.bob * 5) * 3
                self.draw_ghost(s, g, gx, gy)
        if self.phase == "ready" and self.state == "play":
            draw_text(s, "READY!", 34, GOLD, self.to_pixels((self.W / 2 - 0.5, 15.0)))

    def draw_chomper(self, s, cx, cy, r, direction, mouth):
        if direction == (0, 0):
            direction = (1, 0)
        facing = math.atan2(direction[1], direction[0])
        if mouth < 0.05:
            pygame.draw.circle(s, (255, 230, 0), (int(cx), int(cy)), r)
            return
        points = [(cx, cy)]
        steps = 18
        for i in range(steps + 1):
            a = facing + mouth + (2 * math.pi - 2 * mouth) * i / steps
            points.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
        pygame.draw.polygon(s, (255, 230, 0), points)

    def draw_ghost(self, s, g, cx, cy):
        r = 9
        if g.state != "eyes":
            color = g.color
            if g.frightened:
                color = PM_FRIGHT_COLOR
                if self.fright < 2.0 and int(self.fright * 8) % 2 == 0:
                    color = (230, 230, 255)
            pygame.draw.circle(s, color, (int(cx), int(cy - 2)), r)
            pygame.draw.rect(s, color, irect(cx - r, cy - 2, 2 * r + 1, r))
            wiggle = 1.5 if int(self.clock * 8) % 2 else -1.5
            for i in range(3):
                fx = cx - r + r / 3 + i * 2 * r / 3
                pygame.draw.circle(s, color, (int(fx), int(cy + r - 3 + (wiggle if i % 2 else -wiggle))), int(r / 3) + 1)
            if g.frightened:
                pygame.draw.circle(s, (255, 220, 200), (int(cx - 3), int(cy - 3)), 2)
                pygame.draw.circle(s, (255, 220, 200), (int(cx + 3), int(cy - 3)), 2)
                for i in range(4):
                    pygame.draw.line(s, (255, 220, 200), (int(cx - 6 + i * 3), int(cy + 3 + (i % 2) * 2)),
                                     (int(cx - 3 + i * 3), int(cy + 3 + ((i + 1) % 2) * 2)), 1)
                return
        dx, dy = g.dir
        for side in (-3.5, 3.5):
            pygame.draw.circle(s, WHITE, (int(cx + side), int(cy - 3)), 3)
            pygame.draw.circle(s, (30, 40, 160), (int(cx + side + dx * 1.5), int(cy - 3 + dy * 1.5)), 2)


# =============================================================================
# SECTION 6 - GAME 4: PADDLE DUEL (a paddle-and-ball game)
# =============================================================================

PO_W, PO_H = 820, 560
PO_DIFFICULTY = "normal"     # easy, normal or hard computer player (chosen first on the start screen)
PO_WIN_SCORE = 11            # first to 11
PO_PADDLE_W = 14
PO_PADDLE_H = 90
PO_PADDLE_SPEED = 520        # pixels per second for a human
PO_MARGIN = 30               # paddle distance from the edge
PO_BALL_SIZE = 14
PO_BALL_SPEED = 380          # serve speed
PO_SPEEDUP = 1.05            # each hit makes the ball 5% faster...
PO_MAX_BALL_SPEED = 950      # ...up to this
PO_MAX_ANGLE = 55            # degrees, when the ball hits the very end of a paddle
PO_SERVE_DELAY = 0.9
# The computer is not perfect: it reacts late, aims with an error, and now and
# then makes a completely wrong guess.
PO_AI = {
    "easy":   {"delay": 0.30, "error": 70, "wrong": 0.18, "speed": 300},
    "normal": {"delay": 0.18, "error": 40, "wrong": 0.08, "speed": 420},
    "hard":   {"delay": 0.09, "error": 14, "wrong": 0.025, "speed": 600},
}
PO_MODES = ["easy", "normal", "hard", "two players"]


class PongGame(GameBase):
    NAME = "Paddle Duel"
    KEY = "pong"
    SIZE = (PO_W, PO_H)

    def __init__(self, app):
        self.choice = PO_MODES.index(PO_DIFFICULTY) if PO_DIFFICULTY in PO_MODES else 1
        super().__init__(app)

    def best_text(self):
        return "Wins %d   Losses %d" % (self.app.scores.best("pong_wins"), self.app.scores.best("pong_losses"))

    def record(self):
        pass   # Paddle Duel counts wins and losses instead of a score

    def reset(self):
        self.mode = PO_MODES[self.choice]
        left_x = PO_MARGIN
        right_x = PO_W - PO_MARGIN - PO_PADDLE_W
        if self.mode == "two players":
            self.left = PaddlePlayer(left_x, (pygame.K_w,), (pygame.K_s,), ACCENT)
            self.right = PaddlePlayer(right_x, (pygame.K_UP,), (pygame.K_DOWN,), GOLD)
        else:
            self.left = PaddlePlayer(left_x, (pygame.K_w, pygame.K_UP), (pygame.K_s, pygame.K_DOWN), ACCENT)
            self.right = ComputerPaddle(right_x, PO_AI[self.mode])
        self.score_left = 0
        self.score_right = 0
        self.score = 0
        self.winner = None
        self.trail = []
        self.fx.clear()
        self.serve(random.choice((-1, 1)))

    def serve(self, direction):
        self.bx, self.by = PO_W / 2, PO_H / 2
        self.vx, self.vy = 0.0, 0.0
        self.serve_dir = direction
        self.serve_timer = PO_SERVE_DELAY
        self.trail = []

    def launch(self):
        angle = random.uniform(-0.45, 0.45)
        self.vx = math.cos(angle) * PO_BALL_SPEED * self.serve_dir
        self.vy = math.sin(angle) * PO_BALL_SPEED

    # -- input -------------------------------------------------------------------
    def handle_key(self, key):
        if self.state == "start":
            number_keys = (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4)
            if key in number_keys:
                self.choice = number_keys.index(key)
                self.start()
                return
            if key in (pygame.K_UP, pygame.K_w):
                self.choice = (self.choice - 1) % len(PO_MODES)
                self.sound("menu_move")
                return
            if key in (pygame.K_DOWN, pygame.K_s):
                self.choice = (self.choice + 1) % len(PO_MODES)
                self.sound("menu_move")
                return
        if self.state == "over" and key == pygame.K_c:
            self.state = "start"       # choose another opponent
            return
        super().handle_key(key)

    def on_key(self, key):
        self.left.press(key)
        self.right.press(key)

    def on_keyup(self, key):
        self.left.release(key)
        self.right.release(key)

    # -- every frame -------------------------------------------------------------
    def step(self, dt):
        self.left.update(dt, self)
        self.right.update(dt, self)
        if self.serve_timer > 0:
            self.serve_timer -= dt
            if self.serve_timer <= 0:
                self.launch()
            return
        speed = math.hypot(self.vx, self.vy)
        steps = int(speed * dt / 5) + 1     # small steps so a fast ball never skips a paddle
        for _ in range(steps):
            if self.move_ball(dt / steps):
                break
        self.trail.append((self.bx, self.by))
        self.trail = self.trail[-8:]

    def move_ball(self, h):
        """Move the ball a little. Returns True if someone scored."""
        r = PO_BALL_SIZE / 2
        self.bx += self.vx * h
        self.by += self.vy * h
        if self.by - r < 0:
            self.by = r
            self.vy = abs(self.vy)
            self.sound("po_wall")
        elif self.by + r > PO_H:
            self.by = PO_H - r
            self.vy = -abs(self.vy)
            self.sound("po_wall")
        ball = irect(self.bx - r, self.by - r, PO_BALL_SIZE, PO_BALL_SIZE)
        if self.vx < 0 and self.left.rect().colliderect(ball):
            self.hit(self.left, 1)
        elif self.vx > 0 and self.right.rect().colliderect(ball):
            self.hit(self.right, -1)
        if self.bx < -30:
            self.point(left_scored=False)
            return True
        if self.bx > PO_W + 30:
            self.point(left_scored=True)
            return True
        return False

    def hit(self, paddle, direction):
        """The paddle sends the ball back: the angle depends on where it hit."""
        r = PO_BALL_SIZE / 2
        offset = clamp((self.by - paddle.center()) / (PO_PADDLE_H / 2), -1.0, 1.0)
        angle = offset * math.radians(PO_MAX_ANGLE)
        speed = min(PO_MAX_BALL_SPEED, math.hypot(self.vx, self.vy) * PO_SPEEDUP)
        self.vx = math.cos(angle) * speed * direction
        self.vy = math.sin(angle) * speed
        self.bx = paddle.x + PO_PADDLE_W + r if direction > 0 else paddle.x - r
        paddle.flash = 0.15
        self.fx.burst(self.bx, self.by, paddle.color, 8, 140, 3, 0.35)
        self.sound("po_paddle")

    def point(self, left_scored):
        if left_scored:
            self.score_left += 1
            edge_x = PO_W - 6
        else:
            self.score_right += 1
            edge_x = 6
        self.fx.burst(edge_x, clamp(self.by, 10, PO_H - 10), RED, 24, 260, 4, 0.8)
        self.shake = 0.25
        self.sound("po_score")
        if max(self.score_left, self.score_right) >= PO_WIN_SCORE:
            self.end_match()
        else:
            self.serve(1 if left_scored else -1)   # serve toward whoever lost the point

    def end_match(self):
        self.winner = "left" if self.score_left > self.score_right else "right"
        self.score = self.score_left
        if self.mode != "two players":
            won = self.winner == "left"
            self.app.scores.add("pong_wins" if won else "pong_losses")
            self.new_best = won
        else:
            self.new_best = False
        self.state = "over"
        self.sound("best" if self.new_best or self.mode == "two players" else "over")

    # -- drawing -----------------------------------------------------------------
    def draw_game(self, s):
        s.fill((14, 18, 30))
        for y in range(0, PO_H, 28):
            pygame.draw.rect(s, (50, 56, 80), (PO_W // 2 - 2, y + 6, 4, 14))
        draw_text(s, self.score_left, 90, darken(ACCENT, 0.8), (PO_W / 2 - 80, 60))
        draw_text(s, self.score_right, 90, darken(GOLD, 0.8), (PO_W / 2 + 80, 60))
        label = "Two players" if self.mode == "two players" else "You vs computer (%s)" % self.mode
        draw_text(s, label, 24, GREY, (PO_W / 2, PO_H - 16))
        for p in (self.left, self.right):
            color = WHITE if p.flash > 0 else p.color
            pygame.draw.rect(s, color, p.rect(), border_radius=5)
        r = PO_BALL_SIZE / 2
        for i, (tx, ty) in enumerate(self.trail[:-1]):
            size = max(2, int(PO_BALL_SIZE * (i + 1) / len(self.trail) * 0.7))
            pygame.draw.rect(s, (70, 70, 100), (int(tx - size / 2), int(ty - size / 2), size, size))
        if self.serve_timer <= 0 or int(self.serve_timer * 8) % 2 == 0:
            pygame.draw.rect(s, WHITE, irect(self.bx - r, self.by - r, PO_BALL_SIZE, PO_BALL_SIZE), border_radius=3)

    def draw_start(self, s):
        shade_overlay(s, 175)
        w, h = self.SIZE
        draw_text(s, self.NAME, 72, ACCENT, (w / 2, h * 0.16))
        draw_text(s, "Choose your opponent (Up / Down + Enter, or 1-4)", 28, WHITE, (w / 2, h * 0.29))
        names = ["1   Computer - easy", "2   Computer - normal", "3   Computer - hard", "4   Two players"]
        for i, name in enumerate(names):
            y = h * 0.40 + i * 46
            if i == self.choice:
                pygame.draw.rect(s, PANEL_LIGHT, irect(w / 2 - 190, y - 20, 380, 40), border_radius=8)
            draw_text(s, name, 34, GOLD if i == self.choice else WHITE, (w / 2, y))
        draw_text(s, "Left player: W / S (or arrows vs computer)    Right player: arrows", 24, GREY,
                  (w / 2, h * 0.80))
        draw_text(s, "First to %d.   %s" % (PO_WIN_SCORE, self.best_text()), 26, GOLD, (w / 2, h * 0.88))

    def draw_over(self, s):
        shade_overlay(s, 165)
        w, h = self.SIZE
        if self.mode == "two players":
            title, color = ("LEFT PLAYER WINS" if self.winner == "left" else "RIGHT PLAYER WINS"), GOLD
        elif self.winner == "left":
            title, color = "YOU WIN!", GREEN
        else:
            title, color = "COMPUTER WINS", RED
        draw_text(s, title, 76, color, (w / 2, h * 0.3))
        draw_text(s, "%d - %d" % (self.score_left, self.score_right), 56, WHITE, (w / 2, h * 0.46))
        draw_text(s, self.best_text(), 30, GOLD, (w / 2, h * 0.58))
        draw_text(s, "Enter: rematch     C: change opponent     Esc: menu", 28, GREY, (w / 2, h * 0.75))


# =============================================================================
# SECTION 7 - PLAYER CLASSES (the keys each game listens to)
# =============================================================================

class SnakePlayer:
    """Viper Bite: remembers up to SN_TURN_QUEUE turns between two moves."""

    KEYS = {pygame.K_UP: (0, -1), pygame.K_w: (0, -1),
            pygame.K_DOWN: (0, 1), pygame.K_s: (0, 1),
            pygame.K_LEFT: (-1, 0), pygame.K_a: (-1, 0),
            pygame.K_RIGHT: (1, 0), pygame.K_d: (1, 0)}

    def __init__(self):
        self.queue = []

    def press(self, key, current_direction):
        d = self.KEYS.get(key)
        if d is None:
            return
        last = self.queue[-1] if self.queue else current_direction
        if d == last or d == (-last[0], -last[1]):   # no point, or a U-turn into yourself
            return
        if len(self.queue) < SN_TURN_QUEUE:
            self.queue.append(d)

    def next_turn(self):
        return self.queue.pop(0) if self.queue else None


class TetrisPlayer:
    """Brick Fall: tap or hold to move (auto-repeat), turn, drop and hold."""

    LEFT = (pygame.K_LEFT, pygame.K_a)
    RIGHT = (pygame.K_RIGHT, pygame.K_d)
    DOWN = (pygame.K_DOWN, pygame.K_s)
    TURN = (pygame.K_UP, pygame.K_w, pygame.K_x)
    TURN_BACK = (pygame.K_z,)
    DROP = (pygame.K_SPACE,)
    HOLD = (pygame.K_c, pygame.K_LSHIFT, pygame.K_RSHIFT)

    def __init__(self):
        self.held = set()
        self.direction = 0     # -1 left, 1 right, 0 none
        self.repeat = 0.0
        self.soft = False

    def press(self, key, game):
        self.held.add(key)
        if key in self.LEFT:
            self.direction = -1
            self.repeat = TE_DAS
            game.shift(-1)
        elif key in self.RIGHT:
            self.direction = 1
            self.repeat = TE_DAS
            game.shift(1)
        elif key in self.DOWN:
            self.soft = True
        elif key in self.TURN:
            game.rotate(1)
        elif key in self.TURN_BACK:
            game.rotate(-1)
        elif key in self.DROP:
            game.hard_drop()
        elif key in self.HOLD:
            game.hold_piece()

    def release(self, key):
        self.held.discard(key)
        if key in self.DOWN:
            self.soft = any(k in self.held for k in self.DOWN)
        if key in self.LEFT or key in self.RIGHT:
            if any(k in self.held for k in self.LEFT):
                self.direction = -1
            elif any(k in self.held for k in self.RIGHT):
                self.direction = 1
            else:
                self.direction = 0
            self.repeat = TE_DAS

    def update(self, dt, game):
        if self.direction == 0:
            return
        self.repeat -= dt
        while self.repeat <= 0:
            self.repeat += TE_ARR
            if not game.shift(self.direction):
                self.repeat = TE_ARR
                break


class MazePlayer(Mover):
    """Chomp Maze: forgiving turns - late turns still take the corner, early ones are remembered."""

    KEYS = {pygame.K_UP: (0, -1), pygame.K_w: (0, -1),
            pygame.K_DOWN: (0, 1), pygame.K_s: (0, 1),
            pygame.K_LEFT: (-1, 0), pygame.K_a: (-1, 0),
            pygame.K_RIGHT: (1, 0), pygame.K_d: (1, 0)}

    def __init__(self, tile):
        super().__init__(tile, (-1, 0))
        self.wanted = None
        self.wanted_age = 0.0
        self.moving = False
        self.chew = 0.0

    def press(self, key, game):
        d = self.KEYS.get(key)
        if d is None:
            return
        self.wanted = d
        self.wanted_age = 0.0
        dx, dy = self.dir
        if (dx, dy) == (0, 0) or self.progress <= 0.0:
            return                                   # update() takes it at once
        if d == (-dx, -dy):                          # turning back: right away
            self.reverse(game)
            self.wanted = None
        elif d[0] * dx + d[1] * dy == 0 and self.progress < PM_TURN_FORGIVENESS:
            # Pressed a little late: we just passed the corner, so take it anyway.
            if game.is_open(pm_step(self.tile, d)):
                self.dir = d
                self.wanted = None

    def mouth_angle(self):
        return 0.7 * abs(math.sin(self.chew * math.pi)) + 0.05

    def update(self, dt, game, speed):
        if self.wanted is not None:
            self.wanted_age += dt
            if self.wanted_age > PM_TURN_MEMORY:
                self.wanted = None
        if self.progress <= 0.0:
            if self.wanted is not None and game.is_open(pm_step(self.tile, self.wanted)):
                self.dir = self.wanted
                self.wanted = None
            if not game.is_open(pm_step(self.tile, self.dir)):
                self.moving = False
                return
        self.moving = True
        self.chew += dt * speed * 0.5
        self.progress += speed * dt
        while self.progress >= 1.0:
            self.progress -= 1.0
            self.tile = game.wrap(pm_step(self.tile, self.dir))
            game.player_arrived(self.tile)
            if self.wanted is not None and game.is_open(pm_step(self.tile, self.wanted)):
                self.dir = self.wanted
                self.wanted = None
            if not game.is_open(pm_step(self.tile, self.dir)):
                self.progress = 0.0
                self.moving = False
                break


class PaddlePlayer:
    """Paddle Duel: a human paddle moved by its own up / down keys."""

    def __init__(self, x, up_keys, down_keys, color):
        self.x = x
        self.y = (PO_H - PO_PADDLE_H) / 2
        self.up_keys = up_keys
        self.down_keys = down_keys
        self.color = color
        self.held = set()
        self.flash = 0.0

    def press(self, key):
        if key in self.up_keys or key in self.down_keys:
            self.held.add(key)

    def release(self, key):
        self.held.discard(key)

    def center(self):
        return self.y + PO_PADDLE_H / 2

    def rect(self):
        return irect(self.x, self.y, PO_PADDLE_W, PO_PADDLE_H)

    def update(self, dt, game):
        move = 0
        if any(k in self.held for k in self.up_keys):
            move -= 1
        if any(k in self.held for k in self.down_keys):
            move += 1
        self.y = clamp(self.y + move * PO_PADDLE_SPEED * dt, 0, PO_H - PO_PADDLE_H)
        self.flash = max(0.0, self.flash - dt)


class ComputerPaddle(PaddlePlayer):
    """The computer player: late reactions, aiming errors and the odd wrong guess."""

    def __init__(self, x, settings):
        super().__init__(x, (), (), GOLD)
        self.s = settings
        self.think_timer = 0.0
        self.target = PO_H / 2
        self.coming = False
        self.aim_error = 0.0
        self.wrong_guess = None

    def ball_coming(self, game):
        if game.serve_timer > 0:
            return False
        return (game.vx > 0 and game.bx < self.x) or (game.vx < 0 and game.bx > self.x)

    def predict_y(self, game):
        """Where the ball will cross this paddle, counting bounces off the walls."""
        r = PO_BALL_SIZE / 2
        face = self.x if game.vx > 0 else self.x + PO_PADDLE_W
        if game.vx == 0:
            return game.by
        t = (face - game.bx) / game.vx
        y = game.by + game.vy * t - r
        span = PO_H - 2 * r
        y %= 2 * span
        if y > span:
            y = 2 * span - y
        return y + r

    def update(self, dt, game):
        coming = self.ball_coming(game)
        if coming and not self.coming:        # a new shot: decide how well to read it
            self.aim_error = random.uniform(-self.s["error"], self.s["error"])
            if random.random() < self.s["wrong"]:
                self.wrong_guess = random.uniform(PO_PADDLE_H / 2, PO_H - PO_PADDLE_H / 2)
            else:
                self.wrong_guess = None
            self.think_timer = self.s["delay"]   # reaction delay before it starts to move
        self.coming = coming
        self.think_timer -= dt
        if self.think_timer <= 0:
            self.think_timer = self.s["delay"] * random.uniform(0.7, 1.3)
            if not coming:
                self.target = PO_H / 2 + random.uniform(-20, 20)
            elif self.wrong_guess is not None:
                self.target = self.wrong_guess
            else:
                self.target = self.predict_y(game) + self.aim_error
        diff = self.target - self.center()
        max_step = self.s["speed"] * dt
        if abs(diff) > 4:
            self.y += clamp(diff, -max_step, max_step)
        self.y = clamp(self.y, 0, PO_H - PO_PADDLE_H)
        self.flash = max(0.0, self.flash - dt)


# =============================================================================
# SECTION 8 - THE MENU
# =============================================================================

CARD_W, CARD_H = 440, 300


class Menu:
    """Four cards with small moving previews and each game's best score."""

    def __init__(self, app):
        self.app = app
        self.selected = 0
        self.t = 0.0
        self.cards = []
        for i in range(4):
            x = 30 + (i % 2) * (CARD_W + 20)
            y = 95 + (i // 2) * (CARD_H + 20)
            self.cards.append(pygame.Rect(x, y, CARD_W, CARD_H))

    def handle_key(self, key):
        old = self.selected
        if key in (pygame.K_LEFT, pygame.K_a):
            self.selected = (self.selected - 1) % 4
        elif key in (pygame.K_RIGHT, pygame.K_d):
            self.selected = (self.selected + 1) % 4
        elif key in (pygame.K_UP, pygame.K_w, pygame.K_DOWN, pygame.K_s):
            self.selected = (self.selected + 2) % 4
        elif key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
            self.app.open_game((pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4).index(key))
            return
        elif key in START_KEYS:
            self.app.open_game(self.selected)
            return
        elif key == pygame.K_ESCAPE:
            self.app.quit()
            return
        if self.selected != old:
            self.app.sounds.play("menu_move")

    def card_at(self, pos):
        for i, card in enumerate(self.cards):
            if card.collidepoint(pos):
                return i
        return None

    def handle_mouse(self, pos, clicked):
        i = self.card_at(pos)
        if i is None:
            return
        if i != self.selected and not clicked:
            self.selected = i
        if clicked:
            self.app.open_game(i)

    def update(self, dt):
        self.t += dt

    def draw(self, c):
        draw_text(c, "ARCADE LAB", 76, ACCENT, (CANVAS_W / 2, 42))
        draw_text(c, "RetroBox lobby edition", 24, GREY, (CANVAS_W / 2, 80))
        scores = self.app.scores
        for i, (card, game) in enumerate(zip(self.cards, self.app.games)):
            selected = i == self.selected
            pygame.draw.rect(c, PANEL_LIGHT if selected else PANEL, card, border_radius=14)
            glow = mix(ACCENT, WHITE, 0.5 + 0.5 * math.sin(self.t * 5)) if selected else DARK_GREY
            pygame.draw.rect(c, glow, card, 3 if selected else 2, border_radius=14)
            draw_text(c, str(i + 1), 34, GOLD, (card.x + 22, card.y + 26))
            draw_text(c, game.NAME, 40, WHITE, (card.x + 46, card.y + 26), "midleft")
            preview = pygame.Rect(card.x + 20, card.y + 50, CARD_W - 40, 190)
            pygame.draw.rect(c, BG, preview)
            c.set_clip(preview)
            [self.preview_snake, self.preview_blocks, self.preview_maze, self.preview_pong][i](c, preview)
            c.set_clip(None)
            if game.KEY == "pong":
                best = "Wins %d    Losses %d" % (scores.best("pong_wins"), scores.best("pong_losses"))
            else:
                best = "Best %d" % scores.best(game.KEY)
            draw_text(c, best, 30, GOLD, (card.centerx, card.bottom - 30))
        sound = "on" if self.app.sounds.enabled else "off"
        quit_text = "" if IS_WEB else "     Esc: quit"
        draw_text(c, "Arrows + Enter, 1-4, or click     M: sound %s%s" % (sound, quit_text), 24, GREY,
                  (CANVAS_W / 2, CANVAS_H - 12))

    # -- the little moving pictures on the cards ---------------------------------
    def preview_snake(self, c, r):
        cell = 16
        loop_w, loop_h = 18, 8
        perimeter = 2 * (loop_w + loop_h)
        color = SN_APPLE_COLORS[int(self.t / 2) % len(SN_APPLE_COLORS)]
        ox = r.x + (r.w - loop_w * cell) / 2
        oy = r.y + (r.h - loop_h * cell) / 2
        for k in range(12):
            d = (self.t * 8 - k) % perimeter
            if d < loop_w:
                x, y = d, 0
            elif d < loop_w + loop_h:
                x, y = loop_w, d - loop_w
            elif d < 2 * loop_w + loop_h:
                x, y = loop_w - (d - loop_w - loop_h), loop_h
            else:
                x, y = 0, loop_h - (d - 2 * loop_w - loop_h)
            shade = 1.0 - k * 0.04
            pygame.draw.rect(c, darken(color, shade), irect(ox + x * cell, oy + y * cell, cell - 2, cell - 2),
                             border_radius=4)
        apple = SN_APPLE_COLORS[(int(self.t / 2) + 1) % len(SN_APPLE_COLORS)]
        pygame.draw.circle(c, apple, (r.centerx, r.centery), 7)

    def preview_blocks(self, c, r):
        cell = 18
        cols, rows = 10, 10
        ox = r.centerx - cols * cell // 2
        oy = r.y + 5
        pygame.draw.rect(c, (18, 18, 34), (ox, oy, cols * cell, rows * cell))
        stack = ["..........", "..........", "..........", "..........", "..........",
                 "..........", "J.......LL", "JJJ..O.OL.", "IIIIZOO.LT", "SS.ZZTTTT."]
        for y, row in enumerate(stack):
            for x, ch in enumerate(row):
                if ch != ".":
                    pygame.draw.rect(c, TE_COLORS[ch], (ox + x * cell + 1, oy + y * cell + 1, cell - 2, cell - 2))
        kinds = "TSZLJOI"
        kind = kinds[int(self.t / 1.6) % 7]
        fall = int((self.t % 1.6) / 1.6 * 7)
        for cx, cy in TE_ROTATIONS[kind][int(self.t / 1.6) % 4]:
            pygame.draw.rect(c, TE_COLORS[kind], (ox + (3 + cx) * cell + 1, oy + (fall + cy) * cell + 1,
                                                  cell - 2, cell - 2))

    def preview_maze(self, c, r):
        y = r.centery
        pygame.draw.rect(c, PM_WALL_COLOR, (r.x, y - 26, r.w, 3))
        pygame.draw.rect(c, PM_WALL_COLOR, (r.x, y + 24, r.w, 3))
        span = r.w + 120
        pac_x = r.x - 60 + (self.t * 90) % span
        for k in range(0, r.w, 24):
            dx = r.x + 12 + k
            if dx > pac_x:
                pygame.draw.circle(c, (255, 200, 170), (int(dx), y), 3)
        mouth = 0.7 * abs(math.sin(self.t * 10)) + 0.05
        self.app.games[2].draw_chomper(c, pac_x, y, 14, (1, 0), mouth)
        names = [g for g in PM_GHOSTS]
        for i, info in enumerate(names):
            gx = pac_x - 55 - i * 40
            color = info[3]
            pygame.draw.circle(c, color, (int(gx), y - 3), 13)
            pygame.draw.rect(c, color, (int(gx) - 13, y - 3, 27, 15))
            pygame.draw.circle(c, WHITE, (int(gx) + 1, y - 6), 4)
            pygame.draw.circle(c, WHITE, (int(gx) + 9, y - 6), 4)
            pygame.draw.circle(c, (30, 40, 160), (int(gx) + 3, y - 6), 2)
            pygame.draw.circle(c, (30, 40, 160), (int(gx) + 11, y - 6), 2)

    def preview_pong(self, c, r):
        def bounce(value, length):
            value %= 2 * length
            return value if value < length else 2 * length - value
        inner_w = r.w - 60
        bx = r.x + 30 + bounce(self.t * 220, inner_w)
        by = r.y + 10 + bounce(self.t * 130, r.h - 20)
        for y in range(r.y, r.bottom, 20):
            pygame.draw.rect(c, (50, 56, 80), (r.centerx - 1, y + 4, 3, 10))
        left_y = clamp(by - 30 + math.sin(self.t * 3) * 10, r.y, r.bottom - 60)
        right_y = clamp(by - 30 - math.sin(self.t * 2) * 12, r.y, r.bottom - 60)
        pygame.draw.rect(c, ACCENT, (r.x + 12, int(left_y), 8, 60), border_radius=3)
        pygame.draw.rect(c, GOLD, (r.right - 20, int(right_y), 8, 60), border_radius=3)
        pygame.draw.rect(c, WHITE, (int(bx) - 5, int(by) - 5, 10, 10))


# =============================================================================
# SECTION 9 - THE APP AND THE MAIN LOOP
# =============================================================================

class ArcadeApp:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Arcade Lab")
        self.scale = self.pick_scale()
        size = (int(CANVAS_W * self.scale), int(CANVAS_H * self.scale))
        self.screen = pygame.display.set_mode(size)
        self.canvas = pygame.Surface((CANVAS_W, CANVAS_H))
        self.clock = pygame.time.Clock()
        self.sounds = SoundBank()
        self.scores = ScoreBook()
        self.games = [SnakeGame(self), BlockGame(self), MazeGame(self), PongGame(self)]
        self.menu = Menu(self)
        self.current = None          # None = the menu is showing
        self.running = True
        self.toast_text = ""
        self.toast_time = 0.0

    def pick_scale(self):
        """Shrink the window to fit the screen (Windows display scaling makes windows bigger)."""
        if IS_WEB:
            return 1.0               # the web page scales the picture itself
        if WINDOW_SCALE > 0:
            return WINDOW_SCALE
        info = pygame.display.Info()
        screen_w, screen_h = info.current_w, info.current_h
        if screen_w <= 0 or screen_h <= 0:
            return 1.0
        # leave room for the title bar and the taskbar so the bottom is never cut off
        return min(1.0, (screen_h - 100) / CANVAS_H, (screen_w - 40) / CANVAS_W)

    def to_canvas(self, pos):
        """Scale a mouse position from the window back to the 960x740 canvas."""
        return pos[0] / self.scale, pos[1] / self.scale

    def open_game(self, index):
        self.sounds.play("menu_pick")
        self.current = self.games[index]
        self.current.enter()

    def back_to_menu(self):
        if self.current is not None:
            self.current.leave()
        self.current = None
        self.sounds.play("menu_move")

    def quit(self):
        if not IS_WEB:               # a web page cannot close itself
            self.running = False

    def toast(self, text):
        self.toast_text = text
        self.toast_time = 1.3

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            self.quit()
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_m:
                on = self.sounds.toggle()
                self.toast("Sound on" if on else "Sound off")
            elif self.current is None:
                self.menu.handle_key(event.key)
            elif event.key == pygame.K_ESCAPE:
                self.back_to_menu()
            else:
                self.current.handle_key(event.key)
        elif event.type == pygame.KEYUP:
            if self.current is not None:
                self.current.handle_keyup(event.key)
        elif event.type == pygame.MOUSEMOTION:
            if self.current is None:
                self.menu.handle_mouse(self.to_canvas(event.pos), False)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.current is None:
                self.menu.handle_mouse(self.to_canvas(event.pos), True)

    def update(self, dt):
        if self.current is None:
            self.menu.update(dt)
        else:
            self.current.update(dt)
        self.toast_time = max(0.0, self.toast_time - dt)

    def draw(self):
        c = self.canvas
        c.fill(BG)
        if self.current is None:
            self.menu.draw(c)
        else:
            game = self.current
            surf = game.draw()
            draw_text(c, game.NAME, 34, ACCENT, (20, TOP_BAR / 2 + 2), "midleft")
            draw_text(c, game.best_text(), 28, GOLD, (CANVAS_W - 20, TOP_BAR / 2 + 2), "midright")
            w, h = surf.get_size()
            sx, sy = game.shake_offset()
            x = (CANVAS_W - w) // 2
            y = TOP_BAR + (CANVAS_H - TOP_BAR - BOTTOM_BAR - h) // 2
            pygame.draw.rect(c, PANEL_LIGHT, (x - 3, y - 3, w + 6, h + 6), 2, border_radius=4)
            c.blit(surf, (x + sx, y + sy))
            sound = "on" if self.sounds.enabled else "off"
            draw_text(c, "Esc: menu     P: pause     M: sound %s" % sound, 24, GREY,
                      (CANVAS_W / 2, CANVAS_H - BOTTOM_BAR / 2))
        if self.toast_time > 0:
            box = draw_text(c, self.toast_text, 30, WHITE, (CANVAS_W / 2, CANVAS_H - 60))
            pygame.draw.rect(c, PANEL_LIGHT, box.inflate(24, 12), 2, border_radius=8)
        self.present()

    def present(self):
        if self.scale == 1.0:
            self.screen.blit(self.canvas, (0, 0))
        else:
            pygame.transform.smoothscale(self.canvas, self.screen.get_size(), self.screen)
        pygame.display.flip()

    def frame(self, dt):
        for event in pygame.event.get():
            self.handle_event(event)
        self.update(dt)
        self.draw()
        self.sounds.build_some()


async def main():
    app = ArcadeApp()
    while app.running:
        dt = app.clock.tick(FPS) / 1000.0
        dt = min(dt, 0.05)           # if the computer hiccups, don't jump ahead
        app.frame(dt)
        await asyncio.sleep(0)       # lets the browser breathe - without it the web tab freezes
    pygame.quit()


asyncio.run(main())