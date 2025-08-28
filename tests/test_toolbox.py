# Copyright (c) 2022-2024 by Fraunhofer Institute for Energy Economics and Energy System Technology (IEE)
# Kassel and individual contributors (see AUTHORS file for details).
# All rights reserved.
# Copyright (c) 2024-2025 DAVE_core contributors
# Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.

from shapely.geometry import MultiLineString

from dave_core.toolbox import adress_to_coords
from dave_core.toolbox import multiline_coords


def test_multiline_coords():
    # define multilinestring
    lines = [[(0, 0), (1, 1), (2, 0)], [(2, 1), (3, 1), (4, 2)], [(0, 2), (1, 3), (2, 2)]]
    multi_line = MultiLineString(lines)
    # extract coordinates from multilinestring
    coords = multiline_coords(multi_line)
    # check coordinates
    assert isinstance(coords, list)
    assert len(coords) == 9


def test_adress_to_coords():
    # define example adress
    adress = "Joseph-Beuys-Straße 8 34117 Kassel"
    # request coordinates
    coords = adress_to_coords(adress, geolocator=None)
    # check coordinates
    assert coords == (9.487695307232, 51.319827694129)
