"""
Unit tests for CutOut._classify_contours()

Tests the automatic detection of interior vs exterior contours
for the Cutout Tool's auto-interior-detection feature.

Run with: python -m pytest tests/test_classify_contours.py -v
Requires only: shapely >= 2.0
"""

import pytest
from shapely import Polygon, LineString, LinearRing, Point


# Import the static method directly to test without PyQt6/app dependencies
# We replicate the function here for standalone testing (same logic as in ToolCutOut.py)
def _classify_contours(geometries: list) -> set:
    """
    Classify polygons as interior (contained within a larger exterior polygon).
    Standalone copy for testing without app dependencies.
    """
    if len(geometries) <= 1:
        return set()

    filled_polys = []
    for geo in geometries:
        try:
            if hasattr(geo, 'exterior'):
                filled_polys.append(Polygon(geo.exterior))
            else:
                filled_polys.append(geo.convex_hull)
        except Exception:
            filled_polys.append(None)

    max_area = -1
    exterior_idx = 0
    for i, fp in enumerate(filled_polys):
        if fp is not None and fp.area > max_area:
            max_area = fp.area
            exterior_idx = i

    exterior_filled = filled_polys[exterior_idx]
    if exterior_filled is None or exterior_filled.is_empty:
        return set()

    interior_indices = set()
    for i, geo in enumerate(geometries):
        if i == exterior_idx:
            continue
        try:
            test_point = geo.representative_point()
            if exterior_filled.contains(test_point):
                interior_indices.add(i)
        except Exception:
            pass

    return interior_indices


# ============================================================================
# Helper: simulate Gerber profile geometry (thin band = LineString.buffer(width/2))
# ============================================================================

def make_gerber_band(coords, width=0.254):
    """Simulate a Gerber profile path: LineString buffered with aperture width/2."""
    line = LineString(coords)
    return line.buffer(width / 2)


def make_rectangular_outline(xmin, ymin, xmax, ymax, width=0.254):
    """Create a rectangular outline as a thin band (like Gerber profile)."""
    ring_coords = [(xmin, ymin), (xmax, ymin), (xmax, ymax), (xmin, ymax), (xmin, ymin)]
    return make_gerber_band(ring_coords, width)


def make_circular_outline(cx, cy, radius, width=0.254, segments=64):
    """Create a circular outline as a thin band."""
    import math
    coords = []
    for i in range(segments + 1):
        angle = 2 * math.pi * i / segments
        coords.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    return make_gerber_band(coords, width)


# ============================================================================
# TEST CASES
# ============================================================================

class TestSinglePolygon:
    """REQ-03: Zero regression for single polygon."""

    def test_single_polygon_returns_empty_set(self):
        """One polygon → no interior detected."""
        outline = make_rectangular_outline(0, 0, 64, 40)
        result = _classify_contours([outline])
        assert result == set()

    def test_empty_list_returns_empty_set(self):
        """Empty input → empty set."""
        result = _classify_contours([])
        assert result == set()


class TestExteriorWithOneSlot:
    """REQ-01/REQ-02: Detect internal contour and classify correctly."""

    def test_rectangular_outline_with_internal_circle(self):
        """Rectangular outline + circular slot inside → slot is interior."""
        outline = make_rectangular_outline(0, 0, 64, 40)
        slot = make_circular_outline(32, 20, 8)
        result = _classify_contours([outline, slot])
        assert result == {1}  # index 1 is the slot

    def test_slot_first_in_list(self):
        """Even if slot comes first in list, exterior is detected by area."""
        outline = make_rectangular_outline(0, 0, 64, 40)
        slot = make_circular_outline(32, 20, 8)
        result = _classify_contours([slot, outline])
        assert result == {0}  # index 0 is the slot (smaller)

    def test_rectangular_outline_with_rectangular_slot(self):
        """Rectangular outline + rectangular internal slot."""
        outline = make_rectangular_outline(0, 0, 64, 40)
        slot = make_rectangular_outline(20, 10, 44, 30)
        result = _classify_contours([outline, slot])
        assert result == {1}


class TestExteriorWithMultipleSlots:
    """REQ-07: Support multiple internal cutouts."""

    def test_three_internal_slots(self):
        """Exterior + 3 slots → all 3 classified as interior."""
        outline = make_rectangular_outline(0, 0, 100, 60)
        slot1 = make_circular_outline(25, 30, 8)
        slot2 = make_circular_outline(50, 30, 8)
        slot3 = make_circular_outline(75, 30, 8)
        result = _classify_contours([outline, slot1, slot2, slot3])
        assert result == {1, 2, 3}


class TestPanelNoContainment:
    """REQ-04: Panel with multiple PCBs side by side → all exterior."""

    def test_two_boards_side_by_side(self):
        """Two PCBs next to each other (no containment) → both exterior."""
        board1 = make_rectangular_outline(0, 0, 30, 40)
        board2 = make_rectangular_outline(35, 0, 65, 40)
        result = _classify_contours([board1, board2])
        assert result == set()  # neither is inside the other

    def test_three_boards_in_panel(self):
        """Three PCBs in a row → all exterior."""
        board1 = make_rectangular_outline(0, 0, 20, 30)
        board2 = make_rectangular_outline(25, 0, 45, 30)
        board3 = make_rectangular_outline(50, 0, 70, 30)
        result = _classify_contours([board1, board2, board3])
        assert result == set()


class TestSlotTouchingBorder:
    """Edge case: slot that is clearly outside the outline."""

    def test_slot_completely_outside(self):
        """Slot completely outside the exterior → not classified as interior."""
        outline = make_rectangular_outline(0, 0, 64, 40)
        # Slot entirely outside the outline bounds
        slot = make_rectangular_outline(70, 15, 80, 25)
        result = _classify_contours([outline, slot])
        assert 1 not in result

    def test_slot_partially_overlapping_is_interior(self):
        """Slot that starts inside and extends outside — representative_point
        is at the leftmost interior point which is inside the outline.
        This is correctly classified as interior (the internal part needs inside offset)."""
        outline = make_rectangular_outline(0, 0, 64, 40)
        slot = make_rectangular_outline(60, 15, 70, 25)
        result = _classify_contours([outline, slot])
        # representative_point is at (60, 20) which IS inside the outline
        # Classification as interior is acceptable behavior
        assert result == {1}


class TestDegenerateGeometries:
    """Edge cases with unusual geometries."""

    def test_linestring_without_exterior(self):
        """Open LineString (no .exterior attribute in meaningful sense)."""
        outline = make_rectangular_outline(0, 0, 64, 40)
        open_line = LineString([(10, 10), (50, 10)])
        # LineString has no .exterior → uses convex_hull
        # convex_hull of a line is the line itself (area=0), representative_point inside outline
        result = _classify_contours([outline, open_line])
        # The LineString is geometrically inside the outline
        assert result == {1}

    def test_point_like_geometry(self):
        """Very small geometry that could cause issues."""
        outline = make_rectangular_outline(0, 0, 64, 40)
        tiny = Point(32, 20).buffer(0.01)  # tiny circle inside
        result = _classify_contours([outline, tiny])
        assert result == {1}


class TestRealWorldGerberSimulation:
    """Simulate the actual user's case: gear-shaped outline + triangular slot."""

    def test_gear_outline_with_triangular_slot(self):
        """
        Simulates a gear-like PCB outline (large irregular polygon)
        with a rounded triangular internal slot.
        The Gerber produces both as thin bands (buffered LineStrings).
        """
        import math

        # Gear-like exterior (simplified: circle with bumps)
        gear_coords = []
        for i in range(60):
            angle = 2 * math.pi * i / 60
            r = 32 + 4 * math.sin(6 * angle)  # 6-bump gear
            gear_coords.append((r * math.cos(angle), r * math.sin(angle)))
        gear_coords.append(gear_coords[0])  # close
        gear_outline = make_gerber_band(gear_coords, width=0.254)

        # Rounded triangle inside (simplified: 3-point smoothed)
        tri_coords = []
        for i in range(36):
            angle = 2 * math.pi * i / 36
            r = 10 + 3 * math.cos(3 * angle)  # 3-lobe shape
            tri_coords.append((r * math.cos(angle), r * math.sin(angle)))
        tri_coords.append(tri_coords[0])
        tri_slot = make_gerber_band(tri_coords, width=0.254)

        result = _classify_contours([gear_outline, tri_slot])
        assert result == {1}  # triangular slot is interior


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
