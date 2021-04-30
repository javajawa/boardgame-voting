#!/usr/bin/env python3
# vim: fileencoding=utf-8 expandtab ts=4 nospell

# SPDX-FileCopyrightText: 2020 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

"""Boardgames Voting"""

from __future__ import annotations

from typing import Dict, List, Optional, Union

import abc
import cgi
import sqlite3

from http.cookies import SimpleCookie, Morsel

import bcrypt

from boardgames.handler import Handler, Response, WSGIEnv
from boardgames.model import Realm, User


PostData = Dict[str, List[Union[str, bytes]]]


class AuthHandler(Handler):
    connection: sqlite3.Connection
    cursor: sqlite3.Cursor

    def auth(self, realm: Realm, cookie: str) -> Optional[User]:
        """Checks if a user is authorised"""

        cookies: SimpleCookie[str] = SimpleCookie(cookie)

        user_cookie: Optional[Morsel[str]] = cookies.get(f"user-{realm.realm}")
        auth_cookie: Optional[Morsel[str]] = cookies.get(f"auth-{realm.realm}")

        user: Optional[str] = user_cookie.value if user_cookie else None
        auth: Optional[str] = auth_cookie.value if auth_cookie else None

        if not user or not auth:
            return None

        candidates = User.model(self.cursor).search(realm=realm, username=user)

        if not candidates:
            return None

        authed = candidates[0]

        return authed if bcrypt.checkpw(authed.password, auth.encode("utf-8")) else None

    @abc.abstractmethod
    def auth_challenge(self, realm: Realm) -> Response:
        pass

    def login(self, realm: Realm, environ: WSGIEnv) -> Response:
        data = cgi.FieldStorage(environ=environ, fp=environ["wsgi.input"])  # type: ignore

        username = data["username"].file.read() if "username" in data else ""
        password = data["password"].file.read() if "password" in data else ""

        if not username or not password:
            return self.auth_challenge(realm)

        user_model = User.model(self.cursor)
        user: User

        candidates = user_model.search(username=username, realm=realm)

        if not candidates:
            _pass = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())

            user = User(realm=realm, username=username, password=_pass, role="none")
            user_model.store(user)
            self.connection.commit()

        else:
            user = candidates[0]

            if not bcrypt.checkpw(password.encode("utf-8"), user.password):
                return self.auth_challenge(realm)

        token: str = bcrypt.hashpw(user.password, bcrypt.gensalt(4)).decode("utf-8")

        return Response(
            302,
            "text/plain",
            b"Redirecting...",
            headers=[
                ("Set-Cookie", f"user-{realm.realm}={username}; path=/{realm.realm}"),
                ("Set-Cookie", f"auth-{realm.realm}={token}; path=/{realm.realm}"),
                ("Location", f"/{realm.realm}/"),
            ],
        )

    @staticmethod
    def logout(realm: Realm) -> Response:
        expires = "; expires=Thu, 01 Jan 1970 00:00:00 GMT"

        return Response(
            302,
            "text/plain",
            b"You are now logged out",
            headers=[
                ("Set-Cookie", f"user-{realm.realm}=; path=/{realm.realm}{expires}"),
                ("Set-Cookie", f"auth-{realm.realm}=; path=/{realm.realm}{expires}"),
                ("Location", f"/{realm.realm}/"),
            ],
        )
