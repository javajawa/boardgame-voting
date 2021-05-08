#!/bin/sh -e

# SPDX-FileCopyrightText: 2020 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
# SPDX-FileCopyrightText: 2021 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

reuse lint
black boardgames orm
flake8 boardgames orm
mypy --strict boardgames orm
pylint boardgames orm
