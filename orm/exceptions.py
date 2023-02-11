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


class ORMException(Exception):
    pass


class MissingIdField(ORMException):
    """Exception class for a Table which does not have an appropriate ID field"""
