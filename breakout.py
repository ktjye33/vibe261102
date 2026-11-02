import tkinter as tk
import random


class BreakoutGame:
    def __init__(self, root):
        self.root = root
        self.root.title("Breakout")
        self.root.resizable(False, False)

        self.width = 800
        self.height = 600
        self.running = False
        self.score = 0
        self.lives = 3
        self.left_pressed = False
        self.right_pressed = False

        self.canvas = tk.Canvas(root, width=self.width, height=self.height, bg="#101820")
        self.canvas.pack()

        self.status = self.canvas.create_text(
            400, 20, text="", fill="white", font=("Arial", 16, "bold")
        )
        self.message = self.canvas.create_text(
            400, 300, text="스페이스바를 눌러 시작", fill="white",
            font=("Arial", 24, "bold")
        )

        self.paddle = self.canvas.create_rectangle(350, 550, 450, 565, fill="#F2A900")
        self.ball = self.canvas.create_oval(390, 535, 410, 555, fill="#FFFFFF")
        self.ball_dx = 4
        self.ball_dy = -4

        self.bricks = []
        self.create_bricks()
        self.update_status()

        root.bind("<Left>", lambda event: self.set_key("left", True))
        root.bind("<KeyRelease-Left>", lambda event: self.set_key("left", False))
        root.bind("<Right>", lambda event: self.set_key("right", True))
        root.bind("<KeyRelease-Right>", lambda event: self.set_key("right", False))
        root.bind("a", lambda event: self.set_key("left", True))
        root.bind("<KeyRelease-a>", lambda event: self.set_key("left", False))
        root.bind("d", lambda event: self.set_key("right", True))
        root.bind("<KeyRelease-d>", lambda event: self.set_key("right", False))
        root.bind("<space>", lambda event: self.start_or_restart())

        self.game_loop()

    def create_bricks(self):
        colors = ["#E63946", "#F77F00", "#F2CC8F", "#2A9D8F", "#457B9D"]
        brick_width = 68
        brick_height = 24
        gap = 6
        start_x = 40
        start_y = 70

        for row in range(5):
            for column in range(10):
                x1 = start_x + column * (brick_width + gap)
                y1 = start_y + row * (brick_height + gap)
                brick = self.canvas.create_rectangle(
                    x1, y1, x1 + brick_width, y1 + brick_height,
                    fill=colors[row], outline="#101820"
                )
                self.bricks.append(brick)

    def set_key(self, direction, pressed):
        if direction == "left":
            self.left_pressed = pressed
        else:
            self.right_pressed = pressed

    def start_or_restart(self):
        if not self.running:
            if not self.bricks:
                self.reset_game()
            elif self.lives <= 0:
                self.reset_game()
            else:
                self.running = True
                self.canvas.itemconfigure(self.message, text="")
                self.launch_ball()

    def launch_ball(self):
        self.ball_dx = random.choice((-4, -3, 3, 4))
        self.ball_dy = -4

    def reset_game(self):
        for brick in self.bricks:
            self.canvas.delete(brick)
        self.bricks.clear()
        self.create_bricks()
        self.score = 0
        self.lives = 3
        self.reset_positions()
        self.running = True
        self.canvas.itemconfigure(self.message, text="")
        self.launch_ball()
        self.update_status()

    def reset_positions(self):
        self.canvas.coords(self.paddle, 350, 550, 450, 565)
        self.canvas.coords(self.ball, 390, 535, 410, 555)

    def update_status(self):
        self.canvas.itemconfigure(
            self.status, text=f"점수: {self.score}    생명: {self.lives}"
        )

    def move_paddle(self):
        dx = 0
        if self.left_pressed:
            dx -= 8
        if self.right_pressed:
            dx += 8

        x1, _, x2, _ = self.canvas.coords(self.paddle)
        if 0 <= x1 + dx and x2 + dx <= self.width:
            self.canvas.move(self.paddle, dx, 0)

    def move_ball(self):
        self.canvas.move(self.ball, self.ball_dx, self.ball_dy)
        x1, y1, x2, y2 = self.canvas.coords(self.ball)

        if x1 <= 0 or x2 >= self.width:
            self.ball_dx *= -1
        if y1 <= 0:
            self.ball_dy *= -1

        paddle_coords = self.canvas.coords(self.paddle)
        if self.ball_dy > 0 and self.overlaps(self.canvas.coords(self.ball), paddle_coords):
            self.ball_dy *= -1
            center_x = (x1 + x2) / 2
            paddle_center = (paddle_coords[0] + paddle_coords[2]) / 2
            self.ball_dx = (center_x - paddle_center) / 10

        for brick in list(self.bricks):
            if self.overlaps(self.canvas.coords(self.ball), self.canvas.coords(brick)):
                self.canvas.delete(brick)
                self.bricks.remove(brick)
                self.ball_dy *= -1
                self.score += 10
                self.update_status()
                break

        if not self.bricks:
            self.running = False
            self.canvas.itemconfigure(self.message, text="승리! 스페이스바로 다시 시작")
        elif y2 >= self.height:
            self.lives -= 1
            self.update_status()
            if self.lives <= 0:
                self.running = False
                self.canvas.itemconfigure(self.message, text="게임 오버! 스페이스바로 다시 시작")
            else:
                self.running = False
                self.reset_positions()
                self.canvas.itemconfigure(self.message, text="스페이스바를 눌러 계속")

    @staticmethod
    def overlaps(a, b):
        return a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]

    def game_loop(self):
        self.move_paddle()
        if self.running:
            self.move_ball()
        self.root.after(16, self.game_loop)


def main():
    root = tk.Tk()
    BreakoutGame(root)
    root.mainloop()


if __name__ == "__main__":
    main()
