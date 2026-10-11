"""Touch toolbar for the test REAPER: 156 px icons (~9 mm on a Galaxy A15 through the app) + reaper-menu.ini.
Toolbar 1 = ARRANGE, Toolbar 2 = EDIT (docked at the top, switched from the app rail or the ARR/EDIT buttons);
Main toolbar (box above the track list) = context switch + SAVE/TALL."""
from PIL import Image, ImageDraw, ImageFont
import os, sys
RP = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser('~/.config/REAPER')
F = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
S = 156
I = {  # name: (label, glyph, command, colour)
 'play': ('PLAY', '▶', 1007, '#2e7d32'), 'stop': ('STOP', '■', 1016, '#455a64'), 'rec': ('REC', '●', 1013, '#c62828'),
 'loop': ('LOOP', '⟲', 1068, '#6a1b9a'), 'undo': ('UNDO', '↶', 40029, '#37474f'), 'redo': ('REDO', '↷', 40030, '#37474f'),
 'split': ('SPLIT', '✂', 40012, '#ef6c00'), 'del': ('DELETE', '✖', 40697, '#8e2424'), 'zinh': ('ZOOM', '↔+', 1012, '#1565c0'),
 'zouth': ('ZOOM', '↔−', 1011, '#1565c0'), 'zinv': ('ZOOM', '↕+', 40111, '#00838f'), 'zoutv': ('ZOOM', '↕−', 40112, '#00838f'),
 'fit': ('FIT', '⤢', 40295, '#1565c0'), 'trk': ('+TRACK', '≡', 40001, '#4e342e'), 'arm': ('ARM', '◉', 9, '#b71c1c'),
 'click': ('CLICK', '♩', 40364, '#5d4037'), 'mix': ('MIXER', '▥', 40078, '#283593'), 'midi': ('MIDI', '♪', 40153, '#00695c'),
 'save': ('SAVE', '⬇', 40026, '#2e7d32'), 'mark': ('MARKER', '⚑', 40157, '#f9a825'), 'selall': ('SEL ALL', '▦', 40182, '#455a64'),
 'tall': ('TALL', '⇕', 40113, '#00838f'), 'unsel': ('UNSEL', '▢', 40289, '#455a64'), 'snap': ('SNAP', '⌗', 1157, '#6d4c41'),
 'arr': ('◂ ARRANGE', '▤', 41105, '#0d47a1'), 'edit': ('EDIT ▸', '✎', 41106, '#bf360c'),
}
# The context switch lives on the docked toolbar itself: pressing it makes that toolbar the active one, so
# "Toolbars: Switch to toolbar N" swaps the docked strip in place.
ARRANGE = ['edit', 'play', 'stop', 'rec', 'undo', 'redo', 'zinh', 'zouth', 'zinv', 'zoutv', 'fit', 'trk', 'arm', 'click']
EDIT = ['arr', 'undo', 'redo', 'split', 'del', 'snap', 'selall', 'unsel', 'mark', 'loop', 'midi', 'mix', 'tall']
MAIN = ['save', 'mix', 'fit', 'tall']

def icon(path, label, glyph, col):
    im = Image.new('RGBA', (S * 3, S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    for i, f in enumerate([1.0, 1.25, 0.7]):
        c = tuple(min(255, int(int(col[j:j + 2], 16) * f)) for j in (1, 3, 5)); o = i * S; m = 4
        d.rounded_rectangle([o + m, m, o + S - m - 1, S - m - 1], radius=S // 8, fill=c + (255,), outline=(255, 255, 255, 90), width=2)
        d.text((o + S / 2, S * 0.40), glyph, font=ImageFont.truetype(F, int(S * 0.42)), fill='white', anchor='mm')
        d.text((o + S / 2, S * 0.80), label, font=ImageFont.truetype(F, int(S * 0.19) if len(label) < 6 else int(S * 0.14)), fill='white', anchor='mm')
    im.save(path)

for sub in ('', '150', '200'):
    dd = os.path.join(RP, 'Data/toolbar_icons', sub); os.makedirs(dd, exist_ok=True)
    for k, (l, g, c, col) in I.items():
        icon(os.path.join(dd, f'fyah_{k}.png'), l, g, col)

def section(title, name, keys):
    out = [f'[{title}]']
    for i, k in enumerate(keys):
        out += [f'item_{i}={I[k][2]} {I[k][0]}', f'icon_{i}=fyah_{k}.png']
    return out + [f'title={name}', '']
ini = section('Main toolbar', 'Fyah Context', MAIN) + section('Floating toolbar 1', 'Fyah ARRANGE', ARRANGE) + section('Floating toolbar 2', 'Fyah EDIT', EDIT)
open(os.path.join(RP, 'reaper-menu.ini'), 'w').write('\n'.join(ini))
print('ok', len(ARRANGE), len(EDIT))
