---
name: Skill registry
description: Every skill an agent writes or fetches records where it came from, so the owner can see it, trust it and reuse it in another realm.
runs: reads
why: ARMADA reads these records to fill the Catalogue. It ships with the app and is given to every agent automatically, because a register with gaps in it is not a register.
---

# Skill registry

A skill that exists only in one agent's folder, with nothing saying where it came from, is
invisible to the owner and unusable anywhere else. Whenever you **create** a skill or **fetch one
from somewhere else**, write a record beside it. It takes one file.

## The record

In the skill's own folder — next to its `SKILL.md`, not in a list somewhere else — write
`armada.json`:

    {
      "origin": "authored",              // "authored" if you wrote it, "installed" if you fetched it
      "source": "",                      // where it came from: a URL, a repo, a package name. Empty when authored.
      "by": "<your-agent-id>",
      "at": "<ISO-8601 timestamp>",
      "why": "one line: what this skill is for and who asked for it"
    }

It lives in the folder so it travels with the skill: copied to another realm, exported, or moved,
the record goes too, and there is no central index to fall out of step with the disk.

`origin` has exactly two values and they are not interchangeable:

* **authored** — you wrote the instructions. Nothing was downloaded.
* **installed** — the content came from outside this machine, however small the edit you made
  afterwards. A skill you fetched and then adjusted is still installed.

## Getting it right matters more than filling it in

The owner reads `origin` to decide how much to trust the skill, and ARMADA files it in the
Catalogue on that basis. Recording something you downloaded as "authored" removes the one signal
that would have prompted a review.

* Put the real source in `source`. "GitHub" is not a source; the URL you fetched is.
* If you did not fetch it and did not write it — you found it already there — write no record at
  all. A missing record is read as "nobody has said", which is true. An invented one is not.
* Never edit or remove another agent's record to make a skill look better vetted. If you think a
  record is wrong, say so to the owner rather than correcting it yourself.

## What you are not being asked to do

You are not being asked to vet the skill, to run it, or to judge whether the owner should keep it.
Record what happened. The owner decides what to do about it, and no skill reaches another agent
until they turn it on and grant it.
