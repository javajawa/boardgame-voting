#!/usr/bin/env python3
# vim: fileencoding=utf-8 expandtab ts=4 nospell

# SPDX-FileCopyrightText: 2020 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from typing import Any, Dict, List

import requests
import sqlite3

from bs4 import BeautifulSoup  # type: ignore

from model import Game, Tag
from orm.model import ModelWrapper


TAG_CACHE: Dict[str, Tag] = {}

CUSTOM_GAMES: List[Game] = [
    Game(
        "Other",
        "Pictionary",
        "Draw a thing whilst everyone else tries to guess!",
        "",
        3,
        12,
        1,
        0,
        3,
        4,
    ),
    Game(
        "Other",
        "Broken Picturephone",
        (
            "Take another player's sentence and draw it, "
            "or take their drawing are try to determine what it is. "
            "Your output is passed onto the next player!"
        ),
        "",
        4,
        12,
        1,
        0,
        3,
        4,
    ),
    Game("Steam", "Among Us", "Among Us", "", 5, 10, 3, 3, 3, 2),
    Game("NetGames.io", "Codewords", "", "", 4, 10, 1, 2, 3, 5),
    Game("NetGames.io", "Secret Hitler", "", "", 5, 10, 2, 3, 3, 2),
    Game("NetGames.io", "Spyfall", "", "", 3, 8, 2, 2, 4, 3),
    Game("NetGames.io", "Avalon", "", "", 5, 10, 2, 2, 4, 3),
]


def get_tag(model: ModelWrapper[Tag], name: str) -> Tag:
    if name in TAG_CACHE:
        return TAG_CACHE[name]

    candidates = model.search(tag=name)

    if not candidates:
        tag = Tag(name)
        model.store(tag)
    else:
        tag = candidates[0]

    TAG_CACHE[name] = tag

    return tag


def update_bga(model: ModelWrapper[Game], tags: ModelWrapper[Tag]) -> None:
    existing = [game.name for game in model.search(platform="BGA")]

    html = requests.get("https://boardgamearena.com/gamelist")
    soup = BeautifulSoup(html.content, "html.parser")

    game_list = soup.find("select", id="gamelist_gameselect")
    new_games = [
        x.text for x in game_list.find_all("option") if x.text and x.text not in existing
    ]

    for data in soup.find(id="gamecategory_wrap_all").find_all("div", class_="gamelist_item"):
        name = data.find("div", class_="gamename").text.strip()

        if name not in new_games:
            continue

        print(f"New BGA Game: {name}")
        game = fill_game_data(Game(platform="BGA", name=name), data)
        model.store(game)


def fill_game_data(game: Game, data: Any) -> Game:
    game.image = data.find("img")["bga_lazyload"]

    game_html = requests.get("https://boardgamearena.com" + data.find("a")["href"])
    game_data = BeautifulSoup(game_html.content, "html.parser")

    desc = game_data.find(id="game_description_text")
    if desc:
        game.description = desc.text.strip()

    for attribute in game_data.find_all("div", class_="row-data"):
        key = attribute.find(class_="row-label").text.strip()
        value = attribute.find(class_="row-value").text.strip()

        if key == "Number of players":
            if "-" in value:
                game.min_players, game.max_players = [
                    int(x.strip()) for x in value.split("-")
                ]
            elif value.isnumeric():
                game.min_players = int(value.strip())
                game.max_players = int(value.strip())

        elif value and key in ["Complexity", "Strategy", "Luck", "Interaction"]:
            setattr(game, key.lower(), int(value))

    return game


if __name__ == "__main__":
    with sqlite3.connect("games.db") as conn:
        cursor = conn.cursor()

        game_model = Game.model(cursor)

        for game in CUSTOM_GAMES:
            if game_model.search(platform=game.platform, name=game.name):
                continue

            game_model.store(game)

        update_bga(game_model, Tag.model(cursor))
