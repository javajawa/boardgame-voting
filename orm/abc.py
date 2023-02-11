#!/usr/bin/env python3
# vim: fileencoding=utf-8 expandtab ts=4 nospell

# SPDX-FileCopyrightText: 2020 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

"""
Base support for SQL tables and WHERE clauses
"""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, Generator, Iterable, List, Mapping, Tuple, Union

import abc
import logging
import orm  # pylint: disable=unused-import
from orm.exceptions import ORMException

OurField = str
TheirField = str
ForeignerMap = Dict[OurField, Tuple[TheirField, "orm.table.TableModel[Any]"]]

PrimitiveTypes = Union[str, int, float, bool, None]
FilterTypes = Union[
    PrimitiveTypes,
    "orm.table.Table[Any]",
    Iterable[PrimitiveTypes],
    Iterable["orm.table.Table[Any]"],
]
Filters = Mapping[str, FilterTypes]
MutableFilters = Dict[str, FilterTypes]
SQLParams = Union[Tuple[PrimitiveTypes, ...], Dict[str, str]]


_LOGGER = logging.getLogger("tiny-orm")


def execute(cursor: sqlite3.Cursor, query: str, params: SQLParams) -> None:
    try:
        cursor.execute(query, params)
    except sqlite3.Error as ex:
        _LOGGER.error("%s", query)
        _LOGGER.error("%s", params)
        raise ex

    _LOGGER.debug("%s", query)
    _LOGGER.debug("%s", params)


class BaseModel(abc.ABC):
    """Common functionality for different types of ORM model"""

    def where(
        self, foreigners: ForeignerMap, conditions: Filters
    ) -> Tuple[str, Dict[str, Any]]:
        """Creates an SQL WHERE clause based on a set of filters.

        The return comes in two parts: the SQL clause, and a Mapping of the
        values to be used.

        Each entry in the Mapping/Dict represents a filter on a particular
        column. The overall WHERE clause will require all columns to match
        these values.

        A simple example, such as:

          `where({}, {visible: True, name: "Cat"})`

        will generate an SQL block and mapping like:

          `[visible] = :visible AND [name] = :name`
          `{visible: True, name: "Cat"}`

        Iterables values for a filter are processed as "and of" (OR).

          `where({}, {some_id: [1, 3, 5]}`

        generates as

          `[some_id] IN (:some_id__0, :some_id__1, :some_id__2))`
          `{some_id__0: 1, some_id__1: 3, some_id__2: 5}`

        In order to facilitiate the mapping of other objects, we can also provider
        foreign key information to the `where` function. This maps the column ID
        of the object to the local field name.

          `where({cat: (cat_id, Cat)}, {cat: Cat(1)})`

        yields

          `[cat_id] = :cat_id`
          `{cat_id: 1}`
        """
        keys = list(conditions.keys())
        values = dict(conditions)
        clauses = []

        for key in keys:
            if key in foreigners:
                their_field, model = foreigners[key]

                subvalues: List["orm.table.Table[Any]"]
                if isinstance(values[key], (set, tuple, list)):
                    subvalues = list(values[key])  # type: ignore
                else:
                    subvalues = [values[key]]  # type: ignore

                if not all(isinstance(x, model.record) for x in subvalues):
                    raise ORMException("Passed incorrect object to foreign key")

                values[their_field] = set(self.map_foreign_objects(their_field, subvalues))
                key = their_field

            clauses.append(self.where_clause(key, values))

        return " AND ".join(clauses), values

    @staticmethod
    def map_foreign_objects(
        field: TheirField, objects: List["orm.table.Table[Any]"]
    ) -> Generator[PrimitiveTypes, None, None]:
        """Converts a list of Table[Any] to a List of their IDs"""
        for obj in objects:
            yield getattr(obj, field) if obj else None

    @staticmethod
    def where_clause(field: str, filters: Dict[str, Any]) -> str:
        """Creates a specific sub-clause for a WHERE query.

        This will by representing some number of values a specific
        column must match at least one of"""
        if not isinstance(filters[field], (list, set, tuple)):
            return (
                f"[{field}] = :{field}"
                if filters[field] is not None
                else f"[{field}] IS NULL"
            )

        if len(filters[field]) == 1:
            filters[field] = list(filters[field]).pop()

            return (
                f"[{field}] = :{field}"
                if filters[field] is not None
                else f"[{field}] IS NULL"
            )

        fields = []
        i = 0
        null = False

        for value in filters[field]:
            if value is None:
                null = True
                continue

            subfield = field + "__" + str(i)
            filters[subfield] = value
            fields.append(":" + subfield)
            i += 1

        if not fields and null:
            return f"[{field}] IS NULL"

        return (
            f"([{field}] IN ({', '.join(fields)})"
            + (f" OR [{field}] IS NULL" if null else "")
            + ")"
        )
