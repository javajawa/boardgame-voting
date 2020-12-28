#!/usr/bin/env python3
# vim: fileencoding=utf-8 expandtab ts=4 nospell

# SPDX-FileCopyrightText: 2020 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

"""Boardgames Voting"""

from __future__ import annotations

from typing import Any, Dict

import gunicorn.app.base  # type: ignore

from boardgames.wsgi import BGHandler


class StandAlone(gunicorn.app.base.Application):  # type: ignore
    options: Dict[str, Any]

    def __init__(self, options: Dict[str, Any]):
        self.options = options

        super().__init__()

    def load_config(self) -> None:
        config = {
            key: value
            for key, value in self.options.items()
            if key in self.cfg.settings and value is not None
        }
        for key, value in config.items():
            self.cfg.set(key.lower(), value)

    def load(self) -> wsgi.BGHandler:
        return wsgi.BGHandler()


if __name__ == "__main__":
    options = {
        "bind": "%s:%s" % ("127.0.0.1", "8888"),
        "workers": 1,
    }

    StandAlone(options).run()
