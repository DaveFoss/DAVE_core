# Copyright (c) 2022-2024 by Fraunhofer Institute for Energy Economics and Energy System Technology (IEE)
# Kassel and individual contributors (see AUTHORS file for details). All rights reserved.
# Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.

from tqdm import tqdm
from tqdm.dask import TqdmCallback

from dave_core.settings import dave_settings


def create_tqdm(desc, bar_type="main_bar"):
    """
    This function creates a tqdm progress bar object

    INPUT:
        **desc** (str) - Name of the task (max 33 signs)

    OPTIONAL:
        **bar_type** (str, default "main_bar") - Which style of progress bar \
            should be used. Options: "main_bar, "sub_bar"

    OUTPUT:
        **tqdm_object** (tqdm object) - tqdm object suitale to the usage in DAVE code
    """
    # limit desc string to 34 signs
    desc = desc[:33]
    # define bar style
    if bar_type == "main_bar":
        # bar style for main task
        tqdm_object = tqdm(
            total=100,
            desc=f"{desc}:" + " " * (35 - len(f"{desc}:")),
            position=0,
            bar_format=dave_settings["bar_format"],
            colour="green",
        )
    elif bar_type == "sub_bar":
        # bar style for subtask
        tqdm_object = tqdm(
            total=100,
            desc=f"{desc}:" + " " * (34 - len(f"{desc}:")),
            position=0,
            bar_format=dave_settings["sub_bar_format"],
        )
    return tqdm_object


def create_tqdm_dask(desc, bar_type):
    """
    This function creates a tqdm progress bar object for dask functions

    INPUT:
        **desc** (str) - Name of the task (max 33 signs)
        **bar_type** (str) - Which style of progress bar should be used \
            Options: "main_bar, "sub_bar"

    OUTPUT:
        **tqdm_object_dask** (tqdm object) - tqdm object suitale to the usage \
            in DAVE code
    """
    # limit desc string to 34 signs
    desc = desc[:33]
    # define bar style
    if bar_type == "main_bar":
        # bar style for main task
        tqdm_object_dask = TqdmCallback(
            desc=f"{desc}:" + " " * (35 - len(f"{desc}:")),
            position=1,
            bar_format=dave_settings["bar_format"],
            colour="green",
            tqdm_class=tqdm,
        )
    elif bar_type == "sub_bar":
        # bar style for subtask
        tqdm_object_dask = TqdmCallback(
            desc=f"{desc}:" + " " * (34 - len(f"{desc}:")),
            position=0,
            bar_format=dave_settings["sub_bar_format"],
            tqdm_class=tqdm,
        )
    return tqdm_object_dask
