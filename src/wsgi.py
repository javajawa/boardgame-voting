#!/usr/bin/env python3
# vim: fileencoding=utf-8 expandtab ts=4 nospell

# SPDX-FileCopyrightText: 2020 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

"""Boardgames Voting"""

from __future__ import annotations

from typing import Dict, IO, Tuple

import dataclasses
import json
import sqlite3

from handler import FileData, Response, WSGIEnv
from auth_handler import AuthHandler
from model import Game, Realm, User, Vote, Veto


FILES: Dict[str, Tuple[str, str]] = {
    "/script.js": ("html/script.js", "application/javascript"),
    "/vote.js": ("html/vote.js", "application/javascript"),
    "/results.js": ("html/results.js", "application/javascript"),
    "/style.css": ("html/style.css", "text/css"),
    "/favicon.ico": ("html/favicon.png", "image/png"),
}

REALM_FILES: Dict[str, str] = {
    "": "html/welcome.html",
    "vote": "html/vote.html",
    "results": "html/results.html",
}


class BGHandler(AuthHandler):
    connection: sqlite3.Connection

    realms: Dict[str, Realm] = {}
    files: Dict[str, FileData] = {}
    rfiles: Dict[str, FileData] = {}
    _login: FileData

    def __init__(self) -> None:
        self.connection = sqlite3.connect("games.db")
        self.cursor = self.connection.cursor()

        self.realms = {x.realm: x for x in Realm.model(self.cursor).all()}
        self.files = {route: FileData(path, mime) for route, (path, mime) in FILES.items()}
        self.rfiles = {
            route: FileData(path, "text/html; charset=utf-8")
            for route, path in REALM_FILES.items()
        }
        self._login = FileData("html/login.html", "text/html; charset=utf-8")

    def call(self, verb: str, path: str, environ: WSGIEnv) -> Response:
        if verb == "GET" and path in self.files:
            return self.page_file(environ, self.files[path])

        realm_name, path = self.normalise_path(path)

        if realm_name not in self.realms:
            return Response(404, "text/plain", b"Not Found")

        realm = self.realms[realm_name]

        if verb == "POST":
            return self.post_request(environ, realm, path)

        user = self.auth(realm, environ.get("HTTP_COOKIE", ""))

        if not user:
            return self.auth_challenge(realm)

        if verb == "GET":
            return self.get_request(environ, realm, user, path)
        elif verb == "PUT":
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

    def get_request(self, environ: WSGIEnv, realm: Realm, user: User, path: str) -> Response:
        if path in self.rfiles:
            return self.realm_file(environ, realm, self.rfiles[path])

        elif path == "games.json":
            return self.send_games_list(realm)

        elif path == "results.json":
            return self.send_results(realm)

        elif path == "me":
            return self.send_user_details(user)

        else:
            return Response(404, "text/plain", f"Path not found {path}".encode("utf-8"))

    def put_request(self, realm: Realm, user: User, path: str, data: IO[bytes]) -> Response:
        if path not in ["vote", "veto"]:
            return Response(404, "text/plain", f"Path not found {path}".encode("utf-8"))

        game_model = Game.model(self.cursor)
        vote_model = Vote.model(self.cursor) if path == "vote" else Veto.model(self.cursor)

        vote_model.clear_left(user)

        ids = map(int, json.load(data))

        for game in game_model.get_many(*ids).values():
            vote_model.store(user, game)

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

    def send_user_details(self, user: User) -> Response:
        data = {
            "username": user.username,
            "role": user.role,
            "votes": Vote.model(self.cursor).ids_for_left(user),
            "vetos": Veto.model(self.cursor).ids_for_left(user),
            "max_votes": 8,
            "max_vetos": 3,
        }

        return self.send_json(data)

    def send_results(self, realm: Realm) -> Response:
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

        votes: Dict[int, int] = {k: v for k, v in self.cursor.fetchall()}

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

        vetos: Dict[int, int] = {k: v for k, v in self.cursor.fetchall()}

        game_ids = set(votes.keys()).union(vetos.keys())

        games = Game.model(self.cursor).get_many(*game_ids)
        data = []

        for game_id in game_ids:
            if game_id not in games:
                continue

            game = dataclasses.asdict(games[game_id])
            game["votes"] = votes.get(game_id, 0)
            game["vetos"] = vetos.get(game_id, 0)
            data.append(game)

        return self.send_json(data)