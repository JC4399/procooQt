# Obsidian session flow

Cross-module flow linking an Obsidian note line to a Procoo session.

## Actors

| Actor | Role |
|---|---|
| Obsidian plugin (`obsidian-procoo/`) | Adds/reads the HTML marker, shows the context menu, calls HTTP |
| [control-server](modules/control-server.md) | Validates and routes the HTTP request |
| [qt-window-manager](modules/qt-window-manager.md) | Opens/focuses/closes the per-session window |
| [chat-store](modules/chat-store.md) | Holds the stable session UUID and layout |
| [qt-session-controller](modules/qt-session-controller.md) | Builds the window's panels for the session |

## Marker

A linked span stores the session UUID in HTML so it survives rendering and can
carry data:

```html
<span class="procoo-link" data-procoo-id="<uuid>">selected text</span>
```

The inner text is an arbitrary bookmark and doubles as the session name; it is
never synced to session content. The plugin only ever adds or removes this
markup — note content is never modified by the flow, and crossed-out lines may
host sessions just as well.

Rendering: Obsidian renders the inline `span` when the line is unfocused (styled
by `.cm-editor .procoo-link`), while the focused line shows raw source where the
CM6 extension hides the tags and marks the inner text (`.procoo-mark`). Both are
styled from `styles.css`, so the highlight is persistent in live preview and
reading view.

## New session

1. User selects text, right-clicks, chooses **New procoo session**.
2. Plugin generates a UUID, `POST /sessions` with `{id, name: <selection>}`.
3. Server finds no matching id/name, calls
   `WindowManager.create_session(name, session_id=id)`.
4. `ChatStore.create_session` records `{id, name, layout}`; `WindowManager`
   builds a fresh `session`/`chat`/`skill` triple on a child context and shows
   `ChatWindow.qml`. The new session gets one empty chat (`session.ensure_chat`)
   so the per-chat skill/model dock is active immediately.
5. Server returns `{id, name, created: true}`; the plugin wraps the selection in
   the marker (storing the returned `id`). The session starts empty (no seeded
   message).

## Open session

1. User right-clicks a marked span, chooses **Open procoo session**.
2. Plugin reads `data-procoo-id`, `POST /sessions/open`.
3. Server resolves the id to a name and calls
   `WindowManager.open_session(name)`, which focuses the existing window or
   spawns a new one. `404` when the session no longer exists (plugin may offer
   to recreate).

## Delete session

1. User right-clicks a marked span, chooses **Delete procoo session** and
   confirms in Obsidian.
2. Plugin `POST /sessions/delete` with `{id}`.
3. Server resolves the id and calls `WindowManager.delete_session(name)`, which
   closes the window and removes the session + chats from `ChatStore`.
4. Plugin strips only the marker from the line, leaving the inner text untouched.
