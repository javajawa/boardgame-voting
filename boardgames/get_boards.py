#!/usr/bin/env python3
# vim: fileencoding=utf-8 expandtab ts=4 nospell

# SPDX-FileCopyrightText: 2021 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations

from typing import Any, Dict, List, Optional

import contextlib
import datetime
import logging
import time
import re
import sqlite3
import sys

import requests


from orm.table import ModelWrapper
from boardgames.model import Board, BoardAdmin, BoardAdminRealm, BoardRealm, Game, Realm


LOGGER = logging.getLogger("boardgames")


class BoardImporter(contextlib.ContextDecorator):
    realms: Dict[int, Realm]
    games: Dict[int, Game]
    admins: List[BoardAdmin]
    connection: sqlite3.Connection
    cursor: sqlite3.Cursor
    board_model: ModelWrapper[Board]
    now: datetime.datetime

    def __init__(self, connection: sqlite3.Connection):
        self.realms = {}
        self.games = {}

        self.connection = connection
        self.cursor = connection.cursor()

        self.board_model = Board.model(self.cursor)
        self.admins = BoardAdmin.model(self.cursor).all()
        self.games = {
            game.bga_id: game for game in Game.model(self.cursor).all() if game.bga_id
        }
        self.realms = {
            realm.bga_group: realm
            for realm in Realm.model(self.cursor).all()
            if realm.bga_group
        }
        self.now = datetime.datetime.now()

    @staticmethod
    def get_bga_game_id(game: Game) -> Optional[int]:
        if not game.link.startswith("https://boardgamearena.com/lobby"):
            return None

        _, gid = game.link.split("=")

        return int(gid)

    def do_import(self) -> None:
        with requests.Session() as session:
            for line in session.get("https://boardgamearena.com/").text.split("\n"):
                if "requestToken: " not in line:
                    continue

                _, token = line.split("'", 1)
                token = token.strip("',")

                session.headers.update({"x-request-token": token})

            for admin in self.admins:
                if admin.bga_id:
                    self.import_by_user(session, admin)

        self.cursor.execute(
            (
                "UPDATE Board SET state = 'no_fire', close_time = ? "
                "WHERE state = 'open' AND last_seen < ?"
            ),
            (self.now, self.now),
        )
        self.cursor.execute(
            (
                "UPDATE Board SET state = 'finished', close_time = ?"
                "WHERE state = 'play' AND last_seen < ?"
            ),
            (self.now, self.now),
        )

        LOGGER.info("Committing")
        self.connection.commit()
        self.cursor.close()

    def import_by_user(self, session: requests.Session, admin: BoardAdmin) -> None:
        LOGGER.info("Loading boards from %s", admin.admin)

        request = session.get(
            "https://en.boardgamearena.com/tablemanager/tablemanager/tableinfos.html",
            params={
                "playerfilter": str(admin.bga_id),
                # "status": "open",
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
        board_id = int(table["id"])
        game_id = int(table["game_id"])

        if int(table.get("admin_id", 0)) != admin.bga_id:
            return

        if game_id not in self.games:
            LOGGER.error("Unable to find game %s in database", table["game_name"])
            return

        board = self.board_model.get(board_id)
        realms = self.get_realms_for_board(default_realms, table)

        if not board:
            board = self.create_board(admin, table)

        board.state = table["status"].replace("async", "")
        board.created = datetime.datetime.utcfromtimestamp(int(table["scheduled"]))
        board.launch_time = (
            datetime.datetime.utcfromtimestamp(int(table["gamestart"]))
            if table["gamestart"]
            else None
        )
        board.last_seen = self.now
        board.seats_taken = len(table["players"])

        # We want to keep the max/min seat info from the board's creation
        if board.state == "open":
            board.min_seats = self.get_min_players(table)
            board.max_seats = int(table["max_player"])
            board.description = table["presentation"]
            board.options = {int(k): int(v) for k, v in table["options"].items()}
            if table["players"][str(admin.bga_id)]["played"] == "0":
                board.options[-1] = 1

        LOGGER.debug("Adding board %s (%s)", table["id"], self.games[game_id].name)

        self.store(board, realms)

    def create_board(self, admin: BoardAdmin, table: Dict[str, Any]) -> Board:
        return Board(
            board_id=table["id"],
            game=self.games[int(table["game_id"])],
            creator=admin,
            state="open",
            link="https://boardgamearena.com/table?table=" + table["id"] + "&nr=true",
            min_seats=0,
            max_seats=0,
            seats_taken=0,
            created=self.now,
            description=table["presentation"],
            options={},
        )

    def get_realms_for_board(
        self, default_realms: List[Realm], table: Dict[str, Any]
    ) -> List[Realm]:
        if table["filter_group_type"] is None:
            LOGGER.info("Missing filter group for board %s", table["id"])
            return []

        if table["filter_group_type"] != "normal":
            return default_realms

        group_id = int(table["filter_group"])
        group = self.realms.get(group_id, None)

        if group:
            return [group]

        LOGGER.warning(
            "Unknown group %s for game %s", table["filter_group"], table["game_name"]
        )
        return []

    def get_min_players(self, table: Dict[str, Any]) -> int:
        players = self.games[int(table["game_id"])].min_players

        pres = table.get("presentation", "")
        match = re.search(r"{([0-9])}", pres)

        if not match or not match.group(1):
            return players

        table["presentation"] = pres.replace(match.group(0), "")
        players = max(players, int(match.group(1)))

        return players

    def store(self, board: Board, realms: List[Realm]) -> None:
        self.board_model.store(board)

        realm_model = BoardRealm.model(self.cursor)
        for realm in realms:
            realm_model.store(board, realm)


def main() -> None:
    with sqlite3.connect("games.db") as connection:
        importer = BoardImporter(connection)
        importer.do_import()


if __name__ == "__main__":
    if sys.stdout.isatty():
        LOGGER.addHandler(logging.StreamHandler())
        LOGGER.setLevel(logging.DEBUG)
    else:
        from systemd.journal import JournalHandler  # type: ignore

        LOGGER.addHandler(JournalHandler(SYSLOG_IDENTIFIER="bg-get-boards"))
        LOGGER.setLevel(logging.WARNING)

    main()
