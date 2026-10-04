# When something goes wrong

The problems people actually run into, newest lessons first. If yours isn't here, the logs are in
`%USERPROFILE%\.armada\logs\` — `armada.log` for the app, `scheduler.log` for scheduled jobs.

## Every agent answers "Failed to authenticate"

Check the engine selected for the affected agent in **Settings → App → Engines**.
If its login has expired, choose **Sign in** and finish the provider's browser flow.
An unavailable status probe is not proof that you are signed out. Other connected
engines remain usable; connector authentication is separate from engine login.

## My scheduled jobs stopped running

- **Is there a banner on the Jobs page?** It says why the realm is paused — see
  [Jobs → Paused jobs](jobs.md#paused-jobs).
- **Is the job switched on?**
- **Is the scheduler running?** Jobs continue while ARMADA is open or hidden in the tray;
  full quit stops the scheduler. Opening ARMADA starts it, and if it stops, a yellow bar under the
  menu says so, with a **Start it** button. If the bar comes back straight after you click it,
  `scheduler.log` (above) says why.
- **Open the job** — its last run shows the error.

## A job says it ran, but I can't find what it made

Open the thread the job ran in (the job's page links it). The agent says where it wrote files;
**Artefacts** lists them. Agents are asked to write to the realm's `shared` folder.

## The usage bars in the header disappeared or look old

Each provider reports its own limits. ARMADA caches readings for five minutes and
keeps the last reading during refresh. Hover the bar for its age or error. Some
accounts do not report every window. Check that provider's engine status before
reconnecting; a missing number does not by itself mean a login problem.

## An update says it is waiting

The banner identifies active work across all realms, scheduler shutdown, or an
activity-record error. An idle scheduler does not count as a running job. New tasks
pause while an update is requested. Keep active work running until it finishes.
If an older version has multiple windows open, finish the work, fully quit ARMADA
from the tray and reopen it once. Current versions prevent duplicate desktop instances.

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

Ask [Alexander](alexander.md) first (his portrait beside the settings gear, top right, on every
page): often he can fix it, and when he can't he writes the report for you. To write it yourself,
open him and choose **Report an issue yourself** at the bottom. Say what happened; add your email if
you'd like a reply. Before anything is sent you see the **whole report**
exactly as it will go: your words, the page you were on, ARMADA's version, your Windows version, and —
if you leave the box ticked — the last lines of ARMADA's logs, with keys, tokens, email addresses and
your Windows user name removed. Then **Send report**. It goes to the ARMADA team at
armada@stamih.com.

If it can't be sent (no connection, say), the report is saved in `%USERPROFILE%\.armada\reports\`
and the dialog tells you where — email it to armada@stamih.com yourself.
