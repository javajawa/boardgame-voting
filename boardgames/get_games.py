#!/usr/bin/env python3
# vim: fileencoding=utf-8 expandtab ts=4 nospell

# SPDX-FileCopyrightText: 2021 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from typing import Any, Dict, List

import json
import logging
import os
import sqlite3
import sys
import yaml

import requests

from systemd.journal import JournalHandler  # type: ignore

from boardgames.model import Game, GameTags, Tag
from orm import TableModel, JoinModel


class BGAImporter:
    logger: logging.Logger
    session: requests.Session

    game_model: TableModel[Game]
    tags_model: TableModel[Tag]
    tag_mapper: JoinModel[Game, Tag]

    def __init__(self, logger: logging.Logger, cursor: sqlite3.Cursor) -> None:
        self.logger = logger
        self.session = requests.Session()

        self.game_model = Game.model(cursor)
        self.tag_model = Tag.model(cursor)
        self.tag_mapper = GameTags.model(cursor)

    def update_bga(self) -> None:
        self._load_token()
        game_data = self._load_bga_metadata()

        self.load_bga_tags(game_data["game_tags"])
        self.load_bga_games(game_data["game_list"])

    def _load_token(self) -> None:
        for line in self.session.get("https://boardgamearena.com/").text.split("\n"):
            if "requestToken: " not in line:
                continue

            _, token = line.split("'", 1)
            token = token.strip("',")

            self.session.headers.update({"x-request-token": token})
            return

    def _load_bga_metadata(self) -> Dict[str, Any]:
        for line in self.session.get("https://boardgamearena.com/gamelist").text.split("\n"):
            if "globalUserInfos={" not in line:
                continue

            _, game_json = line.split("=", 1)

            data = json.loads(game_json.strip(";"))
            if isinstance(data, dict):
                return data

            break

        raise IOError("Failed to get game metadata from BGA")

    def load_bga_tags(self, data: List[Dict[str, Any]]) -> None:
        existing = set(tag.bga_id for tag in self.tag_model.all() if tag.bga_id)

        for tag in data:
            if tag["id"] in existing:
                continue

            dat = Tag(bga_id=tag["id"], category=tag["cat"] or "Meta", tag=tag["name"])
            self.tag_model.store(dat)
            LOGGER.info("Added BGA Tag %s:%s (%d)", dat.category, dat.tag, dat.bga_id)

    def load_bga_games(self, data: List[Dict[str, Any]]) -> None:
        existing: Dict[int, Game] = {
            game.bga_id: game
            for game in self.game_model.search(platform="BGA")
            if game.bga_id
        }
        tag_map: Dict[int, Tag] = {
            tag.bga_id: tag for tag in self.tag_model.all() if tag.bga_id
        }

        for game_json in data:
            if game_json["id"] in existing:
                continue

            game = existing.get(
                game_json["id"],
                Game(
                    platform="BGA", name=game_json["display_name_en"], bga_id=game_json["id"]
                ),
            )
            game.bgg_id = game_json["bgg_id"]

            game_info = self.session.post(
                "https://en.boardgamearena.com/gamelist/gamelist/gameDetails.html",
                data={"game": game_json["name"]},
            ).json()["results"]

            game.min_players = min(game_info["players"])
            game.max_players = min(game_info["players"])
            game.complexity = game_info.get("complexity", 0)
            game.luck = game_info.get("luck", 0)
            game.strategy = game_info.get("strategy", 0)
            game.interaction = game_info.get("diplomacy", 0)
            game.description = game.description or str(game_info.get("presentation", ""))
            game.link = "https://boardgamearena.com/gamepanel?game=" + game_json["name"]
            game.image = game_info["assets_url"] + "/game_box180.png"
            game.options = {}

            for option in game_info["options"]:
                if 200 <= option["id"] < 300:
                    continue

                game.options[option["id"]] = json.dumps(option)

            self.game_model.store(game)

            for tag_id in game_info.get("tags", []):
                if tag_id in tag_map:
                    self.tag_mapper.store(game, tag_map[tag_id])

            self.logger.warning("New Game: %s (%s)", game.name, game.platform)


def import_from_files(cursor: sqlite3.Cursor, logger: logging.Logger) -> None:
    game_model = Game.model(cursor)

    for path in os.listdir("games"):
        if not path.endswith(".yaml"):
            continue

        logger.info("Importing data from ./games/%s", path)
        with open("games/" + path, "rt", encoding="utf-8") as yaml_stream:
            for game_data in yaml.load_all(yaml_stream, Loader=yaml.SafeLoader):
                game = Game(**game_data)

                if game_model.search(platform=game.platform, name=game.name):
                    continue

                logger.warning("New Game: %s (%s)", game.name, game.platform)
                game_model.store(game)


def main(logger: logging.Logger) -> None:
    with sqlite3.connect("games.db") as conn:
        cursor = conn.cursor()

        import_from_files(cursor, logger)

        logger.info("Importing data from BGA")
        BGAImporter(logger, cursor).update_bga()
        conn.commit()


if __name__ == "__main__":
    LOGGER = logging.getLogger("boardgames")

    if sys.stdout.isatty():
        LOGGER.addHandler(logging.StreamHandler())
        LOGGER.setLevel(logging.DEBUG)
    else:
        LOGGER.addHandler(JournalHandler(SYSLOG_IDENTIFIER="bg-get-games"))
        LOGGER.setLevel(logging.WARNING)

    main(LOGGER)
