#!/usr/bin/env python3
# vim: fileencoding=utf-8 expandtab ts=4 nospell

# SPDX-FileCopyrightText: 2020 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations

from typing import Optional

from dataclasses import dataclass, field
import datetime

import orm


@orm.data_model(["realm"])
@dataclass
class Realm(orm.Modelled["Realm"]):
    realm_id: int
    realm: str
    bga_group: Optional[int]


@orm.data_model(["realm_id", "username"])
@dataclass
class User(orm.Modelled["User"]):
    username: str
    password: bytes
    realm: Realm
    role: str = "none"
    user_id: Optional[int] = None


@orm.data_model(["platform", "name"])
@dataclass
class Game(orm.Modelled["Game"]):
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

    game_id: Optional[int] = None


@orm.data_model(["tag"])
@dataclass
class Tag(orm.Modelled["Tag"]):
    tag: str
    tag_id: Optional[int] = None


@orm.join_model
@dataclass
class GameTags(orm.Joiner[Game, Tag]):
    game: Game
    tag: Tag


@orm.join_model
@dataclass
class RealmBlacklist(orm.Joiner[Realm, Game]):
    realm: Realm
    game: Game


@orm.join_model
@dataclass
class Vote(orm.Joiner[User, Game]):
    user: User
    game: Game


@orm.join_model
@dataclass
class Veto(orm.Joiner[User, Game]):
    user: User
    game: Game


@orm.data_model()
@dataclass
class Board(orm.Modelled["Board"]):
    realm: Optional[Realm]
    game: Game
    link: str
    # mods: List[str]
    min_seats: int
    max_seats: int
    seats_taken: int
    created: datetime.datetime
    description: str

    board_id: Optional[int] = None
