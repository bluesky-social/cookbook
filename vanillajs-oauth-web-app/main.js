import { BrowserOAuthClient } from '@atproto/oauth-client-browser'
import { Agent, RichText } from '@atproto/api'

const OAUTH_SCOPE = "atproto repo:app.bsky.feed.post?action=create"

const clientId = `http://localhost?${new URLSearchParams({
	scope: OAUTH_SCOPE,
	redirect_uri: Object.assign(new URL(window.location.origin), { hostname: '127.0.0.1' }).href,
})}`

let oac; // undefined | BrowserOAuthClient
let agent; // undefined | Agent

async function init() {
	/* Set up form/button handlers */
	document.getElementById("login-form").onsubmit = function(e) {
		e.preventDefault();
		doLogin(e.target.username.value);
	}

	document.getElementById("bsky-button").onclick = function() {
		doLogin("https://bsky.social");
	}

	document.getElementById("post-form").onsubmit = function(e) {
		e.preventDefault();
		doPost(document.getElementById("post-text").value);
	}

	document.getElementById("logout-nav").onclick = function() {
		oac.revoke(agent.did);
		window.location.reload();
	}

	/* Set up the OAuth client */
	oac = await BrowserOAuthClient.load({
		clientId,
		handleResolver: 'https://bsky.social',
	});
	const result = await oac.init();

	if (result) {
		const { session, state } = result
		if (state != null) {
			console.log(`${session.sub} was successfully authenticated (state: ${state})`)
		} else {
			console.log(`${session.sub} was restored (last active session)`)
		}

		agent = new Agent(session);
		window.agentDebug = agent; // TODO: remove this

		const res = await agent.com.atproto.server.getSession();
		if (!res.success) {
			console.log("getSession failed", res);
			return; // TODO: surface error to user!
		}

		document.getElementById("welcome-message").innerText = `@${res.data.handle}`;
		document.getElementById("post-container").style.display = "inherit"; // unhide
		document.getElementById("logout-nav").style.display = "inherit"; // unhide
	} else { // there is no existing session
		document.getElementById("login-container").style.display = "inherit"; // unhide
	}

	document.getElementById("loading-spinner").style.display = "none";
	console.log("init done");
}

async function doLogin(identifier) {
	const loginButton = document.getElementById("login-button");
	loginButton.setAttribute("aria-busy", "true");
	try {
		await oac.signIn(identifier, {
			state: 'some value needed later',
			signal: new AbortController().signal, // Optional, allows to cancel the sign in (and destroy the pending authorization, for better security)
		})
		console.log('Never executed')
	} catch (err) {
		console.log('The user aborted the authorization process by navigating "back"')
	}
	loginButton.removeAttribute("aria-busy");
}

async function doPost(message) {
	const postButton = document.getElementById("post-button");
	postButton.setAttribute("aria-busy", "true");

	const rt = new RichText({text: message});
	await rt.detectFacets(agent);

	const res = await agent.com.atproto.repo.createRecord({
		repo: agent.did,
		collection: 'app.bsky.feed.post',
		record: {
			$type: 'app.bsky.feed.post',
			text: message,
			facets: rt.facets,
			createdAt: new Date().toISOString(),
		},
	});

	if (!res.success) {
		// TODO: something!
	}

	const atUri = res.data.uri;
	const [uriRepo, uriCollection, uriRkey] = atUri.split('/').slice(2);
	const pdsHost = (await window.agentDebug.sessionManager.getTokenInfo()).aud; // XXX: is this really the best way?

	console.log(res);

	// hide the "post" screen
	postButton.removeAttribute("aria-busy");
	document.getElementById("post-container").style.display = "none";

	// show the "success" screen
	document.getElementById("success-pds").href = `${pdsHost}xrpc/com.atproto.repo.getRecord?repo=${uriRepo}&collection=app.bsky.feed.post&rkey=${uriRkey}`;
	document.getElementById("success-bsky").href = `https://bsky.app/profile/${uriRepo}/post/${uriRkey}`;
	document.getElementById("success-zeppelin").href = `https://zeppelin.social/profile/${uriRepo}/post/${uriRkey}`;
	document.getElementById("success-pdsls").href = `https://pdsls.dev/${atUri}`;
	document.getElementById("success-container").style.display = "inherit"; // unhide
}

console.log("hello");

// is this the right time to init?
document.addEventListener('DOMContentLoaded', init);
