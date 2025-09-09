# Copyright (c) 2022-2024 by Fraunhofer Institute for Energy Economics and Energy System Technology (IEE)
# Kassel and individual contributors (see AUTHORS file for details).
# All rights reserved.
# Copyright (c) 2024-2025 DAVE_core contributors
# Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.


import re
from pathlib import Path

from setuptools import find_packages
from setuptools import setup


def read(*names, **kwargs):
    with Path(__file__).parent.joinpath(*names).open(encoding=kwargs.get("encoding", "utf8")) as fh:
        return fh.read()


setup(
    name="dave_core",
    version="1.3.2",
    license="BSD-3-Clause",
    description="DAVE is a tool for automatic energy grid generation",
    long_description="{}\n{}".format(
        re.compile("^.. start-badges.*^.. end-badges", re.M | re.S).sub("", read("README.rst")),
        re.sub(
            ":[a-z]+:`~?(.*?)`",
            r"``\1``",
            "https://dave-core.readthedocs.io/en/latest/about/changelog.html",
        ),
    ),
    long_description_content_type="text/x-rst",
    author="DAVE_core Developers",
    author_email="tobias.banze@iee.fraunhofer.de",
    url="https://github.com/DaveFoss/DAVE_core",
    packages=find_packages("src"),
    package_dir={"": "src"},
    py_modules=[path.stem for path in Path("src").glob("*.py")],
    include_package_data=True,
    zip_safe=False,
    classifiers=[
        # http://pypi.python.org/pypi?%3Aaction=list_classifiers
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Operating System :: Unix",
        "Operating System :: POSIX",
        "Operating System :: Microsoft :: Windows",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        # "Programming Language :: Python :: Implementation :: CPython",
        # "Programming Language :: Python :: Implementation :: PyPy",
        # uncomment if you test on these interpreters:
        # "Programming Language :: Python :: Implementation :: IronPython",
        # "Programming Language :: Python :: Implementation :: Jython",
        # "Programming Language :: Python :: Implementation :: Stackless",
        "Topic :: Utilities",
    ],
    project_urls={
        "Documentation": "https://dave-core.readthedocs.io",
        "Changelog": ("https://dave-core.readthedocs.io/en/latest/changelog.html"),
        "Issue Tracker": "https://github.com/DaveFoss/DAVE_core/issues",
        "Homepage": "http://databutler.energy/",
    },
    keywords=[
        # eg: "keyword1", "keyword2", "keyword3",
    ],
    python_requires=">=3.10",
    install_requires=[
        "pandas>=2.3",
        "Shapely>=2.1",
        "geopandas>=1.1",
        "matplotlib>=3.10",
        "geopy>=2.4",
        "fiona>=1.10",
        "networkx>=3.4",
        "contextily>=1.6",
        "pytest>=8.4",
        "pytest-cov>=6.2",
        "pytest-xdist>=3.8",
        "xmlschema>=4.1",
        "lxml>=6.0",
        "tables>=3.10",
        "tqdm>=4.67",
        "pandapower>=3.1",
        "pandapipes>=0.12",
        "defusedxml>=0.7",
        "dask_geopandas>=0.5",
        "scipy>=1.16",
        "openpyxl>=3.1",
    ],
    extras_require={
        "dev": ["black", "isort>=6.0", "pre-commit>=4.3"]
        #   "rst": ["docutils>=0.11"],
        #   ":python_version=='3.8'": ["backports.zoneinfo"],
    },
    entry_points={
        "console_scripts": [
            "dave_core = dave_core.cli:run",
        ]
    },
)
