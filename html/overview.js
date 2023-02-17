// SPDX-FileCopyrightText: 2021 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
//
// SPDX-License-Identifier: BSD-2-Clause

// vim: expandtab ts=4
"use strict";

import { elemGenerator } from "https://javajawa.github.io/elems.js/elems.js";

const table = elemGenerator("table");
const thead = elemGenerator("thead");
const tbody = elemGenerator("tbody");
const tr = elemGenerator("tr");
const td = elemGenerator("td");
const th = elemGenerator("th");
const div = elemGenerator("div");
const a = elemGenerator("a");
const input = elemGenerator("input");

function formatGame(game) {
	if (game.last_created) {
		game.last_created = new Date(game.last_created);
	}
	if (game.last_launched) {
		game.last_launched = new Date(game.last_launched);
	}

	game.suppressed = false;
	if (game.until) {
		game.until = new Date(game.until);
		game.suppressed = true;
	}

	return game;
}

function fixLink(bga_id) {
    const url = new URL("https://boardgamearena.com/lobby");
    url.searchParams.set("game", bga_id);

    return url.toString();
}

function autoBoard(e) {
    const tokens = document.getElementById("tokens").value;

    if (!tokens) {
        return true;
    }

    const game = e.target.getAttribute("game_id");

    e.target.href = `/cursed-chat/create/${encodeURIComponent(game)}/${encodeURIComponent(tokens)}`;
    console.log(e.target.href);

    return true;
}

function suppress(e) {
	const game_id = e.target.getAttribute("game_id");
	const days = e.target.getAttribute("amount");

	console.log(game_id, days);
	fetch("suppress", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
        	"admin": admin,
        	"game_id": parseInt(game_id),
        	"days": parseInt(days),
        }),
    }).then((e.target.closest("tr").classList.add("suppressed")));
}

function buildTable(games) {
    const searchbox = input({ id: "search", type: "text", keyup: search });

    const header = thead(
        tr(
            th("Game", searchbox),
            th({ id: "_t", class: "smol border numeric", click: sortTable }, div("Total Votes")),
            th({ id: "_a", class: "smol border numeric", click: sortTable }, div("My Boards")),
            th({ id: "_l", class: "smol border numeric", click: sortTable }, div("Boards Launched")),
            th({ id: "_r", class: "smol numeric", click: sortTable }, div("Launch Rate")),
            th({ class: "border" }, div("Suppress")),
            th({ id: "_s", class: "smol border numeric", click: sortTable }, div("Suppressed")),
        )
    );

    const rows = tbody(
        Object.values(games).map(game => tr(
                { class: [game.open > 0 ? "has_boards" : "", game.suppressed ? "suppressed" : ""].join(" ")},
                td(a({ href: fixLink(game.bga_id), target: "_blank", title: game.description, mousedown: autoBoard, game_id: game.bga_id }, game.name)),
                td({ class: "number border", title: (game?.users||"").replaceAll(",", "\n") }, (game.votes||0).toString()),
                td({ class: "number border" }, (game.open||0).toString()),
                td({ class: "number border" }, (game.launched||"").toString()),
                td({ class: "number" }, game.created > 0 ? (100 * (game.launched||0) / game.created).toFixed(0) + "%": ""),
                td({ class: "border"},
                	a({click: suppress, game_id: game.game_id, amount: "4"}, "1wk"),
                	" | ",
                	a({click: suppress, game_id: game.game_id, amount: "12"}, "2wk"),
                	" | ",
                	a({click: suppress, game_id: game.game_id, amount: "26"}, "4wk"),
                	" | ",
                	a({click: suppress, game_id: game.game_id, amount: "9999"}, "hide"),
                ),
                td({ class: "number border" }, game.suppressed ? "0" : "1"),
            )
        )
    );

    return table(header, rows);
}

function sortTable(event) {
    const target = event.target.closest("th");
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

function search() {
    const term = document.getElementById("search").value;
    const terms = term.split(/\s+/);

    [...document.querySelectorAll("tbody tr")].forEach(row => {
        const matches = terms.every(term => row.textContent.toLowerCase().includes(term.toLowerCase()));

        row.style.display = matches ? "" : "none";
    });
}

function initTokens() {
	const tokens = document.getElementById("tokens");
	tokens.value = window.localStorage.getItem("admintoken") || "";
	tokens.addEventListener("change", () => {
		window.localStorage.setItem("admintoken", tokens.value);
	});
}

const admin = new URLSearchParams(window.location.search).get("admin");
initTokens();
fetch(`overview.json/${admin}`)
    .then(r => r.json())
    .then(games => games.map(formatGame))
    .then(buildTable)
    .then(table => document.body.appendChild(table))
    .then(() => {
        const totalColumn = document.getElementById("_t");
        const launchedColumn = document.getElementById("_l");
        const activeColumn = document.getElementById("_a");
        const suppressedColumn = document.getElementById("_s");
        sortTable({ target: launchedColumn });
        sortTable({ target: totalColumn });
        sortTable({ target: activeColumn });
        sortTable({ target: activeColumn });
        sortTable({ target: suppressedColumn });
    });
