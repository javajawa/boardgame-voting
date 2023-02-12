#!/usr/bin/env python3
# vim: fileencoding=utf-8 expandtab ts=4 nospell

# SPDX-FileCopyrightText: 2020-2021 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

"""
Abstract class and Model implementation for basic Tables in the ORM system.

Tables store an array of fields.
"""

from __future__ import annotations

from typing import (
    get_type_hints,
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Mapping,
    Optional,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
)

import datetime
import inspect
import logging
import re
import sqlite3
import typing_inspect  # type: ignore


from .exceptions import MissingIdField, ORMException
from .abc import (
    BaseModel,
    MutableFilters as Filters,
    FilterTypes,
    ForeignerMap,
    PrimitiveTypes,
    execute,
)


ModelledTable = TypeVar("ModelledTable", bound="Table[Any]")
SecondTable = TypeVar("SecondTable", bound="Table[Any]")
NoneType: Type[None] = type(None)

_LOGGER = logging.getLogger("tiny-orm")

_TYPE_MAP = {
    str: "TEXT",
    bytes: "BLOB",
    int: "INTEGER",
    float: "REAL",
    bool: "SMALLINT",
    datetime.datetime: "INTEGER",
}

_UNIQUES = "__orm_uniques__"
_SUBTABLES = "__orm_subtable__"

_MODELS: Dict[Type[ModelledTable], TableModel[ModelledTable]] = {}  # type: ignore


def _get_model(data_class: Type[Table[Any]]) -> TableModel[ModelledTable]:
    """Gets the TableModel instance for a given class that extends Table."""

    if data_class not in _MODELS:
        # Prevent recursion problems with self-referential classes.
        _MODELS[data_class] = ...  # type: ignore
        _MODELS[data_class] = _make_model(data_class)

    return _MODELS[data_class]


def _make_model(cls: Type[ModelledTable]) -> TableModel[ModelledTable]:
    """Gets the TableModel instance for a given class that extends Table."""

    if not inspect.isclass(cls):
        raise TypeError("Can not make model data from non-class")

    if not issubclass(cls, Table):
        raise TypeError("Data models can only be made from sub-classes of Table")

    table = cls.__name__
    id_field = re.sub(r"(?<!^)(?=[A-Z])", "_", table).lower() + "_id"

    model: TableModel[ModelledTable] = TableModel(cls, table, id_field)  # type: ignore
    types = get_type_hints(cls)

    if id_field not in types:
        raise MissingIdField(f"ID field `{id_field}` missing in `{table}`")

    model.table_fields[id_field] = "INTEGER NOT NULL PRIMARY KEY"

    for _field, _type in types.items():
        if _field in [id_field]:
            continue

        _process_type(model, cls, _field, _type)  # type: ignore

    return model


def _process_type(
    model: TableModel[ModelledTable],
    cls: Type[ModelledTable],
    _field: str,
    _type: Type[Any],
) -> None:
    _type, required = _decompose_type(_type)

    for field, submodel in getattr(cls, _SUBTABLES, {}).items():
        if _field == field:
            if _type != submodel.get_expected_type():
                raise ORMException(
                    f"Unexpected type {_type} for submodel {submodel.model.table}"
                )

            submodel.connect_to(model)
            model.submodels[_field] = submodel
            return

    if not _is_valid_type(_type):
        raise ORMException(
            f"Field `{_field}` of type `{_type}` in `{model.table}` is not a valid type"
        )

    if _type not in _TYPE_MAP:
        # Set up the foreign type mapping
        sub_model = model if _type == cls else _get_model(_type)
        model.foreigners[_field] = (sub_model.id_field, sub_model)
        # Update our field info with the underlying ID reference
        _type = int
        _field = _field if _type == cls else sub_model.id_field

    model.table_fields[_field] = _TYPE_MAP[_type] + (" NOT NULL" if required else "")


def _decompose_type(_type: Type[Any]) -> Tuple[Type[Any], bool]:
    """Converts "Type" or "Optional[Type]" to Type + Required"""

    if not typing_inspect.is_optional_type(_type):
        return _type, True

    args: Set[Type[Any]] = set(typing_inspect.get_args(_type))
    args.remove(NoneType)

    if len(args) != 1:
        _type.__args__ = tuple(args)
        return _type, False

    return args.pop(), False


def _is_valid_type(_type: Type[Any]) -> bool:
    """Checks if a given type is recognised and usable with the ORM system"""

    if _type in _TYPE_MAP:
        return True

    if not inspect.isclass(_type):
        return False

    return issubclass(_type, Table)


class Table(Generic[ModelledTable]):
    """
    Base class for defining a basic data table.

    Your tables should extend this class, with themselves as the generic parameter:

        class User(Table["User"]):

    This allows typing tools to determine that the model will return objects
    of this type.

    The fields of the table are dervived from the attributes of the class,
    using the type information for the following scalar types:

        str      => TEXT
        bytes    => BLOB
        int      => INTEGER
        float    => REAL
        bool     => SMALLINT

    Additionally, another type that extends Table can be used; this will be
    mapped to an INTEGER column with the other Table's ID field name, and a
    FOREIGN KEY will be added.

    You *must* specify the primary key field, which is the "{table}_id"
    (snake case)

        class User(Table["User"]):
            user_id: int
            name: str
            foo: OtherTable
    """

    def __init__(self, **kwargs: Any):
        """
        Creates a record of this table type.

        The init method of your class must support parameters for each of the
        fields listed in the class, using the same names.

        If you are using a dataclass as your table type, this will be handled
        for you. Otherwise, you will need to override this method.

        This function uses **kwargs to prevent type checkers from complaining
        about this undescribable requirement.
        """

    @classmethod
    def model(cls, cursor: sqlite3.Cursor) -> ModelWrapper[ModelledTable]:
        """Get the model instance, using the supplied cursor"""

        return ModelWrapper(_get_model(cls), cursor)

    @classmethod
    def create_table(cls, cursor: sqlite3.Cursor) -> None:
        """
        Ensures that this table is created in the SQLite database backing
        the supplied cursor.

        It is recommended that you call this function as soon as you open the
        database, unless your program design guarantees the table will exist.

        Note that py-tiny-orm does not support altering existing tables.
        """

        _get_model(cls).create_table(cursor)


def unique(*fields: str) -> Callable[[Type[ModelledTable]], Type[ModelledTable]]:
    """Adds a unique key to a Table"""

    def _unique(cls: Type[ModelledTable]) -> Type[ModelledTable]:
        """Adds a unique key to a Table"""

        if not issubclass(cls, Table):
            raise ORMException(f"{cls.__name__} is not a sub class of Table")

        model: TableModel[ModelledTable] = _get_model(cls)

        if not all(field in model.table_fields for field in fields):
            raise ORMException(f"{cls.__name__} does not have all fields specified in key")

        uniques: List[Set[str]] = getattr(cls, _UNIQUES, [])
        uniques.append(set(fields))
        setattr(cls, _UNIQUES, uniques)

        return cls

    return _unique


class TableModel(Generic[ModelledTable], BaseModel):
    """The generated model for a given Table."""

    record: Type[ModelledTable]

    created: bool
    table: str
    id_field: str

    table_fields: Dict[str, str]
    foreigners: ForeignerMap
    submodels: Dict[str, SubTable[Any]]

    def __init__(self, record: Type[ModelledTable], table: str, id_field: str):
        self.record = record
        self.table = table
        self.id_field = id_field
        self.created = False

        self.table_fields = {}
        self.foreigners = {}
        self.submodels: Dict[str, SubTable[Any]] = {}

    def create_table(self, cursor: sqlite3.Cursor) -> None:
        """Creates the table(s) in SQLite"""

        if self.created:
            return

        # Preset this to true to work with Foreign key loops.
        self.created = True

        for _, model in self.foreigners.values():
            model.create_table(cursor)

        compiled_sql = self._create_table_sql()

        execute(cursor, compiled_sql, tuple())

        for smodel in self.submodels.values():
            smodel.model.create_table(cursor)

    def _create_table_sql(self) -> str:
        """CREATE TABLE Statement for this table"""

        sql: List[str] = [f"CREATE TABLE IF NOT EXISTS `{self.table}` ("]

        for _field, _type in self.table_fields.items():
            sql.append(f"[{_field}] {_type}, ")

        for _fields in getattr(self.record, _UNIQUES, []):
            sql.append(f"UNIQUE ([{'], ['.join(_fields)}]), ")

        for _field, (f_key, _model) in self.foreigners.items():
            sql.append(
                f"FOREIGN KEY ([{f_key}]) REFERENCES [{_model.table}] ([{_model.id_field}]), "
            )

        return "\n".join(sql).strip(", ") + "\n);"

    def all(self, cursor: sqlite3.Cursor) -> List[ModelledTable]:
        """
        Returns all records on the current table.

        Note: records will be loaded into memory before being returned,
        in order to optimise the number of queries to realted tables.
        """

        sql = f"SELECT {self.id_field} FROM [{self.table}]"

        execute(cursor, sql, tuple())

        ids = [x[0] for x in cursor.fetchall()]

        return list(self.get_many(cursor, *ids).values())

    def get(self, cursor: sqlite3.Cursor, unique_id: int) -> Optional[ModelledTable]:
        """Gets a record by ID, or None if no record with that ID exists"""

        return self.get_many(cursor, unique_id).get(unique_id, None)

    def get_many(self, cursor: sqlite3.Cursor, *ids: int) -> Dict[int, ModelledTable]:
        """
        Gets all records that exist with ID in the supplied list.

        Entries in the dict are not generated for records which do not exist.
        """

        if not ids:
            return {}

        fields: List[str] = list(self.table_fields.keys())
        fields.append(self.id_field)

        sql = (
            f"SELECT [{'], ['.join(fields)}] FROM [{self.table}] "
            f"WHERE [{self.id_field}] IN ({', '.join(['?'] * len(ids))})"
        )

        execute(cursor, sql, tuple(ids))

        rows = cursor.fetchall()

        if not rows:
            return {}

        packed = [dict(zip(fields, row)) for row in rows]

        del rows

        packed = self._add_joins(cursor, packed)

        output: Dict[int, ModelledTable] = {}

        for row in packed:
            output[row[self.id_field]] = self.record(**row)

        return output

    def _add_joins(
        self, cursor: sqlite3.Cursor, packed: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        for our_key, (their_key, model) in self.foreigners.items():
            their_ids: Set[int] = {row[their_key] for row in packed}
            frens = model.get_many(cursor, *their_ids)

            for row in packed:
                row[our_key] = frens[row[their_key]]

                if our_key != their_key:
                    del row[their_key]

        for our_key, sub_model in self.submodels.items():
            children = sub_model.select(cursor, *[row[self.id_field] for row in packed])

            for row in packed:
                row[our_key] = children[row[self.id_field]]

        return packed

    def search(self, cursor: sqlite3.Cursor, **kwargs: FilterTypes) -> List[ModelledTable]:
        """
        Gets records for this model which match the given filters.

        You can filter using any field in the table, or by a foreign object.

            class Foo(Table["Foo"]):
                foo_id: int

            class Bar(Table["Bar"]
                bar_id: int
                foo: Foo
                name: str

            # Search by standard field
            Bar.model(cursor).search(name="Hello")

            # Search by foreign ID
            Bar.model(cursor).search(foo_id=1)

            # Search by foreign object
            Bar.model(cursor).search(foo=Foo(1))

            # Search by local ID
            # NOTE: This is valid, but using Model.get() is faster.
            Bar.model(cursor).search(bar_id=123)
        """

        sql, params = self.where(self.foreigners, kwargs)
        sql = f"SELECT {self.id_field} FROM [{self.table}] WHERE " + sql

        execute(cursor, sql, params)

        ids = [x[0] for x in cursor.fetchall()]

        return list(self.get_many(cursor, *ids).values())

    def store(self, cursor: sqlite3.Cursor, record: ModelledTable) -> bool:
        """
        Writes a record to the database.

        In all cases, this is done as an INSERT OR REPLACE statement.
        If the ID field is not set, this may cause the ID of a record to change,
        where it is matched via a unique key.

        The ID field will be updated with the inserted row's ID.
        """

        if not isinstance(record, self.record):
            raise ORMException("Wrong type")

        fields = list(self.table_fields.keys())
        data: Dict[str, Any] = {}

        for field in fields:
            data[field] = getattr(record, field, None)

        for _attr, (_id_field, _model) in self.foreigners.items():
            _data = getattr(record, _attr)
            data[_id_field] = getattr(_data, _model.id_field) if _data is not None else None

        if data[self.id_field] is None:
            fields.remove(self.id_field)
            del data[self.id_field]
        else:
            fields.append(self.id_field)

        sql = (
            f"INSERT OR REPLACE INTO [{self.table}] ([{'], ['.join(fields)}])"
            f" VALUES (:{', :'.join(fields)})"
        )

        execute(cursor, sql, data)

        setattr(record, self.id_field, cursor.lastrowid)

        for our_key, sub_model in self.submodels.items():
            sub_data = getattr(record, our_key)
            sub_model.store(
                cursor,
                record,
                set(sub_data) if isinstance(sub_data, (set, list)) else None,
                sub_data if isinstance(sub_data, dict) else None,
            )

        return True

    def delete(self, cursor: sqlite3.Cursor, **kwargs: FilterTypes) -> int:
        """
        Gets records for this model which match the given filters.

        You can filter using any field in the table, or by a foreign object.

            class Foo(Table["Foo"]):
                foo_id: int

            class Bar(Table["Bar"]
                bar_id: int
                foo: Foo
                name: str

            # Search by standard field
            Bar.model(cursor).search(name="Hello")

            # Search by foreign ID
            Bar.model(cursor).search(foo_id=1)

            # Search by foreign object
            Bar.model(cursor).search(foo=Foo(1))

            # Search by local ID
            # NOTE: This is valid, but using Model.get() is faster.
            Bar.model(cursor).search(bar_id=123)
        """

        sql, params = self.where(self.foreigners, kwargs)
        sql = f"DELETE FROM [{self.table}] WHERE " + sql

        execute(cursor, sql, params)

        return int(cursor.rowcount)


class ModelWrapper(Generic[ModelledTable]):
    """
    Binding class between a Table, it's Model, and an SQL-Lite cursor.

    The Model for table "Foo" can be retrieved with

        Foo.model(cursor)
    """

    model: TableModel[ModelledTable]
    cursor: sqlite3.Cursor

    def __init__(self, model: TableModel[ModelledTable], cursor: sqlite3.Cursor):
        self.model = model
        self.cursor = cursor

    def all(self) -> List[ModelledTable]:
        """
        Returns all records on the current table.

        Note: records will be loaded into memory before being returned,
        in order to optimise the number of queries to realted tables.
        """

        return self.model.all(self.cursor)

    def get(self, unique_id: int) -> Optional[ModelledTable]:
        """Gets a record by ID, or None if no record with that ID exists"""

        return self.model.get(self.cursor, unique_id)

    def get_many(self, *ids: int) -> Dict[int, ModelledTable]:
        """
        Gets all records that exist with ID in the supplied list.

        Entries in the dict are not generated for records which do not exist.
        """

        return self.model.get_many(self.cursor, *ids)

    def search(self, **kwargs: FilterTypes) -> List[ModelledTable]:
        """
        Gets records for this model which match the given filters.

        You can filter using any field in the table, or by a foreign object.

            class Foo(Table["Foo"]):
                foo_id: int

            class Bar(Table["Bar"]
                bar_id: int
                foo: Foo
                name: str

            # Search by standard field
            Bar.model(cursor).search(name="Hello")

            # Search by foreign ID
            Bar.model(cursor).search(foo_id=1)

            # Search by foreign object
            Bar.model(cursor).search(foo=Foo(1))

            # Search by local ID
            # NOTE: This is value, but using Model.get() is faster.
            Bar.model(cursor).search(bar_id=123)
        """

        return self.model.search(self.cursor, **kwargs)

    def store(self, record: ModelledTable) -> bool:
        """
        Writes a record to the database.

        In all cases, this is done as an INSERT OR REPLACE statement.
        If the ID field is not set, this may cause the ID of a record to change,
        where it is matched via a unique key.

        The ID field will be updated with the inserted row's ID.
        """

        return self.model.store(self.cursor, record)

    def delete(self, **kwargs: FilterTypes) -> int:
        """
        Delete records for this model which match the given filters.

        You can filter using any field in the table, or by a foreign object.

            class Foo(Table["Foo"]):
                foo_id: int

            class Bar(Table["Bar"]
                bar_id: int
                foo: Foo
                name: str

            # Search by standard field
            Bar.model(cursor).delete(name="Hello")

            # Search by foreign ID
            Bar.model(cursor).delete(foo_id=1)

            # Search by foreign object
            Bar.model(cursor).delete(foo=Foo(1))

            # Search by local ID
            # NOTE: This is value, but using Model.get() is faster.
            Bar.model(cursor).delete(bar_id=123)
        """

        return self.model.delete(self.cursor, **kwargs)


def subtable(
    field: str,
    table: Type[ModelledTable],
    subfield: Optional[str] = None,
    pivot: Optional[str] = None,
    selectors: Optional[Dict[str, PrimitiveTypes]] = None,
) -> Callable[[Type[SecondTable]], Type[SecondTable]]:
    """Registers a field as a subtable to a Table"""

    if not subfield:
        subfield = field

    if not selectors:
        selectors = {}

    sub: SubTable[ModelledTable] = SubTable(table, subfield, pivot, selectors)

    def _subtable(cls: Type[SecondTable]) -> Type[SecondTable]:
        """Adds a subtable key to a Table"""

        if not issubclass(cls, Table):
            raise ORMException(f"{cls.__name__} is not a sub class of Table")

        subtables: Dict[str, SubTable[ModelledTable]] = getattr(cls, _SUBTABLES, {})
        subtables[field] = sub
        setattr(cls, _SUBTABLES, subtables)

        return cls

    return _subtable


class SubTable(Generic[ModelledTable], BaseModel):
    """
    Class which represents a request for the ORM tools to expand a field
    with the values in a sub table
    """

    model: TableModel[ModelledTable]
    field: str
    connector: Optional[str]
    pivot: Optional[str]
    selector: Dict[str, PrimitiveTypes]

    def __init__(
        self,
        source: Type[ModelledTable],
        field: str,
        pivot: Optional[str],
        selectors: Dict[str, PrimitiveTypes],
    ) -> None:
        # This is the model that the actual data for the sub tables is storeed in.
        self.model = _get_model(source)

        # Field is the output field mapped into new parent table
        self.field = field

        # Selectors are filters on the sub-table beyond the foreign key
        # of the parent type. This is used when you want to store two
        # different sub-types of data in one sub table.
        self.selectors = selectors

        # If this sub-table is being mapped into a dictionary, this is
        # the field to use as the key for that dictionary.
        self.pivot = pivot

        self.connector = None

        # Validate the settings we have so far (this will not include
        # the foreign key relation to the parent)
        self.validate()

    def validate(self) -> None:
        """Check if this subtable has a valid configuration.

        This includes:
          - That the underlying table model has the correct data, connector,
            and (where appropriate) pivot fields
          - That the parent table, once connected, has the correct fields in
            the model.
        """

        if self.field not in self.model.table_fields:
            raise ValueError(f"Value field {self.field} not present in {self.model.table}")

        if self.pivot:
            if (
                self.pivot not in self.model.table_fields
                and self.pivot not in self.model.foreigners
            ):
                raise ValueError(
                    f"Pivot field {self.pivot} not present in {self.model.table}"
                )

        if self.connector:
            if self.connector not in self.model.table_fields:
                raise ValueError(
                    f"Connector field {self.connector} not present in {self.model.table}"
                )

        for field in self.selectors:
            if field not in self.model.table_fields:
                raise ValueError(f"Selector field {field} not present in {self.model.table}")

    def connect_to(self, parent: TableModel[Any]) -> None:
        """Connects this sub-table to a its parent.

        The validity of the join is checked at this time.

        This method will fail if it has been connected already."""

        if self.connector:
            raise ORMException(
                "Attempting to connect an already connected sub-table instance"
            )

        # Confirm that the source table has a relation to the parent table
        # that is now claiming us as a sub-table
        if parent.id_field not in self.model.table_fields:
            raise ValueError(
                f"Can not use {self.model.table} as a sub-table of {parent.table}, "
                f"as it has no foreign key to {parent.table}"
            )

        self.connector = parent.id_field
        self.model.foreigners[parent.id_field] = (parent.id_field, parent)
        self.validate()

    def get_expected_type(self) -> Type[Any]:
        """Determines the expected type of the sub-field in the parent
        ype definition, based off the parameters to this helper class.

        This will either be a Set[] or Dict[] depending on whether a
        pivot has been specified. The types will be taken from the completed
        model of this sub-table."""

        types = get_type_hints(self.model.record)

        if self.pivot:
            return Dict[types[self.pivot], types[self.field]]  # type: ignore

        return Set[types[self.field]]  # type: ignore

    def select(
        self, cursor: sqlite3.Cursor, *connector_value: int
    ) -> Mapping[int, Union[Mapping[PrimitiveTypes, PrimitiveTypes], Set[PrimitiveTypes]]]:
        """Selects the sub table values for a set of parent objects."""

        if not self.connector:
            raise ORMException(f"{self.model.table} has not been attached to a model")

        if self.pivot:
            return self.select_pivot(cursor, connector_value)

        return self.select_column(cursor, connector_value)

    def select_column(
        self, cursor: sqlite3.Cursor, connector_value: Tuple[int, ...]
    ) -> Mapping[int, Set[PrimitiveTypes]]:
        """Selects the sub table values for a set of parent objects

        This is a sub-call of select(), for use when the sub table is a Set[] type."""

        if not self.connector:
            raise ORMException(f"{self.model.table} has not been attached to a model")

        where: Filters = dict(self.selectors)
        where[self.connector] = connector_value

        sql, params = self.where({}, where)
        sql = (
            f"SELECT [{self.connector}], [{self.field}] FROM [{self.model.table}] WHERE "
            + sql
        )

        execute(cursor, sql, params)

        result: Dict[int, Set[Any]] = dict(
            zip(connector_value, [set()] * len(connector_value))
        )

        for connected, value in cursor.fetchall():
            result[connected] += value

        return result

    def select_pivot(
        self, cursor: sqlite3.Cursor, connectors: Tuple[int, ...]
    ) -> Dict[int, Dict[PrimitiveTypes, PrimitiveTypes]]:
        """Selects the sub table values for a set of parent objects

        This is a sub-call of select(), for use when the sub table is a Dict[] type."""

        if not self.connector:
            raise ORMException(f"{self.model.table} has not been attached to a model")

        where: Filters = dict(self.selectors)
        where[self.connector] = connectors

        sql, params = self.where({}, where)
        sql = (
            f"SELECT [{self.connector}], [{self.pivot}], [{self.field}] "
            + f"FROM [{self.model.table}] WHERE "
            + sql
        )

        execute(cursor, sql, params)

        result: Dict[int, Dict[PrimitiveTypes, PrimitiveTypes]] = dict(
            zip(connectors, [{} for _ in range(len(connectors))])
        )

        for connecter, key, value in cursor.fetchall():
            result[connecter][key] = value

        return result

    def store(
        self,
        cursor: sqlite3.Cursor,
        connector: Table[Any],
        lvalues: Optional[Set[PrimitiveTypes]] = None,
        kvalues: Optional[Dict[PrimitiveTypes, PrimitiveTypes]] = None,
    ) -> None:
        """Stores a list of values for a single parent object in the sub table"""

        if not self.connector:
            raise ORMException(f"{self.model.table} has not been attached to a model")

        if self.pivot:
            if not isinstance(kvalues, dict):
                raise ORMException(
                    f"Expected dict for {self.model.table}, got {type(kvalues).__name__}"
                )

            return self.store_pivot(cursor, connector, kvalues)

        if not isinstance(kvalues, list):
            raise ORMException(
                f"Expected list for {self.model.table}, got {type(kvalues).__name__}"
            )

        if lvalues is None:
            raise ORMException(
                f"Expected set for {self.model.table}, got {type(lvalues).__name__}"
            )

        return self.store_column(cursor, connector, lvalues)

    def store_pivot(
        self,
        cursor: sqlite3.Cursor,
        connector: Table[Any],
        values: Dict[PrimitiveTypes, PrimitiveTypes],
    ) -> None:
        """Stores a dict of values in the sub table"""

        if not self.connector:
            raise ORMException(f"{self.model.table} has not been attached to a model")

        if not self.pivot:
            raise ORMException(f"{self.model.table} has not been attached to a model")

        connector_value = getattr(connector, self.connector)

        current = self.select_pivot(cursor, (connector_value,))[connector_value]
        existing = set(current.keys())
        desired = set(values.keys())

        filters: Filters = dict(self.selectors)
        filters[self.connector] = connector
        filters[self.pivot] = existing - desired

        rows = self.model.delete(cursor, **filters)

        if rows != len(existing - desired):
            _LOGGER.warning(
                (
                    "Potential issue when processing pivot sub-table: expected to delete %d rows, "
                    "but cursor only reported %d deleted."
                ),
                len(existing - desired),
                rows,
            )
            _LOGGER.warning("Filters: %s", filters)
            _LOGGER.warning("Existing: %s", existing)
            _LOGGER.warning("Desired: %s", desired)

        for new_key in desired - existing:
            filters[self.pivot] = new_key
            filters[self.field] = values[new_key]

            self.model.store(cursor, self.model.record(**filters))

    def store_column(
        self, cursor: sqlite3.Cursor, connector: Table[Any], values: Set[PrimitiveTypes]
    ) -> None:
        """Stores a list of values in the sub table"""

        if not self.connector:
            raise ORMException(f"{self.model.table} has not been attached to a model")

        if self.pivot:
            raise ORMException(f"{self.model.table} has not been attached to a model")

        connector_value = getattr(connector, self.connector)

        existing = self.select_column(cursor, (connector_value,))[connector_value]
        desired = set(values)

        filters: Filters = dict(self.selectors)
        filters[self.connector] = connector_value

        rows = self.model.delete(cursor, **filters)

        if rows != len(existing - desired):
            _LOGGER.warning(
                (
                    "Potential issue when processing column sub-table: expected to delete %d rows, "
                    "but cursor only reported %d deleted."
                ),
                len(existing - desired),
                rows,
            )
            _LOGGER.warning("Filters: %s", filters)
            _LOGGER.warning("Existing: %s", existing)
            _LOGGER.warning("Desired: %s", desired)

        for new_value in desired - existing:
            filters[self.field] = new_value

            self.model.store(cursor, self.model.record(**filters))
