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

fetch("overview.json")
    .then(r => r.json())
    .then(games =>
        table(
            thead(tr(th("Game"), th("Link"), th("Plaid"), th("Brew"), th("Cursed"), th("LRR"), th("Total"))),
            tbody(
                games.map(game =>
                    tr(
                        td(game.game),
                        td(a({ href: fixLink(game.link), target: "_blank" }, game.link)),
                        td(game.plaid.toString()),
                        td(game.brew.toString()),
                        td(game.cursed.toString()),
                        td(game.lrr.toString()),
                        td(game.total.toString())
                    )
                )
            )
        )
    )
    .then(table => document.body.appendChild(table));
