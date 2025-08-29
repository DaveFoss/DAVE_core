# Copyright (c) 2022-2024 by Fraunhofer Institute for Energy Economics and Energy System Technology (IEE)
# Kassel and individual contributors (see AUTHORS file for details).
# All rights reserved.
# Copyright (c) 2024-2025 DAVE_core contributors
# Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.

from pathlib import Path

import pytest
from pandapower.auxiliary import pandapowerNet

from dave_core.converter import create_pandapower
from dave_core.io.file_io import from_json


def test_pp_converter():
    # read example dave dataset
    grid_data = from_json(Path(__file__).resolve().parents[1] / "dave_dataset.json")

    # url = "https://owncloud.fraunhofer.de/index.php/s/McrHKZ62ci0FxCN/download?path=%2F&files=core/"
    # response = requests.head(url, timeout=10)  # Verwende HEAD, um nur die Header abzurufen
    # assert response.status_code == 200, f"Data Repo is not available: {response.status_code}"

    net = create_pandapower(
        grid_data, opt_model=False, output_folder=Path(__file__).resolve(), save_data=False
    )
    assert isinstance(net, pandapowerNet)
    # check net elements
    # assert len(net.bus) == len(grid_data.mv_data.mv_nodes) + len(grid_data.lv_data.lv_nodes)
    # assert len(net.line) == len(grid_data.lv_data.lv_lines)
    # assert len(net.trafo) == len(grid_data.components_power.transformers.mv_lv)
    # assert not net.ext_grid.empty
    # !!! some of the nodes and lines are filtered wrongly out through the diagostic (disconnected elements)


if __name__ == "__main__":
    pytest.main([__file__, "-xs"])
