#!/usr/bin/env python3
# vim: fileencoding=utf-8 expandtab ts=4 nospell

# SPDX-FileCopyrightText: 2020-2021 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

"""
Entry point for the "orm" module of "py-tiny-orm".

This package is a ~1000 line SQLite object relation manager (ORM) which
automatically generates tables and queries using dataclasses.

Find this project at:
  https://github.com/javajawa/py-tiny-orm
  https://pypi.org/project/py-tiny-orm/
"""

from __future__ import annotations

from .table import Table, ModelWrapper as TableModel, subtable, unique
from .join import JoinTable, JoinWrapper as JoinModel


__all__ = ["Table", "TableModel", "JoinTable", "JoinModel", "subtable", "unique"]
