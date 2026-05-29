# Install the Amazon Comp Suggestions skill (3 steps, ~5 minutes)

Welcome! This is an LF internal tool for drafting comp-title messages to send to Amazon. Once installed, every comp request takes about 90 seconds.

---

## Step 1 — Install the skill (10 seconds)

Double-click **`amazon-comp-suggestions.skill`** in this folder.

Claude will open with a "Save skill" or "Install" prompt — click it. You're done.

If that doesn't work for any reason, use **`amazon-comp-suggestions.zip`** instead: in Claude, go to Skills → Upload, and drag in the .zip file.

## Step 2 — Add your TMDb API key (~5 minutes, one time)

The skill needs a free API key from TMDb to look up movie and TV data. Full instructions are in **`SETUP_KEY.md`** in this folder.

Short version:
1. Sign up free at https://www.themoviedb.org/signup (~30 seconds)
2. Get your key at https://www.themoviedb.org/settings/api (~5 min approval)
3. Tell Claude: *"Save my TMDb API key to the amazon-comp-suggestions skill: \<paste-your-key\>"*

## Step 3 — Use it (30 seconds per request, forever)

In any new Claude conversation, just type:

> Amazon wants comps for [title]

The skill will:
- Ask you 5-7 quick button questions (release type, opening weekend range, etc.)
- Generate a list of 4-7 comparable titles in ~60 seconds
- Show it in the exact Slack-style format we use with Amazon
- Let you refine ("remove X", "add Y", "swap A for B") until it's right
- Save a log of the session for future reference

When you're happy, just say *"done"* or *"send it"* — Claude prints the final block, you paste it into Slack to Amazon.

---

## When Amazon responds days later

Come back to Claude and say:

> Log feedback for [title]

The skill will find your session and let you record what Amazon said (accepted all / rejected which / partial). This builds the dataset that lets us tune the rules over time.

---

## Need help?

- Detailed setup steps: see **`SETUP_KEY.md`**
- Something broke: ping <your-LF-contact> on Slack
- Want to suggest a rule change: tell Claude during a session — it'll log it for the LF team to review
