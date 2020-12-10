#!/bin/sh

# SPDX-FileCopyrightText: 2020 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

NAME="Benedict Harcourt"
EMAIL="ben.harcourt@harcourtprogramming.co.uk"

COPYRIGHT="$NAME <$EMAIL>"

LICENSE="BSD-2-Clause"

find src html tools -type f -exec \
	reuse addheader --copyright "$COPYRIGHT" --license "$LICENSE" '{}' +
