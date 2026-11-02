"""
종스크롤 슈팅 게임 (pygame)

공중의 적은 기관포로, 지상의 목표물은 조준점에 폭탄을 떨어뜨려 파괴한다.
P 아이템을 먹으면 기관포가 2 → 4 → 8 → 16발로 강화된다 (피격 시 한 단계 하락).
외부 이미지/사운드 파일 없이 그래픽과 효과음을 모두 코드로 만든다.

조작:
    방향키 / WASD  이동
    Z / Space      기관포 (누르고 있으면 연사)
    X              폭탄 (조준점 위치의 지상 목표물 공격)
    P              일시정지
    Enter          시작 / 재시작
    Esc            종료
"""
import math
import random
import sys
from array import array

import pygame

# ---------------------------------------------------------------------------
# 설정
# ---------------------------------------------------------------------------
WIDTH, HEIGHT = 480, 720
FPS = 60
SCROLL_SPEED = 1.5
TILE = 48

PLAYER_SPEED = 5
SHOT_SPEED = 12
SHOT_COOLDOWN = 7
BOMB_RANGE = 150          # 기체 앞쪽 조준점까지의 거리
BOMB_FLIGHT = 30          # 폭탄이 조준점에 닿기까지의 프레임 수
SHOT_LEVELS = (2, 4, 8, 16)  # 파워 단계별 동시 발사 수

SAMPLE_RATE = 22050

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
YELLOW = (255, 220, 60)
RED = (255, 70, 70)
CYAN = (80, 230, 255)
ORANGE = (255, 150, 40)
GRAY = (130, 130, 140)
DARK = (40, 40, 50)

GRASS = [(54, 110, 60), (60, 120, 66), (50, 102, 56)]
FOREST = (30, 80, 40)
SAND = (170, 150, 100)
WATER = (40, 80, 150)
ROAD = (90, 90, 95)


# ---------------------------------------------------------------------------
# 효과음 (파형을 직접 합성)
# ---------------------------------------------------------------------------
class Sfx:
    """사운드 파일 없이 사각파/노이즈를 합성해 효과음을 만든다.
    오디오 장치가 없으면 조용히 무음으로 동작한다."""

    def __init__(self):
        self.sounds = {}
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(SAMPLE_RATE, -16, 1, 512)
            self.rate, _, self.channels = pygame.mixer.get_init()
            pygame.mixer.set_num_channels(24)
        except pygame.error:
            return
        self.sounds = {
            "shot":    self._synth([(900, 500, 0.05)], "square", 0.10),
            "bomb":    self._synth([(700, 200, 0.25)], "square", 0.18),
            "boom":    self._synth([(200, 60, 0.30)], "noise", 0.45),
            "bigboom": self._synth([(150, 30, 0.80)], "noise", 0.60),
            "hit":     self._synth([(300, 250, 0.03)], "square", 0.12),
            "die":     self._synth([(600, 40, 1.00)], "noise", 0.60),
            "item":    self._synth([(660, 660, 0.06), (880, 880, 0.06), (1320, 1320, 0.10)], "square", 0.22),
            "powerup": self._synth([(440, 1760, 0.35)], "square", 0.22),
            "oneup":   self._synth([(523, 523, 0.08), (659, 659, 0.08), (784, 784, 0.08), (1047, 1047, 0.18)], "square", 0.25),
            "start":   self._synth([(392, 392, 0.1), (523, 523, 0.1), (659, 659, 0.1), (784, 784, 0.25)], "square", 0.22),
        }

    def _synth(self, segments, wave, volume):
        """segments: (시작 주파수, 끝 주파수, 길이(초)) 목록을 이어 붙인다."""
        buf = array("h")
        phase = 0.0
        noise_val, noise_step = 0.0, 0
        for f0, f1, dur in segments:
            n = int(self.rate * dur)
            for i in range(n):
                t = i / n
                freq = f0 + (f1 - f0) * t
                phase += freq / self.rate
                if wave == "noise":
                    # 주파수가 낮을수록 노이즈 값을 오래 유지해 묵직한 소리를 낸다
                    noise_step += 1
                    if noise_step >= max(1, int(self.rate / (freq * 8))):
                        noise_step = 0
                        noise_val = random.uniform(-1, 1)
                    v = noise_val
                else:
                    v = 1.0 if (phase % 1.0) < 0.5 else -1.0
                env = (1 - t) ** 1.5 if len(segments) == 1 else (1 - t * 0.6)
                sample = int(v * env * volume * 32767)
                for _ in range(self.channels):
                    buf.append(sample)
        return pygame.mixer.Sound(buffer=buf.tobytes())

    def play(self, name):
        snd = self.sounds.get(name)
        if snd:
            snd.play()


# ---------------------------------------------------------------------------
# 배경 (지형 타일 스크롤)
# ---------------------------------------------------------------------------
class Terrain:
    """세로로 무한 스크롤되는 지형. 행 단위로 타일을 생성한다."""

    COLS = WIDTH // TILE

    def __init__(self):
        self.rows = []
        self.offset = 0.0
        self.river_x = random.randint(2, self.COLS - 3)
        self.road_x = random.randint(1, self.COLS - 2)
        for _ in range(HEIGHT // TILE + 2):
            self.rows.insert(0, self._make_row())

    def _make_row(self):
        # 강과 도로는 조금씩 좌우로 굽이친다
        if random.random() < 0.25:
            self.river_x = max(1, min(self.COLS - 2, self.river_x + random.choice((-1, 1))))
        if random.random() < 0.1:
            self.road_x = max(0, min(self.COLS - 1, self.road_x + random.choice((-1, 1))))
        row = []
        for c in range(self.COLS):
            if c == self.river_x:
                kind = "water"
            elif abs(c - self.river_x) == 1:
                kind = "sand"
            elif c == self.road_x:
                kind = "road"
            elif random.random() < 0.18:
                kind = "forest"
            else:
                kind = "grass"
            row.append((kind, random.randrange(3)))
        return row

    def update(self):
        self.offset += SCROLL_SPEED
        while self.offset >= TILE:
            self.offset -= TILE
            self.rows.insert(0, self._make_row())
            self.rows.pop()

    def draw(self, surf):
        for r, row in enumerate(self.rows):
            y = (r - 1) * TILE + self.offset
            for c, (kind, v) in enumerate(row):
                rect = pygame.Rect(c * TILE, y, TILE, TILE + 1)
                if kind == "grass":
                    pygame.draw.rect(surf, GRASS[v], rect)
                elif kind == "forest":
                    pygame.draw.rect(surf, GRASS[0], rect)
                    for i in range(3):
                        cx = rect.x + 10 + i * 14
                        cy = rect.y + 14 + (i % 2) * 18
                        pygame.draw.circle(surf, FOREST, (cx, cy), 11)
                elif kind == "water":
                    pygame.draw.rect(surf, WATER, rect)
                    pygame.draw.line(surf, (70, 110, 180),
                                     (rect.x + 8, rect.y + 12 + v * 8),
                                     (rect.x + 24, rect.y + 12 + v * 8), 2)
                elif kind == "sand":
                    pygame.draw.rect(surf, SAND, rect)
                elif kind == "road":
                    pygame.draw.rect(surf, ROAD, rect)
                    pygame.draw.line(surf, (200, 200, 200),
                                     (rect.centerx, rect.y + 6),
                                     (rect.centerx, rect.y + 24), 2)


# ---------------------------------------------------------------------------
# 이펙트
# ---------------------------------------------------------------------------
class Explosion:
    def __init__(self, x, y, size=1.0, ground=False):
        self.x, self.y = x, y
        self.size = size
        self.ground = ground
        self.t = 0
        self.life = int(24 * size) + 6
        self.sparks = [
            [x, y, math.cos(a) * s, math.sin(a) * s]
            for a, s in ((random.uniform(0, math.tau), random.uniform(1, 4) * size)
                         for _ in range(int(12 * size)))
        ]

    def update(self):
        self.t += 1
        if self.ground:
            self.y += SCROLL_SPEED
        for s in self.sparks:
            s[0] += s[2]
            s[1] += s[3] + (SCROLL_SPEED if self.ground else 0)
            s[2] *= 0.92
            s[3] *= 0.92
        return self.t < self.life

    def draw(self, surf):
        p = self.t / self.life
        radius = int((8 + 26 * p) * self.size)
        alpha_col = (255, int(220 * (1 - p)), int(80 * (1 - p)))
        pygame.draw.circle(surf, alpha_col, (int(self.x), int(self.y)), radius, max(1, int(4 * (1 - p)) + 1))
        if p < 0.4:
            pygame.draw.circle(surf, WHITE, (int(self.x), int(self.y)), int(radius * 0.5))
        for sx, sy, _, _ in self.sparks:
            pygame.draw.circle(surf, YELLOW, (int(sx), int(sy)), 2)


class Crater:
    """지상 목표물이 파괴된 자리. 지형과 함께 스크롤된다."""

    def __init__(self, x, y):
        self.x, self.y = x, y

    def update(self):
        self.y += SCROLL_SPEED
        return self.y < HEIGHT + 40

    def draw(self, surf):
        pygame.draw.ellipse(surf, (35, 30, 25), (self.x - 18, self.y - 12, 36, 24))
        pygame.draw.ellipse(surf, (60, 50, 40), (self.x - 12, self.y - 8, 24, 16))


# ---------------------------------------------------------------------------
# 플레이어
# ---------------------------------------------------------------------------
class Player:
    def __init__(self):
        self.x = WIDTH / 2
        self.y = HEIGHT - 120
        self.cooldown = 0
        self.bomb_out = False
        self.invincible = 120
        self.tilt = 0

    @property
    def rect(self):
        return pygame.Rect(self.x - 8, self.y - 10, 16, 20)  # 판정은 작게

    @property
    def target(self):
        return self.x, self.y - BOMB_RANGE

    def update(self, keys):
        dx = (keys[pygame.K_RIGHT] or keys[pygame.K_d]) - (keys[pygame.K_LEFT] or keys[pygame.K_a])
        dy = (keys[pygame.K_DOWN] or keys[pygame.K_s]) - (keys[pygame.K_UP] or keys[pygame.K_w])
        if dx and dy:
            dx *= 0.7071
            dy *= 0.7071
        self.x = max(20, min(WIDTH - 20, self.x + dx * PLAYER_SPEED))
        self.y = max(BOMB_RANGE + 20, min(HEIGHT - 30, self.y + dy * PLAYER_SPEED))
        self.tilt = dx
        if self.cooldown:
            self.cooldown -= 1
        if self.invincible:
            self.invincible -= 1

    def draw(self, surf, frame):
        if self.invincible and (frame // 4) % 2:
            return
        x, y = int(self.x), int(self.y)
        w = 22 - abs(self.tilt) * 4
        # 그림자
        pygame.draw.polygon(surf, (25, 45, 30),
                            [(x + 18, y - 4), (x + 18 - w, y + 30), (x + 18 + w, y + 30)])
        # 날개
        pygame.draw.polygon(surf, (190, 200, 215), [(x, y - 6), (x - w, y + 14), (x + w, y + 14)])
        # 동체
        pygame.draw.polygon(surf, (230, 235, 245), [(x, y - 22), (x - 7, y + 16), (x + 7, y + 16)])
        pygame.draw.polygon(surf, (90, 100, 120), [(x, y - 22), (x - 7, y + 16), (x + 7, y + 16)], 1)
        # 조종석
        pygame.draw.ellipse(surf, CYAN, (x - 3, y - 8, 6, 10))
        # 엔진 불꽃
        flame = 6 + (frame % 4) * 2
        pygame.draw.polygon(surf, ORANGE, [(x - 4, y + 16), (x + 4, y + 16), (x, y + 16 + flame)])

    def draw_sight(self, surf, frame, locked):
        tx, ty = map(int, self.target)
        color = RED if locked else (WHITE if (frame // 10) % 2 else (200, 200, 200))
        size = 14
        pygame.draw.rect(surf, color, (tx - size, ty - size, size * 2, size * 2), 2)
        pygame.draw.line(surf, color, (tx - size - 6, ty), (tx - size + 4, ty), 2)
        pygame.draw.line(surf, color, (tx + size - 4, ty), (tx + size + 6, ty), 2)
        pygame.draw.line(surf, color, (tx, ty - size - 6), (tx, ty - size + 4), 2)
        pygame.draw.line(surf, color, (tx, ty + size - 4), (tx, ty + size + 6), 2)


class Shot:
    def __init__(self, x, y, dx=0):
        self.x, self.y, self.dx = x, y, dx

    @property
    def rect(self):
        return pygame.Rect(self.x - 2, self.y - 8, 4, 16)

    def update(self):
        self.y -= SHOT_SPEED
        self.x += self.dx
        return self.y > -20

    def draw(self, surf):
        pygame.draw.rect(surf, YELLOW, self.rect)
        pygame.draw.rect(surf, WHITE, (self.x - 1, self.y - 6, 2, 8))


class Bomb:
    """기체에서 조준점(고정 지면 좌표)으로 날아가 지면에 닿으면 폭발한다."""

    def __init__(self, x, y, tx, ty):
        self.sx, self.sy = x, y
        self.tx, self.ty = tx, ty
        self.t = 0

    def update(self):
        self.t += 1
        self.ty += SCROLL_SPEED  # 목표 지점은 지면과 함께 내려온다
        return self.t < BOMB_FLIGHT

    @property
    def pos(self):
        p = self.t / BOMB_FLIGHT
        return self.sx + (self.tx - self.sx) * p, self.sy + (self.ty - self.sy) * p

    def draw(self, surf):
        p = self.t / BOMB_FLIGHT
        x, y = self.pos
        r = int(6 - 3 * p)  # 멀어질수록(지면에 가까워질수록) 작게
        pygame.draw.circle(surf, (60, 60, 60), (int(x), int(y)), r + 1)
        pygame.draw.circle(surf, (220, 220, 220), (int(x), int(y)), r)


class Item:
    """파워업 아이템. 천천히 흔들리며 내려온다."""

    def __init__(self, x, y):
        self.x, self.y = x, y
        self.base_x = x
        self.t = 0

    @property
    def rect(self):
        return pygame.Rect(self.x - 14, self.y - 14, 28, 28)

    def update(self):
        self.t += 1
        self.y += 1.3
        self.x = max(16, min(WIDTH - 16, self.base_x + math.sin(self.t / 20) * 30))
        return self.y < HEIGHT + 20

    def draw(self, surf, frame, label):
        x, y = int(self.x), int(self.y)
        glow = 16 + (frame // 4) % 3
        pygame.draw.circle(surf, (255, 255, 160), (x, y), glow, 2)
        color = ORANGE if (frame // 8) % 2 else RED
        pygame.draw.circle(surf, color, (x, y), 12)
        pygame.draw.circle(surf, WHITE, (x, y), 12, 2)
        surf.blit(label, label.get_rect(center=(x, y)))


# ---------------------------------------------------------------------------
# 적
# ---------------------------------------------------------------------------
class EnemyBullet:
    def __init__(self, x, y, vx, vy):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy

    @property
    def rect(self):
        return pygame.Rect(self.x - 3, self.y - 3, 6, 6)

    def update(self):
        self.x += self.vx
        self.y += self.vy
        return -10 < self.x < WIDTH + 10 and -10 < self.y < HEIGHT + 10

    def draw(self, surf, frame):
        c = (255, 120, 200) if (frame // 3) % 2 else (255, 255, 255)
        pygame.draw.circle(surf, c, (int(self.x), int(self.y)), 4)
        pygame.draw.circle(surf, RED, (int(self.x), int(self.y)), 4, 1)


def aim(x, y, px, py, speed):
    ang = math.atan2(py - y, px - x)
    return math.cos(ang) * speed, math.sin(ang) * speed


class AirEnemy:
    """공중 적. kind에 따라 움직임 패턴이 다르다."""

    STATS = {
        "dart":   dict(hp=1, score=100, r=12),
        "spinner": dict(hp=1, score=150, r=13),
        "diver":  dict(hp=2, score=200, r=14),
        "heavy":  dict(hp=8, score=800, r=24),
    }

    def __init__(self, kind, x, y, level):
        self.kind = kind
        self.x, self.y = x, y
        s = self.STATS[kind]
        self.hp = s["hp"] + (level // 4 if kind == "heavy" else 0)
        self.score = s["score"]
        self.r = s["r"]
        self.t = 0
        self.level = level
        self.base_x = x
        self.vx = 0
        self.vy = 0
        self.flash = 0
        self.fire_at = random.randint(40, 100)

    @property
    def rect(self):
        return pygame.Rect(self.x - self.r, self.y - self.r, self.r * 2, self.r * 2)

    def update(self, player, bullets):
        self.t += 1
        if self.flash:
            self.flash -= 1
        k = self.kind
        if k == "dart":
            self.y += 3.2
            self.x = self.base_x + math.sin(self.t / 18) * 50
        elif k == "spinner":
            # 내려오다가 플레이어 쪽으로 방향을 틀어 빠져나감
            if self.t < 50:
                self.y += 4
            else:
                if self.t == 50:
                    self.vx = 3 if player.x > self.x else -3
                self.x += self.vx
                self.y -= 1.5
        elif k == "diver":
            if self.t < 40:
                self.y += 2
            elif self.t == 40:
                self.vx, self.vy = aim(self.x, self.y, player.x, player.y, 5.5)
            else:
                self.x += self.vx
                self.y += self.vy
        elif k == "heavy":
            if self.y < 140:
                self.y += 1.2
            else:
                self.x = self.base_x + math.sin(self.t / 60) * 120
            if self.t > 300:
                self.y += 1.5

        # 사격
        if self.t == self.fire_at or (k == "heavy" and self.t % max(30, 70 - self.level * 4) == 0 and self.y > 40):
            if k == "heavy":
                base = math.atan2(player.y - self.y, player.x - self.x)
                for i in range(-2, 3):
                    a = base + i * 0.25
                    bullets.append(EnemyBullet(self.x, self.y + 10, math.cos(a) * 3.5, math.sin(a) * 3.5))
            elif self.y < player.y - 60:
                vx, vy = aim(self.x, self.y, player.x, player.y, 3 + self.level * 0.2)
                bullets.append(EnemyBullet(self.x, self.y, vx, vy))

        return -60 < self.x < WIDTH + 60 and -80 < self.y < HEIGHT + 60

    def draw(self, surf, frame):
        x, y = int(self.x), int(self.y)
        body = WHITE if self.flash else None
        if self.kind == "dart":
            pygame.draw.polygon(surf, body or (220, 80, 80), [(x, y + 14), (x - 12, y - 10), (x, y - 4), (x + 12, y - 10)])
            pygame.draw.circle(surf, YELLOW, (x, y), 3)
        elif self.kind == "spinner":
            for i in range(3):
                a = self.t / 6 + i * math.tau / 3
                pygame.draw.line(surf, body or (200, 200, 230), (x, y),
                                 (x + math.cos(a) * 13, y + math.sin(a) * 13), 4)
            pygame.draw.circle(surf, body or (120, 90, 200), (x, y), 7)
        elif self.kind == "diver":
            pygame.draw.polygon(surf, body or (240, 160, 40), [(x, y + 16), (x - 14, y - 6), (x - 5, y - 14), (x + 5, y - 14), (x + 14, y - 6)])
            pygame.draw.circle(surf, RED, (x, y - 2), 4)
        elif self.kind == "heavy":
            pygame.draw.ellipse(surf, body or (110, 120, 140), (x - 24, y - 18, 48, 36))
            pygame.draw.rect(surf, body or (80, 90, 110), (x - 34, y - 6, 68, 12))
            pygame.draw.circle(surf, RED if (frame // 8) % 2 else ORANGE, (x, y), 8)
            pygame.draw.ellipse(surf, BLACK, (x - 24, y - 18, 48, 36), 2)


class GroundEnemy:
    """지상 목표물. 폭탄으로만 파괴할 수 있다."""

    def __init__(self, kind, x, y, level):
        self.kind = kind
        self.x, self.y = x, y
        self.level = level
        self.t = random.randint(0, 60)
        self.hp = 2 if kind == "fortress" else 1
        self.score = {"turret": 300, "tank": 400, "radar": 500, "fortress": 2000}[kind]
        self.r = 28 if kind == "fortress" else 16
        self.flash = 0

    def update(self, player, bullets):
        self.t += 1
        if self.flash:
            self.flash -= 1
        self.y += SCROLL_SPEED
        if self.kind == "tank":
            self.x += math.sin(self.t / 50) * 0.8
        interval = {"turret": 110, "tank": 140, "radar": 0, "fortress": 50}[self.kind]
        interval = max(40, interval - self.level * 5) if interval else 0
        if interval and self.t % interval == 0 and 20 < self.y < player.y - 80:
            speed = 2.8 + self.level * 0.15
            if self.kind == "fortress":
                for i in range(8):
                    a = i * math.tau / 8 + self.t / 40
                    bullets.append(EnemyBullet(self.x, self.y, math.cos(a) * speed, math.sin(a) * speed))
            else:
                vx, vy = aim(self.x, self.y, player.x, player.y, speed)
                bullets.append(EnemyBullet(self.x, self.y, vx, vy))
        return self.y < HEIGHT + 40

    def hit_by(self, x, y):
        return math.hypot(self.x - x, self.y - y) < self.r + 10

    def draw(self, surf, frame):
        x, y = int(self.x), int(self.y)
        f = self.flash
        if self.kind == "turret":
            pygame.draw.circle(surf, WHITE if f else GRAY, (x, y), 15)
            pygame.draw.circle(surf, DARK, (x, y), 15, 2)
            pygame.draw.circle(surf, (90, 90, 100), (x, y), 7)
        elif self.kind == "tank":
            pygame.draw.rect(surf, WHITE if f else (90, 110, 70), (x - 13, y - 16, 26, 32), border_radius=4)
            pygame.draw.rect(surf, DARK, (x - 13, y - 16, 26, 32), 2, border_radius=4)
            pygame.draw.circle(surf, (70, 90, 55), (x, y), 8)
            pygame.draw.line(surf, DARK, (x, y), (x, y + 18), 4)
        elif self.kind == "radar":
            pygame.draw.rect(surf, WHITE if f else (150, 150, 160), (x - 14, y - 14, 28, 28))
            a = self.t / 15
            pygame.draw.line(surf, CYAN, (x, y), (x + math.cos(a) * 16, y + math.sin(a) * 16), 3)
            pygame.draw.circle(surf, DARK, (x, y), 4)
        elif self.kind == "fortress":
            pts = [(x + math.cos(i * math.tau / 8) * 30, y + math.sin(i * math.tau / 8) * 30) for i in range(8)]
            pygame.draw.polygon(surf, WHITE if f else (120, 110, 100), pts)
            pygame.draw.polygon(surf, DARK, pts, 3)
            pygame.draw.circle(surf, RED if (frame // 10) % 2 else (150, 30, 30), (x, y), 10)


# ---------------------------------------------------------------------------
# 게임
# ---------------------------------------------------------------------------
class Game:
    def __init__(self):
        pygame.mixer.pre_init(SAMPLE_RATE, -16, 1, 512)
        pygame.init()
        self.sfx = Sfx()
        pygame.display.set_caption("Sky Striker")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = self._font(22)
        self.big_font = self._font(48)
        self.item_label = self._font(16).render("P", True, WHITE)
        self.hiscore = 0
        self.state = "title"
        self.frame = 0
        self.terrain = Terrain()
        self.reset()

    @staticmethod
    def _font(size):
        # 한글이 표시되는 시스템 폰트를 우선 사용
        for name in ("malgungothic", "applegothic", "nanumgothic", "notosanscjkkr"):
            path = pygame.font.match_font(name)
            if path:
                return pygame.font.Font(path, size)
        return pygame.font.Font(None, size + 6)

    def reset(self):
        self.player = Player()
        self.shots, self.bombs = [], []
        self.air, self.ground = [], []
        self.bullets, self.effects, self.craters = [], [], []
        self.items = []
        self.power = 0  # SHOT_LEVELS 인덱스
        self.score = 0
        self.lives = 3
        self.distance = 0
        self.level = 1
        self.spawn_timer = 60
        self.ground_timer = 120
        self.heavy_timer = 1200
        self.fortress_timer = 2400

    # --- 생성 -------------------------------------------------------------
    def spawn_waves(self):
        self.spawn_timer -= 1
        if self.spawn_timer <= 0:
            kind = random.choices(("dart", "spinner", "diver"), (5, 3, 2 + self.level))[0]
            count = random.randint(3, 4 + self.level // 2)
            if kind == "dart":
                x = random.randint(70, WIDTH - 70)
                for i in range(count):
                    self.air.append(AirEnemy(kind, x, -30 - i * 40, self.level))
            elif kind == "spinner":
                for i in range(count):
                    self.air.append(AirEnemy(kind, 50 + i * (WIDTH - 100) / max(1, count - 1), -30, self.level))
            else:
                for _ in range(min(count, 3)):
                    self.air.append(AirEnemy(kind, random.randint(40, WIDTH - 40), random.randint(-120, -30), self.level))
            self.spawn_timer = max(35, 110 - self.level * 8) + random.randint(0, 40)

        self.ground_timer -= 1
        if self.ground_timer <= 0:
            kind = random.choices(("turret", "tank", "radar"), (4, 3, 2))[0]
            self.ground.append(GroundEnemy(kind, random.randint(40, WIDTH - 40), -30, self.level))
            self.ground_timer = max(50, 140 - self.level * 8) + random.randint(0, 60)

        self.heavy_timer -= 1
        if self.heavy_timer <= 0:
            self.air.append(AirEnemy("heavy", WIDTH / 2, -40, self.level))
            self.heavy_timer = max(600, 1300 - self.level * 80)

        self.fortress_timer -= 1
        if self.fortress_timer <= 0:
            self.ground.append(GroundEnemy("fortress", random.randint(100, WIDTH - 100), -40, self.level))
            self.fortress_timer = max(1200, 2600 - self.level * 120)

    # --- 입력 -------------------------------------------------------------
    def handle_fire(self, keys):
        p = self.player
        if (keys[pygame.K_z] or keys[pygame.K_SPACE]) and p.cooldown == 0:
            n = SHOT_LEVELS[self.power]
            # 2발은 평행, 그 이상은 부채꼴로 퍼진다
            spread = 0 if n == 2 else 6.0 / n
            gap = 12 if n == 2 else 24 / n
            for i in range(n):
                off = i - (n - 1) / 2
                self.shots.append(Shot(p.x + off * gap, p.y - 16 + abs(off) * 1.5, off * spread))
            p.cooldown = SHOT_COOLDOWN
            self.sfx.play("shot")

    def drop_bomb(self):
        if not self.bombs:  # 한 번에 한 발만
            tx, ty = self.player.target
            self.bombs.append(Bomb(self.player.x, self.player.y - 10, tx, ty))
            self.sfx.play("bomb")

    def maybe_drop_item(self, x, y, chance):
        if random.random() < chance:
            self.items.append(Item(x, y))

    def collect_item(self):
        if self.power < len(SHOT_LEVELS) - 1:
            self.power += 1
            self.sfx.play("powerup")
        else:
            self.add_score(1000)  # 최대 단계에서는 보너스 점수
            self.sfx.play("item")

    # --- 갱신 -------------------------------------------------------------
    def update(self):
        keys = pygame.key.get_pressed()
        self.terrain.update()
        self.player.update(keys)
        self.handle_fire(keys)
        self.spawn_waves()

        self.distance += 1
        self.level = 1 + self.distance // 1800

        self.shots = [s for s in self.shots if s.update()]
        self.bullets = [b for b in self.bullets if b.update()]
        self.air = [e for e in self.air if e.update(self.player, self.bullets)]
        self.ground = [g for g in self.ground if g.update(self.player, self.bullets)]
        self.effects = [e for e in self.effects if e.update()]
        self.craters = [c for c in self.craters if c.update()]
        self.items = [i for i in self.items if i.update()]

        # 폭탄 착탄
        alive = []
        for b in self.bombs:
            if b.update():
                alive.append(b)
            else:
                self.effects.append(Explosion(b.tx, b.ty, 0.8, ground=True))
                self.sfx.play("boom")
                for g in self.ground:
                    if g.hp > 0 and g.hit_by(b.tx, b.ty):
                        g.hp -= 1
                        g.flash = 6
                        if g.hp <= 0:
                            self.add_score(g.score)
                            self.effects.append(Explosion(g.x, g.y, 1.6 if g.kind == "fortress" else 1.1, ground=True))
                            self.craters.append(Crater(g.x, g.y))
                            if g.kind == "fortress":
                                self.sfx.play("bigboom")
                            # 레이더·요새는 반드시, 나머지는 가끔 아이템을 떨어뜨린다
                            self.maybe_drop_item(g.x, g.y, 1.0 if g.kind in ("radar", "fortress") else 0.15)
        self.bombs = alive
        self.ground = [g for g in self.ground if g.hp > 0]

        # 기관포 vs 공중 적
        for s in self.shots[:]:
            for e in self.air:
                if e.hp > 0 and s.rect.colliderect(e.rect):
                    e.hp -= 1
                    e.flash = 4
                    if s in self.shots:
                        self.shots.remove(s)
                    if e.hp <= 0:
                        self.add_score(e.score)
                        self.effects.append(Explosion(e.x, e.y, 1.5 if e.kind == "heavy" else 0.8))
                        self.sfx.play("bigboom" if e.kind == "heavy" else "boom")
                        self.maybe_drop_item(e.x, e.y, 1.0 if e.kind == "heavy" else 0.08)
                    else:
                        self.sfx.play("hit")
                    break
        self.air = [e for e in self.air if e.hp > 0]

        # 아이템 획득 (판정은 기체보다 넉넉하게)
        p = self.player
        grab = p.rect.inflate(16, 16)
        for it in self.items[:]:
            if grab.colliderect(it.rect):
                self.items.remove(it)
                self.collect_item()

        # 플레이어 피격
        if not p.invincible:
            pr = p.rect
            hit = any(pr.colliderect(b.rect) for b in self.bullets) or \
                any(pr.colliderect(e.rect.inflate(-6, -6)) for e in self.air)
            if hit:
                self.player_die()

    def add_score(self, pts):
        before = self.score // 20000
        self.score += pts
        if self.score // 20000 > before:  # 2만점마다 1UP
            self.lives += 1
            self.sfx.play("oneup")

    def player_die(self):
        p = self.player
        self.effects.append(Explosion(p.x, p.y, 2.0))
        self.sfx.play("die")
        self.bullets.clear()
        self.power = max(0, self.power - 1)  # 피격 시 파워 한 단계 하락
        self.lives -= 1
        if self.lives <= 0:
            self.hiscore = max(self.hiscore, self.score)
            self.state = "over"
        else:
            p.x, p.y = WIDTH / 2, HEIGHT - 120
            p.invincible = 150

    # --- 그리기 -----------------------------------------------------------
    def draw_text(self, text, font, color, center):
        shadow = font.render(text, True, BLACK)
        img = font.render(text, True, color)
        r = img.get_rect(center=center)
        self.screen.blit(shadow, r.move(2, 2))
        self.screen.blit(img, r)

    def locked(self):
        tx, ty = self.player.target
        return any(g.hit_by(tx, ty) for g in self.ground)

    def draw(self):
        s = self.screen
        self.terrain.draw(s)
        for c in self.craters:
            c.draw(s)
        for g in self.ground:
            g.draw(s, self.frame)
        for e in self.effects:
            if e.ground:
                e.draw(s)
        if self.state in ("play", "pause"):
            self.player.draw_sight(s, self.frame, self.locked())
        for b in self.bombs:
            b.draw(s)
        for it in self.items:
            it.draw(s, self.frame, self.item_label)
        for sh in self.shots:
            sh.draw(s)
        for e in self.air:
            e.draw(s, self.frame)
        if self.state in ("play", "pause"):
            self.player.draw(s, self.frame)
        for e in self.effects:
            if not e.ground:
                e.draw(s)
        for b in self.bullets:
            b.draw(s, self.frame)

        # HUD
        hud = pygame.Surface((WIDTH, 34), pygame.SRCALPHA)
        hud.fill((0, 0, 0, 140))
        s.blit(hud, (0, 0))
        s.blit(self.font.render(f"SCORE {self.score:07d}", True, WHITE), (10, 5))
        s.blit(self.font.render(f"HI {max(self.hiscore, self.score):07d}", True, YELLOW), (WIDTH // 2 - 50, 5))
        s.blit(self.font.render(f"LV {self.level}", True, CYAN), (WIDTH - 70, 5))
        for i in range(max(0, self.lives - 1)):
            x, y = 16 + i * 22, HEIGHT - 20
            pygame.draw.polygon(s, WHITE, [(x, y - 10), (x - 8, y + 6), (x + 8, y + 6)])
        power_img = self.font.render(f"SHOT x{SHOT_LEVELS[self.power]}", True, ORANGE)
        box = power_img.get_rect(bottomright=(WIDTH - 10, HEIGHT - 6)).inflate(10, 4)
        pygame.draw.rect(s, (0, 0, 0), box, border_radius=4)
        s.blit(power_img, power_img.get_rect(center=box.center))

        if self.state == "title":
            self.draw_overlay("SKY STRIKER", [
                "방향키: 이동   Z/Space: 기관포",
                "X: 폭탄 (조준점의 지상 목표 공격)",
                "P 아이템: 총알 2 → 4 → 8 → 16발",
                "P: 일시정지",
                "",
                "Enter 키를 눌러 시작",
            ])
        elif self.state == "over":
            self.draw_overlay("GAME OVER", [f"SCORE {self.score}", "", "Enter 키를 눌러 재시작"])
        elif self.state == "pause":
            self.draw_overlay("PAUSE", ["P 키를 눌러 계속"])

    def draw_overlay(self, title, lines):
        dim = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        dim.fill((0, 0, 20, 150))
        self.screen.blit(dim, (0, 0))
        self.draw_text(title, self.big_font, YELLOW, (WIDTH // 2, HEIGHT // 2 - 100))
        for i, line in enumerate(lines):
            self.draw_text(line, self.font, WHITE, (WIDTH // 2, HEIGHT // 2 - 20 + i * 32))

    # --- 메인 루프 --------------------------------------------------------
    def run(self):
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        return
                    if self.state in ("title", "over") and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        self.reset()
                        self.state = "play"
                        self.sfx.play("start")
                    elif self.state == "play" and event.key == pygame.K_x:
                        self.drop_bomb()
                    elif event.key == pygame.K_p and self.state in ("play", "pause"):
                        self.state = "pause" if self.state == "play" else "play"

            if self.state == "play":
                self.update()
            elif self.state in ("title", "over"):
                self.terrain.update()
                self.effects = [e for e in self.effects if e.update()]

            self.draw()
            pygame.display.flip()
            self.clock.tick(FPS)
            self.frame += 1


if __name__ == "__main__":
    Game().run()
    pygame.quit()
    sys.exit()
