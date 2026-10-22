# Creating a Skill

## Purpose

A skill lets a future agent do a task you know, without you supervising it. The
agent is competent but knows nothing about your task until the skill tells it.
A well-built skill closes that gap: it gives the agent the purpose, the
deliverable, the methodology, and the detail it needs, each in the right place,
so it can carry the work to completion and deliver what you want. What belongs
in the skill is what the agent cannot derive on its own: your definition of
done, your preferences, and where it must ask rather than guess.

## Deliverable

A finished skill is a folder:

```
skill-name/
├── SKILL.md      # purpose, deliverable, methodology, references
├── references/   # steps, tests, rules, guides (and any records database)
└── scripts/      # tools (static input-to-output machines)
```

## Methodology

Author the three parts in order, then test.

1. Align. Confirm what the skill should do, when it should trigger, and what its
   output looks like. Ask for edge cases, example files, and success criteria.
   Also ask where a future agent must come back to you instead of guessing; the
   judgments only you can make are part of the skill.
   **First check for overlap.** Search the skill set (catalog skill, sibling skill
   folders) for an existing skill covering the same ground. If the request
   duplicates or extends one, say so and confirm merge-versus-new with the user
   before writing anything. Users do not always know their own inventory.
2. Write the briefing (`SKILL.md`): the purpose, the deliverable, and the
   methodology. If you cannot state these clearly, you do not understand the task
   well enough to automate it.
3. Write the detail (`references/`): the steps and tests, and any rules or guides.
4. Write the tools (`scripts/`): anything that is a fixed input-to-output machine.
   See `creating-script.md`.
5. Test the tools and check against the checks below.

## Structure

The three parts answer three questions: what defines the work, what detail it
needs, and what it computes. Each is written and read at a different time, so the
always-loaded briefing stays small and the rarely-needed detail stays available.

### SKILL.md: the briefing

The agent reads this whole file at the start of a session. It is the only part
always in front of the agent, so it carries only what defines the work.

The file starts with YAML frontmatter. Fill it in as follows:

- **name**: the skill identifier.
- **description**: when to trigger and what the skill does. This is the primary
  triggering mechanism: include both what the skill does and the specific contexts
  for when to use it. All "when to use" information goes here, not in the body.
  Write it slightly "pushy" to counteract undertriggering. Instead of "how to build
  dashboards", write "how to build simple fast dashboards to display internal data;
  use whenever the user mentions dashboards, data visualization, internal metrics,
  or wants to display company data, even if they do not say 'dashboard'."
- **compatibility**: required tools or dependencies (optional, rarely needed).

The `description` value is a YAML plain scalar. Never put `": "` (colon + space)
inside it. A plain scalar containing `": "` parses as a nested mapping and the
frontmatter fails with `mapping values are not allowed in this context`.

```yaml
# broken — the colon after "tools" starts a new key
description: Umbrella for four independent utility tools: transcribe audio, …

# fixed — use a dash instead
description: Umbrella for four independent utility tools — transcribe audio, …
# or wrap the whole value in double quotes (a quoted scalar is safe)
description: "Umbrella for four independent utility tools: transcribe audio, …"
```

The body then contains:

- **Purpose**: why the task exists and what it achieves.
- **Deliverable**: the exact output, in the form the user can use, and the
  checks that define when it is done.
- **Methodology**: how to approach the work, as an ordered loop.
- **References**: a brief list pointing to the reference files, so the agent
  knows where to find the detail when it needs it.

Steps and tests do not belong here. SKILL.md holds what stays true across every
session; it points to the rest rather than carrying it. What changes with the
case (steps, tests, edge-case playbooks) lives in `references/`.

### references/: the rules and guides

Optional guidance the agent opens only when it needs it. A reference is optional
in that not every session requires all of them, and it is a rule or guide in that
once it is required, it must be followed completely. This is where steps, tests,
code of practice, ISO standards, calculation steps or spreadsheets, and letter
templates live.

A skill that stores and searches a body of records (document text, letters,
sections of documents) keeps its records database in this folder too. Initialise
it with the `basic-ops` skill's `init_db` tool and read and write it with
`access_db`; the caller chooses the file name (e.g.
`references/uch_letter_record.db`).

### scripts/: the tools

Fixed input-to-output machines. They hold no knowledge, only action, and they
hide whatever harness they run on. Write a tool only when the work is
deterministic, repetitive, or safer in code. See `creating-script.md`.

## Testing Scripts

After the draft is written, test the bundled scripts with real inputs. Prefer
real user data over synthetic examples; they surface issues synthetic tests miss.

Ask the user for sample files or data. Guide them through what to test:

- **Happy path**: typical, expected input.
- **Edge case**: boundary values, empty inputs, single-item cases.
- **Error path**: malformed input, wrong file type, missing required fields.
- **Scale**: unusually large input, many items.
- **Locale/encoding**: different character sets, timezones, number formats.

As the user tests, watch for unexpected errors, wrong outputs, slow performance,
and confusing error messages. Fix issues immediately and ask the user to re-test.

## Checks

Before shipping the skill, confirm:

- The purpose, deliverable, and methodology are all present and unambiguous.
- The frontmatter name and description are filled in, and the description carries
  the trigger in the user's words.
- Rules the user asks to be written into a skill are rephrased in the agent's own
  compressed words; only the description triggers stay in the user's words.
- The References section lists the reference files and points to them.
- Steps and tests live in `references/`, not in SKILL.md.
- The skill carries what a future agent cannot derive on its own: the user's
  definition of done, their preferences, and where the agent must ask instead of
  guess.
- Each tool is callable on its own and returns clean output.
- The skill loads through the app's `SkillManager` (`src/skill/manager.py`) with
  no validation errors. This is what catches malformed frontmatter, including a
  `": "` inside an unquoted `description` scalar (`mapping values are not
  allowed in this context`).
