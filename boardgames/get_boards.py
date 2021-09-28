#!/usr/bin/env python3
# vim: fileencoding=utf-8 expandtab ts=4 nospell

# SPDX-FileCopyrightText: 2021 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import contextlib
import datetime
import logging
import time
import sqlite3

import requests

from systemd.journal import JournalHandler  # type: ignore

from boardgames.model import Board, BoardAdmin, BoardAdminRealm, BoardRealm, Game, Realm


LOGGER = logging.getLogger("boardgames")


class BoardImporter(contextlib.ContextDecorator):
    realms: Dict[int, Realm]
    games: Dict[int, Game]
    admins: List[BoardAdmin]
    connection: sqlite3.Connection
    cursor: sqlite3.Cursor
    boards: List[Tuple[Board, List[Realm]]]

    def __init__(self, connection: sqlite3.Connection):
        self.realms = {}
        self.games = {}
        self.boards = []

        self.connection = connection
        self.cursor = connection.cursor()

        self.admins = BoardAdmin.model(self.cursor).all()

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

    @staticmethod
    def get_bga_game_id(game: Game) -> Optional[int]:
        if not game.link.startswith("https://boardgamearena.com/lobby"):
            return None

        _, gid = game.link.split("=")

        return int(gid)

    def do_import(self) -> None:
        for admin in self.admins:
            self.import_by_user(admin)

        self.store()

        LOGGER.info("Committing")
        self.connection.commit()
        self.cursor.close()

    def import_by_user(self, admin: BoardAdmin) -> None:
        LOGGER.info("Loading boards from %s", admin.admin)

        request = requests.get(
            "https://en.boardgamearena.com/tablemanager/tablemanager/tableinfos.html",
            params={
                "playerfilter": str(admin.bga_id),
                "status": "open",
                "dojo.preventCache": str(int(time.time())),
            },
        )
        data = request.json()

        tables = data["data"]["tables"]

        if not tables:
            LOGGER.info("No tables found for %s", admin.admin)
            return

        realms = BoardAdminRealm.model(self.cursor).of_left(admin)

        for table in tables.values():
            self.process_table(admin, realms, table)

    def process_table(
        self, admin: BoardAdmin, default_realms: List[Realm], table: Dict[str, Any]
    ) -> None:
        game_id = int(table["game_id"])

        if int(table["admin_id"]) != admin.bga_id:
            return

        if game_id not in self.games:
            LOGGER.error("Unable to find game %s in database", table["game_name"])
            return

        if table["filter_group_type"] is None:
            LOGGER.warning("Missing filter group for board")
            return

        realms: List[Realm] = list(default_realms)

        if table["filter_group_type"] == "normal":
            group_id = int(table["filter_group"])
            group = self.realms.get(group_id, None)

            if not group:
                LOGGER.warning(
                    "Unknown group %s for game %s", table["filter_group"], table["game_name"]
                )
                return

            realms = [group]

        LOGGER.debug("Adding board %s (%s)", table["id"], self.games[game_id].name)
        self.boards.append(
            (
                Board(
                    self.games[game_id],
                    admin,
                    "https://boardgamearena.com/table?table=" + table["id"],
                    int(table["min_player"]),
                    int(table["max_player"]),
                    len(table["players"]),
                    datetime.datetime.utcfromtimestamp(int(table["scheduled"])),
                    table["presentation"],
                ),
                realms,
            )
        )

    def store(self) -> None:
        model = Board.model(self.cursor)
        rmodel = BoardRealm.model(self.cursor)

        LOGGER.info("Deleting all boards")
        self.cursor.execute("DELETE FROM BoardRealm")
        self.cursor.execute("DELETE FROM Board")

        LOGGER.info("Addings %d boards", len(self.boards))
        for board, realms in self.boards:
            model.store(board)

            for realm in realms:
                rmodel.store(board, realm)


def main() -> None:
    with sqlite3.connect("games.db") as connection:
        importer = BoardImporter(connection)
        importer.do_import()


if __name__ == "__main__":
    #LOGGER.addHandler(JournalHandler())
    LOGGER.setLevel(logging.INFO)
    main()
