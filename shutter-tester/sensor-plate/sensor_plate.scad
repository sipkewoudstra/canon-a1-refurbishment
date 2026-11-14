// Canon A-1 shutter-tester sensor plate — parametric OpenSCAD version
// Same geometry as sensor_plate.py / the STL files.
// Print FRONT FACE DOWN (pinholes on the bed) in black filament.
// Seen from above while printing = seen from the back of the camera: A is left.

bay     = true;  // true: open-top bay on the back for the comparator perfboard
W       = 42.0;  // 36 mm gate + 3 mm each side (keeps clear of the sprocket)
H       = 34.6;  // must drop between the outer film rails; try 34.0 if it binds
T       = 4.2;   // plate thickness
front   = 0.8;   // wall in front of the photodiode
spacing = 30.0;  // sensor A to B, centre to centre
pocket  = 5.8;   // square pocket, BPW34 body 5.4 x 4.3 x 3.2 fits either way round
pin     = 1.0;   // pinhole side (square; 50 % threshold makes shape uncritical)
band_w  = 3.0;   // rubber-band notch width
band_d  = 1.5;   // rubber-band notch depth (plate only; with the bay it cuts the whole wall)
mark    = 2.0;   // corner notch marking channel A (bottom-left, back view)
// bay
wall    = 1.6;
ledge   = 1.0;
ledge_z = 7.5;   // underside of the perfboard
wall_z  = 11.5;  // top of the walls
board_t = 1.6;
cable_x = [5.0, 11.0];
trim_slot = [-14.2, -6.1];  // openings in the left/right walls: 3006P body end + screw pass through (perfboard rows 10-11)
trim_floor = 8.6;  // bottom of the trimmer openings, 0.5 mm below the board top
// bay version: photodiodes soldered flat on the perfboard copper side (legs B2/B4, N2/N4)
diode_x = 15.24;   // column B / N
diode_y = 8.89;    // row 3
pin_bay = 1.5;     // pinhole side; keep <= half the 1/1000 slit (~3 mm)
pocket_bay = 6.6;  // pocket under each diode, floor thinned to `front`

e = 0.01;
nd = bay ? wall : band_d;
slot_top = bay ? H/2 - wall - ledge : H/2 + e;

difference() {
    union() {
        translate([-W/2, -H/2, 0]) cube([W, H, T]);
        if (bay) {
            // walls
            difference() {
                translate([-W/2, -H/2, 0]) cube([W, H, wall_z]);
                translate([-W/2 + wall, -H/2 + wall, -e]) cube([W - 2*wall, H - 2*wall, wall_z + 2*e]);
            }
            // ledge
            difference() {
                translate([-W/2 + wall, -H/2 + wall, 0]) cube([W - 2*wall, H - 2*wall, ledge_z]);
                translate([-W/2 + wall + ledge, -H/2 + wall + ledge, -e]) cube([W - 2*(wall+ledge), H - 2*(wall+ledge), ledge_z + 2*e]);
            }
        }
    }
    if (bay) {
        for (c = [-diode_x, diode_x]) {
            // pocket under the board-mounted diode (the ledge/walls stay solid)
            intersection() {
                translate([c - pocket_bay/2, diode_y - pocket_bay/2, front]) cube([pocket_bay, pocket_bay, T]);
                translate([-W/2 + wall + ledge, -H/2 + wall + ledge, -1]) cube([W - 2*(wall+ledge), H - 2*(wall+ledge), T + 2]);
            }
            // pinhole through the front wall, centred under the diode
            translate([c - pin_bay/2, diode_y - pin_bay/2, -e]) cube([pin_bay, pin_bay, front + 2*e]);
        }
    } else {
        for (c = [-spacing/2, spacing/2]) {
            // pocket + lead slot
            translate([c - pocket/2, -pocket/2, front]) cube([pocket, slot_top + pocket/2, T]);
            // pinhole through the front wall
            translate([c - pin/2, -pin/2, -e]) cube([pin, pin, front + 2*e]);
        }
    }
    // rubber-band notches, top and bottom centre
    for (s = [-1, 1]) translate([-band_w/2, s > 0 ? H/2 - nd : -H/2 - e, -e]) cube([band_w, nd + e, wall_z + 2*e]);
    // channel-A marker
    translate([-W/2 - e, -H/2 - e, -e]) cube([mark + e, mark + e, wall_z + 2*e]);
    // wire exit in the top wall, down to board top
    if (bay) translate([cable_x[0], H/2 - wall - e, ledge_z + board_t]) cube([cable_x[1] - cable_x[0], wall + 2*e, wall_z]);
    // trimmer openings in the left and right walls
    if (bay) for (sx = [-W/2 - e, W/2 - wall - e])
        translate([sx, trim_slot[0], trim_floor]) cube([wall + 2*e, trim_slot[1] - trim_slot[0], wall_z]);
}
