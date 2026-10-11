"""CI-only stand-in for the REAPER window: logs every X11 click/scroll/key it receives."""
import sys, tkinter as tk
LOG = sys.argv[1]; W, H = int(sys.argv[2]), int(sys.argv[3])
root = tk.Tk(); root.geometry(f'{W}x{H}+0+0'); root.configure(bg='#2b2b33')
tk.Label(root, text='FYAH CI TEST WINDOW  (stands in for REAPER)', font=('DejaVu Sans', 48), fg='white', bg='#2b2b33').pack(expand=True, fill='both')
for x in range(0, W, 195):
    tk.Frame(root, bg=('#bb3341' if (x // 195) % 2 else '#4a90d9'), width=12, height=H).place(x=x, y=0)
def log(kind):
    def f(e):
        with open(LOG, 'a') as fh:
            fh.write(f'{kind} {getattr(e, "x_root", "")} {getattr(e, "y_root", "")} {getattr(e, "keysym", "")}\n')
    return f
for ev, k in (('<Button-1>', 'LEFT'), ('<Button-2>', 'MIDDLE'), ('<Button-3>', 'RIGHT'), ('<Button-4>', 'SCROLL_UP'), ('<Button-5>', 'SCROLL_DOWN'), ('<KeyPress>', 'KEY')):
    root.bind_all(ev, log(k))
root.focus_force()
root.mainloop()
