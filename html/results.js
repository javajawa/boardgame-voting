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
const input = elemGenerator("input");

const summary = elemGenerator("summary");
const details = elemGenerator("details");

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
    let vote;

    if (game.voted) {
        vote = [td({"class": "border"}), {"class": "voted"}];
    } else if (game.vetoed) {
        vote = [td({"class": "border veto", "click": toggleVeto}), {"class": "vetoed"}];
    } else {
        vote = [td({"class": "border veto", "click": toggleVeto})];
    }

    return tr(
        {"game-id": game.game_id},
        td(a({href: game.link, target: "_blank"}, game.platform), {"class": "border"}),
        td(make_details(game.name, game.description), {"class": "border"}),
        number_to_td(game.min_players, "players", "border"),
        td("-"),
        number_to_td(game.max_players, "players", ""),
        number_to_td(game.votes, "border votes", ""),
        number_to_td(game.vetos, "votes", ""),
        ...vote
    );
}

function filter_player_count(e)
{
    const players = parseInt(e.target.value || 0);

    [...document.querySelectorAll("tbody>tr")].forEach(row => {
        if (players == 0) {
            row.style.display = "";
            return;
        }

        const [min, max] = [...row.querySelectorAll("td.players")].map(e => parseInt(e.textContent));
        row.style.display = (min <= players && players <= max) ? "" : "none";
    });
}

function table_headers()
{
    const headings = {
        "Platform": {"class": "border"},
        "Name": {"class": "border"},
        "Players": {"class": "border numeric", "colspan": "2"},
        "": input({"type": "number", "min": "1", "max": "12", "change": filter_player_count}),
        "∑": {"class": "border numeric", "title": "Total Votes"},
        "⚔️": {"class": "numeric", "title": "Total Vetoes"},
        "Veto": {"class": "border button"},
    };

    return tr(
        Object.entries(headings).map((h) => th(...h))
    );
}


Promise.all([
    fetch("results.json").then(r => r.json()),
    fetch("me").then(r => r.json())
]).then(r => {
    const games = r[0];
    const me = r[1];

    return games.map(game => {
        game.voted = (me.votes.indexOf(game.game_id) !== -1);
        game.vetoed = (me.vetos.indexOf(game.game_id) !== -1);
        game.score = game.votes - 4 * game.vetos;
        return game;
    });
}).then(games => {
    games.sort((a, b) => b.score - a.score);
    return games;
}).then(games => table(
    thead(table_headers()),
    tbody(games.map(game_to_tr))
))
    .then(table=>document.body.appendChild(table))
    .catch(e => console.error(e));

let bounceTimer;

function toggleVeto(event)
{
    const cell = event.target;
    const row  = event.target.closest("tr");

    cell.textContent = 1 - row.classList.toggle("vetoed");

    if (bounceTimer) {
        return;
    }

    bounceTimer = window.setTimeout(sendVetos, 500);
}

function sendVetos()
{
    bounceTimer = null;

    const games = [...document.querySelectorAll("tr.vetoed")].map(e => e.getAttribute("game-id"));

    console.log("Sending vetos for", games);

    fetch(
        "veto",
        {
            method: "PUT",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(games)
        }
    ).then(document.querySelector(".js-vetoes").textContent = games.length);
}

