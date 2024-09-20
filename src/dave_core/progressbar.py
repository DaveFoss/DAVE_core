# Copyright (c) 2022-2024 by Fraunhofer Institute for Energy Economics and Energy System Technology (IEE)
# Kassel and individual contributors (see AUTHORS file for details). All rights reserved.
# Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.

from tqdm import tqdm

from dave_core.settings import dave_settings


def create_tqdm(desc):
    """
    This function creates a tqdm progress bar object

    INPUT:
        **desc** (str) - Name of the task (max 34 signs)

    OUTPUT:
        **tqdm_object** (tqdm object) - tqdm object suitale to the usage in DAVE code
    """
    # limit desc string to 34 signs
    desc = desc[:33]
    # define bar style
    # bar style for main task
    tqdm_object = tqdm(
        total=100,
        desc=f"{desc}:" + " " * (35 - len(f"{desc}:")),
        position=0,
        bar_format=dave_settings["bar_format"],
    )
    return tqdm_object
