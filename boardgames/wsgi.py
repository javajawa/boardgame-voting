#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2021 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

"""Boardgames Voting"""

from __future__ import annotations

import datetime
from typing import Callable, Dict, IO, Optional, Tuple

import dataclasses
import json
import sqlite3

import requests

from boardgames.handler import FileData, Response, WSGIEnv
from boardgames.auth_handler import AuthHandler
from boardgames.model import (
    AsyncVote,
    BoardRealm,
    BoardAdmin,
    BoardAdminSuppression,
    Game,
    Realm,
    User,
    Vote,
    Veto,
)


FILES: Dict[str, Tuple[str, str]] = {
    "/boards.js": ("html/boards.js", "application/javascript"),
    "/script.js": ("html/script.js", "application/javascript"),
    "/vote.js": ("html/vote.js", "application/javascript"),
    "/elems.js": ("html/elems.js", "application/javascript"),
    "/results.js": ("html/results.js", "application/javascript"),
    "/overview.js": ("html/overview.js", "application/javascript"),
    "/style.css": ("html/style.css", "text/css"),
    "/favicon.ico": ("html/favicon.png", "image/png"),
    "/cookies.png": ("html/cookies.png", "image/png"),
    "/group.png": ("html/group.png", "image/png"),
    "/person.svg": ("html/person.svg", "image/svg+xml"),
    "/seat.svg": ("html/seat.svg", "image/svg+xml"),
}

REALM_FILES: Dict[str, Tuple[str, bool]] = {
    "": ("html/welcome.html", True),
    "vote": ("html/vote.html", True),
    "results": ("html/results.html", True),
    "boards": ("html/boards.html", False),
    "overview": ("html/overview.html", False),
}


class BGHandler(AuthHandler):
    realms: Dict[str, Realm] = {}
    files: Dict[str, FileData] = {}
    realm_files: Dict[str, Tuple[bool, FileData]] = {}
    realm_data: Dict[str, Tuple[bool, Callable[[BGHandler, Realm], Response]]]
    _login: FileData

    def __init__(self) -> None:
        self.connection = sqlite3.connect("games.db")
        self.cursor = self.connection.cursor()

        self.realms = {x.realm: x for x in Realm.model(self.cursor).all()}
        self.files = {route: FileData(path, mime) for route, (path, mime) in FILES.items()}
        self.realm_files = {
            route: (path[1], FileData(path[0], "text/html; charset=utf-8"))
            for route, path in REALM_FILES.items()
        }
        self.realm_data = {
            "games.json": (True, BGHandler.send_games_list),
            "results.json": (True, BGHandler.send_results),
            "boards.json": (False, BGHandler.send_boards_list),
        }

        self._login = FileData("html/login.html", "text/html; charset=utf-8")

    def call(  # pylint: disable=too-many-return-statements
        self, verb: str, path: str, environ: WSGIEnv
    ) -> Response:
        if verb == "GET" and path in self.files:
            return self.page_file(environ, self.files[path])

        realm_name, path = self.normalise_path(path)

        if realm_name not in self.realms:
            return Response(404, "text/plain", b"Not Found")

        realm = self.realms[realm_name]

        if verb == "POST":
            return self.post_request(environ, realm, path)

        user = self.auth(realm, environ.get("HTTP_COOKIE", ""))

        if verb == "GET":
            return self.get_request(environ, realm, user, path)

        if verb == "PUT":
            data: IO[bytes] = environ.get("wsgi.input")  # type: ignore
            return self.put_request(realm, user, path, data)

        return Response(404, "text/plain", f"Path not found {path}".encode("utf-8"))

    def auth_challenge(self, realm: Realm) -> Response:
        return self.realm_file({}, realm, self._login)

    def post_request(self, environ: WSGIEnv, realm: Realm, path: str) -> Response:
        if path == "login":
            return self.login(realm, environ)

        if path == "logout":
            return self.logout(realm)

        return Response(404, "text/plain", f"Path not found {path}".encode("utf-8"))

    def get_request(
        self, environ: WSGIEnv, realm: Realm, user: Optional[User], path: str
    ) -> Response:
        if path in self.realm_files:
            authed, file = self.realm_files[path]
            return (
                self.auth_challenge(realm)
                if authed and not user
                else self.realm_file(environ, realm, file)
            )

        if path in self.realm_data:
            authed, call = self.realm_data[path]
            return self.auth_challenge(realm) if authed and not user else call(self, realm)

        if path.startswith("overview.json/"):
            _, admin = path.split("/", 1)
            return self.send_votes_overview(admin)

        if path.startswith("create/"):
            _, game, tokens = path.split("/", 2)

            game_id = int(game)

            return self.create_board(game_id, tokens)

        if path == "me":
            return self.send_user_details(realm, user)

        return Response(404, "text/plain", f"Path not found {path}".encode("utf-8"))

    def put_request(
        self, realm: Realm, user: Optional[User], path: str, data: IO[bytes]
    ) -> Response:
        if path == "suppress":
            return self.suppress_request(data)

        if not user:
            return self.auth_challenge(realm)

        mapping = {"vote": Vote.model, "async-vote": AsyncVote.model, "veto": Veto.model}

        if path not in mapping:
            return Response(404, "text/plain", f"Path not found {path}".encode("utf-8"))

        game_model = Game.model(self.cursor)
        vote_model = mapping[path](self.cursor)

        vote_model.clear_left(user)

        ids = map(int, json.load(data))

        for game in game_model.get_many(*ids).values():
            vote_model.store(user, game)

        self.connection.commit()

        return Response(204, "", b"")

    def suppress_request(self, data: IO[bytes]) -> Response:
        request = json.load(data)

        admins = BoardAdmin.model(self.cursor).search(admin=request.get("admin", ""))
        game = Game.model(self.cursor).get(request.get("game_id", 0))

        if not admins or not game:
            return Response(404, "", b"")

        BoardAdminSuppression.model(self.cursor).store(
            BoardAdminSuppression(
                admins[0].board_admin_id or 0,
                game,
                datetime.datetime.now() + datetime.timedelta(days=request.get("days", 0)),
            )
        )

        self.connection.commit()

        return Response(204, "", b"")

    def send_games_list(self, realm: Realm) -> Response:
        self.cursor.execute(
            """
            SELECT [Game].[game_id] FROM [Game]
            LEFT JOIN [RealmBlacklist]
              ON [Game].[game_id] = [RealmBlacklist].[game_id]
              AND [RealmBlacklist].[realm_id] = ?
            WHERE [realm_id] IS NULL
            """,
            (realm.realm_id,),
        )

        ids = [x[0] for x in self.cursor.fetchall()]
        games = Game.model(self.cursor).get_many(*ids)
        data = [dataclasses.asdict(game) for game in games.values()]

        return self.send_json(data)

    def send_boards_list(self, realm: Realm) -> Response:
        model = BoardRealm.model(self.cursor)

        boards = model.of_right(realm)
        data = [dataclasses.asdict(board) for board in boards if board.state == "open"]

        return self.send_json(data)

    def send_votes_overview(self, admin: str) -> Response:
        admins = BoardAdmin.model(self.cursor).search(admin=admin)

        if not admins:
            return Response(404, "text/plain", b"Not Found")

        admin_id = admins[0].board_admin_id

        self.cursor.execute(
            (
                "SELECT game_id, name, bga_id, link, description, votes, users, "
                "until, open, all_open, created, last_created, launched, last_launched "
                "FROM Game "
                "NATURAL LEFT JOIN ( "
                "SELECT game_id, SUM(IIF(state == 'open', 1, 0)) open, "
                "COUNT(0) created, MAX(created) last_created, "
                "COUNT(launch_time) launched, MAX(launch_time) last_launched "
                "FROM Board WHERE board_admin_id = ? GROUP BY game_id "
                ") "
                "NATURAL LEFT JOIN ( "
                "SELECT game_id, COUNT(0) all_open "
                "FROM Board WHERE state == 'open' GROUP BY game_id "
                ") "
                "NATURAL LEFT JOIN ( "
                "SELECT game_id, COUNT(0) votes, GROUP_CONCAT(DISTINCT username) users "
                "FROM AsyncVote NATURAL JOIN User NATURAL JOIN BoardAdminRealm "
                "WHERE board_admin_id = ? "
                "GROUP BY game_id "
                ") "
                "NATURAL LEFT JOIN ( "
                "SELECT game_id, until "
                "FROM BoardAdminSuppression "
                "WHERE board_admin_id = ? AND until > CURRENT_TIMESTAMP "
                ") "
                "WHERE Game.platform = 'BGA' "
                "GROUP BY Game.game_id; "
            ),
            (admin_id, admin_id, admin_id),
        )

        fields = [
            "game_id",
            "name",
            "bga_id",
            "link",
            "description",
            "votes",
            "users",
            "until",
            "open",
            "all_open",
            "created",
            "last_created",
            "launched",
            "last_launched",
        ]

        rows = [dict(zip(fields, x)) for x in self.cursor.fetchall()]

        return self.send_json(rows)

    def send_user_details(self, realm: Realm, user: Optional[User]) -> Response:
        if not user:
            return self.send_json(
                {
                    "username": None,
                    "role": None,
                    "votes": [],
                    "async_votes": [],
                    "vetoes": [],
                    "max_votes": 999,
                    "max_vetoes": 3,
                    "realm": dataclasses.asdict(realm),
                }
            )

        data = {
            "username": user.username,
            "role": user.role,
            "votes": Vote.model(self.cursor).ids_for_left(user),
            "async_votes": AsyncVote.model(self.cursor).ids_for_left(user),
            "vetoes": Veto.model(self.cursor).ids_for_left(user),
            "max_votes": 999,
            "max_vetoes": 3,
            "realm": dataclasses.asdict(user.realm),
        }

        return self.send_json(data)

    def send_results(self, realm: Realm) -> Response:
        votes, vetoes = self.get_realtime_votes(realm)
        async_votes, async_vetoes = self.get_async_votes(realm)

        game_ids = (
            set(votes.keys())
            .union(vetoes.keys())
            .union(async_votes.keys())
            .union(async_vetoes.keys())
        )
        games = Game.model(self.cursor).get_many(*game_ids)

        data = []
        async_data = []

        for game in games.values():
            if game.game_id in votes:
                datum = dataclasses.asdict(game)
                datum["votes"] = votes.get(game.game_id, 0)
                datum["vetoes"] = vetoes.get(game.game_id, 0)
                data.append(datum)

            if game.game_id in async_votes:
                datum = dataclasses.asdict(game)
                datum["votes"] = async_votes.get(game.game_id, 0)
                datum["vetoes"] = async_vetoes.get(game.game_id, 0)
                async_data.append(datum)

        return self.send_json({"results": data, "async_results": async_data})

    def get_realtime_votes(self, realm: Realm) -> Tuple[Dict[int, int], Dict[int, int]]:
        self.cursor.execute(
            """
            SELECT [game_id], COUNT(0)
            FROM [Vote] JOIN [User] USING ([user_id])
            WHERE [realm_id] = ?
            GROUP BY [game_id]
            ORDER BY COUNT(0) DESC
            """,
            (realm.realm_id,),
        )

        votes: Dict[int, int] = dict(self.cursor.fetchall())

        self.cursor.execute(
            """
            SELECT [game_id], COUNT(0)
            FROM [Veto] JOIN [User] USING ([user_id])
            WHERE [realm_id] = ?
            GROUP BY [game_id]
            ORDER BY COUNT(0) DESC
            """,
            (realm.realm_id,),
        )

        vetoes: Dict[int, int] = dict(self.cursor.fetchall())

        return votes, vetoes

    def get_async_votes(self, realm: Realm) -> Tuple[Dict[int, int], Dict[int, int]]:
        self.cursor.execute(
            """
            SELECT [game_id], COUNT(0)
            FROM [AsyncVote] JOIN [User] USING ([user_id])
            WHERE [realm_id] = ?
            GROUP BY [game_id]
            ORDER BY COUNT(0) DESC
            """,
            (realm.realm_id,),
        )

        votes: Dict[int, int] = dict(self.cursor.fetchall())

        self.cursor.execute(
            """
            SELECT [game_id], COUNT(0)
            FROM [Veto] JOIN [User] USING ([user_id])
            WHERE [realm_id] = ?
            GROUP BY [game_id]
            ORDER BY COUNT(0) DESC
            """,
            (realm.realm_id,),
        )

        vetoes: Dict[int, int] = dict(self.cursor.fetchall())

        return votes, vetoes

    def create_board(self, game_id: int, tokens: str) -> Response:
        config = json.loads(tokens)

        board_info = requests.get(
            "https://boardgamearena.com/table/table/createnew.html",
            params={
                "game": str(game_id),
                "gamemode": "async",
                "forceManual": "true",
                "is_meeting": "false",
            },
            cookies=config,
            headers={"x-request-token": config["TournoiEnLigneid"]},
            timeout=30,
        )

        result = board_info.json()
        table_id = result.get("data", {}).get("table")

        response = self.send_json(
            {"error": result.get("error"), "id": result.get("data", {}).get("table")}
        )
        response.status = 302 if table_id else 503

        if table_id:
            response.headers.append(
                ("location", f"https://boardgamearena.com/table?table={table_id}&nr=true")
            )

        return response
