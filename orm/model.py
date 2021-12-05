#!/usr/bin/env python3
# vim: fileencoding=utf-8 expandtab ts=4 nospell

# SPDX-FileCopyrightText: 2021 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause


from __future__ import annotations

from typing import (
    get_type_hints,
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Set,
    Tuple,
    Type,
    TypeVar,
)

import dataclasses
import datetime
import inspect
import logging
import re
import sqlite3
import typing_inspect  # type: ignore


Table = TypeVar("Table")
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

_MODELS: Dict[Type[Modelled[Table]], Model[Table]] = {}  # type: ignore


def decompose_type(_type: Type[Any]) -> Tuple[Type[Any], bool]:
    if not typing_inspect.is_optional_type(_type):
        return _type, True

    args: Set[Type[Any]] = set(typing_inspect.get_args(_type))
    args.remove(NoneType)

    if len(args) != 1:
        return _type, False

    return args.pop(), False


def is_valid_type(_type: Type[Any]) -> bool:
    if _type in _TYPE_MAP:
        return True

    if not inspect.isclass(_type):
        return False

    return _type in _MODELS


class Modelled(Generic[Table]):
    @classmethod
    def model(cls: Type[Modelled[Table]], cursor: sqlite3.Cursor) -> ModelWrapper[Table]:
        return ModelWrapper(_MODELS[cls], cursor)

    @classmethod
    def create_table(cls: Type[Modelled[Table]], cursor: sqlite3.Cursor) -> None:
        _MODELS[cls].create_table(cursor)


def _add_uniques(model: Model[Table], *uniques: List[str]) -> None:
    model.uniques = []

    for _fields in uniques:
        if not all(x in model.table_fields for x in _fields):
            raise Exception(f"Unique key not possible {_fields}")

        model.uniques.append(_fields)


def data_model(
    *uniques: List[str],
) -> Callable[[Type[Modelled[Table]]], Type[Modelled[Table]]]:
    def make_model(data_class: Type[Modelled[Table]]) -> Type[Modelled[Table]]:
        if not inspect.isclass(data_class):
            raise Exception("Can not make model data from non-class")

        table = data_class.__name__
        id_field = re.sub(r"(?<!^)(?=[A-Z])", "_", table).lower() + "_id"

        model = Model(data_class, table, id_field)
        types = get_type_hints(data_class)

        if id_field not in types:
            raise Exception(f"ID field `{id_field}` missing in `{table}`")

        for _field, _type in types.items():
            if _field in [id_field]:
                continue

            _type, required = decompose_type(_type)

            if not is_valid_type(_type):
                raise Exception(f"Field `{_field}` in `{table}` is not a valid type")

            if _type not in _TYPE_MAP:
                sub_model = _MODELS[_type]

                model.foreigners[sub_model.id_field] = (_field, sub_model)

                _field = sub_model.id_field
                _type = int

            model.table_fields[_field] = _TYPE_MAP[_type] + (" NOT NULL" if required else "")
            model.searchable_fields.append(_field)

        _add_uniques(model, *uniques)

        _MODELS[data_class] = model

        return data_class

    return make_model


class Model(Generic[Table]):
    cursor: sqlite3.Cursor
    record: Type[Table]

    table: str
    id_field: str

    table_fields: Dict[str, str]
    foreigners: Dict[str, Tuple[str, Model[Any]]]
    uniques: List[List[str]]
    searchable_fields: List[str]

    def __init__(self, record: Type[Table], table: str, id_field: str):
        self.record = record
        self.table = table
        self.id_field = id_field

        self.table_fields = {}
        self.foreigners = {}
        self.searchable_fields = []

    def create_table(self, cursor: sqlite3.Cursor) -> None:
        for _, model in self.foreigners.values():
            model.create_table(cursor)

        sql: List[str] = [f"CREATE TABLE IF NOT EXISTS `{self.table}` ("]

        sql.append(f"{self.id_field} INTEGER NOT NULL PRIMARY KEY, ")

        for _field, _type in self.table_fields.items():
            sql.append(f"[{_field}] {_type}, ")

        for _fields in self.uniques:
            sql.append(f"UNIQUE ([{'], ['.join(_fields)}]), ")

        for _field, (_, _model) in self.foreigners.items():
            sql.append(f"FOREIGN KEY ([{_field}]) REFERENCES [{_model.table}] ([{_field}]), ")

        compiled_sql = "\n".join(sql).strip(", ") + "\n);"
        _LOGGER.debug(compiled_sql)

        cursor.execute(compiled_sql)

    def get(self, cursor: sqlite3.Cursor, unique_id: int) -> Optional[Table]:
        return self.get_many(cursor, unique_id).get(unique_id, None)

    def get_many(self, cursor: sqlite3.Cursor, *ids: int) -> Dict[int, Table]:
        if not ids:
            return {}

        fields: List[str] = list(self.table_fields.keys())
        fields.append(self.id_field)

        sql = (
            f"SELECT [{'], ['.join(fields)}] FROM [{self.table}] "
            f"WHERE [{self.id_field}] IN ({', '.join(['?'] * len(ids))})"
        )

        _LOGGER.debug(sql)
        _LOGGER.debug(ids)

        cursor.execute(sql, tuple(ids))

        rows = cursor.fetchall()

        if not rows:
            return {}

        packed = [dict(zip(fields, row)) for row in rows]

        del rows

        for fkey, (okey, model) in self.foreigners.items():
            fids: Set[int] = {row[fkey] for row in packed if row[fkey]}
            frens = model.get_many(cursor, *fids)

            for row in packed:
                row[okey] = frens[row[fkey]] if row[fkey] else None
                del row[fkey]

        output: Dict[int, Table] = {}

        for row in packed:
            output[row[self.id_field]] = self.record(**row)  # type: ignore

        return output

    def all(self, cursor: sqlite3.Cursor) -> List[Table]:
        sql = f"SELECT {self.id_field} FROM [{self.table}]"

        _LOGGER.debug(sql)

        cursor.execute(sql)

        ids = [x[0] for x in cursor.fetchall()]

        return list(self.get_many(cursor, *ids).values())

    @staticmethod
    def where_clause(field: str, kwargs: Dict[str, Any]) -> str:
        if not isinstance(kwargs[field], list):
            return f"[{field}] = :{field}"

        fields = []
        i = 0
        null = False

        for value in kwargs[field]:
            if value is None:
                null = True
                continue

            subfield = field + "__" + str(i)
            kwargs[subfield] = value
            fields.append(":" + subfield)
            i += 1

        if not fields and null:
            return f"[{field}] IS NULL"

        return (
            f"([{field}] IN ({', '.join(fields)})"
            + (f" OR [{field}] IS NULL" if null else "")
            + ")"
        )

    def search(self, cursor: sqlite3.Cursor, **kwargs: Any) -> List[Table]:
        for name, model in self.foreigners.values():
            if name in kwargs and isinstance(kwargs[name], model.record):
                kwargs[model.id_field] = getattr(kwargs[name], model.id_field)
                del kwargs[name]

        for key in kwargs:
            if key not in self.searchable_fields:
                raise AttributeError(f"{self.record.__name__} has no attribute {key}")

        args = list(kwargs.keys())
        clauses = []

        for arg in args:
            clauses.append(self.where_clause(arg, kwargs))

        sql = f"SELECT {self.id_field} FROM [{self.table}] WHERE " + " AND ".join(clauses)

        _LOGGER.debug(sql)
        _LOGGER.debug(kwargs)

        cursor.execute(sql, kwargs)

        ids = [x[0] for x in cursor.fetchall()]

        return list(self.get_many(cursor, *ids).values())

    def store(self, cursor: sqlite3.Cursor, record: Table) -> bool:
        if not isinstance(record, self.record):
            raise Exception("Wrong type")

        data = dataclasses.asdict(record)

        for _field, (_attr, _model) in self.foreigners.items():
            data[_field] = data[_attr][_field] if data[_attr] else None
            del data[_attr]

        fields = list(self.table_fields.keys())

        if data[self.id_field] is None:
            del data[self.id_field]
        else:
            fields.append(self.id_field)

        sql = (
            f"INSERT OR REPLACE INTO [{self.table}] ([{'], ['.join(fields)}])"
            f" VALUES (:{', :'.join(fields)})"
        )

        _LOGGER.debug(sql)
        _LOGGER.debug(data)

        cursor.execute(sql, data)

        setattr(record, self.id_field, cursor.lastrowid)

        return True


class ModelWrapper(Generic[Table]):
    model: Model[Table]
    cursor: sqlite3.Cursor

    def __init__(self, model: Model[Table], cursor: sqlite3.Cursor):
        self.model = model
        self.cursor = cursor

    def store(self, record: Table) -> bool:
        return self.model.store(self.cursor, record)

    def all(self) -> List[Table]:
        return self.model.all(self.cursor)

    def get(self, unique_id: int) -> Optional[Table]:
        return self.model.get(self.cursor, unique_id)

    def get_many(self, *ids: int) -> Dict[int, Table]:
        return self.model.get_many(self.cursor, *ids)

    def search(self, **kwargs: Any) -> List[Table]:
        return self.model.search(self.cursor, **kwargs)
