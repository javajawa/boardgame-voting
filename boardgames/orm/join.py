#!/usr/bin/env python3
# vim: fileencoding=utf-8 expandtab ts=4 nospell

# SPDX-FileCopyrightText: 2020 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations

from typing import (
    get_type_hints,
    Any,
    Dict,
    Generic,
    List,
    Type,
    TypeVar,
)

import inspect
import logging
import sqlite3

from .model import Model, _MODELS as registered


Table = TypeVar("Table")
Left = TypeVar("Left")
Right = TypeVar("Right")
NoneType: Type[None] = type(None)

_LOGGER = logging.getLogger("tiny-orm")

_MODELS: Dict[Type[Joiner[Left, Right]], JoinModel[Left, Right]] = {}  # type: ignore


class Joiner(Generic[Left, Right]):
    @classmethod
    def model(
        cls: Type[Joiner[Left, Right]], cursor: sqlite3.Cursor
    ) -> JoinWrapper[Left, Right]:
        return JoinWrapper(_MODELS[cls], cursor)

    @classmethod
    def create_table(cls: Type[Joiner[Left, Right]], cursor: sqlite3.Cursor) -> None:
        _MODELS[cls].create_table(cursor)


def join_model(data_class: Type[Joiner[Left, Right]]) -> Type[Joiner[Left, Right]]:
    if not inspect.isclass(data_class):
        raise Exception("Can not make model data from non-class")

    types = get_type_hints(data_class)

    if len(types) != 2:
        raise Exception("Can only build a join table with two fields")

    left, right = types.values()

    if left not in registered:
        raise Exception(f"No model for {left.__name__}")

    if right not in registered:
        raise Exception(f"No model for {right.__name__}")

    table = data_class.__name__

    _MODELS[data_class] = JoinModel(table, registered[left], registered[right])

    return data_class


class JoinModel(Generic[Left, Right]):
    cursor: sqlite3.Cursor

    table: str
    left: Model[Left]
    right: Model[Right]

    def __init__(self, table: str, left: Model[Left], right: Model[Right]):
        self.table = table
        self.left = left
        self.right = right

    def create_table(self, cursor: sqlite3.Cursor) -> None:
        self.left.create_table(cursor)
        self.right.create_table(cursor)

        sql = f"""
            CREATE TABLE IF NOT EXISTS [{self.table}] (
              [{self.left.id_field}] INTEGER NOT NULL,
              [{self.right.id_field}] INTEGER NOT NULL,
              PRIMARY KEY ([{self.left.id_field}], [{self.right.id_field}]),
              FOREIGN KEY ([{self.left.id_field}])
                REFERENCES [{self.left.table}] ([{self.left.id_field}]),
              FOREIGN KEY ([{self.right.id_field}])
                REFERENCES [{self.right.table}] ([{self.right.id_field}])
            )
        """

        _LOGGER.debug(sql)

        cursor.execute(sql)

    def ids_for_right(self, cursor: sqlite3.Cursor, right: Right) -> List[int]:
        sql = f"""
            SELECT [{self.left.id_field}]
            FROM [{self.table}] WHERE [{self.right.id_field}] = ?
        """

        cursor.execute(sql, tuple(getattr(right, self.right.id_field)))

        return [x[0] for x in cursor.fetchall()]

    def of_right(self, cursor: sqlite3.Cursor, right: Right) -> List[Left]:
        ids = self.ids_for_right(cursor, right)

        return list(self.left.get_many(cursor, *ids).values())

    def from_right(self, cursor: sqlite3.Cursor, **kwargs: Any) -> List[Left]:
        for key in kwargs:
            if key not in self.right.searchable_fields:
                raise AttributeError(f"{self.right.record.__name__} has no attribute {key}")

        def field(_field: str) -> str:
            return f"[{_field}] = :{_field}"

        sql = (
            f"SELECT DISTINCT [{self.left.id_field}] "
            f"FROM [{self.right.table}] JOIN [{self.table}] USING ([{self.right.id_field}]) "
            f"WHERE {' AND '.join(map(field, kwargs))}"
        )

        _LOGGER.debug(sql)
        _LOGGER.debug(kwargs)

        cursor.execute(sql, kwargs)

        ids = [x[0] for x in cursor.fetchall()]

        return list(self.left.get_many(cursor, *ids).values())

    def clear_right(self, cursor: sqlite3.Cursor, right: Right) -> None:
        sql = f"DELETE FROM [{self.table}] WHERE [{self.right.id_field}] = ?"

        cursor.execute(sql, (getattr(right, self.right.id_field),))

    def ids_for_left(self, cursor: sqlite3.Cursor, left: Left) -> List[int]:
        sql = f"SELECT [{self.right.id_field}] FROM [{self.table}] WHERE [{self.left.id_field}] = ?"

        _LOGGER.debug(sql)
        _LOGGER.debug(getattr(left, self.left.id_field))

        cursor.execute(sql, (getattr(left, self.left.id_field),))

        return [x[0] for x in cursor.fetchall()]

    def of_left(self, cursor: sqlite3.Cursor, left: Left) -> List[Right]:
        ids = self.ids_for_left(cursor, left)

        return list(self.right.get_many(cursor, *ids).values())

    def from_left(self, cursor: sqlite3.Cursor, **kwargs: Any) -> List[Right]:
        for key in kwargs:
            if key not in self.left.searchable_fields:
                raise AttributeError(f"{self.left.record.__name__} has no attribute {key}")

        def field(_field: str) -> str:
            return f"[{_field}] = :{_field}"

        sql = (
            f"SELECT DISTINCT [{self.right.id_field}] "
            f"FROM [{self.left.table}] JOIN [{self.table}] USING ([{self.left.id_field}]) "
            f"WHERE {' AND '.join(map(field, kwargs))}"
        )

        _LOGGER.debug(sql)
        _LOGGER.debug(kwargs)

        cursor.execute(sql, kwargs)

        ids = [x[0] for x in cursor.fetchall()]

        return list(self.right.get_many(cursor, *ids).values())

    def clear_left(self, cursor: sqlite3.Cursor, left: Left) -> None:
        sql = f"DELETE FROM [{self.table}] WHERE [{self.left.id_field}] = ?"

        cursor.execute(sql, (getattr(left, self.left.id_field),))

    def store(self, cursor: sqlite3.Cursor, left: Left, right: Right) -> bool:
        if not isinstance(left, self.left.record):
            raise Exception("Wrong type")

        if not isinstance(right, self.right.record):
            raise Exception("Wrong type")

        left_id = getattr(left, self.left.id_field)
        right_id = getattr(right, self.right.id_field)

        sql = (
            f"INSERT OR IGNORE INTO [{self.table}] "
            f"([{self.left.id_field}], [{self.right.id_field}]) "
            f"VALUES (?, ?)"
        )

        _LOGGER.debug(sql)
        _LOGGER.debug(left_id, right_id)

        cursor.execute(sql, (left_id, right_id))

        return True


class JoinWrapper(Generic[Left, Right]):
    model: JoinModel[Left, Right]
    cursor: sqlite3.Cursor

    def __init__(self, model: JoinModel[Left, Right], cursor: sqlite3.Cursor):
        self.model = model
        self.cursor = cursor

    def store(self, left: Left, right: Right) -> bool:
        return self.model.store(self.cursor, left, right)

    def ids_for_left(self, left: Left) -> List[int]:
        return self.model.ids_for_left(self.cursor, left)

    def of_left(self, left: Left) -> List[Right]:
        return self.model.of_left(self.cursor, left)

    def from_left(self, **kwargs: Any) -> List[Right]:
        return self.model.from_left(self.cursor, **kwargs)

    def clear_left(self, left: Left) -> None:
        return self.model.clear_left(self.cursor, left)

    def ids_for_right(self, right: Right) -> List[int]:
        return self.model.ids_for_right(self.cursor, right)

    def of_right(self, right: Right) -> List[Left]:
        return self.model.of_right(self.cursor, right)

    def from_right(self, **kwargs: Any) -> List[Left]:
        return self.model.from_right(self.cursor, **kwargs)

    def clear_right(self, right: Right) -> None:
        return self.model.clear_right(self.cursor, right)
