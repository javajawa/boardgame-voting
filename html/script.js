// SPDX-FileCopyrightText: 2021 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
//
// SPDX-License-Identifier: BSD-2-Clause

"use strict";

function updateField(selector, value)
{
    [...document.querySelectorAll(selector)].forEach(e => e.textContent = value);
}

fetch("me").then(r=>r.json()).then(me => {
    updateField(".js-user", me.username);

    updateField(".js-votes", me.votes.length);
    updateField(".js-max-votes", me.max_votes);
    updateField(".js-votes-left", me.max_votes - me.votes.length);

    updateField(".js-avotes", me.avotes.length);
    updateField(".js-max-avotes", me.max_votes);
    updateField(".js-avotes-left", me.max_votes - me.avotes.length);

    updateField(".js-vetoes", me.vetos.length);
    updateField(".js-max-vetoes", me.max_vetos);
    updateField(".js-vetoes-left", me.max_vetos - me.vetos.length);

    window.me = me;
});
