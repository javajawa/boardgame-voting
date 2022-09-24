// SPDX-FileCopyrightText: 2021 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
//
// SPDX-License-Identifier: BSD-2-Clause

"use strict";

function updateField(selector, value) {
    [...document.querySelectorAll(selector)].forEach(e => (e.textContent = value));
}

fetch("me")
    .then(r => r.json())
    .then(me => {
        updateField(".js-user", me.username || "Not Logged In");

        updateField(".js-votes", me.votes.length);
        updateField(".js-max-votes", me.max_votes);
        updateField(".js-votes-left", me.max_votes - me.votes.length);

        updateField(".js-async-votes", me.async_votes.length);
        updateField(".js-max-async-votes", me.max_votes);
        updateField(".js-async-votes-left", me.max_votes - me.async_votes.length);

        updateField(".js-vetoes", me.vetoes.length);
        updateField(".js-max-vetoes", me.max_vetoes);
        updateField(".js-vetoes-left", me.max_vetoes - me.vetoes.length);

        window.me = me;
    });
