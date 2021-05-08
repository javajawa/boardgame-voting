#!/usr/bin/env python3
# vim: fileencoding=utf-8 expandtab ts=4 nospell

# SPDX-FileCopyrightText: 2021 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations

from typing import Any, Dict, List, Optional

import contextlib
import datetime
import time
import sqlite3

import requests

from boardgames.model import Board, Game, Realm


class BoardImporter(contextlib.ContextDecorator):
    realms: Dict[int, Realm]
    games: Dict[int, Game]
    connection: sqlite3.Connection
    cursor: sqlite3.Cursor
    boards: List[Board]

    def __init__(self, connection: sqlite3.Connection):
        self.realms = {}
        self.games = {}
        self.boards = []

        self.connection = connection
        self.cursor = connection.cursor()

    def __enter__(self) -> BoardImporter:
        self.games = {
            self.get_bga_game_id(game) or 0: game
            for game in Game.model(self.cursor).all()
            if self.get_bga_game_id(game)
        }

        self.realms = {
            realm.bga_group: realm
            for realm in Realm.model(self.cursor).all()
            if realm.bga_group
        }

        return self

    def __exit__(self, *exc: Any) -> bool:
        self.connection.commit()
        self.cursor.close()
        return False

    @staticmethod
    def get_bga_game_id(game: Game) -> Optional[int]:
        if not game.link.startswith("https://boardgamearena.com/lobby"):
            return None

        _, gid = game.link.split("=")

        return int(gid)

    def import_by_user(self, user_id: int) -> None:
        request = requests.get(
            "https://en.boardgamearena.com/tablemanager/tablemanager/tableinfos.html",
            params={
                "playerfilter": str(user_id),
                "status": "open",
                "dojo.preventCache": str(int(time.time())),
            },
        )
        data = request.json()

        for table in data["data"]["tables"].values():
            self.process_table(table)

    def process_table(self, table: Dict[str, Any]) -> None:
        game_id = int(table["game_id"])

        if game_id not in self.games:
            print(f"Unable to find game '{table['game_name']}' in database")
            return

        if table["filter_group_type"] is None:
            return

        realm: Optional[Realm] = None

        if table["filter_group_type"] == "normal":
            if int(table["filter_group"]) not in self.realms:
                print(f"Unknown group {table['filter_group']} for game {table['game_name']}")
                return

            realm = self.realms.get(int(table["filter_group"]))

        self.boards.append(
            Board(
                realm,
                self.games[game_id],
                "https://boardgamearena.com/table?table=" + table["id"],
                # list(table["options"].keys()),
                int(table["min_player"]),
                int(table["max_player"]),
                len(table["players"]),
                datetime.datetime.utcfromtimestamp(int(table["scheduled"])),
                table["presentation"]
            )
        )

    def store(self) -> None:
        model = Board.model(self.cursor)

        self.cursor.execute("DELETE FROM Board")
        for board in self.boards:
            model.store(board)


def main() -> None:
    with sqlite3.connect("games.db") as connection:
        with BoardImporter(connection) as importer:
            importer.import_by_user(88078650)
            importer.store()


if __name__ == "__main__":
    main()
