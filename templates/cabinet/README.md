# Cabinet — starter agents

Eight suggested agents a new owner can pick from at setup. They are **starting points, not a
prescription**: take one, take three, take all eight, rename them, or rewrite them entirely. A realm
with two agents the owner actually uses is better than eight they inherited.

Each agent is modelled on a historical figure, which is doing real work rather than decoration. A
named character gives an agent a specific way of deciding rather than a generic one — and, more
usefully, it gives it a set of documented failures to be prohibited by name. The pattern in every
`soul.md` is the same:

- **Where the character comes from** — who this was, in a paragraph, and why it matters here.
- **Traits** — the behaviours the owner is getting.
- **What you are not — explicitly forbidden** — the figure's own faults, banned individually. This
  is the half that does the most work. An agent told to be like Jobs becomes abrasive; an agent
  told which of his behaviours are prohibited does not.

All eight figures are long dead and their lives are a matter of public record.

## The set

| Agent | Ministry | After | Chosen for |
|---|---|---|---|
| Marcus | The Hand (coordinator) | Marcus Agrippa | Competence without ambition for the throne |
| Ricardo | Strategy | David Ricardo | Second-level thinking, 200 years early |
| Graham | Finance | Benjamin Graham | Margin of safety; Mr Market |
| Wedgwood | Development | Josiah Wedgwood | Polish, customer judgement, operations |
| Aristotle | Education | Aristotle of Stagira | Go and look; precision fitted to the subject |
| Galen | Health | Galen of Pergamon | Measure before you conclude; prevention |
| Palladio | Estate | Andrea Palladio | Measure it yourself; the ground before the house |
| Ibn Battuta | Travel | Ibn Battuta | Verify before you recommend; substance over spectacle |

Only the Hand is a coordinator. Without one, no agent can reach every capability — which is the
intended default.

## The three documents

- **`soul.md`** — who the agent is. Character, traits, prohibitions. Rarely changes.
- **`mandate.md`** — what the agent is for. Mission, what the role covers, standing limits. Changes
  when the owner's situation does.
- **`tenets.md`** — how the agent decides when two good things conflict. Ordered, so a lower number
  wins a collision. Not a summary of the Covenant: the Covenant is absolute and settles nothing
  because nothing is in tension with it. Tenets are for the hard calls it leaves open.

## `covenant.md`

Realm-level, binding on every agent, identical for all of them: whose they are, honesty before
comfort, no irreversible actions, what they value. Copy it to the realm root as `tenets.md`. Every
agent's tenets file refers to it, so it is not optional if the agents are used as written.

## Ownership — the rule that matters

**These files ship with ARMADA and are replaced whenever the app updates. The copies in a realm
belong to the owner and are never touched again.**

At setup the wizard copies from here into the new realm — `covenant.md` becomes the realm's
`tenets.md`, and each chosen agent folder is copied whole. From that moment the two have nothing to
do with each other. An app update may change what a *future* realm gets; it never overwrites,
merges into, or reverts anything in an existing one. Where a newer template version exists, it is
offered and explained, never applied.

That asymmetry is the point. An owner who rewrites Galen's tenets after a month of use has produced
something better than the template for their realm, and an update that quietly restored our version
would be destroying their work.

`template.json` carries the version, the copy map and the one-line summaries the setup screen
shows. It is the file a wizard reads; this README is for humans.

## Using these by hand

1. Copy `covenant.md` to the realm root as `tenets.md` and read it — it is the shortest document
   here and the one that matters most.
2. Copy the agent folders you want into the realm's `agents/`.
3. Edit each `mandate.md`. The souls and tenets are close to portable; the mandates are
   deliberately generic and are the weakest part of any template, because what a minister is *for*
   depends entirely on the owner. An agent whose mandate still says "the owner's goals" has not
   been set up yet.

The text says "the owner" throughout. Replacing that with a name, and the generic missions with
real ones, is the whole of the work.
