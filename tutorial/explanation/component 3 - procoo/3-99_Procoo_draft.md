# Procoo user tutorial

## 0. Before you start

### 0.1 What Procoo does

Procoo runs an LLM agent that can act on your machine. You send a message; the model either answers or calls one of the scripts you have made available, reads what comes back, and keeps going until it can answer. Several conversations can run at once, each with its own model, skills and tools.

A skill is a folder of instructions with optional Python scripts. Select it for a chat and the instructions join the system prompt while the scripts become tools the model may call. Writing one is Appendix A.

### 0.2 Words used throughout

| Word | Meaning |
|---|---|
| session | a named group of chats with a saved panel layout; the title bar switches between sessions |
| chat | one conversation, stored as one file, with its own skills, tool modes and model |
| panel | one column of the chat page; up to four fit |
| tab | one chat inside a panel |
| skill | a folder under `capabilities/skills/` containing `SKILL.md` and optionally `scripts/` |
| activated skill | instructions and tools loaded into the system prompt on every turn |
| tool | one `.py` file under a skill's `scripts/`, callable by the model |
| tool mode | allow, ask or block: run without asking, wait for approval, refuse |
| preset | a saved skill and tool selection you can load into a chat |
| automation | an `AUTOMATION.py` program run on a cron schedule or an incoming HTTP event |
| notification | the result card an automation leaves behind |

### 0.3 Launching

```
uv run python -m src.app
```

Run that from the `procooQt` directory, or double-click `start_procoo_qt.bat`, which activates the virtual environment and runs the same module. Procoo reads `config/config.yaml`, scans the skills and automations folders, and opens the `Default` session.

### 0.4 What has to exist first

The config needs an `llm` list, and exactly one entry in it must have `default: true` with `model_name`, `api_key` and `api_base`. Zero defaults or two of them stop the app at startup with a config error, before any window appears. `config/config_template.yaml` shows the shape.

`capabilities/skills/` and `capabilities/automations/` have to exist. `storage/` Procoo creates itself. Relative paths in the config resolve against the `procooQt` directory, which is why the defaults read `../capabilities` and `./storage`.

### 0.5 The window

The app is one frameless window. The title bar sits across the top and four pages sit under it: Chat, Editor, Automation and Notification. The editor and the notification history are separate windows that open when you ask for them.

The Chat page is a split workspace. Every panel in it has a tab bar, a transcript, a token bar, an input row and a skill dock.

## 1. Chat panel

### 1.1 Parts of the chat panel

#### 1.1.1 Title bar

Procoo has no system title bar. The app draws its own strip across the top, and that strip is where sessions, pages and alerts live. The window still drags by it, resizes from the edges and snaps to half a screen.

Clicking the session name opens the list of sessions. Rows switch sessions. The `+` row at the bottom creates one, and the same list is the only place to delete a session, which takes its chats with it. `+ Win` creates a session and opens it in a window of its own; asking for a session that is already open raises that window.

Chat, Editor, Automation and Notification are the four pages, and the tabs across the strip choose between them. The app opens on Chat.

Badges beside the Notification tab count unread items by kind, grey for logs, amber for info, red for errors, and a kind with nothing unread gets no badge at all.

Every open window reads the same session list, so a session made in one appears in the rest.

#### 1.1.2 Split workspace

Up to four panels share the Chat page, side by side at equal width.

They are independent. Each has its own tabs, transcript, token bar and skill dock, which is what lets one panel run a coding skill on a local model while another talks to a hosted model with no tools at all. A panel can sit on an approval prompt for ten minutes while you work in the next one.

Panels fill four fixed positions. Moving one changes which positions are in use and where they sit; conversations in the panels you did not move are left alone.

Procoo stores the arrangement with the session: each session remembers its own, and a restart brings it back.

At least one panel is always on screen. Delete the last tab of a panel and the panel goes with it, unless it is the only one.

#### 1.1.3 Tab bar

A tab is a chat: one conversation, its own skill configuration, its own model. A panel can hold a dozen of them and shows one at a time.

The dot on each tab tells you what the chat is doing without opening it.

| Dot | Status | Meaning |
|---|---|---|
| grey | `EMPTY` | created, no messages yet |
| blue, blinking | `RUNNING` | generating |
| amber, blinking | `WAITING` | generating, paused for a tool approval |
| green | `FINISHED` | has messages, idle |
| red | `ERROR` | last turn failed or you stopped it |

`+` opens another chat in the panel and copies the skills, tool modes and model of the chat you are on. `×` deletes the chat and its file, and the file does not come back.

Drag a tab onto the left or right half of a panel to split the workspace and put the chat there, or onto another panel's tab bar to move it into that panel.

Dots blink even when the window is in the background, which is how you notice a long run finishing or stopping for approval while you were reading something else.

#### 1.1.4 Chat window

Each piece of a turn becomes a card, in the order it happened, and the card type says which part of the work it holds.

| Card | What it holds |
|---|---|
| User | your message, verbatim |
| Waiting | a headerless scanner, shown while a turn runs but has produced nothing yet |
| Thinking | the model's reasoning, streamed as plain text |
| Response | the answer, rendered as Markdown while it streams, including tables, links and `$…$` maths |
| Tool call | the tool name, its permission mode, and the arguments as YAML |
| Tool result | the tool's output, with the tool name in the subtitle; failures look the same, as text |
| Context banner | what the chat was given, neutral at the start and orange for an update after you changed skills |

Headers show an icon, a title, the token count for that card (`n tk`) and a collapse arrow. Hovering one also reveals two actions, both disabled while a generation runs. The trash icon deletes the turn that card belongs to. The reload icon, on user cards, regenerates from that message and throws away everything after it.

Long transcripts stay quick because only the last twelve cards are built expanded. Anything older sits there as a header until you click it.

The view follows the newest card while auto-scroll is on. Scroll up and it stops following; return to the bottom and it starts again. The toggle is in the input row (1.1.6).

#### 1.1.5 Token and config bar

Five values sit above the input row and describe the active chat.

Input tokens is the size of what the next turn will send: system prompt, loaded skills, and the whole conversation. Output tokens sums what the chat has produced over all its turns. Activated counts loaded skills, Allow, Ask and Block count tools in each permission mode, and the model name closes the row.

The numbers come from the model provider, which reports real usage. They change on every round-trip; a turn that calls three tools updates them three or four times. After a restart they are restored from the values last saved with the chat.

Watch the input count on a long conversation. It climbs toward the model's context window, and once the configured limit is passed Procoo summarises the chat and continues in a new one (1.2.10).

The tool counts tell you what a turn will run into. Anything in Block is refused without asking, and anything in Ask stops the turn at the approval bar (1.1.7).

#### 1.1.6 Input row

Type in the box at the bottom of the panel and press Enter, or click Send. While a chat generates, that button becomes Stop.

Two controls appear when the pointer enters the row: a checkbox that locks Enter, for writing a message across several lines without sending it early, and the auto-scroll toggle, on by default and faded out whenever auto-scroll is paused, so a paused view is not decorated with a button you are not using.

Stopping a turn leaves the partial transcript in place and marks the chat as stopped, which shows as a red dot on its tab.

#### 1.1.7 Approval bar

A tool set to Ask does not run by itself. When the model calls one, generation stops and a bar appears above the input row naming the tool and the arguments it wants to pass.

Approve runs the call and the turn continues. Deny skips it and tells the model that execution was denied, which usually gets you an answer built from what the model already had, or a second attempt by another route. Stop cancels the whole turn rather than deciding on that one call.

Only Ask raises the bar. Allow runs straight through, and Block refuses before the model sees anything.

Approvals belong to a single chat. A panel waiting on one blinks amber, so you can find it again after switching tabs.

#### 1.1.8 Skill dock

The right edge of each panel has a narrow rail. Clicking it expands a dock over the transcript, and the dock holds the skills and tools of the active chat.

It covers part of the panel while open. Drag its left edge to resize it, or click anywhere outside to close it; that click still reaches the transcript or the input, so closing the dock never swallows what you meant to do. Every panel has its own dock, which is why two panels can hold different configurations.

The search field filters the skill tree by name, opening the folders that match and hiding the ones that lead nowhere. `×` clears it and restores the folders you had collapsed.

Ticking a skill sends its instructions into the system prompt and registers its tools.

Tools sit under the skill that owns them, each with a mode: Allow runs the call, Ask raises the approval bar, Block refuses it. The model dropdown sets the model for this chat. The preset bar loads a saved selection as soon as you pick it, saves one under a name, or deletes one. Open Editor raises the editor window.

Every change applies to the active chat and is written into that chat's record as you make it.

#### 1.1.9 Toasts

Toasts are the small messages at the window edge that leave on their own: a preset saved, a file written, a skill that failed to load at startup. Each has a level (error, warning, info) and none of them is stored, so a toast you miss is gone. Results you are meant to act on arrive as notifications instead (3.1.3).

#### 1.1.10 Loading overlay

A chat you just switched to, or just dragged into a new panel, goes blank behind an opaque overlay while Procoo rebuilds it. The rebuild reads the stored conversation and re-renders its cards, which is slow enough on a long chat to be worth covering.

The overlay holds for at least a fifth of a second even when the rebuild finishes sooner, so a fast switch does not flash. Other panels keep working throughout, and when it lifts the view is pinned to the newest card.

### 1.2 Navigating the chat panel

#### 1.2.1 Start a chat

Open the app and you land in the `Default` session. If the panel has no tabs, click `+` in its tab bar; an empty panel has nothing to type into.

Type in the input row and press Enter. Cards arrive as the turn proceeds: thinking, then a tool call, then its result, then the response, depending on what the model decides to do.

Press Stop to cancel. The chat ends in the stopped state, which the tab shows as a red dot.

#### 1.2.2 Add a chat

Click `+` in a panel's tab bar and the new chat opens there with the skills, tool modes and model of the chat you were on, since the next question usually belongs to the same job. The layout saves as the tab appears.

#### 1.2.3 Switch and delete a chat

Click a tab to open it. Clicking a tab in another panel changes that panel's active chat and leaves this one where it was.

`×` deletes the chat and its file. If it was the active chat, another chat in the workspace opens in its place, and if it was the last tab in its panel the panel closes, unless it is the only panel left.

#### 1.2.4 Set skills and tools

Open the dock, then search for a skill or open the folders. Tick a skill to load its instructions; ticking a skill that has scripts also brings its tools into the tool list. Set each tool to Allow, Ask or Block, and close the dock. The counts in the token bar change as you go.

Ask is the useful mode while you are learning what a skill does, because it shows you every call before it runs. Move a tool to Allow once you trust it.

Changes reach the chat immediately. A chat that has already run gets the new instructions as a system message before its next turn, and the transcript shows an orange Context banner listing what was added and which modes changed. A chat that has never run picks the configuration up when it first runs.

Unchecking a skill cannot remove instructions that are already in the conversation, so Procoo warns you when you do it. The agent keeps the old text in its history; only a new chat starts clean.

To reuse a setup, type a name in the preset field and save it. Picking it from the dropdown later applies the whole selection at once.

#### 1.2.5 Set the model

The model dropdown in the dock lists every model in the config and marks the one this chat uses. Picking another changes the chat from its next turn, without reloading anything or losing the transcript.

The choice is stored with the chat. A new chat copies the model of the chat it came from, and a chat with no model of its own falls back to the `default: true` entry.

#### 1.2.6 Split and move panels

Drag a tab and the workspace shows where it will land.

Drop it on the left or right half of a panel to split that panel and put the chat on that side. Drop it on another panel's tab bar to move the chat into that panel, which closes the source panel if it ends up empty.

Four panels is the limit. At four, the drop hints stop appearing on the halves, and dropping onto a tab bar still works.

Conversations survive the move. Only the panels whose active chat actually changed rebuild, behind the loading overlay, while the rest keep their scroll position.

#### 1.2.7 Work with sessions

The `+` row in the session list asks for a name. A session created with `+ Win` arrives with one empty chat, so its dock is usable straight away; after creating one from the list, check the panel and click `+` in the tab bar if it has no tabs.

Switching sessions swaps the whole workspace, since each session keeps its own panels, tabs and layout. Deleting a session deletes its chats too, and Procoo falls back to `Default` if you delete the one you are in. With no session left, the next start creates `Default` again.

Because every window reads the same list, a session created in one window shows up in the others without a refresh.

#### 1.2.8 Work with windows

`+ Win` creates a session and opens it in a second window, with its own panels, tabs and docks, so two sessions can sit side by side.

Asking for a session that is already open focuses its window instead of making a duplicate. Closing a secondary window leaves the app running; closing the primary one quits it, so keep the session you are working in wherever you want it.

#### 1.2.9 Work with a running turn

A generation runs while you do other things. The tab dot keeps blinking and the card actions stay disabled until the turn ends.

Stop cancels the turn and keeps the partial transcript. The reload icon on a user card regenerates from that message and discards everything after it. The trash icon deletes the turn its card belongs to. Both are ways to redo a step without starting a new chat.

#### 1.2.10 Long chats

Every chat has a size limit and a token limit from `limits` in the config. When either is crossed, Procoo asks the model to summarise the conversation and starts a new chat from that summary, in the same panel, with the work so far condensed into its opening context.

A limit of `0` or a negative number disables it. The committed config disables the token limit and keeps the byte limit at 70 MB, which is a very long conversation.

#### 1.2.11 Sessions from outside Procoo

A local control server on port 12841 lets another program create, open and delete sessions. The Obsidian plugin uses it: a marked span in a note stores a session id, and the context menu can open that session or start one from the selected text.

Session ids are stable, so renaming a session does not break a link from a note. The server binds to `127.0.0.1` and accepts the keys in `control_server.api_keys`, falling back to `auth.api_keys`; an empty list means no authentication.

## 2. Editor panel

### 2.1 Parts of the editor panel

#### 2.1.1 Editor window

The editor is a separate window with a system title bar of its own, holding a file tree, a code pane and a chat panel. Procoo creates it the first time you ask and keeps it afterwards: closing it hides the window, and the next request brings it back with the same file open.

Three things open it. Open Editor in the skill dock, Debug on an error notification, and Edit on an automation card. The last two also load the file they refer to.

#### 2.1.2 File tree

The tree on the left is rooted at the capabilities directory, so it holds both skills and automations. Folders expand and collapse, and clicking a file opens it.

A search field filters by name. A matching folder keeps its whole subtree, a folder with a matching descendant shows only the chain leading to it, and every folder renders expanded while a term is active. Clearing the field brings back the collapse state you had.

#### 2.1.3 Code pane

Files open read-only, highlighted by file extension, in a monospaced font. A plain text file opens without highlighting.

Text can be selected and copied, and the pane tracks whether the buffer differs from what is on disk. That difference is what the action buttons act on.

#### 2.1.4 Edit, save, cancel and reload

Four buttons sit above the code pane. Edit unlocks the buffer. Save writes it to disk, reports success with a toast and returns to read-only. Cancel throws the buffer away and reloads the file. Reload does the same thing, for when you only want the file reread.

Opening a different file while editing is refused with a warning. Save or cancel first.

#### 2.1.5 Conflict dialog

Files change on disk while a window sits open. If the open file is edited elsewhere, or deleted, Procoo asks before anything is overwritten.

Keeping the buffer means the editor's text wins. For a deleted file that writes the file back; for a modified one it keeps your text and stops asking until the file changes again. Taking the disk state means the file wins: a modified file is reloaded, and a deleted one closes in the editor.

A dialog you leave pending comes back when you return to the window, so switching away does not lose it.

#### 2.1.6 Editor chat

The right side of the editor window is a full chat: the same cards, the same token bar, the same input row, and a dock of its own.

It differs from a panel chat in two ways. There is no approval bar, because the skills and tools it copies from your active chat are all forced to Allow, which is worth knowing before you hand it an unrestricted tool set. And it knows which file you have open: when you send a message after opening or changing a file, Procoo attaches an editor context block with the path and up to 8000 characters of the file, so you can ask about the code without pasting it. The block refreshes when the file or its content changes, and is not resent while neither has.

The chat lives under a private session name and never appears in the session list or the workspace panels.

### 2.2 Navigating the editor panel

#### 2.2.1 Open a file

Click it in the tree, or arrive from elsewhere: Debug on an error notification and Edit on an automation card both open the editor with that automation's `AUTOMATION.py` loaded. The tree rebuilds as files change on disk, so a file an agent created appears without a restart.

#### 2.2.2 Edit and save a file

Click Edit, change the text, then Save to write it or Cancel to discard. Reload re-reads the file from disk and is the way out when you are unsure what the buffer holds; Cancel and Reload both leave edit mode.

#### 2.2.3 Keep the tree in step with disk

Procoo watches the capabilities folder. While the editor window is visible, a change on disk rebuilds the tree and re-checks the open file, and a file that changed underneath you raises the conflict dialog instead of reloading silently.

The watcher ignores the window while it is hidden. Showing it again runs a full re-sync, and a conflict that was pending before you closed the window comes back as a dialog.

#### 2.2.4 Edit files with the agent

Open the file, then ask in the editor chat. The context block carries the path and the file body, so the agent can read and rewrite code without you pasting it. The block is capped at 8000 characters, so for a longer file name the function or line range you mean, or ask the agent to read the file with a tool.

Because every tool is set to Allow here, a request to change a file can be carried out without a prompt. The editor's Save button plays no part in that: when the agent writes the open file through a tool, the watcher notices and asks whether to keep the buffer or take the disk state. Taking the disk state shows you the agent's version.

#### 2.2.5 Clear the editor chat

Clear stops any generation, drops the live agent, empties the transcript and rewrites the chat record with a fresh skill configuration taken from your active chat. The file you have open is untouched.

## 3. Automation and notification

### 3.1 Parts of the automation and notification surfaces

#### 3.1.1 Automation page

The Automation tab lists everything Procoo found under `capabilities/automations/`, one card each, with a search field above the list. The list rebuilds when files change, so a new automation appears without a restart.

#### 3.1.2 Automation card

A card shows the name and description from the file's frontmatter, the activation type, and either the cron schedule or the event name it listens for.

When the frontmatter sets `start_date` or `end_date`, a Window row shows the range and whether it is pending, active or expired. Set neither date and the row disappears. Both are read from the file; nothing in the interface edits them.

The toggle enables or disables the automation. Run now starts it immediately, sweeping an indicator across the card while the button stays disabled, and Edit opens its `AUTOMATION.py` in the editor.

#### 3.1.3 Notification badges

Three badges beside the Notification tab, one per kind of unread item: grey for logs, amber for info, red for errors. Each shows a count and disappears at zero.

The colour is the summary. Grey means a run finished normally, amber means it finished and left something to read, red means it failed.

#### 3.1.4 Notification page

The page lists unread notifications, newest first. A card shows the task name, the message the automation returned, and when it ran; an error card adds the captured log.

Confirm acknowledges a card and removes it from the page. Debug appears on errors and opens the automation that produced them in the editor. View history switches to the history window.

#### 3.1.5 Notification history

The history window lists everything, read or not, with a search field at the top. Search matches the task name and the message, ignoring case.

Rows load twenty at a time and scrolling to the bottom fetches the next twenty. A search resets the list to its first page.

#### 3.1.6 Toasts and notifications

A toast is transient and reports something that needs no decision. A notification is stored, counted in the badges, and waits until you confirm it. Notifications are written to `storage/notifications.json`; toasts are never stored.

### 3.2 Navigating automations and notifications

#### 3.2.1 Where automations come from

An automation is a directory holding an `AUTOMATION.py`, anywhere under `capabilities/automations/`. Its identity is the path relative to that folder, so `reports/daily` is the automation in `capabilities/automations/reports/daily/`.

The file starts with YAML frontmatter and continues with Python. The frontmatter needs `name`, `description` and `activation`, plus `schedule` for a scheduled automation or `event` for an event-driven one. Optional keys add `activated_skills`, `start_date` and `end_date`.

The body must define `async def run(ctx)`. It returns a dict with a `status` of `log`, `info`, `error` or `silent` and a `message`, and may add `data`. Procoo redirects the script's output into the notification log and stops a run after 30 minutes.

A file missing a required field, or carrying a cron expression that does not parse, is skipped and reported at startup. A cosmetic problem such as an empty body loads the automation and raises a warning.

#### 3.2.2 Enable and disable an automation

Use the toggle on its card. The state lives in `storage/automations.json`, so it survives a restart and editing the file does not reset it. An automation with no stored state counts as enabled.

Disabling stops scheduled and event runs. Run now still works, which is how you test one you have switched off.

#### 3.2.3 Run one now

Click Run now. The card shows a sweeping indicator and disables the button until the run finishes, and the result becomes a notification. The run ignores the date window, so a pending automation can be tested before it is due.

#### 3.2.4 Scheduled runs

A scheduled automation fires at the times its five-field cron expression names. Procoo plans each run ahead of the wait, and a time that passes while the app is closed is skipped rather than replayed, so opening the app in the morning does not run the night's work again.

The date window applies here and nowhere else. Before `start_date` the automation does not fire, and after `end_date` Procoo disables it.

#### 3.2.5 Event-driven runs

An event automation fires when something posts to `POST /event/{name}` on the local event server, which listens on `127.0.0.1:12840` by default. The name is matched against the `event` field without regard to case, and every enabled automation with that name runs.

A JSON body reaches the script as `ctx.payload`. With `auth.api_keys` set in the config, the request must carry `Authorization: Bearer <key>` or `X-Api-Key`; an empty list turns authentication off.

The response says what ran. A 200 carries the results, a 400 means the body was not valid JSON, a 401 means the key was missing or wrong, and a 404 means no enabled automation answers to that event. `GET /health` answers without a key.

#### 3.2.6 Edit an automation

Click Edit on its card. The editor opens with `AUTOMATION.py` loaded, and saving it makes Procoo re-read the file: a changed schedule, event name or description shows on the card within a moment, and broken frontmatter turns the automation into a skipped one with a warning.

#### 3.2.7 Read and clear notifications

Open the Notification tab. Logs are acknowledged by that act alone and stay on the page, dimmed, until you close it. Info and error wait for Confirm, and errors also offer Debug.

Once a card is confirmed, or the page closes, it leaves the page and stays in history.

#### 3.2.8 Debug a failed run

Click Debug on an error card. The editor opens with that automation's source file loaded, which is where the log and the code meet.

#### 3.2.9 Search the history

Open View history and type in the search field. Matching runs on the task name and the message, so a partial word is usually enough. The list resets to the newest page on each search, and scrolling to the bottom loads older ones.

## Appendix A: writing a skill

### A.1 What the model can see

The model reads a list of messages. It cannot see your files, the folder names on disk, your earlier chats, or the fact that a script exists unless something puts that in front of it.

Before each turn, Procoo builds that list in a fixed order: the system prompt from the config, the instructions of every activated skill, the schemas of the available tools, and then the conversation. A skill works by adding text to that list and by adding tools whose results come back into it.

Two consequences follow, and they explain most of the advice below. Anything the agent needs to know must be in the list or reachable through a tool. And everything in an activated skill is sent again on every turn, so length costs money and dilutes attention.

### A.2 How the model chooses a tool

The model was trained to call tools by reading their name, their description and their parameter schema. It generalises to tools it has never seen from that text alone, which makes the description the part that decides whether your tool is used, used correctly, or used on the wrong task.

That is why a thin description fails while the code behind it is fine. The model has no way to infer that `run(path)` wants a relative path unless the description says so.

### A.3 Activated skills

An activated skill sends its full instructions and registers its tools. Choose activated for what every turn needs: the rules of the job, the conventions of the output, the tools that are always relevant.

A skill whose instructions you retype into every conversation belongs in activated.

### A.4 Writing the instructions

Write for a competent colleague who has the tool but not the background.

Say what finished work looks like. An agent that cannot tell when it is done keeps going, and a description of the goal on its own leaves the end open.

Spell out the constraints a model guesses wrong when left alone: units, formats, file paths, naming, what may be overwritten.

Give it a stopping rule. When to stop gathering and answer, and when to ask you rather than guess. A cap on tool calls, a rule about unverified claims, or a plain instruction to ask when a decision is ambiguous all prevent long runs that produce nothing usable.

Tool calls fail, so say what to do about it: read the error, correct the arguments, try another tool, and only then report the failure.

Say which steps a script must do and which are judgement. A model asked to do arithmetic in prose will eventually get it wrong; a script asked to decide what matters cannot.

Keep the file short. Every line is re-sent with every message, and a long instruction set buries the line that mattered.

### A.5 Writing a tool

Tools are Python files under the skill's `scripts/` folder. The file name becomes the tool name, and a file whose name starts with an underscore is skipped.

Each file exposes `run`, plain or async. Its docstring is what the model reads: the first paragraph becomes the description, and an `Args:` section documents the parameters, while type annotations become the JSON schema and a parameter without a default becomes required.

A description that works answers four questions. What the tool does, when to call it, what it returns, and when not to call it. The last one is the one most often left out, and the one that stops a model reaching for your file reader when the user asked a question it already knows the answer to.

Errors belong in exceptions with a message the model can act on, because that message becomes the tool result it reads next. Return short text rather than objects; a large result spends context on data the agent will not use.

```
capabilities/skills/reports/weekly/
  SKILL.md
  scripts/
    collect.py
```

### A.6 Test and iterate

1. Put the folder in `capabilities/skills/`. Procoo notices it and the dock lists it without a restart.
2. Select it in a new chat, and set its tools to Ask for the first run so every call is shown to you before it happens.
3. Ask for the job. Read the tool call card for the name and arguments, and the result card for what came back.
4. When the call is wrong, fix the description before anything else. A wrong argument is usually a description that did not say what the argument means.
5. When the model calls the right tool at the wrong moment, add an instruction about when to call it, and about when not to.
6. When the output format is wrong, put the format in the skill file rather than repeating it in each message.

Read the transcript after each run. A run that needed three corrections before it worked is telling you which paragraph to write.

### A.7 Checklist

| Question | If the answer is no |
|---|---|
| Does the description say when to call the tool and when not to? | rewrite the docstring first paragraph |
| Is every parameter's meaning stated, including format and units? | document it under `Args:` |
| Does the skill say what finished work looks like? | add a finish condition |
| Does it say when to stop and ask? | add a stopping rule |
| Does it say what to do when a tool fails? | add a recovery rule |
| Is any paragraph repeated in every conversation you have? | move it into the skill |
| Is the skill longer than the job needs? | cut the parts that restate what the model already knows |

## Appendix B: reference

### B.1 Where actions live

| Action | Where |
|---|---|
| Switch or delete a session | title bar, session name |
| Create a session | `+` row in the session list |
| Create a session in a new window | `+ Win` |
| New chat | `+` in a panel's tab bar |
| Delete a chat | `×` on its tab |
| Split or move a panel | drag a tab onto a panel half or another tab bar |
| Change skills, tools or model | skill dock, right edge of a panel |
| Approve or deny a tool | approval bar above the input row |
| Stop a turn | Stop button in the input row |
| Regenerate from a message | reload icon on a user card |
| Delete a turn | trash icon on a card |
| Open the editor | Open Editor in the dock, or Debug, or Edit |
| Enable or run an automation | its card on the Automation page |
| Read notifications | Notification tab |
| Search old notifications | View history |

### B.2 Where data is stored

| File | Holds |
|---|---|
| `storage/sessions.json` | sessions, their ids and their panel layouts |
| `storage/chats/<chat_id>.json` | one conversation, its skills, tool modes, model and context snapshot |
| `storage/automations.json` | enabled state and last run time per automation |
| `storage/notifications.json` | every notification and whether it was read |

### B.3 When something is wrong

| Symptom | Cause and fix |
|---|---|
| App exits at startup with a config error | the `llm` list is empty, or zero or two entries carry `default: true` |
| A skill is missing from the dock | discovery skipped it; the startup toast names the missing field |
| A tool never gets called | the description does not say when to use it, or the tool is set to Block |
| The agent ignores an instruction | it was added to a chat that already had history; start a new chat |
| An automation is missing from the page | its frontmatter failed validation; the startup toast names the field |
| An event returns 404 | no enabled automation matches that event name |
| An event returns 401 | `auth.api_keys` is set and the request carried no matching key |
| A session will not open from a note | the session was deleted; the id no longer resolves |
| The editor asks about a conflict | the open file changed or disappeared on disk; keep the buffer or take the disk state |
| A long chat starts a new one by itself | a limit in `limits` was crossed and the history was summarised |
