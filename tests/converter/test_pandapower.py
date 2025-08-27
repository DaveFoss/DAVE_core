# Copyright (c) 2022-2024 by Fraunhofer Institute for Energy Economics and Energy System Technology (IEE)
# Kassel and individual contributors (see AUTHORS file for details).
# All rights reserved.
# Copyright (c) 2024-2025 DAVE_core contributors
# Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.

from pathlib import Path

import pytest

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
    # check net elements
    assert len(net.bus) == 32  # !!! wrong number should be 1020
    # !!! add more asserts


if __name__ == "__main__":
    pytest.main([__file__, "-xs"])
