# Copyright (c) 2022-2024 by Fraunhofer Institute for Energy Economics and Energy System Technology (IEE)
# Kassel and individual contributors (see AUTHORS file for details). All rights reserved.
# Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.

from setuptools import find_packages, setup

from dave_core import __version__

# read information files
with open("README.rst", "rb") as f:
    readme = f.read().decode("utf-8")
with open("CHANGELOG.rst", "rb") as f:
    changelog = f.read().decode("utf-8")

# create long description
long_description = "\n\n".join((readme, changelog))

# define setup
setup(
    name="dave_core",
    version=__version__,
    author="Tobias Banze",
    author_email="tobias.banze@iee.fraunhofer.de",
    description="DAVE is a tool for automatic energy grid generation",
    long_description=long_description,
    long_description_content_type="text/x-rst",
    install_requires=[
        "Shapely",
        "geopandas",
        "matplotlib",
        "geopy",
        "contextily",
        "pytest",
        "pytest-cov",
        "pytest-xdist",
        "openpyxl",
        "xmlschema",
        "lxml",
        "authlib",
        "tables",
        "pyopenssl",
        "rasterio",
        "tqdm",
        "pandapower",
        "pandapipes",
    ],
    packages=find_packages(),
    include_package_data=True,
)
