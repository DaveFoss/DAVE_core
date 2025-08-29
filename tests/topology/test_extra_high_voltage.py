# Copyright (c) 2022-2024 by Fraunhofer Institute for Energy Economics and Energy System Technology (IEE)
# Kassel and individual contributors (see AUTHORS file for details).
# All rights reserved.
# Copyright (c) 2024-2025 DAVE_core contributors
# Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.

import pytest

from dave_core import create_grid


def test_ehv_topo():
    # generate model
    grid_data = create_grid(
        federal_state=["Hessen"],
        # grid level parameters
        power_levels=["ehv"],
        # power grid components
        transformers=False,
        renewable_powerplants=False,
        conventional_powerplants=False,
        loads=False,
        save_data=False,
    )
    assert not grid_data.ehv_data.ehv_nodes.empty
    assert not grid_data.ehv_data.ehv_lines.empty


if __name__ == "__main__":
    pytest.main([__file__, "-xs"])
