"""뱀 게임 (Snake Game) - tkinter 사용 (추가 설치 불필요)

조작법:
  방향키 / WASD : 이동
  Space / P     : 일시정지
  R             : 게임 오버 후 재시작
  Esc           : 종료
"""

import random
import tkinter as tk

# ===== 설정 =====
CELL = 20             # 칸 크기(픽셀)
COLS = 30             # 가로 칸 수
ROWS = 24             # 세로 칸 수
START_SPEED = 120     # 시작 속도(ms, 작을수록 빠름)
MIN_SPEED = 50        # 최대 속도 제한
SPEED_STEP = 3        # 먹이를 먹을 때마다 빨라지는 정도

BG_COLOR = "#1e1e1e"
GRID_COLOR = "#262626"
SNAKE_HEAD = "#7CFC00"
SNAKE_BODY = "#32CD32"
FOOD_COLOR = "#FF4136"
TEXT_COLOR = "#FFFFFF"

DIRECTIONS = {
    "Up": (0, -1), "w": (0, -1), "W": (0, -1),
    "Down": (0, 1), "s": (0, 1), "S": (0, 1),
    "Left": (-1, 0), "a": (-1, 0), "A": (-1, 0),
    "Right": (1, 0), "d": (1, 0), "D": (1, 0),
}


class SnakeGame:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("뱀 게임")
        self.root.resizable(False, False)

        self.score_var = tk.StringVar()
        tk.Label(root, textvariable=self.score_var, font=("Malgun Gothic", 14, "bold"),
                 bg=BG_COLOR, fg=TEXT_COLOR, anchor="w", padx=10).pack(fill="x")

        self.canvas = tk.Canvas(root, width=COLS * CELL, height=ROWS * CELL,
                                bg=BG_COLOR, highlightthickness=0)
        self.canvas.pack()

        root.configure(bg=BG_COLOR)
        root.bind("<Key>", self.on_key)

        self.high_score = 0
        self.after_id = None
        self.reset()

    # ----- 게임 상태 -----
    def reset(self):
        cx, cy = COLS // 2, ROWS // 2
        self.snake = [(cx, cy), (cx - 1, cy), (cx - 2, cy)]
        self.direction = (1, 0)
        self.pending_dirs = []   # 빠른 연속 입력을 위한 방향 큐
        self.score = 0
        self.speed = START_SPEED
        self.game_over = False
        self.paused = False
        self.food = self.spawn_food()
        self.update_score()
        if self.after_id:
            self.root.after_cancel(self.after_id)
        self.tick()

    def spawn_food(self):
        free = [(x, y) for x in range(COLS) for y in range(ROWS)
                if (x, y) not in set(self.snake)]
        return random.choice(free) if free else None

    def update_score(self):
        self.score_var.set(f"점수: {self.score}    최고 점수: {self.high_score}")

    # ----- 입력 -----
    def on_key(self, event):
        key = event.keysym
        if key == "Escape":
            self.root.destroy()
            return
        if self.game_over:
            if key in ("r", "R"):
                self.reset()
            return
        if key in ("space", "p", "P"):
            self.paused = not self.paused
            self.draw()
            return
        if key in DIRECTIONS and not self.paused:
            new_dir = DIRECTIONS[key]
            last = self.pending_dirs[-1] if self.pending_dirs else self.direction
            # 반대 방향 / 같은 방향 입력 무시
            if new_dir != last and (new_dir[0] + last[0], new_dir[1] + last[1]) != (0, 0):
                if len(self.pending_dirs) < 3:
                    self.pending_dirs.append(new_dir)

    # ----- 게임 루프 -----
    def tick(self):
        if not self.game_over and not self.paused:
            self.step()
        self.draw()
        self.after_id = self.root.after(self.speed, self.tick)

    def step(self):
        if self.pending_dirs:
            self.direction = self.pending_dirs.pop(0)

        hx, hy = self.snake[0]
        dx, dy = self.direction
        new_head = (hx + dx, hy + dy)

        will_eat = new_head == self.food
        # 꼬리는 이번 턴에 이동하므로 먹지 않을 때는 충돌 검사에서 제외
        body = self.snake if will_eat else self.snake[:-1]

        if (not (0 <= new_head[0] < COLS and 0 <= new_head[1] < ROWS)
                or new_head in body):
            self.game_over = True
            self.high_score = max(self.high_score, self.score)
            self.update_score()
            return

        self.snake.insert(0, new_head)
        if will_eat:
            self.score += 10
            self.speed = max(MIN_SPEED, self.speed - SPEED_STEP)
            self.food = self.spawn_food()
            self.update_score()
            if self.food is None:  # 화면을 가득 채움 = 승리
                self.game_over = True
                self.high_score = max(self.high_score, self.score)
                self.update_score()
        else:
            self.snake.pop()

    # ----- 그리기 -----
    def draw(self):
        c = self.canvas
        c.delete("all")

        for x in range(0, COLS * CELL, CELL):
            c.create_line(x, 0, x, ROWS * CELL, fill=GRID_COLOR)
        for y in range(0, ROWS * CELL, CELL):
            c.create_line(0, y, COLS * CELL, y, fill=GRID_COLOR)

        if self.food:
            fx, fy = self.food
            c.create_oval(fx * CELL + 3, fy * CELL + 3,
                          (fx + 1) * CELL - 3, (fy + 1) * CELL - 3,
                          fill=FOOD_COLOR, outline="")

        for i, (x, y) in enumerate(self.snake):
            color = SNAKE_HEAD if i == 0 else SNAKE_BODY
            c.create_rectangle(x * CELL + 1, y * CELL + 1,
                               (x + 1) * CELL - 1, (y + 1) * CELL - 1,
                               fill=color, outline="")

        mid_x, mid_y = COLS * CELL // 2, ROWS * CELL // 2
        if self.game_over:
            title = "승리!" if self.food is None else "게임 오버"
            c.create_text(mid_x, mid_y - 20, text=title, fill=TEXT_COLOR,
                          font=("Malgun Gothic", 32, "bold"))
            c.create_text(mid_x, mid_y + 25, text=f"점수: {self.score}   (R: 재시작, Esc: 종료)",
                          fill=TEXT_COLOR, font=("Malgun Gothic", 13))
        elif self.paused:
            c.create_text(mid_x, mid_y, text="일시정지 (Space)", fill=TEXT_COLOR,
                          font=("Malgun Gothic", 24, "bold"))


def main():
    root = tk.Tk()
    SnakeGame(root)
    root.mainloop()


if __name__ == "__main__":
    main()
