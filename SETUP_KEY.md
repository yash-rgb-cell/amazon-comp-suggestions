# Setting up your TMDb API key (one-time, ~5 minutes)

This skill needs a free key from The Movie Database (TMDb) to look up film and TV metadata. Here's how to set it up — no programming required.

## Step 1 — Get a free TMDb key

1. Go to https://www.themoviedb.org/signup and create a free account (~30 seconds).
2. Verify your email.
3. Once logged in, go to https://www.themoviedb.org/settings/api
4. Click **Request an API Key** → choose **Developer** → fill in the short form:
   - Application Name: `LF Comp Suggestions`
   - Application URL: `https://listenfirstmedia.com` (or any LF URL)
   - Application Summary: `Internal tool for drafting comp-title suggestions`
5. Submit. You'll see your key (32-character string starting with letters/numbers) appear immediately on the same page. Copy it.

## Step 2 — Tell Claude the key (easiest, no PowerShell)

In a Cowork conversation, just say:

> Save my TMDb API key to the amazon-comp-suggestions skill: `<paste-your-key-here>`

Claude will create a `.env` file in the skill folder and the skill will pick it up automatically. You only do this once per machine.

## Alternative — Windows environment variable (technical)

If you'd rather set a system-wide environment variable:

1. Open PowerShell (right-click Start → Windows PowerShell).
2. Run:
   ```powershell
   setx TMDB_API_KEY "your-32-character-key-here"
   ```
3. Quit and reopen Cowork so it sees the new variable.

The skill checks both places (env var first, then `.env` file), so use whichever you prefer.

## Verify it worked

Start a fresh Cowork conversation and say:

> Test the TMDb connection for amazon-comp-suggestions

You should see Claude return search results for a sample title. If you see an error mentioning `TMDB_API_KEY`, the key didn't get saved — try Step 2 again.

## Sharing with the team

The key is per-person. Each LF analyst should follow Steps 1-2 on their own machine with their own key. (You CAN share one key across the team if you prefer — TMDb's free tier handles way more traffic than 10 comp requests a month — but separate keys make usage attributable.)
