=======================
What's new in DAVE_core
=======================

These are new features and improvements of note in each release.

Unreleased
==========

Changed
-------

* Changelog style

Event
-----

* Switched name from DAVE to DAVE_core as part of the open source publication and restructuring

1.2.0 (November 20, 2023)
=========================

Added
-----

* Building height based on raster data
* Extend api with functions for database managment
* Environment files for the possibility to install DAVE via mamba
* Converter for the multiphysical network simulator MYNTS
* Population data from census and the possibility to request the raster data
* Importer for data from the gassimulation softwaretool SIMONE
* Api restriction by user role
* Option to choose year for nuts regions (2013, 2016, 2021)
* Geopackage as possible output format
* Extend geographical data with more landuse information and data for waterways

Changed
-------

* Archiv i/o function in seperated file
* Input parameters for geographical objects reduced to one parameter "geodata"

Removed
-------

* Moved dave structure functions to DAVE client
* Moved read simone function to DAVE client
* Moved read gaslib function to DAVE client
* Moved io module to DAVE client
* Moved plotting module to DAVE client

1.1.0 (November 03, 2022)
=========================

Added
-----

* Algorithm for automated deployment
* Geography module and separated geographical data from grid model generation
* Restructured target area functions
* Different years as option for nuts regions
* Function for intersection with considering mixed geometries
* Topology cleanup for power and gas models
* Gaslib converter
* Gas component: source, sink, compressor
* Pandapipes converter
* Function to transform address into coordinates

Changed
-------

* Renamed building category from "for_living" to "residential"
* Power components script splitted to separate scripts according to the components
* Bus naming in ehv and hv models from "bus0/bus1" to "from/to_bus"
* Channel for required packages to only "conda forge" because of anaconda terms changes

Fixed
-----

* Osm gateway timeout
* Stack overflow error
* Duplicate naming

Event
-----

* First open accessible "software as a service" platform version
* DAVE licensed under a three clause bsd license 

1.0.6 (October 20, 2021)
========================

Added
-----

* Option for output folder path
* Functions for serialization
* Basic test structure
* setup file
* Uniform code style (with black) via pre-commit hooks
* Uniform import order (with isort) via pre-commit hooks

Changed
-------

* Build seperated io modul, changed structure and moved existing io functions to that
* Rebuild from/to hdf functions and merged with from/to archiv
* Moved dave dir paths to settings file

Fixed
-----

* Wrong/missing types at pandapower converter
* Missing crs definitions

1.0.5 (March 21, 2021)
======================

Added
-----

* Substations for other voltage levels

Changed
-------

* Move ehv substations to components power

Fixed
-----

* Missing line and trafo data within pandapower converting

1.0.4 (March 18, 2021)
======================

Changed
-------

* Pandapower converter function restructured
* Condition deleted that more than one bus must exist for transformers

1.0.3 (March 04, 2021)
======================

Added
-----

* Description in install tutorial for using DaVe in PyCharm
* Runtime count

1.0.2 (February 10, 2021)
=========================

Added
-----

* Progress bars

Fixed
-----

* Overwriting points in voronoi calculation

1.0.1 (January 26, 2021)
========================

Added
-----

* Json to pp converting function with considering geometries
* pp to json converting function with considering geometries
* Nuts regions as input option for grid area
* Possibility to choose components individually

Changed
-------

* Voronoi function expanded with dynamic corner points
* Use scigridgas igginl dataset instead of lkd_eu dataset for high pressure gas level

Fixed
-----

* Replaced deprecated shapely "cascaded union" function with "unary_union" function

1.0.0 (December 21, 2020)
=========================

Event
-----

* First usable DaVe version

0.0.0 (February 05, 2020)
=========================

Event
-----

* Started DaVe development
