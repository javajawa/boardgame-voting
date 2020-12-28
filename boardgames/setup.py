#!/usr/bin/env python3
# vim: fileencoding=utf-8 expandtab ts=4 nospell

# SPDX-FileCopyrightText: 2020 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

"""Boardgames Voting"""

from __future__ import annotations

from typing import Dict

import sqlite3

from boardgames.model import GameTags, Realm, RealmBlacklist, Veto, Vote


REALMS: Dict[int, str] = {
    1: "plaid-posse",
    2: "brew-crew",
    3: "cursed-chat",
    4: "frens",
}


def main() -> None:
    with sqlite3.connect("games.db") as conn:
        cursor = conn.cursor()

        model = Realm.model(cursor)

        for _id, realm in REALMS.items():
            model.store(Realm(_id, realm))

        Veto.model(cursor)
        Vote.model(cursor)
        GameTags.model(cursor)
        RealmBlacklist.model(cursor)

        cursor.execute(
            """
            INSERT OR IGNORE INTO RealmBlacklist
            SELECT realm_id, game_id FROM Game JOIN Realm
            WHERE max_players <= 2
            """
        )
        cursor.execute(
            """
            INSERT OR IGNORE INTO RealmBlacklist
            SELECT 4, game_id FROM Game
            WHERE max_players <= 4 OR complexity >= 4 OR strategy = 5
            """
        )


if __name__ == "__main__":
    main()
