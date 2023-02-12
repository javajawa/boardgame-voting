#!/usr/bin/env python3
# vim: fileencoding=utf-8 expandtab ts=4 nospell

# SPDX-FileCopyrightText: 2021 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

# pylint: disable=too-many-instance-attributes

from __future__ import annotations

from typing import Dict, Optional

import sqlite3

from dataclasses import dataclass, field
import datetime

import orm


@orm.unique("realm")
@dataclass
class Realm(orm.Table["Realm"]):
    realm_id: int
    realm: str
    realm_name: str
    bga_group: Optional[int]
    realtime: bool = True
    passnplay: bool = True


@orm.unique("realm_id", "username")
@dataclass
class User(orm.Table["User"]):
    username: str
    password: bytes
    realm: Realm
    role: str = "none"
    user_id: Optional[int] = None


@orm.unique("game_id", "option_id")
@dataclass
class GameOptions(orm.Table["GameOptions"]):
    game_id: int
    option_id: int
    json: str
    game_options_id: Optional[int] = None


@orm.unique("platform", "name")
@orm.subtable("options", GameOptions, "json", "option_id")
@dataclass
class Game(orm.Table["Game"]):
    platform: str
    name: str

    description: str = ""
    link: str = ""
    image: str = ""
    min_players: int = 0
    max_players: int = 0

    complexity: int = 0
    strategy: int = 0
    luck: int = 0
    interaction: int = 0

    added: datetime.datetime = field(default_factory=datetime.datetime.now)

    options: Dict[int, str] = field(default_factory=dict)

    bga_id: Optional[int] = None
    bgg_id: Optional[int] = None
    game_id: Optional[int] = None


@dataclass
class Tag(orm.Table["Tag"]):
    tag: str
    category: str
    bga_id: Optional[int] = None
    tag_id: Optional[int] = None


@dataclass
class GameTags(orm.JoinTable[Game, Tag]):
    game: Game
    tag: Tag


@dataclass
class RealmBlacklist(orm.JoinTable[Realm, Game]):
    realm: Realm
    game: Game


@dataclass
class Vote(orm.JoinTable[User, Game]):
    user: User
    game: Game


@dataclass
class AsyncVote(orm.JoinTable[User, Game]):
    user: User
    game: Game


@dataclass
class Veto(orm.JoinTable[User, Game]):
    user: User
    game: Game


@orm.unique("board_admin_id", "game_id")
@dataclass
class BoardAdminSuppression(orm.Table["BoardAdminSuppression"]):
    board_admin_id: int
    game: Game
    until: datetime.datetime
    board_admin_suppression_id: Optional[int] = None


@orm.unique("admin")
@orm.unique("bga_id")
# @orm.subtable("suppressions", BoardAdminSuppression, "until", "game")
@dataclass
class BoardAdmin(orm.Table["BoardAdmin"]):
    admin: str
    bga_id: int
    # suppressions: Dict[Game, datetime.datetime] = dataclasses.field(default_factory=dict)
    board_admin_id: Optional[int] = None


@dataclass
class BoardAdminRealm(orm.JoinTable[BoardAdmin, Realm]):
    admin: BoardAdmin
    realm: Realm


@orm.unique("board_id", "option_id")
@dataclass
class BoardOptions(orm.Table["BoardOptions"]):
    board_id: int
    option_id: int
    option_value: int
    board_options_id: Optional[int] = None


@orm.subtable("options", BoardOptions, "option_value", "option_id")
@dataclass
class Board(orm.Table["Board"]):
    board_id: int
    game: Game
    creator: BoardAdmin
    state: str
    link: str
    min_seats: int
    max_seats: int
    seats_taken: int
    created: datetime.datetime
    description: str

    launch_time: Optional[datetime.datetime] = None
    last_seen: Optional[datetime.datetime] = None
    close_time: Optional[datetime.datetime] = None

    options: Dict[int, int] = field(default_factory=dict)


@dataclass
class BoardRealm(orm.JoinTable[Board, Realm]):
    board: Board
    realm: Realm


if __name__ == "__main__":
    with sqlite3.connect("games.db") as connection:
        cursor = connection.cursor()

        Realm.create_table(cursor)
        User.create_table(cursor)
        GameOptions.create_table(cursor)
        Game.create_table(cursor)
        Tag.create_table(cursor)
        GameTags.create_table(cursor)
        RealmBlacklist.create_table(cursor)
        Vote.create_table(cursor)
        AsyncVote.create_table(cursor)
        Veto.create_table(cursor)
        BoardAdminSuppression.create_table(cursor)
        BoardAdmin.create_table(cursor)
        BoardAdminRealm.create_table(cursor)
        BoardOptions.create_table(cursor)
        Board.create_table(cursor)
        BoardRealm.create_table(cursor)

        connection.commit()
