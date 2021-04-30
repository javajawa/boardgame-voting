// SPDX-FileCopyrightText: 2020 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
//
// SPDX-License-Identifier: BSD-2-Clause

// vim: expandtab ts=4
"use strict";

class Description
{
	constructor(name, tags, desc, ignore)
	{
		this.tags = tags;
		this.desc = desc;
		this.skip = ignore || [];

		descriptions[name] = this;
	}
}

class Board
{
	constructor(name, link, mods, seat, free)
	{
		this.name = name;
		this.link = link;
		this.mods = mods;
		this.seat = seat;
		this.free = free;
	}
}

const descriptions = {};

// :exclamation:
new Description("7 Wonders", ["drafting"], "Draft your way into a new empire!");
new Description("7 Wonders Duel", ["planning"], "");
new Description("Abyss", [], ":exclamation: Control factions, influence the court and reign over underwater realms!");
new Description("Beyond the Sun", [], "Beyond the Sun is a space civilization game in which players collectively decide the technological progress of humankind at the dawn of the Spacefaring Era, while competing against each other to be the leading faction in economic development, science, and galactic influence.");
new Description("Chakra", ["planning"], "Use your limited action tokens to fill the seven chakras that represent the energy flowing in their body. To score points, a player must harmonize each of their chakras in the best possible way.");
new Description("Alhambra", ["hand management", "tile management"], "Design and build your perfect medieval castle");
new Description("Blue Skies", ["engine building", "bidding"], "Build up your air line by purchasing gates.");
new Description("Can't Stop", ["luck"], "Roll your two dice siz and climb ladders for the value. Race to the top!");
new Description("Carcassonne", ["tile management", "worker placement"], "Build a medieval kindgom from tiles, place your meeple, and score points when features such as cities and roads are complete.");
new Description("Carnegie", [], ":exclamation: Recruit and manage employees, expand your business, invest in real estate, produce and sell goods, and create transport chains across the United States");
new Description("Clans of Caledonia", ["action-rounds"], "A strategic economic game set in 19 th -century Scotland. In Clans of Caledonia, players represent unique historical clans competing to produce, trade, and export agricultural goods, as well as their famous whisky!");
new Description("Colt Express", ["planning", "hidden information"], "Play as one of the many theives on a rain heist. Play out your actions into a deck for the round, and then resolve them -- hoping they are still relevant!");
new Description("CuBirds", ["set matching", "hand management"], "Adorable bird game! Place your bird cards to pick up others and build up your flocks!");
new Description("Dice Forge", ["deck building on 2d6"], "Forge mighty powers onto your dice and challenge the gods themselves to earn glory and victory over just 9 rounds.");
new Description("Dinosaur Tea Party", ["logic"], "A dinosaur themed Guess Who style game where you must ask questions to determin the identity of opponents cards");
new Description("Eminent Domain", ["deck building", "tableau building"], "Create a galactic empire by building a deck of action cards in what I might describe as 'Deckbuild For the Galaxy'");
new Description("Downforce", ["hand management", "positioning"], "Buy cars, bet on winners, and play out movement cards to race around the track. But be warmed: most movement cards effect multiple racers!");
new Description("Dragon Castle", ["tile placement"], "A mulitplayer version of Mah Jong solitaire, draw paired tiles from the stack to build your castle.", ["Yes"]);
new Description("Elfenland", ["hand management", "positioning"], "You're on Elf Gap Year! can you visit all 20 elf towns and end up back at home?");
new Description("Fleet", ["hand management", "engine building", "bidding"], "Bid for fishing contracts and deploy your fleet in this bigging game where all resources are cards in hand");
new Description("Hardback", ["word forming", "deck building"], "Use your deck of letters to create words; each letter you use as itself gives a bonus, and allow you to buy better effects");
new Description("Kingdom Builder", ["objective matching", "positioning"], "Draw a terrain card, add to your contiguous kingdom using that terrain, meet conditions");
new Description("Kingdomino", ["tile management"], "Build your kingdom out of dominos! draft a domino at a time, place it in your 5x5 grid, and score points based on areas of the same terrain.");
new Description("Nidavellir", ["bidding"], "Recruit dwarf heroes for glory; collect suited sets to combine their powers, or collect set of suits to summon mighty heroes");
new Description("No Thanks!", ["bidding"], "Big tokens to not pick up cards, or take a card and all the tokens on it! Lowest total score wins!", ["Hidden chips"]);
new Description("Oriflamme", ["hand management", "positioning"], "Over six rounds, add one of ten powers cards to hidden queue of effects between all players, and attempt to out-wite your opponents");
new Description("Quantum", ["strategy"], "Roll and fleet of ships and attempt to conquer the galaxy by placing your Qunatum cubes on planets");
new Description("Potion Explosion", [], "Brew poitions by picking ingreidents out of the dispenser...but with a candy-crush like twist: if taking an ingreident causes two (or more) of the same colour to match, you get those too!");
new Description("Puerto Rico", ["engine building", "action selection"], "Build your plantations and factories to sell goods locally or export them for points");
new Description("Rallyman: GT", ["planning"], "Plan your gear shifts to navigate the course, then roll those gear dice to navigate the terrain as best you can.");
new Description("Res Arcana", ["drafting"], "Draft magical essences and items to build artifacts, activate their powers, and command dragons.");
new Description("Race for the Galaxy", ["hand management", "tableau building"], "Build a mighty space empire where your workers, actions, and resources are all secretly cards.");
new Description("Roll for the Galaxy", ["worker management", "tableau building"], "Build a mighty space empire where your workers, actions, and resources are all secretly dice.");
new Description("Saboteur", ["tile placing"], ":exclamation: It’s Miners vs. Saboteurs in this race for the gold. As you lay your cards and build a path, your friends are lurking ready to destroy your plans.");
new Description("Seasons", ["drafting", "tableu building"], "Draft dice to receive effects, use those to create spaces on your tableau and play cards, and left over dice determine how much time passes.");
new Description("Senet", ["luck"], "An ancient Egyptian game with a backgammon feel");
new Description("Super Fantasy Brawl", ["stategy", "positioning"], "Draft three heroes, collect their cards, and send them into the arena in this game of positioning and stabbing");
new Description("Steam Works", [], "Steampunk themed objective-filling/contraption making game");
new Description("Stone Age", ["worker placement", "resource management"], "Forge a stone age civilisation with such wonderful fetures as 'huts', 'tools', 'argiculture' and a little something called 'culture'?")
new Description("Takenoko", ["objective matching", "positioning", "tile management"], "Try to build the greatest bamboo farm with a happy panda to attract the Emporer's attention.", ["Original edition"]);
new Description("Tea Time", ["card collecting"], "Take cards from the table to add to your hand, but be aware that mirrored cards cancel eachother out.");
new Description("Terra Mystica", ["full strategy", "action-rounds"], "Wield arcana to teraform a fatnasy world to suit your people, build towns and just generally confuse kitteh.", ["Adjusted Starting VPs", "Variable turn order"]);
new Description("The Builders: Middle Ages", ["resource management"], "Hire craftsmen to help you build buildings in this limited-action game.");
new Description("Tzolk'in", ["worker placement", "resource management"], "A worker placement game where workers are placed on cogs and then rotated turn by turn. Each turn you must place or remove a worker. When removing, you take an action where the worker is, or on a previous step. Build your meso-american civilisation before the main cog completes its full cycle.");
new Description("The Crew", ["cooperative", "trick taking"], "A co-operative trick taking game where you follow missions to have certain cards end up with certain players");
new Description("Through the Ages: A new Story of Civilization", ["full strategy"], "Build a mighty civilisation by making people, producing resources, building technology and buildings, and fighting your neighbours", ["Complete game"]);
new Description("Thurn and Taxis", ["hand management", "routing"], "Build the power of the postal service in the Holy Roman Empire by building routes through the 7 regions");
new Description("Tokaido", ["positioning?"], "Walk the path from Kyoto to Edo along the Tokaido, attempting to have the most fufilling journey possible.");
new Description("Trekking the World", ["hand management", "positioning"], "Travel the world collecting souvenirs and visiting famous sites for the most exciting");
new Description("Welcome To", ["bingo-esque tile management"], "Design the perfect neighbour by accepting contracts to build numbered houses along three streets.");
new Description("Welcome To New Last Vegas", ["bingo-esque tile management"], "Design the perfect Vegas by accepting contracts to build numbered casinos along four streets.");
new Description("Yahtzee", ["luck"], "Roll five dice up to three times, and assign the result to one of your scoring rows");

function getAllBoards()
{
	// Get all async games available for joining on the page
	return [...document.querySelectorAll('.gametable_status_asyncopen')]
	// Extract these into board information
	.map(board => {
		const name = board.querySelector(".gameinfoname").textContent;
		const link = new URL(board.querySelector("a").getAttribute("href"), window.location);
		const stati = [...board.querySelectorAll('.table_top_status_detailed div')]
			.map(s => s.textContent.split(/, /))
			.flat()
			.filter(x => !!x);
		const seats = board.querySelectorAll(".tableplace").length;
		const freeSeats = board.querySelectorAll(".tableplace_freeplace").length;

		return new Board(name, link, stati, seats, freeSeats);
	});
}

function groupBoards(out, board)
{
	if (!Object.prototype.hasOwnProperty.call(out, board.name)) {
		out[board.name] = [];
	}

	out[board.name].push(board);

	return out;
}

function prepareBoardMessage(boards)
{
	const game = boards[0].name;
	let description;

	if (descriptions.hasOwnProperty(game)) {
		description = descriptions[game];
	} else {
		description = new Description(game, [], "", []);
	}

	const output = [`**${game}**`];

	if (description.tags.length) {
		output.push("[" + description.tags.join(", ") + "]");
	}

	boards.forEach(board => {
		const tags = board.mods
			.filter(tag => description.skip.indexOf(tag) === -1)
			//.filter(tag => tag !== group);

		if (tags.length) {
			output.push(`<${board.link.toString()}> (${tags.join(', ')})`);
		} else {
			output.push(`<${board.link.toString()}>`);
		}
	});

	if (description.desc) {
		output.push("\n" + description.desc);
	}

	return output.join(" ") + "\n";
}

function getBoards(group)
{
	// Get all the boards
	return getAllBoards()
		// Select only the ones which are part of the group
		.filter(board => board.mods.indexOf(group) !== -1)
		// Remove that group from the tags, as it is not relevant
		.map(board => {
			const idx = board.mods.indexOf(group);
			board.mods.splice(idx, 1);

			return board;
		});
}

function getGroupBoards(group)
{
	// Get and group all boards for the group
	return Object.values(
		getBoards(group)
			.reduce(groupBoards, new Object())
	)
	// Translate each board group into text
	.map(prepareBoardMessage)
	.sort()
}


function getSharedBoards()
{
	return Object.values(
		getBoards("CuddlyKitteh's friends")
			.filter(board => board.seat > 2)
			.reduce(groupBoards, new Object())
	)
	// Translate each board group into text
	.map(prepareBoardMessage)
	.sort();
}

function getChallengeBoards()
{
	return Object.values(
		getBoards("CuddlyKitteh's friends")
			.filter(board => board.seat === 2)
			.reduce(groupBoards, new Object())
	)
	// Translate each board group into text
	.map(prepareBoardMessage)
	.sort();
}

function addMessage(messages, message)
{
	if (message.length + messages[0].length > 1995) {
		messages.unshift("");
	}

	messages[0] = messages[0] + "\n" + message;

	return messages;
}

function prepareboardGames(group)
{
	let messages = getGroupBoards(group).reduce(addMessage, [" ".repeat(200)])

	const shared = getSharedBoards();

	if (shared.length) {
		messages = addMessage(messages, "\n=== Cross-Community Boards ===\n")
		messages = shared.reduce(addMessage, messages);
	}

	const challenge = getChallengeBoards();

	if (challenge.length) {
		messages = addMessage(messages, "\n=== Challenge Kitteh ===\n")
		messages = challenge.reduce(addMessage, messages);
	}

	return messages.filter(x => !!x).reverse();
}

function createMessages(group) {
	const messages = prepareboardGames(group);

	if (messages.length) {
		console.log("======", group, "======");
		messages.forEach(m => console.log(m));
	}
}

const gameDetails = r =>
{
	r.forEach(game => {
		if (descriptions.hasOwnProperty(game.name))
			return;

		new Description(game.name, [], ":exclamation: " + game.description);
	});

	console.log("createMessages(<group>) loaded!");
	console.log("createMessages('Plaid Posse');");
	console.log("createMessages('Brew Crew');");
	console.log("createMessages('CursedChat');");
};

x = document.createElement("script");
x.setAttribute("src", "https://games.tea-cats.co.uk/games.json");
document.head.appendChild(x);
