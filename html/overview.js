// SPDX-FileCopyrightText: 2021 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
//
// SPDX-License-Identifier: BSD-2-Clause

// vim: expandtab ts=4
"use strict";

import { elemGenerator, documentFragment } from "https://javajawa.github.io/elems.js/elems.js";

const table = elemGenerator("table");
const thead = elemGenerator("thead");
const tbody = elemGenerator("tbody");
const tr = elemGenerator("tr");
const td = elemGenerator("td");
const th = elemGenerator("th");
const div = elemGenerator("div");
const a = elemGenerator("a");

function fixLink(href) {
    const match = href.match(/boardgamearena.com\/lobby\?game=([0-9]+)/);

    if (!match) {
        return href;
    }

    const url = new URL("https://boardgamearena.com/table/table/createnew.html");
    url.searchParams.set("game", match[1]);
    url.searchParams.set("gamemode", "async");
    url.searchParams.set("forceManual", "true");
    url.searchParams.set("is_meeting", "false");

    return url.toString();
}

function buildTable(realms, games) {
    const rkeys = Object.values(realms).map(realm => realm.realm);

    const header = thead(
        tr(
            th("Game"),
            th({ class: "border" }),
            Object.values(realms).map(realm => th({ class: "smol numeric", click: sortTable }, div(realm.realm_name))),
            th({ id: "_t", class: "border numeric", click: sortTable }, "Total\nVotes"),
            th({ class: "border numeric", click: sortTable }, "My\nBoards"),
            th({ id: "_a", class: "numeric", click: sortTable }, "Total\nBoards")
        )
    );

    const rows = tbody(
        Object.values(games).map(game =>
            tr(
                { class: game.active > 0 ? "has_boards" : "" },
                td(a({ href: fixLink(game.link), target: "_blank" }, game.name)),
                td({ class: "border" }),
                rkeys.map(realm_id => td({ class: "number" }, game[realm_id]?.toString() || "")),
                td(
                    { class: "number border" },
                    rkeys.reduce((total, realm_id) => total + (game[realm_id] || 0), 0).toString()
                ),
                td({ class: "number border" }, game.mine.toString()),
                td({ class: "number" }, game.active.toString())
            )
        )
    );

    return table(header, rows);
}

function sortTable(event) {
    const target = event.target;
    const body = target.closest("table").querySelector("tbody");
    const rows = Array.from(body.children);
    const numeric = target.classList.contains("numeric");
    const dir = target.classList.contains("sorted");

    [...target.closest("thead").querySelectorAll("th.sorted")].forEach(e => e.classList.remove("sorted"));
    target.classList.toggle("sorted", !dir);

    let idx = 0,
        pointer = target;
    while ((pointer = pointer.previousElementSibling)) ++idx;

    rows.sort(function (l, r) {
        let l_text = l.children[idx].textContent;
        let r_text = r.children[idx].textContent;

        let res;

        if (numeric) {
            l_text = parseFloat(l_text || -1, 10);
            r_text = parseFloat(r_text || -1, 10);
            res = l_text === r_text ? 0 : l_text < r_text ? 1 : -1;
        } else {
            res = l_text.localeCompare(r_text);
        }

        if (dir) res = -res;

        return res;
    });

    for (const row of rows) {
        row.parentElement.removeChild(row);
    }

    for (const row of rows) {
        body.appendChild(row);
    }
}

const admin = new URLSearchParams(window.location.search).get("admin");
fetch(`overview.json/${admin}`)
    .then(r => r.json())
    .then(({ realms, games }) => buildTable(realms, games))
    .then(table => document.body.appendChild(table))
    .then(() => {
        const totalColumn = document.getElementById("_t");
        const activeColumn = document.getElementById("_a");
        sortTable({ target: totalColumn });
        sortTable({ target: activeColumn });
        sortTable({ target: activeColumn });
    });
