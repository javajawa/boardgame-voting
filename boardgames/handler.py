#!/usr/bin/env python3
# vim: fileencoding=utf-8 expandtab ts=4 nospell

# SPDX-FileCopyrightText: 2020 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

"""Boardgames Voting"""

from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple, Union

import abc
import dataclasses
import hashlib
import json
import os

from wsgiref.handlers import format_date_time

from boardgames.model import Realm


WSGIEnv = Dict[str, str]
WSGICallback = Callable[[str, Sequence[Tuple[str, str]]], None]


@dataclasses.dataclass
class Response:
    status: int
    mime_type: str
    contents: Union[bytes, Iterable[bytes]]
    modified: Optional[float] = None
    tag: Optional[str] = None
    headers: List[Tuple[str, str]] = dataclasses.field(default_factory=list)

    def get_status(self) -> str:
        return str(self.status)

    def get_headers(self) -> List[Tuple[str, str]]:
        headers: Dict[str, str] = {"Content-Type": self.mime_type}

        if self.modified:
            headers["Last-Modified"] = format_date_time(self.modified)

        if self.tag:
            headers["ETag"] = self.tag

        ret = list(headers.items())
        ret.extend(self.headers)

        return ret

    def get_contents(self) -> Iterable[bytes]:
        if isinstance(self.contents, bytes):
            return [self.contents]

        return self.contents


class FileData:
    mime_type: str
    modified: float
    tag: str
    contents: List[bytes]

    def __init__(self, path: str, mime: str):
        self.mime_type = mime

        with open(path, "rb") as infile:
            stat = os.fstat(infile.fileno())
            self.modified = stat.st_mtime
            self.contents = list(infile.readlines())
            self.tag = hashlib.md5(b"".join(self.contents)).hexdigest()


class Handler(abc.ABC):
    def __call__(self, environ: WSGIEnv, start: WSGICallback) -> Iterable[bytes]:
        path = environ.get("PATH_INFO", "/")
        verb = environ.get("REQUEST_METHOD", "GET")

        response = self.call(verb, path, environ)

        print(verb, path, response.get_status(), response.get_headers())
        start(response.get_status(), response.get_headers())

        return response.get_contents()

    @abc.abstractmethod
    def call(self, verb: str, path: str, environ: WSGIEnv) -> Response:
        pass

    @staticmethod
    def normalise_path(path: str) -> Tuple[str, str]:
        if path[0] == "/":
            path = path[1:]

        if "/" not in path:
            return path, "/"

        realm, path = path.split("/", 1)

        return realm, path

    @staticmethod
    def page_file(environ: WSGIEnv, data: FileData) -> Response:
        if environ.get("HTTP_IF_NONE_MATCH", "") == data.tag:
            return Response(304, data.mime_type, [], data.modified, data.tag)

        return Response(200, data.mime_type, data.contents, data.modified, data.tag)

    def realm_file(self, environ: WSGIEnv, realm: Realm, data: FileData) -> Response:
        replacement = realm.realm.encode("utf-8")
        response = self.page_file(environ, data)
        response.contents = [
            x.replace(b"{realm}", replacement) for x in response.get_contents()
        ]

        return response

    @staticmethod
    def send_json(data: Any) -> Response:
        return Response(
            200,
            "application/json",
            [x.encode("utf-8") for x in json.JSONEncoder().iterencode(data)],
        )
