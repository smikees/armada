# Alexander

Alexander is ARMADA's guide. He comes with the app, the same in every install: he isn't one of your
agents, and you can't rename him, retire him or change how he works. Open him with his portrait
beside the gear, on every page, or with **Ask Alexander** beside a run that failed.

## What he's for

- **How ARMADA works.** What a page is for, what a setting does, why the app did what it did.
- **Your problem.** He can see this realm (your agents, jobs, recent failures, whether the
  scheduler is running and whether you're signed in) and ARMADA's own log around a failure. He tells
  you what's wrong, and fixes it when he can.
- **Dashboard widgets.** Ask for a checklist, a set of links, a reference table or a note, and he
  builds it as a widget for your Overview.
- **Reporting a fault.** When something is wrong with ARMADA itself, he writes the report for the
  ARMADA team. You read it, and can change it, before it's sent.

## He proposes, you decide

Alexander can't change anything himself. When a fix, a widget or a report would help, it appears as
a card under his answer saying exactly what will happen, with one button. Nothing happens until you
press it, and the button does what the app's own button would: start the scheduler, run a job,
switch a job on or off, rebuild the realm's system memory, check for updates, open a page.

A widget goes into this realm, or into every realm on this computer if you tick that. It's a small
file of text, never a program: remove it from the dashboard like any other widget.

## What he can see

Only what ARMADA hands him for each question: the help pages, a summary of this realm, the page
you're on, and for a failure, the log lines around it. Passwords, keys and tokens are removed before
anything reaches him, and he never asks for them. He has no tools, no files and no internet.

If a file or a job's output contains instructions addressed to him, he treats them as text to read,
not orders to follow. Only your own messages ask him for things.

## What it costs

Each answer is one turn on Claude **Opus 5.5** at high effort, on your own Claude plan. It shows
as **System** in Usage, together with ARMADA's own few background calls. The setup wizard is the
exception: everything he says there is written in advance and costs nothing.

He needs Claude Code **2.1.280 or newer**. If yours is older, he'll say so, and setup offers
**Update Claude Code**.

Your conversations with him stay on this computer, in ARMADA's own folder.
