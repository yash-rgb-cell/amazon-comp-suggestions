# Delivery messages — copy/paste templates

Pick the message that fits the channel, replace the **[bracketed]** parts, attach the files listed at the top of each one, and send.

---

## Message 1 — Slack / Teams (quick + casual)

**Attach:** `amazon-comp-suggestions.skill` + `CLIENT_INSTALL.md` + `SETUP_KEY.md`

> Hey [name] 👋
>
> Sending over the new comp-suggestions skill — it's the internal tool that drafts the Slack-style comp messages we send to Amazon before launches. Should save you ~25 minutes per request once it's set up.
>
> Three files attached:
> 1. **amazon-comp-suggestions.skill** — double-click to install in Claude
> 2. **CLIENT_INSTALL.md** — 3-step setup (~5 min total)
> 3. **SETUP_KEY.md** — detailed TMDb key instructions
>
> The whole setup takes about 5 minutes (mostly waiting for TMDb to approve your free API key). After that, every comp request is just: type *"Amazon wants comps for [title]"* → click through 5-7 buttons → paste the result into Slack. ~90 seconds end to end.
>
> Ping me here if anything's weird during setup — happy to screen-share if useful. 🚀

---

## Message 2 — Email (formal, for wider team rollout)

**Attach:** `CLIENT_DELIVERY` folder (zipped) OR all four files individually
**Subject:** *New Skill — Amazon Comp Suggestions (internal tool)*

> Hi team,
>
> Attached is a new internal tool we've built that automates the comp-title messages we send to Amazon before each launch. It replaces the manual ChatGPT + Google + Box Office Mojo workflow we've been using.
>
> **What it does:**
> - Asks you 5-7 quick questions about the title (release type, opening weekend range, etc.)
> - Pulls comparable titles from TMDb + Box Office Mojo using a consistent rule set
> - Drafts the exact Slack-style message in our standard format
> - Lets you refine the draft with simple commands ("remove X", "add Y", "swap A for B")
> - Logs every session so we can audit Amazon's feedback and tune the rules over time
>
> **What you save:** ~25 minutes per request, and the output is consistent across analysts.
>
> **Setup:** ~5 minutes, one time per machine. Full instructions in `CLIENT_INSTALL.md`.
>
> **Files attached:**
> - `amazon-comp-suggestions.skill` — the installable skill (double-click in Claude)
> - `amazon-comp-suggestions.zip` — same content, alternate format if the .skill doesn't open
> - `CLIENT_INSTALL.md` — 3-step setup walkthrough
> - `SETUP_KEY.md` — detailed TMDb API key instructions
>
> **Demo:** I'll be running through a live demo on [date/time] — calendar invite coming separately. Bring a real upcoming comp request if you have one and we can run it through the tool together.
>
> Reach out (Slack DM works too) with any questions during setup.
>
> Thanks,
> [your name]

---

## Message 3 — Post-install follow-up (3-5 days after delivery)

**Attach:** (none — text only)

> Hey [name] — quick check-in on the comp-suggestions skill.
>
> A few questions:
> - Did you get it installed and your TMDb key set up?
> - Have you tried it on a real request yet? How did it go?
> - Anything weird or unclear in the flow? Any rule that fired when it shouldn't, or didn't fire when it should?
> - Amazon's feedback on any of the comp sets it produced?
>
> The skill logs every session locally to `feedback_log/YYYY-MM/`, and we'll start collecting those across the team in a few weeks so we can see which rules are working and which need tuning. If you can drop your `feedback_log/` folder into [shared drive path] when you have a sec, that'd be huge for the dataset.
>
> No rush — just want to make sure nothing's blocking you.

---

## Message 4 — When you ship an update (later)

**Attach:** updated `amazon-comp-suggestions.skill`
**Subject prefix:** *[Update]*

> Quick update — new version of the comp-suggestions skill attached.
>
> **What's new:**
> - [bullet 1 — e.g. "extended default time window from 3y to 4y based on feedback"]
> - [bullet 2 — e.g. "added support for limited-series comps"]
> - [bullet 3 — e.g. "fixed BOM scraper after their site redesign"]
>
> **To upgrade:** double-click the attached `.skill` file. It overwrites the previous install in place — no setup steps to repeat, your TMDb key stays put.
>
> Existing feedback logs are preserved (the schema is backward-compatible). Let me know if anything regresses.
