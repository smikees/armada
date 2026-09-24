# When something goes wrong

The problems people actually run into, newest lessons first. If yours isn't here, the logs are in
`%USERPROFILE%\.armada\logs\` — `armada.log` for the app, `scheduler.log` for scheduled jobs.

## Every agent answers "Failed to authenticate"

Claude Code's sign-in has lapsed. A bar at the top of the app offers **Sign in**, which opens
Claude's own sign-in window; finish it in your browser and carry on. ARMADA never handles the
password.

## My scheduled jobs stopped running

- **Is there a banner on the Jobs page?** It says why the realm is paused — see
  [Jobs → Paused jobs](jobs.md#paused-jobs).
- **Is the job switched on?**
- **Is the scheduler running?** It's a separate background process, so jobs run with the window
  closed. Opening ARMADA starts it if it isn't running, and if it stops, a yellow bar under the
  menu says so, with a **Start it** button. If the bar comes back straight after you click it,
  `scheduler.log` (above) says why.
- **Open the job** — its last run shows the error.

## A job says it ran, but I can't find what it made

Open the thread the job ran in (the job's page links it). The agent says where it wrote files;
**Artefacts** lists them. Agents are asked to write to the realm's `shared` folder.

## The usage bars in the header disappeared or look old

They come from your Claude sign-in. When the sign-in token expires, ARMADA shows the last reading
and its age rather than nothing; a background job keeps the sign-in fresh. If the bars stay stale
for a day, sign in again (above).

## I added a realm from another computer and nothing runs

Working as intended: its jobs are paused until you've reviewed them on the Jobs page. If the
banner says the **workspace** is missing, point the realm at the right folder in
Settings → Realm.

## Telegram doesn't answer

- Settings → App → Telegram: is it **linked**, and to *your* name?
- Only a one-to-one chat with the bot works. A group isn't linked.
- Answers come from the scheduler process, so it must be running.

## Dark mode text is hard to read

Fixed in v0.99.41–42. Update to the latest version (Settings → App → Check for updates).

## Reporting a problem

Click the **Report an issue** icon beside the settings gear (top right, on every page). Say what
happened; add your email if you'd like a reply. Before anything is sent you see the **whole report**
exactly as it will go: your words, the page you were on, ARMADA's version, your Windows version, and —
if you leave the box ticked — the last lines of ARMADA's logs, with keys, tokens, email addresses and
your Windows user name removed. Then **Send report**. It goes to the ARMADA team at
armada@stamih.com.

If it can't be sent (no connection, say), the report is saved in `%USERPROFILE%\.armada\reports\`
and the dialog tells you where — email it to armada@stamih.com yourself.
