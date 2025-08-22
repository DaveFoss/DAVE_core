# Copyright (c) 2022-2024 by Fraunhofer Institute for Energy Economics and Energy System Technology (IEE)
# Kassel and individual contributors (see AUTHORS file for details).
# All rights reserved.
# Copyright (c) 2024-2025 DAVE_core contributors
# Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.


import requests


def test_data_availability():
    url = "https://owncloud.fraunhofer.de/index.php/s/McrHKZ62ci0FxCN/download?path=%2F&files=core/"
    response = requests.head(url, timeout=10)  # Verwende HEAD, um nur die Header abzurufen
    assert response.status_code == 200, f"Data Repo is not available: {response.status_code}"
