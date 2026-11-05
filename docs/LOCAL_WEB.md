# Local browser test chat

```sh
python -X utf8 -m app.assistant.local_web --port 8765
```

Open `http://127.0.0.1:8765`. The Persian RTL page uses the existing
`LocalModelSession(trip_state=True)`: actual local-model messages, source notes,
current trip facts, explicit planning preview and session reset. There is no
simulated response or live booking integration. Prepare the existing model using
[the local-model operating guide](LOCAL_MODEL_TURN.md). Inference can take around
a minute; existing 120-second request and four-turn/context bounds remain.

The server binds only to IPv4 loopback. It serves three explicit bundled assets;
there is no file browser, CDN, remote font or new runtime dependency. The HTTP
boundary checks host/origin, JSON shape/body size and a per-session CSRF token.
Session cookies are HttpOnly/SameSite Strict. Browser text is rendered as text,
never interpreted as HTML. This is a local testing interface, not a deployment
or external authentication service.

Conversation UI history and core state stay in memory, at most 16 sessions with
an idle one-hour lifetime. Logs omit requests/prompts/cookies. Different browser
sessions are isolated; reload reconnects to the cookie-owned session. One model
inference runs at a time; concurrent requests get a retryable busy response.
The browser disables controls while waiting. Model/tool rejection preserves the
accepted core session and leaves the message available to retry. Closing the
server clears the conversations; the separately managed model server has its
own logging/lifecycle policy.

`بررسی برنامه سفر` is the explicit confirmation/preview action described in
[session planning](SESSION_PLANNING.md). Missing facts and evidence remain visible;
no dates, logistics, budget compliance or completed travel plan are invented.
`گفتگوی جدید` resets that browser's state and UI history.

HTTP tests use actual isolated local servers and controlled provider replies:
chat/confirmation/reset, cookie isolation, origin/CSRF/host/path boundaries,
invalid input, source text handling and script-safe output. A separate real HTTP
request during implementation returned HTTP 200 from the existing model in
75.75s, preserving Shiraz, three days and relaxed preference, then asking dates.
That narrow synthetic-input observation is not a quality/latency benchmark.
