// SPDX-FileCopyrightText: 2021 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
//
// SPDX-License-Identifier: BSD-2-Clause

// vim: expandtab ts=4
"use strict";

import { elemGenerator } from "https://javajawa.github.io/elems.js/elems.js";

const table = elemGenerator("table");
const tbody = elemGenerator("tbody");
const thead = elemGenerator("thead");

const tr = elemGenerator("tr");
const th = elemGenerator("th");
const td = elemGenerator("td");

const a = elemGenerator("a");

const summary = elemGenerator("summary");
const details = elemGenerator("details");
const input = elemGenerator("input");

function number_to_td(number, prefix, classes)
{
    return td(number.toString(), {"class": `${classes} number ${prefix} ${prefix}_${number}`});
}

function make_details(_summary, _details)
{
    return details(
        summary(_summary),
        _details
    );
}

function game_to_tr(game)
{
    return tr(
        {"game-id": game.game_id},
        {"class": [game.voted ? "voted" : "", game.avoted ? "avoted" : ""].join(" ")},
        td(a({"href": game.link || "", target: "_blank"}, game.platform), {"class": "border"}),
        td(make_details(game.name, game.description), {"class": "border"}),
        number_to_td(game.min_players, "players", "border"),
        td("-"),
        number_to_td(game.max_players, "players", ""),
        number_to_td(game.complexity, "complexity", "border"),
        number_to_td(game.strategy, "complexity", ""),
        number_to_td(game.luck, "complexity", ""),
        number_to_td(game.interaction, "complexity", ""),
        game.realm.realtime ?
            td(
                (1-game.voted).toString(),
                {"class": "border vote", "click": toggleVote}
            ) : null,
        game.realm.passnplay ?
            td(
                (1-game.avoted).toString(),
                {"class": "border avote", "click": toggleVote}
            ) : null,
    );
}

function table_superheaders(realm)
{
    const searchbox = input({id: "search", type: "text", keyup: search});

    return tr(
        th("Search", searchbox, {"colspan": 2, "class": "border"}),
        th("Players", {"colspan": 3, "class": "border"}),
        th("Complexity", {"colspan": 4, "class": "border"}),
        th("Votes", {"colspan": realm.realtime + realm.passnplay, "class": "border"}),
    );
}

function table_headers(realm)
{
    const headings = {
        "Platform": {"class": "border"},
        "Name": {"class": "border"},
        "#": {"class": "border numeric", "title": "Min Players"},
        "": {},
        "*": {"class": "numeric", "title": "Max Players"},
        "∑": {"class": "border numeric", "title": "Complexity"},
        "♜": {"class": "numeric", "title": "Strategy / Planning"},
        "⚅": {"class": "numeric", "title": "Luck"},
        "⚔️": {"class": "numeric", "title": "Interaction Between Players"},
    }

    if (realm.realtime) {
        headings["RT"] = {"class": "border default_sort button", "title": "Real Time"};
    }
    if (realm.passnplay) {
        headings["P'n'P"] = {"class": "border default_sort button", "title": "Pass and Play"};
    }

    return tr(
        Object.entries(headings).map((h) => th(...h, {"click": sortTable}))
    );
}


Promise.all([
    fetch("games.json").then(r => r.json()),
    fetch("me").then(r => r.json())
]).then(r => {
    const games = r[0];
    const me = r[1];

    return games.map(game => {
        game.voted = (me.votes.indexOf(game.game_id) !== -1);
        game.avoted = (me.avotes.indexOf(game.game_id) !== -1);
        game.realm = me.realm;
        return game;
    });
}).then(games => table(
    thead(table_superheaders(games[0].realm), table_headers(games[0].realm)),
    tbody(games.map(game_to_tr))
))
    .then(table=>document.body.appendChild(table))
    .then(() => sortTable({target: document.querySelector("th.default_sort")}))
    .catch(e => console.error(e));

let bounceTimer;

function toggleVote( event )
{
    const cell = event.target;
    const row  = event.target.closest("tr");
    const type = event.target.classList.contains("vote") ? "voted" : "avoted";

    cell.textContent = 1 - row.classList.toggle(type);

    if (bounceTimer) {
        return;
    }

    bounceTimer = window.setTimeout(sendVotes, 500);
}

function sendVotes()
{
    bounceTimer = null;

    const games = [...document.querySelectorAll("tr.voted")].map(e => e.getAttribute("game-id"));
    const agames = [...document.querySelectorAll("tr.avoted")].map(e => e.getAttribute("game-id"));

    console.log("Sending realtime votes for", games);
    console.log("Sending async votes for", agames);

    fetch(
        "vote",
        {
            method: "PUT",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(games)
        }
    ).then(document.querySelector(".js-votes").textContent = games.length);

    fetch(
        "avote",
        {
            method: "PUT",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(agames)
        }
    ).then(document.querySelector(".js-avotes").textContent = games.length);
}


function sortTable( event )
{
    const target = event.target;
    const body = target.closest("table").querySelector("tbody");
    const rows = Array.from( body.children );
    const numeric = target.classList.contains("numeric");
    const dir = target.classList.contains("sorted");

    [...target.closest("thead").querySelectorAll("th.sorted")].forEach(e => e.classList.remove("sorted"));
    target.classList.toggle("sorted", !dir);

    let idx = 0, pointer = target;
    while ( ( pointer = pointer.previousElementSibling ) ) ++idx;

    rows.sort( function( l, r ) {
        let l_text = l.children[idx].textContent;
        let r_text = r.children[idx].textContent;

        let res;

        if ( numeric )
        {
            l_text = parseFloat( l_text || -1 , 10 );
            r_text = parseFloat( r_text || -1 , 10 );
            res = l_text === r_text ? 0 : ( l_text < r_text ? -1 : 1 );
        }
        else
        {
            res = l_text.localeCompare( r_text );
        }

        if ( dir ) res = -res;

        return res;
    } );

    for ( const row of rows )
    {
        row.parentElement.removeChild( row );
    }

    for ( const row of rows )
    {
        body.appendChild( row );
    }
}

function search()
{
    const term = document.getElementById("search").value;
    const terms = term.split(/\s+/);

    [...document.querySelectorAll("tr[game-id]")].forEach(row => {
        const matches = terms.every(term => row.textContent.toLowerCase().includes(term.toLowerCase()));

        row.style.display = matches ? "" : "none";
    });
}
