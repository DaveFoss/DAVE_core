# Copyright (c) 2022-2024 by Fraunhofer Institute for Energy Economics and Energy System Technology (IEE)
# Kassel and individual contributors (see AUTHORS file for details).
# All rights reserved.
# Copyright (c) 2024-2025 DAVE_core contributors
# Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.


import importlib
import io
import json
import sys
import types
import weakref
from ast import literal_eval
from functools import partial
from functools import singledispatch
from inspect import _findclass
from inspect import isclass
from pathlib import Path
from typing import ClassVar
from warnings import warn

import fiona
from deepdiff.diff import DeepDiff
from geopandas import GeoDataFrame
from geopandas import GeoSeries
from networkx import Graph
from networkx.readwrite import json_graph
from numpy import allclose
from numpy import any as anynp
from numpy import array
from numpy import bool_
from numpy import equal
from numpy import floating
from numpy import generic
from numpy import int64
from numpy import integer
from numpy import isnan
from numpy import ndarray
from numpy import number
from pandapower.auxiliary import _preserve_dtypes
from pandapower.auxiliary import get_free_id
from pandapower.auxiliary import soft_dependency_error
from pandas import DataFrame
from pandas import Index
from pandas import MultiIndex
from pandas import Series
from pandas import isnull
from pandas import read_json
from shapely.geometry import LineString
from shapely.geometry import Point
from shapely.geometry import Polygon
from shapely.geometry import mapping
from shapely.geometry import shape

from dave_core.dave_structure import create_empty_dataset
from dave_core.dave_structure import davestructure

try:
    from pandas.testing import assert_frame_equal
    from pandas.testing import assert_series_equal
except ImportError:
    from pandas.util.testing import assert_frame_equal
    from pandas.util.testing import assert_series_equal
try:
    import pandaplan.core.pplog as logging
except ImportError:
    import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Some of this functions are based on the pandapower python package, which is published under the
# following 3-clause BSD license:

# Copyright (c) 2016-2024 by University of Kassel and Fraunhofer Institute for Energy Economics
# and Energy System Technology (IEE) Kassel and individual contributors (see AUTHORS file for details).
# All rights reserved.

# Redistribution and use in source and binary forms, with or without modification, are permitted
# provided that the following conditions are met:

# 1. Redistributions of source code must retain the above copyright notice, this list of conditions
# and the following disclaimer.

# 2. Redistributions in binary form must reproduce the above copyright notice, this list of
# conditions and the following disclaimer in the documentation and/or other materials provided
# with the distribution.

# 3. Neither the name of the copyright holder nor the names of its contributors may be used to
# endorse or promote products derived from this software without specific prior written permission.

# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND
# FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY
# WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


try:
    from cryptography.fernet import Fernet

    cryptography_INSTALLED = True
except ImportError:
    cryptography_INSTALLED = False
try:
    import hashlib

    hashlib_INSTALLED = True
except ImportError:
    hashlib_INSTALLED = False
try:
    import base64

    base64_INSTALLED = True
except ImportError:
    base64_INSTALLED = False

try:
    import zlib

    zlib_INSTALLED = True
except ImportError:
    zlib_INSTALLED = False


def encrypt_string(s, key, compress=True):
    missing_packages = array(["cryptography", "hashlib", "base64"])[
        ~array([cryptography_INSTALLED, hashlib_INSTALLED, base64_INSTALLED])
    ]
    if len(missing_packages):
        soft_dependency_error(str(sys._getframe().f_code.co_name) + "()", missing_packages)
    key_base = hashlib.sha256(key.encode())
    key = base64.urlsafe_b64encode(key_base.digest())
    cipher_suite = Fernet(key)

    s = s.encode()
    if compress:
        import zlib

        s = zlib.compress(s)
    s = cipher_suite.encrypt(s)
    s = s.decode()
    return s


def decrypt_string(s, key):
    missing_packages = array(["cryptography", "hashlib", "base64"])[
        ~array([cryptography_INSTALLED, hashlib_INSTALLED, base64_INSTALLED])
    ]
    if len(missing_packages):
        soft_dependency_error(str(sys._getframe().f_code.co_name) + "()", missing_packages)
    key_base = hashlib.sha256(key.encode())
    key = base64.urlsafe_b64encode(key_base.digest())
    cipher_suite = Fernet(key)

    s = s.encode()
    s = cipher_suite.decrypt(s)
    if zlib_INSTALLED:
        s = zlib.decompress(s)
    s = s.decode()
    return s


def isinstance_partial(obj, cls):
    """
    this function shall make sure that for the given classes, no default string
    functions are used, but the registered ones (to_serializable registry)
    """
    if isinstance(obj, davestructure):
        return False
    return isinstance(obj, cls)


class JSONSerializableClass:
    json_excludes: ClassVar[str] = ["self", "__class__"]

    def __init__(self, **kwargs):
        pass

    def to_json(self):
        """
        Each controller should have this method implemented. The resulting json string should be
        readable by the controller's from_json function and by the function add_ctrl_from_json in
        control_handler.
        """
        return json.dumps(self.to_dict(), cls=DAVEJSONEncoder)

    def to_dict(self):
        def consider_callable(value):
            if callable(value) and value.__class__ in (
                types.MethodType,
                types.FunctionType,
            ):
                if value.__class__ == types.MethodType and _findclass(value) is not None:
                    return with_signature(value, value.__name__, obj_module=_findclass(value))
                return with_signature(value, value.__name__)
            return value

        d = {
            key: consider_callable(val)
            for key, val in self.__dict__.items()
            if key not in self.json_excludes
        }
        return d

    def add_to_net(
        self,
        net,
        element,
        index=None,
        column="object",
        overwrite=False,
        preserve_dtypes=False,
        fill_dict=None,
    ):
        if element not in net:
            net[element] = DataFrame(columns=[column])
        if index is None:
            index = get_free_id(net[element])
        if index in net[element].index.values:
            obj = net[element].object.at[index]
            if overwrite or not isinstance(obj, JSONSerializableClass):
                logger.info(f"Updating {element} with index {index}")
            else:
                raise UserWarning(f"{element} with index {index} already exists")

        dtypes = None
        if preserve_dtypes:
            dtypes = net[element].dtypes

        if fill_dict is not None:
            for k, v in fill_dict.items():
                net[element].at[index, k] = v
        net[element].at[index, column] = self

        if preserve_dtypes:
            _preserve_dtypes(net[element], dtypes)

        return index

    def equals(self, other):
        # todo: can this method be removed?
        warn(
            "JSONSerializableClass: the attribute 'equals' is deprecated "
            "and will be removed in the future. Use the '__eq__' method instead, "
            "by directly comparing the objects 'a == b'. "
            "To check if two variables point to the same object, use 'a is b'",
            DeprecationWarning,
            stacklevel=2,
        )

        logger.warning(
            "JSONSerializableClass: the attribute 'equals' is deprecated "
            "and will be removed in the future. Use the '__eq__' method instead, "
            "by directly comparing the objects 'a == b'. "
            "To check if two variables point to the same object, use 'a is b'"
        )

        class UnequalityFound(Exception):
            pass

        def check_equality(obj1, obj2):
            if isinstance(obj1, (ndarray, generic)) or isinstance(obj2, (ndarray, generic)):
                unequal = True
                if equal(obj1, obj2):
                    unequal = False
                elif anynp(isnan(obj1)):
                    if allclose(obj1, obj2, atol=0, rtol=0, equal_nan=True):
                        unequal = False
                if unequal:
                    raise UnequalityFound
            elif not isinstance(obj2, type(obj1)):
                raise UnequalityFound
            elif isinstance(obj1, DataFrame):
                if len(obj1) > 0:
                    try:
                        assert_frame_equal(obj1, obj2)
                    except Exception as e:
                        raise UnequalityFound from e
            elif isinstance(obj2, Series):
                if len(obj1) > 0:
                    try:
                        assert_series_equal(obj1, obj2)
                    except Exception as e:
                        raise UnequalityFound from e
            elif isinstance(obj1, dict):
                check_dictionary_equality(obj1, obj2)
            elif obj1 != obj1 and obj2 != obj2:
                pass
            elif callable(obj1):
                check_callable_equality(obj1, obj2)
            elif obj1 != obj2:
                try:
                    if not (isnan(obj1) and isnan(obj2)):
                        raise UnequalityFound
                except Exception as e:
                    raise UnequalityFound from e

        def check_dictionary_equality(obj1, obj2):
            if set(obj1.keys()) != set(obj2.keys()):
                raise UnequalityFound
            for key in obj1.keys():
                if key != "_init":
                    check_equality(obj1[key], obj2[key])

        def check_callable_equality(obj1, obj2):
            if isinstance(obj1, weakref.ref) and isinstance(obj2, weakref.ref):
                return
            if str(obj1) != str(obj2):
                raise UnequalityFound

        if isinstance(other, self.__class__):
            try:
                check_equality(self.__dict__, other.__dict__)
                return True
            except UnequalityFound:
                return False
        else:
            return False

    @classmethod
    def from_dict(cls, d):
        obj = JSONSerializableClass.__new__(cls)
        obj.__dict__.update(d)
        return obj

    @classmethod
    def from_json(cls, json_string):
        d = json.loads(json_string, cls=DAVEJSONDecoder)
        return cls.from_dict(d)

    def __eq__(self, other):
        """
        comparing class name and attributes instead of class object address directly.
        This allows more flexibility,
        e.g. when the class definition is moved to a different module.
        Checking isinstance(other, self.__class__) for an early return without calling DeepDiff.
        There is still a risk that the implementation details of the methods can differ
        if the classes are from different modules.
        The comparison is based on comparing dictionaries of the classes.
        To this end, the dictionary comparison library deepdiff is used for recursive comparison.
        """
        if self.__class__.__name__ != other.__class__.__name__:
            return False
        else:
            d = DeepDiff(
                self.__dict__,
                other.__dict__,
                ignore_nan_inequality=True,
                significant_digits=6,
                math_epsilon=1e-6,
                ignore_private_variables=False,
            )
            return len(d) == 0

    def __hash__(self):
        # for now we use the address of the object for hash, but we can change it in the future
        # to be based on the attributes e.g. with DeepHash or similar
        return hash(id(self))


def with_signature(obj, val, obj_module=None, obj_class=None):
    if obj_module is None:
        obj_module = obj.__module__.__str__()
    if obj_class is None:
        obj_class = obj.__class__.__name__
    d = {"_module": obj_module, "_class": obj_class, "_object": val}
    if hasattr(obj, "dtype"):
        d.update({"dtype": str(obj.dtype)})
    return d


# --- from json (decode)
class FromSerializable:
    def __init__(self):
        self.class_name = "class_name"
        self.module_name = "module_name"
        self.registry = {}

    def __get__(self, instance, owner):
        if instance is None:
            return self
        class_module = (
            getattr(instance, self.class_name),
            getattr(instance, self.module_name),
        )
        if class_module not in self.registry:
            _class = (class_module[0], "")
            _module = ("", class_module[1])
            if (_class in self.registry) and (_module in self.registry):
                logger.error(
                    f"the saved object {class_module} is ambiguous. There are at least two possibilites to decode the object"
                )
            elif _class in self.registry:
                class_module = _class
            elif _module in self.registry:
                class_module = _module
            else:
                class_module = ("", "")
        method = self.registry[class_module]
        return method.__get__(instance, owner)

    def register(self, class_name="", module_name=""):
        def decorator(method):
            self.registry[(class_name, module_name)] = method
            return method

        return decorator


class FromSerializableRegistry:
    from_serializable = FromSerializable()
    class_name = ""
    module_name = ""

    def __init__(self, obj, d, dave_hook_funct):
        self.obj = obj
        self.d = d
        self.dave_hook = dave_hook_funct

    @from_serializable.register(class_name="davestructure", module_name="dave_core.dave_structure")
    def davestructure(self):
        if isinstance(self.obj, str):  # backwards compatibility
            from dave_core.io.file_io import from_json_string

            return from_json_string(self.obj)
        else:
            dave_dataset = create_empty_dataset()
            dataset = None
            for key in dave_dataset.keys():
                if (not isinstance(dave_dataset[key], str)) and (
                    next(iter(self.obj)) in dave_dataset[key].keys()
                ):
                    dataset = dave_dataset[key]
                elif isinstance(dave_dataset[key], davestructure):
                    for key_sec in dave_dataset[key].keys():
                        if next(iter(self.obj)) in dave_dataset[key][key_sec].keys():
                            dataset = dave_dataset[key][key_sec]
            if dataset is None:
                dataset = dave_dataset
            dataset.update(self.obj)
            return dataset

    @from_serializable.register(class_name="Series", module_name="pandas.core.series")
    def Series(self):
        is_multiindex = self.d.pop("is_multiindex", False)
        index_name = self.d.pop("index_name", None)
        index_names = self.d.pop("index_names", None)
        ser = read_json(self.obj, precise_float=True, **self.d)

        # restore index name and Multiindex
        if index_name is not None:
            ser.index.name = index_name
        if is_multiindex:
            try:
                if len(ser) == 0:
                    ser.index = MultiIndex.from_tuples([], names=index_names, dtype=int64)
                else:
                    ser.index = MultiIndex.from_tuples(
                        Series(ser.index).apply(literal_eval).tolist()
                    )
            except Exception:
                logger.warning("Converting index to multiindex failed.")
            else:
                if index_names is not None:
                    ser.index.names = index_names
        return ser

    @from_serializable.register(class_name="DataFrame", module_name="pandas.core.frame")
    def DataFrame(self):
        is_multiindex = self.d.pop("is_multiindex", False)
        is_multicolumn = self.d.pop("is_multicolumn", False)
        index_name = self.d.pop("index_name", None)
        index_names = self.d.pop("index_names", None)
        column_name = self.d.pop("column_name", None)
        column_names = self.d.pop("column_names", None)

        obj = self.obj
        if isinstance(obj, str) and (not Path(obj).is_absolute() or not obj.endswith(".json")):
            obj = io.StringIO(obj)

        df = read_json(obj, precise_float=True, convert_axes=False, **self.d)

        if not df.shape[0] or self.d.get("orient", False) == "columns":
            try:
                df.set_index(df.index.astype(int64), inplace=True)
            except (ValueError, TypeError, AttributeError):
                logger.debug("failed setting index to int")
        if self.d.get("orient", False) == "columns":
            try:
                df.columns = df.columns.astype(int64)
            except (ValueError, TypeError, AttributeError):
                logger.debug("failed setting columns to int")

        # restore index name and Multiindex
        if index_name is not None:
            df.index.name = index_name
        if column_name is not None:
            df.columns.name = column_name
        if is_multiindex:
            try:
                if len(df) == 0:
                    df.index = MultiIndex.from_frame(DataFrame(columns=index_names, dtype=int64))
                else:
                    df.index = MultiIndex.from_tuples(Series(df.index).apply(literal_eval).tolist())
                # slower alternative code:
                # df.index = pd.MultiIndex.from_tuples([literal_eval(idx) for idx in df.index])
            except Exception:
                logger.warning("Converting index to multiindex failed.")
            else:
                if index_names is not None:
                    df.index.names = index_names
        if is_multicolumn:
            try:
                if len(df) == 0:
                    df.columns = MultiIndex.from_frame(DataFrame(columns=column_names, dtype=int64))
                else:
                    df.columns = MultiIndex.from_tuples(
                        Series(df.columns).apply(literal_eval).tolist()
                    )
            except Exception:
                logger.warning("Converting columns to multiindex failed.")
            else:
                if column_names is not None:
                    df.columns.names = column_names

        # recreate jsoned objects
        for col in (
            "object",
            "controller",
        ):  # "controller" for backwards compatibility
            if col in df.columns:
                df[col] = df[col].apply(self.dave_hook)
        return df

    @from_serializable.register(class_name="MultiGraph", module_name="networkx")
    def networkx(self):
        mg = json_graph.adjacency_graph(self.obj, attrs={"id": "json_id", "key": "json_key"})
        edges = []
        for n1, n2, e in mg.edges:
            attr = {
                k: v
                for k, v in mg.get_edge_data(n1, n2, key=e).items()
                if k not in ("json_id", "json_key")
            }
            attr["key"] = e
            edges.append((n1, n2, attr))
        mg.clear_edges()
        for n1, n2, ed in edges:
            mg.add_edge(n1, n2, **ed)
        return mg

    @from_serializable.register(class_name="method")
    def method(self):
        logger.warning("deserializing of method not implemented")
        # class_ = getattr(module, obj) # doesn't work
        return self.obj

    @from_serializable.register(class_name="function")
    def function(self):
        module = importlib.import_module(self.module_name)
        if not hasattr(module, self.obj):  # in case a function is a lambda or is not defined
            raise UserWarning(
                f"Could not find the definition of the function {self.obj} in the module {module.__name__}"
            )
        class_ = getattr(module, self.obj)  # works
        return class_

    @from_serializable.register()
    def rest(self):
        module = importlib.import_module(self.module_name)
        class_ = getattr(module, self.class_name)
        if isclass(class_) and issubclass(class_, JSONSerializableClass):
            if isinstance(self.obj, str):
                self.obj = json.loads(self.obj, cls=DAVEJSONDecoder, object_hook=dave_hook)
                # backwards compatibility
            if "net" in self.obj:
                del self.obj["net"]
            return class_.from_dict(self.obj)
        else:
            # for non-pp objects, e.g. tuple
            try:
                return class_(self.obj, **self.d)
            except ValueError:
                data = json.loads(self.obj)
                df = DataFrame(columns=self.d["columns"])
                for d in data["features"]:
                    idx = int(d["id"])
                    for prop, val in d["properties"].items():
                        df.at[idx, prop] = val
                    # for geom, val in d["geometry"].items():
                    #     df.at[idx, geom] = val
                return df

    @from_serializable.register(class_name="GeoDataFrame", module_name="geopandas.geodataframe")
    def GeoDataFrame(self):
        df = GeoDataFrame.from_features(fiona.Collection(self.obj), crs=self.d["crs"])
        # set original index
        if "id" in df:
            df.set_index(df["id"].values.astype(int64), inplace=True)
        else:
            df.set_index(df.index.values.astype(int64), inplace=True)
        # coords column is not handled properly when using from_features
        if "coords" in df:
            # df['coords'] = df.coords.apply(json.loads)
            valid_coords = ~isnull(df.coords)
            df.loc[valid_coords, "coords"] = df.loc[valid_coords, "coords"].apply(json.loads)
        df = df.reindex(columns=self.d["columns"])

        # df.astype changes geodataframe to dataframe -> _preserve_dtypes fixes it
        _preserve_dtypes(df, dtypes=self.d["dtype"])
        return df

    @from_serializable.register(class_name="GeoSeries", module_name="geopandas.geoseries")
    def GeoSeries(self):
        # create GeoDataFrame because from_feature function exist only for gdf
        df = GeoDataFrame.from_features(fiona.Collection(self.obj), crs=self.d["crs"])
        # set original index
        if "id" in df:
            df.set_index(df["id"].values.astype(int64), inplace=True)
        else:
            df.set_index(df.index.values.astype(int64), inplace=True)
        # return only geometry column because it is the only relevant column for Geoseries
        return df["geometry"]

    @from_serializable.register(module_name="shapely")
    def shapely(self):
        return shape(self.obj)


def dave_hook(
    d,
    deserialize_pandas=True,
    empty_dict_like_object=None,
    registry_class=FromSerializableRegistry,
):
    try:
        if "_module" in d and "_class" in d:
            if "pandas" in d["_module"] and not deserialize_pandas:
                return json.dumps(d)
            elif "_object" in d:
                obj = d.pop("_object")
            elif "_state" in d:
                obj = d["_state"]
                if "_init" in obj:
                    del obj["_init"]
                return obj  # backwards compatibility
            else:
                # obj = {"_init": d, "_state": dict()}  # backwards compatibility
                obj = {key: val for key, val in d.items() if key not in ["_module", "_class"]}
            fs = registry_class(obj, d, dave_hook)
            fs.class_name = d.pop("_class", "")
            fs.module_name = d.pop("_module", "")
            fs.empty_dict_like_object = empty_dict_like_object
            return fs.from_serializable()
        else:
            return d
    except TypeError:
        logger.debug(f"Loading your grid raised a TypeError. {d} raised this exception")
        return d


class DAVEJSONDecoder(json.JSONDecoder):
    def __init__(self, **kwargs):
        deserialize_pandas = kwargs.pop("deserialize_pandas", True)
        empty_dict_like_object = kwargs.pop("empty_dict_like_object", None)
        registry_class = kwargs.pop("registry_class", FromSerializableRegistry)
        super_kwargs = {
            "object_hook": partial(
                dave_hook,
                deserialize_pandas=deserialize_pandas,
                empty_dict_like_object=empty_dict_like_object,
                registry_class=registry_class,
            )
        }
        super_kwargs.update(kwargs)
        super().__init__(**super_kwargs)


# --- to json (encode)
class DAVEJSONEncoder(json.JSONEncoder):
    def __init__(self, isinstance_func=isinstance_partial, **kwargs):
        super().__init__(**kwargs)
        self.isinstance_func = isinstance_func

    def iterencode(self, o, _one_shot=False):
        """Encode the given object and yield each string
        representation as available.

        For example::

            for chunk in JSONEncoder().iterencode(bigobject):
                mysocket.write(chunk)

        """
        if self.check_circular:
            markers = {}
        else:
            markers = None
        if self.ensure_ascii:
            _encoder = json.encoder.encode_basestring_ascii
        else:
            _encoder = json.encoder.encode_basestring

        def floatstr(
            o,
            allow_nan=self.allow_nan,
            _repr=float.__repr__,
            _inf=json.encoder.INFINITY,
            _neginf=-json.encoder.INFINITY,
        ):
            # Check for specials.  Note that this type of test is processor
            # and/or platform-specific, so do tests which don't depend on the
            # internals.

            if o != o:
                text = "NaN"
            elif o == _inf:
                text = "Infinity"
            elif o == _neginf:
                text = "-Infinity"
            else:
                return _repr(o)

            if not allow_nan:
                raise ValueError("Out of range float values are not JSON compliant: " + repr(o))

            return text

        _iterencode = json.encoder._make_iterencode(
            markers,
            self.default,
            _encoder,
            self.indent,
            floatstr,
            self.key_separator,
            self.item_separator,
            self.sort_keys,
            self.skipkeys,
            _one_shot,
            isinstance=self.isinstance_func,
        )
        return _iterencode(o, 0)

    def default(self, o):
        try:
            s = to_serializable(o)
        except TypeError:
            # Let the base class default method raise the TypeError
            return json.JSONEncoder.default(self, o)
        else:
            return s


@singledispatch
def to_serializable(obj):
    logger.debug("standard case")
    return str(obj)


@to_serializable.register(davestructure)
def json_dave(obj):
    net_dict = {k: item for k, item in obj.items() if not k.startswith("_")}
    data = with_signature(obj, net_dict)
    return data


@to_serializable.register(ndarray)
def json_array(obj):
    logger.debug("ndarray")
    d = with_signature(obj, list(obj), obj_module="numpy", obj_class="array")
    return d


@to_serializable.register(integer)
def json_npint(obj):
    logger.debug("integer")
    d = with_signature(obj, int(obj), obj_module="numpy")
    d.pop("dtype")
    return d


@to_serializable.register(floating)
def json_npfloat(obj):
    logger.debug("floating")
    if isnan(obj):
        d = with_signature(obj, str(obj), obj_module="numpy")
    else:
        d = with_signature(obj, float(obj), obj_module="numpy")
    d.pop("dtype")
    return d


@to_serializable.register(bool_)
def json_npbool(obj):
    logger.debug("boolean")
    d = with_signature(obj, "true" if obj else "false", obj_module="numpy")
    d.pop("dtype")
    return d


@to_serializable.register(number)
def json_num(obj):
    logger.debug("numbers.Number")
    return str(obj)


@to_serializable.register(complex)
def json_complex(obj):
    logger.debug("complex")
    d = with_signature(obj, str(obj), obj_module="builtins", obj_class="complex")
    d.pop("dtype")
    return d


@to_serializable.register(bool)
def json_bool(obj):
    logger.debug("bool")
    return "true" if obj else "false"


@to_serializable.register(tuple)
def json_tuple(obj):
    logger.debug("tuple")
    d = with_signature(obj, list(obj), obj_module="builtins", obj_class="tuple")
    return d


@to_serializable.register(set)
def json_set(obj):
    logger.debug("set")
    d = with_signature(obj, list(obj), obj_module="builtins", obj_class="set")
    return d


@to_serializable.register(frozenset)
def json_frozenset(obj):
    logger.debug("frozenset")
    d = with_signature(obj, list(obj), obj_module="builtins", obj_class="frozenset")
    return d


@to_serializable.register(Graph)
def json_networkx(obj):
    logger.debug("nx graph")
    json_string = json_graph.adjacency_data(obj, attrs={"id": "json_id", "key": "json_key"})
    d = with_signature(obj, json_string, obj_module="networkx")
    return d


@to_serializable.register(JSONSerializableClass)
def controller_to_serializable(obj):
    logger.debug("JSONSerializableClass")
    d = with_signature(obj, obj.to_json())
    return d


@to_serializable.register(Index)
def json_pdindex(obj):
    logger.debug("pd.Index")
    return with_signature(obj, list(obj), obj_module="pandas")


@to_serializable.register(DataFrame)
def json_dataframe(obj):
    logger.debug("DataFrame")
    orient = (
        "split"
        if not isinstance(obj.index, MultiIndex) and not isinstance(obj.columns, MultiIndex)
        else "columns"
    )
    json_string = obj.to_json(orient=orient, default_handler=to_serializable, double_precision=15)
    d = with_signature(obj, json_string)
    d["orient"] = orient
    if len(obj.columns) > 0 and isinstance(obj.columns[0], str):
        d["dtype"] = obj.dtypes.astype("str").to_dict()

    # store index name (to covert by pandas with orient "split" or "columns" (and totally not with
    # Multiindex))
    if obj.index.name is not None:
        d["index_name"] = obj.index.name
    if obj.columns.name is not None:
        d["column_name"] = obj.columns.name
    if isinstance(obj.index, MultiIndex) and set(obj.index.names) != {None}:
        d["index_names"] = obj.index.names
    if isinstance(obj.columns, MultiIndex) and set(obj.columns.names) != {None}:
        d["column_names"] = obj.columns.names

    # store info that index is of type Multiindex originally
    d["is_multiindex"] = isinstance(obj.index, MultiIndex)
    d["is_multicolumn"] = isinstance(obj.columns, MultiIndex)

    return d


@to_serializable.register(Series)
def json_series(obj):
    logger.debug("Series")
    orient = "split" if not isinstance(obj.index, MultiIndex) else "index"
    d = with_signature(
        obj,
        obj.to_json(orient=orient, default_handler=to_serializable, double_precision=15),
    )
    d.update({"dtype": str(obj.dtypes), "orient": orient, "typ": "series"})

    # store index name (to covert by pandas with orient "split" or "columns" (and totally not with
    # Multiindex))
    if obj.index.name is not None:
        d["index_name"] = obj.index.name
    if isinstance(obj.index, MultiIndex) and set(obj.index.names) != {None}:
        d["index_names"] = obj.index.names

    # store info that index is of type Multiindex originally
    d["is_multiindex"] = isinstance(obj.index, MultiIndex)

    return d


@to_serializable.register(GeoDataFrame)
def json_geodataframe(obj):
    logger.debug("GeoDataFrame")
    d = with_signature(obj, obj.to_json())
    d.update(
        {
            "dtype": obj.dtypes.astype("str").to_dict(),
            "crs": obj.crs,
            "columns": obj.columns,
        }
    )
    return d


@to_serializable.register(GeoSeries)
def json_geoseries(obj):
    data = with_signature(obj, obj.to_json())
    data.update({"dtype": str(obj.dtypes), "typ": "geoseries", "crs": obj.crs})
    return data


@to_serializable.register(LineString)
def json_linestring(obj):
    logger.debug("shapely linestring")
    json_string = mapping(obj)
    d = with_signature(obj, json_string, obj_module="shapely")
    return d


@to_serializable.register(Point)
def json_point(obj):
    logger.debug("shapely Point")
    json_string = mapping(obj)
    d = with_signature(obj, json_string, obj_module="shapely")
    return d


@to_serializable.register(Polygon)
def json_polygon(obj):
    logger.debug("shapely Polygon")
    json_string = mapping(obj)
    d = with_signature(obj, json_string, obj_module="shapely")
    return d
