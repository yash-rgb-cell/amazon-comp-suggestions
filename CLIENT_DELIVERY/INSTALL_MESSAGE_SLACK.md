# Slack install message — copy/paste

Replace `[@Name](slack-link)` and the date/time bits, attach `amazon-comp-suggestions.skill`, and send.

---

Hey [@Name](https://listenfirst.slack.com/team/USER_ID_HERE), here are the steps to install and run the new comp-suggestions skill on your system. Should take about 5 minutes end to end.

## Step-by-step install

### Option A — Cowork (Claude desktop app)

1. Open the Claude desktop app.
2. Save `amazon-comp-suggestions.skill` somewhere on your computer (e.g. the Downloads folder).
3. Drag the `.skill` file into the Cowork chat — Claude will detect it and show a **Save skill** install button.
   * Alternatively, attach it via the paperclip / upload button in chat.
4. Click **Save skill**. The skill installs into your local Cowork sessions directory.
5. Verify by typing `/list_skills` (or asking *"which skills do I have installed?"*). `amazon-comp-suggestions` should appear in the list.
6. Try it: type *"Amazon wants comps for [any title]"*. Claude should activate the skill and start asking the 5-7 intake questions.

### Option B — Claude.ai web app

1. Sign in at https://claude.ai.
2. Open **Settings → Capabilities → Skills** (path may vary by plan tier; look for "Skills" or "Custom Skills" in the settings sidebar).
3. Click **Upload a skill** (or **Add skill**) and select `amazon-comp-suggestions.skill`.
   * If the upload rejects `.skill` files, use `amazon-comp-suggestions.zip` instead — same content, different extension.
4. Wait for the upload to complete. The skill name and description should appear in your skills list.
5. Toggle the skill **on** for the chats / projects you want it active in.
6. Test the same way as Cowork: type *"Amazon wants comps for [any title]"*.

> If the upload UI is greyed out, your Claude.ai workspace owner needs to enable custom skills under **Admin Settings → Capabilities**.

## Optional — TMDb API key for best results

The skill works out of the box using Claude's web-search fallback, but you'll get more accurate, faster results with a free TMDb API key (recommended):

1. Sign up free at https://www.themoviedb.org/signup (~30 seconds).
2. Get your key at https://www.themoviedb.org/settings/api (~5 minute approval).
3. In a Claude conversation, paste: *"Save my TMDb API key to the amazon-comp-suggestions skill: \<your-key\>"*

That's it — Claude saves it to the skill's config and uses it from then on. Without a key, the skill falls back to web search and flags any results it can't fully verify. Either way works.

## Trigger phrases that activate the skill

* *"Amazon wants comps for [title]"*
* *"comps for [title]"* / *"draft a comp message for [title]"*
* *"suggest comparable titles for [title]"*
* *"what should I send Amazon for [title]"*

## After Amazon responds (days later)

Come back to Claude and say:

* *"log feedback for [title]"* — Claude finds your session and records what Amazon said

This is how we build the dataset to tune the rules over time. Worth doing on every request.

## If you hit a snag

DM me on Slack or ping me here — happy to screen-share for 5 min if anything's confusing. The skill is internal-only so any feedback / weird behavior / "this rule doesn't make sense" notes are welcome.

🚀
