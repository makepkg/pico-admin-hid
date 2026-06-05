"""
screensaver.py — экранные заставки для SSD1306 128×32.
Поддерживает 3 анимации: tesseract, starfield, matrix.
"""

import math
import random

def draw_line(bitmap, x0, y0, x1, y1, color):
    """Алгоритм Брезенхема для рисования линий на Bitmap."""
    x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy

    while True:
        if 0 <= x0 < 128 and 0 <= y0 < 32:
            bitmap[x0, y0] = color

        if x0 == x1 and y0 == y1:
            break

        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x0 += sx
        if e2 < dx:
            err += dx
            y0 += sy


class ScreensaverManager:
    def __init__(self, bitmap, name="tesseract"):
        self.bitmap = bitmap
        self.name = name
        self.width = 128
        self.height = 32
        self._init_animation()

    def _init_animation(self):
        if self.name == "tesseract":
            # 16 вершин гиперкуба
            self.vertices = []
            for i in range(16):
                x = 1.0 if (i & 1) else -1.0
                y = 1.0 if (i & 2) else -1.0
                z = 1.0 if (i & 4) else -1.0
                w = 1.0 if (i & 8) else -1.0
                self.vertices.append([x, y, z, w])

            # 32 ребра гиперкуба
            self.edges = []
            for i in range(16):
                for j in range(i + 1, 16):
                    if bin(i ^ j).count('1') == 1:
                        self.edges.append((i, j))

            # Углы и скорости вращения
            self.angle_xy = 0.0
            self.angle_xz = 0.0
            self.angle_xw = 0.0
            self.angle_yz = 0.0
            
            self.speed_xy = 0.03
            self.speed_xz = 0.02
            self.speed_xw = 0.015
            self.speed_yz = 0.025
            
        elif self.name == "starfield":
            # 30 звезд: [x, y, z]
            self.stars = []
            for _ in range(30):
                self.stars.append([
                    random.randint(-100, 100),
                    random.randint(-30, 30),
                    random.randint(10, 150)
                ])
                
        elif self.name == "matrix":
            # 21 колонка
            self.cols = 21
            self.col_width = 6
            # Координата Y и скорость для каждого дождя
            self.drops_y = [float(random.randint(-40, 0)) for _ in range(self.cols)]
            self.drops_speed = [random.uniform(0.6, 1.5) for _ in range(self.cols)]

    def draw_frame(self):
        """Очищает экран и рисует следующий кадр анимации."""
        self.bitmap.fill(0)

        if self.name == "tesseract":
            self.angle_xy += self.speed_xy
            self.angle_xz += self.speed_xz
            self.angle_xw += self.speed_xw
            self.angle_yz += self.speed_yz

            projected = []
            w_distance = 3.0
            camera_distance = 4.0

            # Поворот и проекция
            for v in self.vertices:
                x, y, z, w = v[0], v[1], v[2], v[3]

                # XY
                cosA, sinA = math.cos(self.angle_xy), math.sin(self.angle_xy)
                x, y = x * cosA - y * sinA, x * sinA + y * cosA

                # XZ
                cosA, sinA = math.cos(self.angle_xz), math.sin(self.angle_xz)
                x, z = x * cosA - z * sinA, x * sinA + z * cosA

                # XW
                cosA, sinA = math.cos(self.angle_xw), math.sin(self.angle_xw)
                x, w = x * cosA - w * sinA, x * sinA + w * cosA

                # YZ
                cosA, sinA = math.cos(self.angle_yz), math.sin(self.angle_yz)
                y, z = y * cosA - z * sinA, y * sinA + z * cosA

                # Проекция 4D -> 3D
                scale_3d = w_distance / (w_distance - w) if (w_distance - w) != 0 else 1.0
                x3d, y3d, z3d = x * scale_3d, y * scale_3d, z * scale_3d

                # Проекция 3D -> 2D
                denom = camera_distance + z3d
                if denom < 0.1:
                    denom = 0.1
                scale_2d = camera_distance / denom
                scale_2d = max(0.1, min(scale_2d, 5.0))

                px = int(64 + x3d * scale_2d * 11)
                py = int(16 + y3d * scale_2d * 11)
                projected.append((px, py))

            # Отрисовка ребер
            for edge in self.edges:
                p1 = projected[edge[0]]
                p2 = projected[edge[1]]
                # Простой клиппинг перед отрисовкой
                if not ((p1[0] < -10 and p2[0] < -10) or (p1[0] > 138 and p2[0] > 138) or
                        (p1[1] < -10 and p2[1] < -10) or (p1[1] > 42 and p2[1] > 42)):
                    draw_line(self.bitmap, p1[0], p1[1], p2[0], p2[1], 1)

        elif self.name == "starfield":
            for star in self.stars:
                star[2] -= 3  # приближаем звезду
                if star[2] <= 3:
                    star[0] = random.randint(-100, 100)
                    star[1] = random.randint(-30, 30)
                    star[2] = 150

                px = int(64 + (star[0] * 35) / star[2])
                py = int(16 + (star[1] * 35) / star[2])

                if 0 <= px < 128 and 0 <= py < 32:
                    self.bitmap[px, py] = 1
                    # Если звезда близко, сделаем ее больше
                    if star[2] < 40:
                        if px + 1 < 128: self.bitmap[px + 1, py] = 1
                        if py + 1 < 32: self.bitmap[px, py + 1] = 1

        elif self.name == "matrix":
            for col in range(self.cols):
                self.drops_y[col] += self.drops_speed[col]
                if self.drops_y[col] >= 35:
                    self.drops_y[col] = float(random.randint(-20, 0))
                    self.drops_speed[col] = random.uniform(0.6, 1.5)

                x = col * self.col_width + 2
                y_curr = int(self.drops_y[col])

                # Рисуем падающий хвост
                for tail in range(6):
                    y_draw = y_curr - tail
                    if 0 <= y_draw < 32:
                        # Делаем хвост мерцающим/пунктирным
                        if tail == 0 or (tail > 0 and random.random() > 0.3):
                            self.bitmap[x, y_draw] = 1
