#!/usr/bin/env python3
# vim: fileencoding=utf-8 expandtab ts=4 nospell

# SPDX-FileCopyrightText: 2020-2021 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

"""
The data entity for a 'Join' Table.

A JoinTable has precisely two fields, which are foreign keys to two other
regular Tables, called Left and Right.
"""

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

from .abc import execute
from .table import TableModel, Table, _get_model


Left = TypeVar("Left", bound=Table[Any])
Right = TypeVar("Right", bound=Table[Any])

_LOGGER = logging.getLogger("tiny-orm")
_MODELS: Dict[Type[JoinTable[Left, Right]], JoinModel[Left, Right]] = {}  # type: ignore


def _get_join(data_class: Type[JoinTable[Left, Right]]) -> JoinModel[Left, Right]:
    """Gets the JoinModel instance for a given class that extends JoinTable"""

    if data_class not in _MODELS:
        _MODELS[data_class] = _make_join(data_class)

    return _MODELS[data_class]


def _make_join(data_class: Type[JoinTable[Left, Right]]) -> JoinModel[Left, Right]:
    """Create the model for a JoinTable"""

    if not inspect.isclass(data_class):
        raise Exception("Can not make join data from non-class")

    types = get_type_hints(data_class)

    if len(types) != 2:
        raise Exception("Can only build a join table with two fields")

    left, right = types.values()

    left_model: TableModel[Left] = _get_model(left)
    right_model: TableModel[Right] = _get_model(right)

    if not left_model:
        raise Exception(f"{left.__name__} is not a Table")

    if not right_model:
        raise Exception(f"{right.__name__} is not a Table")

    table = data_class.__name__

    return JoinModel(table, left_model, right_model)


class JoinTable(Generic[Left, Right]):
    """
    The data entity for a 'Join' Table.

    A JoinTable has precisely two fields, which are foreign keys to two other
    regular Tables, called Left and Right.

        class RoleMapping(JoinTable[User, Role]):
            user: User
            role: Role

    Note that the JoinModel does not currently return instances of the
    JoinTable, but future features might; instead functions will return
    sequences of the "Left" or "Right" Tables, based on the calls made.
    """

    @classmethod
    def model(cls, cursor: sqlite3.Cursor) -> JoinWrapper[Left, Right]:
        """Get the model instance, using the supplied cursor"""

        return JoinWrapper(_get_join(cls), cursor)

    @classmethod
    def create_table(cls, cursor: sqlite3.Cursor) -> None:
        """
        Ensures that this table is created in the SQLite database backing
        the supplied cursor.

        It is recommended that you call this function as soon as you open the
        database, unless your program design guarantees the table will exist.

        Note that py-tiny-orm does not support altering models.
        """

        _get_join(cls).create_table(cursor)


class JoinModel(Generic[Left, Right]):
    """
    The generated model for a given JoinTable.
    """

    cursor: sqlite3.Cursor

    table: str
    left: TableModel[Left]
    right: TableModel[Right]

    def __init__(self, table: str, left: TableModel[Left], right: TableModel[Right]):
        self.table = table
        self.left = left
        self.right = right

    def create_table(self, cursor: sqlite3.Cursor) -> None:
        """
        Creates the table in the SQLLite
        """

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

        execute(cursor, sql, tuple())

    def ids_for_left(self, cursor: sqlite3.Cursor, left: Left) -> List[int]:
        """
        Returns all left_ids present for a given Left record

        This is the same extracting the IDs from the Right records returned by
        the "of_right" function, but saves the overhead of doing any extra
        foreign key lookups.
        """

        sql = f"SELECT [{self.right.id_field}] FROM [{self.table}] WHERE [{self.left.id_field}] = ?"

        execute(cursor, sql, (getattr(left, self.left.id_field),))

        return [x[0] for x in cursor.fetchall()]

    def of_left(self, cursor: sqlite3.Cursor, left: Left) -> List[Right]:
        """Returns all Right records which map to a given Left"""

        ids = self.ids_for_left(cursor, left)

        return list(self.right.get_many(cursor, *ids).values())

    def from_left(self, cursor: sqlite3.Cursor, **kwargs: Any) -> List[Right]:
        """
        Returns all unique Right records which map to Left records that match
        the given search criteria. No information about which Left they
        matched is maintained.

        This will have the same result as:

            rights = Left.model().search(**kwargs)
            lefts = {}

            for right in right:
                lefts = join_model.of_right(right)
                lefts.update({l.left_id: l for l in lefts})

            return lefts.values()

        but this function will be considerably more efficient.
        """

        for key in kwargs:
            if key not in self.left.table_fields:
                raise AttributeError(f"{self.left.record.__name__} has no attribute {key}")

        def field(_field: str) -> str:
            return f"[{_field}] = :{_field}"

        sql = (
            f"SELECT DISTINCT [{self.right.id_field}] "
            f"FROM [{self.left.table}] JOIN [{self.table}] USING ([{self.left.id_field}]) "
            f"WHERE {' AND '.join(map(field, kwargs))}"
        )

        execute(cursor, sql, kwargs)

        ids = [x[0] for x in cursor.fetchall()]

        return list(self.right.get_many(cursor, *ids).values())

    def clear_left(self, cursor: sqlite3.Cursor, left: Left) -> None:
        """Deletes all records in the join table that feature the given Left record"""

        sql = f"DELETE FROM [{self.table}] WHERE [{self.left.id_field}] = ?"

        execute(cursor, sql, (getattr(left, self.left.id_field),))

    def ids_for_right(self, cursor: sqlite3.Cursor, right: Right) -> List[int]:
        """
        Returns all left_ids present for a given Right record

        This is the same extracting the IDs from the Left records returned by
        the "of_right" function, but saves the overhead of doing any extra
        foreign key lookups.
        """
        sql = f"SELECT [{self.left.id_field}] FROM [{self.table}] WHERE [{self.right.id_field}] = ?"

        execute(cursor, sql, (getattr(right, self.right.id_field),))

        return [x[0] for x in cursor.fetchall()]

    def of_right(self, cursor: sqlite3.Cursor, right: Right) -> List[Left]:
        """Returns all Left records which map to a given Right"""

        ids = self.ids_for_right(cursor, right)

        return list(self.left.get_many(cursor, *ids).values())

    def from_right(self, cursor: sqlite3.Cursor, **kwargs: Any) -> List[Left]:
        """
        Returns all unique Left records which map to Right records that match
        the given search criteria. No information about which Right they
        matched is maintained.

        This will have the same result as:

            rights = Right.model().search(**kwargs)
            lefts = {}

            for right in right:
                lefts = join_model.of_right(right)
                lefts.update({l.left_id: l for l in lefts})

            return lefts.values()

        but this function will be considerably more efficient.
        """

        for key in kwargs:
            if key not in self.right.table_fields:
                raise AttributeError(f"{self.right.record.__name__} has no attribute {key}")

        def field(_field: str) -> str:
            return f"[{_field}] = :{_field}"

        sql = (
            f"SELECT DISTINCT [{self.left.id_field}] "
            f"FROM [{self.right.table}] JOIN [{self.table}] USING ([{self.right.id_field}]) "
            f"WHERE {' AND '.join(map(field, kwargs))}"
        )

        execute(cursor, sql, kwargs)

        ids = [x[0] for x in cursor.fetchall()]

        return list(self.left.get_many(cursor, *ids).values())

    def clear_right(self, cursor: sqlite3.Cursor, right: Right) -> None:
        """Deletes all records in the join table that feature the given Right record"""

        sql = f"DELETE FROM [{self.table}] WHERE [{self.right.id_field}] = ?"

        execute(cursor, sql, (getattr(right, self.right.id_field),))

    def store(self, cursor: sqlite3.Cursor, left: Left, right: Right) -> bool:
        """
        Adds a mapping between the supplied Left and Right

        No action is taken if this mapping already exists
        """

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

        execute(cursor, sql, (left_id, right_id))

        return True

    def remove(self, cursor: sqlite3.Cursor, left: Left, right: Right) -> bool:
        """
        Removes a mapping between the supplied Left and Right.

        No action is taken if this mapping does not exist.
        """

        if not isinstance(left, self.left.record):
            raise Exception("Wrong type")

        if not isinstance(right, self.right.record):
            raise Exception("Wrong type")

        left_id = getattr(left, self.left.id_field)
        right_id = getattr(right, self.right.id_field)

        sql = (
            f"DELETE FROM [{self.table}] "
            f"WHERE [{self.left.id_field}] = ? AND [{self.right.id_field}] = ?"
        )

        execute(cursor, sql, (left_id, right_id))

        return True


class JoinWrapper(Generic[Left, Right]):
    """
    Binding class between a Table, it's Model, and an SQL-Lite cursor.

    The Model for table "Foo" can be retrieved with

        Foo.model(cursor)
    """

    model: JoinModel[Left, Right]
    cursor: sqlite3.Cursor

    def __init__(self, model: JoinModel[Left, Right], cursor: sqlite3.Cursor):
        self.model = model
        self.cursor = cursor

    def ids_for_left(self, left: Left) -> List[int]:
        """
        Returns all left_ids present for a given Left record

        This is the same extracting the IDs from the Right records returned by
        the "of_right" function, but saves the overhead of doing any extra
        foreign key lookups.
        """

        return self.model.ids_for_left(self.cursor, left)

    def of_left(self, left: Left) -> List[Right]:
        """Returns all Right records which map to a given Left"""

        return self.model.of_left(self.cursor, left)

    def from_left(self, **kwargs: Any) -> List[Right]:
        """
        Returns all unique Right records which map to Left records that match
        the given search criteria. No information about which Left they
        matched is maintained.

        This will have the same result as:

            rights = Left.model().search(**kwargs)
            lefts = {}

            for right in right:
                lefts = join_model.of_right(right)
                lefts.update({l.left_id: l for l in lefts})

            return lefts.values()

        but this function will be considerably more efficient.
        """

        return self.model.from_left(self.cursor, **kwargs)

    def clear_left(self, left: Left) -> None:
        """Deletes all records in the join table that feature the given Left record"""

        return self.model.clear_left(self.cursor, left)

    def ids_for_right(self, right: Right) -> List[int]:
        """
        Returns all left_ids present for a given Right record

        This is the same extracting the IDs from the Left records returned by
        the "of_right" function, but saves the overhead of doing any extra
        foreign key lookups.
        """

        return self.model.ids_for_right(self.cursor, right)

    def of_right(self, right: Right) -> List[Left]:
        """Returns all Left records which map to a given Right"""

        return self.model.of_right(self.cursor, right)

    def from_right(self, **kwargs: Any) -> List[Left]:
        """
        Returns all unique Left records which map to Right records that match
        the given search criteria. No information about which Right they
        matched is maintained.

        This will have the same result as:

            rights = Right.model().search(**kwargs)
            lefts = {}

            for right in right:
                lefts = join_model.of_right(right)
                lefts.update({l.left_id: l for l in lefts})

            return lefts.values()

        but this function will be considerably more efficient.
        """

        return self.model.from_right(self.cursor, **kwargs)

    def clear_right(self, right: Right) -> None:
        """Deletes all records in the join table that feature the given Right record"""

        return self.model.clear_right(self.cursor, right)

    def store(self, left: Left, right: Right) -> bool:
        """
        Adds a mapping between the supplied Left and Right

        No action is taken if this mapping already exists
        """

        return self.model.store(self.cursor, left, right)

    def remove(self, left: Left, right: Right) -> bool:
        """
        Removes a mapping between the supplied Left and Right.

        No action is taken if this mapping does not exist.
        """

        return self.model.remove(self.cursor, left, right)
