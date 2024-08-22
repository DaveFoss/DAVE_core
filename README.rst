=========
DAVE_core
=========

.. start-badges

.. list-table::
    :stub-columns: 1

    * - docs
      - |docs|
    * - tests
      - |github-actions| |coveralls| |codecov|
    * - package
      - |version| |licence| |wheel| |supported-versions| |supported-implementations| |commits-since| |black| |isort|

.. |version| image:: https://img.shields.io/pypi/v/dave_data.svg
    :alt: PyPI Package latest release
    :target: https://pypi.org/project/dave_data

.. |wheel| image:: https://img.shields.io/pypi/wheel/dave_data.svg
    :alt: PyPI Wheel
    :target: https://pypi.org/project/dave_data

.. |supported-versions| image:: https://img.shields.io/pypi/pyversions/dave_data.svg
    :alt: Supported versions
    :target: https://pypi.org/project/dave_data

.. |supported-implementations| image:: https://img.shields.io/pypi/implementation/dave_data.svg
    :alt: Supported implementations
    :target: https://pypi.org/project/dave_data

.. |docs| image:: https://readthedocs.org/projects/dave_data/badge/?version=latest
    :target: https://dave-data.readthedocs.io/en/latest/?badge=latest
    :alt: Documentation Status

.. |github-actions| image:: https://github.com/DaveFoss/DAVE_data/actions/workflows/github-actions.yml/badge.svg
    :alt: GitHub Actions Build Status
    :target: https://github.com/DaveFoss/DAVE_data/actions

.. |coveralls| image:: https://coveralls.io/repos/github/DaveFoss/DAVE_data/badge.svg?branch=main
    :alt: Coverage Status
    :target: https://coveralls.io/github/DaveFoss/DAVE_data?branch=main

.. |codecov| image:: https://codecov.io/gh/DaveFoss/DAVE_data/branch/main/graphs/badge.svg?branch=main
    :alt: Coverage Status
    :target: https://app.codecov.io/github/DaveFoss/DAVE_data

.. |commits-since| image:: https://img.shields.io/github/commits-since/DaveFoss/DAVE_data/v0.0.1.svg
    :alt: Commits since latest release
    :target: https://github.com/DaveFoss/DAVE_data/compare/v0.0.1...main

.. |licence| image:: https://img.shields.io/badge/License-BSD%203--Clause-blue.svg
   :target: https://github.com/OpenDaveTeam/OpenDave/blob/main/LICENSE
   :alt: BSD
   
.. |black| image:: https://img.shields.io/badge/code%20style-black-000000.svg
    :target: https://github.com/psf/black
    
.. |isort| image:: https://img.shields.io/badge/%20imports-isort-%231674b1?style=flat&labelColor=ef8336
    :target: https://pycqa.github.io/isort/

.. end-badges


DAVE is an softwaretool for a automatic generation of region-specific energy grid models. The resulting grid models are based on open data from different sources.


This code ist based on and explained in the following publicationat :

- `Banze, T., Kneiske, T.M. Open data for energy networks: introducing DAVE—a data fusion tool for automated network generation. Sci Rep 14, 1938 (2024). <https://doi.org/10.1038/s41598-024-52199-w>`_

More on DAVE is published on the webside http://databulter.energy


Installation
============

::

    pip install dave_core

You can also install the in-development version with::

    pip install https://github.com/DaveFoss/DAVE_core/archive/main.zip


Documentation
=============


https://dave-core.readthedocs.io


Development
===========

To run all the tests run::

    tox

Note, to combine the coverage data from all the tox environments run:

.. list-table::
    :widths: 10 90
    :stub-columns: 1

    - - Windows
      - ::

            set PYTEST_ADDOPTS=--cov-append
            tox

    - - Other
      - ::

            PYTEST_ADDOPTS=--cov-append tox
