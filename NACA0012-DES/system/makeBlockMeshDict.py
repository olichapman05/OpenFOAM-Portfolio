#!/usr/bin/env python3
"""Generate system/blockMeshDict for a 2D O-grid around a NACA 0012 airfoil.

Topology: 4 blocks arranged around the airfoil (front/top/back/bottom quadrants).
Inner boundary = airfoil surface (upper and lower spline halves, LE->TE).
Outer boundary = circle of radius OUTER_RADIUS chords, split into 4 arcs
matching the 4 inner splits (front stagnation, top, rear stagnation, bottom).

Run:  python3 system/makeBlockMeshDict.py
Output: system/blockMeshDict
"""
import math

# ---------------------------------------------------------------------------
# Parameters (edit here if the mesh needs to be adjusted)
# ---------------------------------------------------------------------------
CHORD = 1.0                 # airfoil chord length [m]
THICKNESS = 0.12            # NACA 00XX thickness (0012 -> 0.12)
N_SURFACE = 80               # number of points along each of upper/lower spline (LE->TE)
OUTER_RADIUS = 20.0 * CHORD  # far-field circle radius [m]
N_RADIAL = 40                 # cells from airfoil surface to outer boundary
RADIAL_GRADING = 400.0        # expansion ratio (last/first cell size) - clusters cells near wall
N_SPANWISE_ALONG_SURFACE = 60 # cells along each quarter of the O-grid (LE-top, top-TE, TE-bot, bot-LE)
FIRST_LAYER_HEIGHT = 5e-4     # approx first cell height off the airfoil surface [m], for y+~1 guidance

# Split fraction (in surface-arclength-like parameter t in [0,1] along upper/lower halves)
# where the O-grid block boundaries meet the airfoil. t=0 is LE, t=1 is TE for each half.
# We use x/c directly (cosine-spaced) as the parameter since NACA thickness is defined vs x/c.


def naca0012_half_thickness(x):
    """NACA 00xx thickness distribution using the closed-trailing-edge
    coefficient (-0.1036 instead of the classic open-TE -0.1015), so that
    yt(x=1) = 0 exactly and the upper/lower splines meet at a single TE
    point (required since both splines share one 'te' block vertex)."""
    t = THICKNESS
    return 5 * t * (
        0.2969 * math.sqrt(x)
        - 0.1260 * x
        - 0.3516 * x**2
        + 0.2843 * x**3
        - 0.1036 * x**4
    )


def cosine_spacing(n):
    """n points from 0 to 1, cosine-clustered near both ends (LE and TE)."""
    return [0.5 * (1 - math.cos(math.pi * i / (n - 1))) for i in range(n)]


def airfoil_surface_points(n):
    """Return (upper, lower) point lists, each length n, ordered LE(x=0) -> TE(x=CHORD).
    Points are (x, y, 0)."""
    xs = [CHORD * s for s in cosine_spacing(n)]
    upper = []
    lower = []
    for x in xs:
        xc = x / CHORD
        yt = CHORD * naca0012_half_thickness(xc)
        upper.append((x, yt, 0.0))
        lower.append((x, -yt, 0.0))
    return upper, lower


def outer_circle_point(angle_deg):
    a = math.radians(angle_deg)
    # Circle centered at (CHORD/2, 0) so it is roughly centered on the airfoil
    cx, cy = CHORD / 2.0, 0.0
    return (cx + OUTER_RADIUS * math.cos(a), cy + OUTER_RADIUS * math.sin(a), 0.0)


def fmt(p):
    return f"({p[0]:.8f} {p[1]:.8f} {p[2]:.8f})"


def main():
    upper, lower = airfoil_surface_points(N_SURFACE)
    # Airfoil corner points used as block vertices:
    #   LE  = upper[0]  == lower[0]   (x=0)
    #   TE  = upper[-1] == lower[-1]  (x=CHORD)
    # We build a genuine O-grid with 4 blocks by picking a mid-point on the
    # upper and lower spline to act as "top" and "bottom" block-corner nodes,
    # so each block spans a quarter of the airfoil perimeter and a quarter of
    # the outer circle: front (around LE), top, back (around TE), bottom.
    mid_idx = N_SURFACE // 2  # index of the max-thickness-ish station

    le = upper[0]
    te = upper[-1]
    top_mid = upper[mid_idx]
    bot_mid = lower[mid_idx]

    # Outer circle corner points at matching angular stations: front(180deg
    # upstream of LE-ish direction is not meaningful for airfoil since airfoil
    # isn't circular) -- instead place outer corners at 0/90/180/270 deg
    # around the circle centered at mid-chord, which pairs naturally with
    # front/top/back/bottom blocks.
    outer_front = outer_circle_point(180.0)   # upstream, matches LE side
    outer_top = outer_circle_point(90.0)      # matches top_mid
    outer_back = outer_circle_point(0.0)      # downstream, matches TE side
    outer_bot = outer_circle_point(270.0)     # matches bot_mid

    # z-thickness for the 2D extrusion (front/back patches are 'empty')
    dz = 0.1 * CHORD
    def z(p, zval):
        return (p[0], p[1], zval)

    z0, z1 = 0.0, dz

    # ------------------------------------------------------------------
    # Vertices (16 total: 8 inner airfoil-side + 8 outer circle-side, x2 for z)
    # Order per z-plane: le, top_mid, te, bot_mid (inner) then
    #                     outer_front, outer_top, outer_back, outer_bot (outer)
    # ------------------------------------------------------------------
    inner_names = ["le", "topMid", "te", "botMid"]
    outer_names = ["outerFront", "outerTop", "outerBack", "outerBot"]
    inner_pts = [le, top_mid, te, bot_mid]
    outer_pts = [outer_front, outer_top, outer_back, outer_bot]

    vtx_index = {}
    vertices_lines = []
    idx = 0
    for zval, zsuffix in ((z0, "0"), (z1, "1")):
        for name, p in zip(inner_names, inner_pts):
            vtx_index[f"{name}{zsuffix}"] = idx
            vertices_lines.append(f"    {fmt(z(p, zval))} // {idx} {name}{zsuffix}")
            idx += 1
        for name, p in zip(outer_names, outer_pts):
            vtx_index[f"{name}{zsuffix}"] = idx
            vertices_lines.append(f"    {fmt(z(p, zval))} // {idx} {name}{zsuffix}")
            idx += 1

    def vi(name, zsuffix):
        return vtx_index[f"{name}{zsuffix}"]

    # ------------------------------------------------------------------
    # Blocks: 4 quadrants, each hex from inner-quad-edge to outer-quad-edge
    # Block ordering of a hex: (bottom face ccw from a corner, top face ccw)
    #   front:  le -> topMid  |  outerFront -> outerTop
    #   top:    topMid -> te  |  outerTop -> outerBack
    #   back:   te -> botMid  |  outerBack -> outerBot
    #   bottom: botMid -> le  |  outerBot -> outerFront
    # ------------------------------------------------------------------
    quadrants = [
        ("front", "le", "topMid", "outerFront", "outerTop"),
        ("top", "topMid", "te", "outerTop", "outerBack"),
        ("back", "te", "botMid", "outerBack", "outerBot"),
        ("bottom", "botMid", "le", "outerBot", "outerFront"),
    ]

    blocks_lines = []
    for name, innerA, innerB, outerA, outerB in quadrants:
        # hex8 vertex order: (i0 i1 i2 i3) bottom ccw, (i4 i5 i6 i7) top ccw
        # bottom face: innerA0 innerB0 outerB0 outerA0  (quad, ccw when viewed from +z... )
        v0 = vi(innerA, "0")
        v1 = vi(innerB, "0")
        v2 = vi(outerB, "0")
        v3 = vi(outerA, "0")
        v4 = vi(innerA, "1")
        v5 = vi(innerB, "1")
        v6 = vi(outerB, "1")
        v7 = vi(outerA, "1")
        blocks_lines.append(
            f"    hex ({v0} {v1} {v2} {v3} {v4} {v5} {v6} {v7}) "
            f"({N_SPANWISE_ALONG_SURFACE} {N_RADIAL} 1) "
            f"simpleGrading (1 {RADIAL_GRADING} 1) // {name}"
        )

    # ------------------------------------------------------------------
    # Edges: spline edges along airfoil surface (inner), arc edges along
    # outer circle. Both z-planes need the curved edges defined.
    # ------------------------------------------------------------------
    def spline_points_str(pts):
        return "\n".join(f"            {fmt(p)}" for p in pts)

    edges_lines = []
    for zval, zsuffix in ((z0, "0"), (z1, "1")):
        # LE -> topMid : first half of 'upper' list (index 0..mid_idx)
        pts = [z(p, zval) for p in upper[0 : mid_idx + 1]]
        edges_lines.append(
            f"    spline {vi('le', zsuffix)} {vi('topMid', zsuffix)}\n    (\n{spline_points_str(pts[1:-1])}\n    )"
        )
        # topMid -> te : second half of 'upper' list (index mid_idx..end)
        pts = [z(p, zval) for p in upper[mid_idx:]]
        edges_lines.append(
            f"    spline {vi('topMid', zsuffix)} {vi('te', zsuffix)}\n    (\n{spline_points_str(pts[1:-1])}\n    )"
        )
        # te -> botMid : second half of 'lower' list, reversed (TE->mid)
        pts = [z(p, zval) for p in list(reversed(lower[mid_idx:]))]
        edges_lines.append(
            f"    spline {vi('te', zsuffix)} {vi('botMid', zsuffix)}\n    (\n{spline_points_str(pts[1:-1])}\n    )"
        )
        # botMid -> le : first half of 'lower' list, reversed (mid->LE)
        pts = [z(p, zval) for p in list(reversed(lower[0 : mid_idx + 1]))]
        edges_lines.append(
            f"    spline {vi('botMid', zsuffix)} {vi('le', zsuffix)}\n    (\n{spline_points_str(pts[1:-1])}\n    )"
        )

        # Outer arcs: need a mid-arc point for OpenFOAM 'arc' edge definition
        def arc_mid(angle_a, angle_b):
            am = (angle_a + angle_b) / 2.0
            return z(outer_circle_point(am), zval)

        edges_lines.append(
            f"    arc {vi('outerFront', zsuffix)} {vi('outerTop', zsuffix)} {fmt(arc_mid(180, 90))}"
        )
        edges_lines.append(
            f"    arc {vi('outerTop', zsuffix)} {vi('outerBack', zsuffix)} {fmt(arc_mid(90, 0))}"
        )
        edges_lines.append(
            f"    arc {vi('outerBack', zsuffix)} {vi('outerBot', zsuffix)} {fmt(arc_mid(0, -90))}"
        )
        edges_lines.append(
            f"    arc {vi('outerBot', zsuffix)} {vi('outerFront', zsuffix)} {fmt(arc_mid(-90, -180))}"
        )

    # ------------------------------------------------------------------
    # Boundary patches
    # ------------------------------------------------------------------
    def quad_face(a, b, zsuffix_pair=("0", "1")):
        z0s, z1s = zsuffix_pair
        return f"{vi(a, z0s)} {vi(b, z0s)} {vi(b, z1s)} {vi(a, z1s)}"

    airfoil_faces = []
    outer_front_faces = []  # inlet: front+bottom-front-ish -> we tag by upstream/downstream
    for name, innerA, innerB, outerA, outerB in quadrants:
        airfoil_faces.append(f"        ({quad_face(innerA, innerB)})")

    inlet_faces = [
        f"        ({quad_face('outerFront', 'outerTop')})",
        f"        ({quad_face('outerBot', 'outerFront')})",
    ]
    outlet_faces = [
        f"        ({quad_face('outerTop', 'outerBack')})",
        f"        ({quad_face('outerBack', 'outerBot')})",
    ]

    front_back_faces = []
    for name, innerA, innerB, outerA, outerB in quadrants:
        v0, v1, v2, v3 = vi(innerA, "0"), vi(innerB, "0"), vi(outerB, "0"), vi(outerA, "0")
        v4, v5, v6, v7 = vi(innerA, "1"), vi(innerB, "1"), vi(outerB, "1"), vi(outerA, "1")
        front_back_faces.append((f"        ({v0} {v3} {v2} {v1})", f"        ({v4} {v5} {v6} {v7})"))

    front_faces = "\n".join(p[0] for p in front_back_faces)
    back_faces = "\n".join(p[1] for p in front_back_faces)

    # ------------------------------------------------------------------
    # Write blockMeshDict
    # ------------------------------------------------------------------
    out = []
    out.append(r"""/*--------------------------------*- C++ -*----------------------------*\
| =========                 |                                                |
| \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox         |
|  \\    /   O peration     | Version:  v2412                               |
|   \\  /    A nd           | Web:      www.openfoam.com                    |
|    \\/     M anipulation  |                                                |
\*-----------------------------------------------------------------------*/
// AUTO-GENERATED by system/makeBlockMeshDict.py -- do not hand-edit.
// Regenerate with: python3 system/makeBlockMeshDict.py
FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      blockMeshDict;
}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

scale   1;

vertices
(
""")
    out.append("\n".join(vertices_lines))
    out.append(");\n\nblocks\n(")
    out.append("\n".join(blocks_lines))
    out.append(");\n\nedges\n(")
    out.append("\n".join(edges_lines))
    out.append(");\n\nboundary\n(")
    out.append("    airfoil")
    out.append("    {")
    out.append("        type wall;")
    out.append("        faces")
    out.append("        (")
    out.append("\n".join(airfoil_faces))
    out.append("        );")
    out.append("    }")
    out.append("    inlet")
    out.append("    {")
    out.append("        type patch;")
    out.append("        faces")
    out.append("        (")
    out.append("\n".join(inlet_faces))
    out.append("        );")
    out.append("    }")
    out.append("    outlet")
    out.append("    {")
    out.append("        type patch;")
    out.append("        faces")
    out.append("        (")
    out.append("\n".join(outlet_faces))
    out.append("        );")
    out.append("    }")
    out.append("    front")
    out.append("    {")
    out.append("        type empty;")
    out.append("        faces")
    out.append("        (")
    out.append(front_faces)
    out.append("        );")
    out.append("    }")
    out.append("    back")
    out.append("    {")
    out.append("        type empty;")
    out.append("        faces")
    out.append("        (")
    out.append(back_faces)
    out.append("        );")
    out.append("    }")
    out.append(");\n")
    out.append("// ************************************************************************* //\n")

    text = "\n".join(out)
    with open("system/blockMeshDict", "w", newline="\n") as f:
        f.write(text)
    print("Wrote system/blockMeshDict")
    print(f"  Chord = {CHORD} m, outer radius = {OUTER_RADIUS} m")
    print(f"  Approx first-layer height target: {FIRST_LAYER_HEIGHT} m (tune RADIAL_GRADING/N_RADIAL if checkMesh complains)")


if __name__ == "__main__":
    main()
