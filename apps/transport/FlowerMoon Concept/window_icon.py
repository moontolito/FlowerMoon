"""Full moon window icon, drawn at native icon sizes."""
import tkinter as tk


def create_icon(root, size):
    image = tk.PhotoImage(master=root, width=size, height=size)
    for y in range(size):
        for x in range(size):
            px, py = (x + .5) * 64 / size, (y + .5) * 64 / size
            color = None
            # Centered full moon; surrounding pixels stay transparent.
            if (px - 32) ** 2 + (py - 32) ** 2 <= 26 ** 2:
                color = '#B779C2'
            if color:
                image.put(color, (x, y))
    return image
