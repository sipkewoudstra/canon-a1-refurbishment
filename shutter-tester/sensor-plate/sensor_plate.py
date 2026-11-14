#!/usr/bin/env python3
"""
Shutter-tester sensor plate for the Canon A-1 (any 24x36 SLR with a similar gate).

Holds two Vishay BPW34 photodiodes behind 1 mm pinholes, 30 mm apart, centred on
the frame. The plate drops between the camera's outer film-guide rails (which are
just over 35 mm apart, to guide 35 mm film) and rests on the inner rails, so it
centres itself vertically and its front face sits at the film plane.

Print FRONT FACE DOWN (the face with the pinholes on the bed), in black filament.
Coordinates: X across the frame as seen from the BACK of the camera (A = left),
Y up, Z = thickness (z=0 is the front face, which touches the film rails).

The part is a height field (every column is solid from z=0 up to h(x,y)), meshed on
a rectilinear grid through all feature edges, so the output is watertight with no
boolean library needed. Run:  python3 sensor_plate.py  -> writes the STL files.
"""
import struct, sys, os, math
from collections import Counter

# ------------------------------------------------------------------ parameters
P = dict(
    W=42.0,          # plate width: 36 mm gate + 3 mm each side (keeps clear of the sprocket)
    H=34.6,          # plate height: must drop between the outer film rails (35 mm film + clearance)
    T=4.2,           # total thickness
    front=0.8,       # front wall in front of the photodiode (pinhole goes through this)
    spacing=30.0,    # sensor A to sensor B, centre to centre
    pocket=5.8,      # square pocket: BPW34 body is 5.4 x 4.3 x 3.2 mm, fits either way round
    pin=1.0,         # pinhole (square) side length
    band_w=3.0,      # rubber-band notch width (top and bottom edge, centre)
    band_d=1.5,      # rubber-band notch depth
    mark=2.0,        # corner notch at bottom-left (back view) marks channel A
    # --- electronics bay (open-top box on the back for a perfboard with the comparator circuit)
    bay=False,
    wall=1.6,        # bay wall thickness
    ledge=1.0,       # ledge width the perfboard rests on
    ledge_z=7.5,     # height of the ledge = underside of the perfboard (room for the diode leads to bend up)
    wall_z=11.5,     # top of the bay walls
    cable_x=(5.0, 11.0),  # wire exit in the top wall (back view), cut down to board top
    board_t=1.6,     # perfboard thickness
    trim_slot=(-14.2, -6.1),    # openings in the left and right bay walls (y range) that the ends of the two 3006P
                                # trimmer bodies and their screws pass through (body 4.83 deep + ~1.6 mm each side),
                                # centred between perfboard rows 10 and 11
    trim_floor=8.6,             # bottom of those openings: 0.5 mm under the board top, so the overhanging body clears
    # --- bay version: photodiodes soldered flat on the copper side of the perfboard (legs B2/B4 and N2/N4)
    diode_x=15.24,              # diode centre = perfboard column B / N (12 columns apart = 30.48 mm)
    diode_y=8.89,               # diode centre = perfboard row 3, 3.5 rows above the board centre
    pin_bay=1.5,                # pinhole side (square) under each diode; keep <= half the 1/1000 slit (~3 mm)
    pocket_bay=6.6,             # square pocket under each diode, floor thinned to `front` so the window sits close to the pinhole
)

def build(p):
    W, H, T = p["W"], p["H"], p["T"]
    hx, hy = W / 2, H / 2
    bay = p["bay"]
    if bay:                                 # diodes on the board: pinholes + pockets centred under them
        sx, cy = p["diode_x"], p["diode_y"]
        pk, pn = p["pocket_bay"] / 2, p["pin_bay"] / 2
    else:                                   # diodes loose in the pockets, centred on the frame
        sx, cy = p["spacing"] / 2, 0.0
        pk, pn = p["pocket"] / 2, p["pin"] / 2
    centres = (-sx, sx)                     # A, B

    wl, ld = p["wall"], p["ledge"]
    band_d = wl if bay else p["band_d"]
    slot_top = (hy - wl - ld) if bay else hy           # slot stops at the ledge in bay mode

    xs = {-hx, hx, -p["band_w"] / 2, p["band_w"] / 2, -hx + p["mark"]}
    ys = {-hy, hy, hy - band_d, -hy + band_d, -hy + p["mark"], cy - pk, cy + pk, cy - pn, cy + pn}
    if bay:
        for s_ in (1, -1):
            xs |= {s_ * (hx - wl), s_ * (hx - wl - ld)}
            ys |= {s_ * (hy - wl), s_ * (hy - wl - ld)}
        xs |= set(p["cable_x"])
        ys |= set(p["trim_slot"])
    for c in centres:
        xs |= {c - pk, c + pk, c - pn, c + pn}
    xs, ys = sorted(xs), sorted(ys)

    def height(x, y):
        # cell-centre test
        if abs(x) < p["band_w"] / 2 and abs(y) > hy - band_d:
            return 0.0                                   # rubber-band notches
        if x < -hx + p["mark"] and y < -hy + p["mark"]:
            return 0.0                                   # 'A' marker corner
        if bay:
            if abs(x) > hx - wl or abs(y) > hy - wl:     # bay wall
                if p["cable_x"][0] < x < p["cable_x"][1] and y > hy - wl:
                    return p["ledge_z"] + p["board_t"]   # wire exit, down to board top
                if abs(x) > hx - wl and p["trim_slot"][0] < y < p["trim_slot"][1]:
                    return p["trim_floor"]               # trimmer openings: body end + screw pass through the wall
                return p["wall_z"]
            if abs(x) > hx - wl - ld or abs(y) > hy - wl - ld:
                return p["ledge_z"]                      # ledge for the perfboard
        for c in centres:
            if abs(x - c) < pn and abs(y - cy) < pn:
                return 0.0                               # pinhole
            if bay:
                if abs(x - c) < pk and abs(y - cy) < pk: # pocket under the board-mounted diode
                    return p["front"]
            elif abs(x - c) < pk and -pk < y < slot_top: # pocket + lead slot
                return p["front"]
        return T

    nx, ny = len(xs) - 1, len(ys) - 1
    h = [[height((xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2) for j in range(ny)] for i in range(nx)]
    return xs, ys, h

def mesh(xs, ys, h):
    nx, ny = len(xs) - 1, len(ys) - 1
    H = lambda i, j: h[i][j] if 0 <= i < nx and 0 <= j < ny else 0.0
    tris = []

    # heights present on each vertical grid line (for T-junction-free walls)
    def zs_at(i, j):              # grid vertex (xs[i], ys[j]); cells around it
        s = {0.0}
        for di in (-1, 0):
            for dj in (-1, 0):
                s.add(H(i + di, j + dj))
        return sorted(s)

    def quad(a, b, c, d):        # counter-clockwise seen from outside
        tris.append((a, b, c)); tris.append((a, c, d))

    for i in range(nx):
        for j in range(ny):
            z = h[i][j]
            if z <= 0: continue
            x0, x1, y0, y1 = xs[i], xs[i + 1], ys[j], ys[j + 1]
            quad((x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z))      # top (+z)
            quad((x0, y0, 0), (x0, y1, 0), (x1, y1, 0), (x1, y0, 0))      # bottom (-z)

    def wall(p0, p1, lo, hi, zl, zr):
        """Vertical wall along p0->p1 (2D), from z=lo to z=hi, outward normal to the
        right of p0->p1 when seen from above. zl/zr: split heights at p0/p1."""
        L = [z for z in zl if lo <= z <= hi]       # heights at p0
        R = [z for z in zr if lo <= z <= hi]       # heights at p1
        # zipper between column p0 (L) and column p1 (R), bottom to top
        a, b = 0, 0
        P0 = lambda k: (p0[0], p0[1], L[k]); P1 = lambda k: (p1[0], p1[1], R[k])
        while a < len(L) - 1 or b < len(R) - 1:
            if b < len(R) - 1 and (a == len(L) - 1 or R[b + 1] <= L[a + 1]):
                tris.append((P0(a), P1(b), P1(b + 1))); b += 1
            else:
                tris.append((P0(a), P1(b), P0(a + 1))); a += 1

    # walls between cell (i-1,j) and (i,j): plane x = xs[i]
    for i in range(nx + 1):
        for j in range(ny):
            zl, zr = H(i - 1, j), H(i, j)
            if zl == zr: continue
            lo, hi = sorted((zl, zr))
            pa, pb = (xs[i], ys[j]), (xs[i], ys[j + 1])
            za, zb = zs_at(i, j), zs_at(i, j + 1)
            if zl > zr:   # solid on the left -> normal +x -> walk +y (right of +y is +x)
                wall(pa, pb, lo, hi, za, zb)
            else:         # solid on the right -> normal -x: walk -y
                wall(pb, pa, lo, hi, zb, za)
    # walls between cell (i,j-1) and (i,j): plane y = ys[j]
    for j in range(ny + 1):
        for i in range(nx):
            zd, zu = H(i, j - 1), H(i, j)
            if zd == zu: continue
            lo, hi = sorted((zd, zu))
            pa, pb = (xs[i], ys[j]), (xs[i + 1], ys[j])
            za, zb = zs_at(i, j), zs_at(i + 1, j)
            if zd > zu:   # solid below -> normal +y: walk -x (right of -x is +y)
                wall(pb, pa, lo, hi, zb, za)
            else:         # solid above -> normal -y: walk +x
                wall(pa, pb, lo, hi, za, zb)
    return tris

def check(tris):
    """Watertight + consistently oriented: every directed edge appears once and its
    reverse appears once."""
    key = lambda v: tuple(round(c, 6) for c in v)
    d = Counter()
    for t in tris:
        a, b, c = map(key, t)
        for e in ((a, b), (b, c), (c, a)):
            d[e] += 1
    bad = [e for e, n in d.items() if n != 1 or d.get((e[1], e[0]), 0) != 1]
    # signed volume
    vol = 0.0
    for a, b, c in tris:
        vol += (a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0]) + a[2] * (b[0] * c[1] - b[1] * c[0])) / 6
    return len(bad), vol

def write_stl(path, tris, name):
    with open(path, "wb") as f:
        f.write(name.encode()[:80].ljust(80, b" "))
        f.write(struct.pack("<I", len(tris)))
        for a, b, c in tris:
            u = [b[k] - a[k] for k in range(3)]; v = [c[k] - a[k] for k in range(3)]
            n = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]
            l = math.sqrt(sum(x * x for x in n)) or 1.0
            f.write(struct.pack("<3f", *[x / l for x in n]))
            for p_ in (a, b, c): f.write(struct.pack("<3f", *p_))
            f.write(b"\0\0")

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "."
    variants = [("A-1 sensor plate.stl", {}),
                ("A-1 sensor plate (H34.0 loose).stl", {"H": 34.0}),
                ("A-1 sensor plate + comparator bay.stl", {"bay": True}),
                ("A-1 sensor plate + comparator bay (H34.0 loose).stl", {"bay": True, "H": 34.0})]
    for fname, over in variants:
        p = dict(P, **over)
        xs, ys, h = build(p)
        tris = mesh(xs, ys, h)
        nbad, vol = check(tris)
        write_stl(os.path.join(out, fname), tris, "A-1 shutter tester sensor plate")
        print(f"{fname}: {len(tris)} triangles, bad edges {nbad}, volume {vol:.1f} mm3")
