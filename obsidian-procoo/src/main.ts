import { Editor, Notice, Plugin } from "obsidian";
import { ConfirmModal } from "./confirm";
import { procooEditorExtension } from "./editor-extension";
import { buildMarker, generateId, markerAt, markerInRange, type ProcooMarker } from "./markup";
import { ProcooClient } from "./procoo";
import { DEFAULT_SETTINGS, ProcooSettingTab, type ProcooSettings } from "./settings";

export default class ProcooPlugin extends Plugin {
  settings: ProcooSettings = DEFAULT_SETTINGS;

  async onload(): Promise<void> {
    await this.loadSettings();
    this.addSettingTab(new ProcooSettingTab(this.app, this));

    // Live-preview highlight + tag hiding.
    this.registerEditorExtension(procooEditorExtension);

    // Reading-view styling of rendered markers.
    this.registerMarkdownPostProcessor((element) => {
      const spans = element.querySelectorAll("span.procoo-link, span[data-procoo-id]");
      spans.forEach((span) => span.classList.add("procoo-link-rendered"));
    });

    // Right-click menu in the editor.
    this.registerEvent(
      this.app.workspace.on("editor-menu", (menu, editor) => {
        const marker = this.markerInEditor(editor);
        if (marker) {
          menu.addItem((item) =>
            item
              .setTitle("Open procoo session")
              .setIcon("external-link")
              .onClick(() => void this.openSession(marker.id)),
          );
          menu.addItem((item) =>
            item
              .setTitle("Delete procoo session")
              .setIcon("trash-2")
              .onClick(() => this.confirmDelete(editor, marker)),
          );
        } else if (editor.getSelection().trim()) {
          menu.addItem((item) =>
            item
              .setTitle("New procoo session")
              .setIcon("plus")
              .onClick(() => void this.newSession(editor)),
          );
        }
      }),
    );
  }

  async loadSettings(): Promise<void> {
    this.settings = Object.assign(
      {},
      DEFAULT_SETTINGS,
      (await this.loadData()) as Partial<ProcooSettings>,
    );
  }

  async saveSettings(): Promise<void> {
    await this.saveData(this.settings);
  }

  // ------------------------------------------------------------------
  //  Editor helpers
  // ------------------------------------------------------------------

  private client(): ProcooClient {
    return new ProcooClient(this.settings.serverUrl, this.settings.apiKey);
  }

  private markerInEditor(editor: Editor): ProcooMarker | null {
    const value = editor.getValue();
    const selections = editor.listSelections();
    if (selections.length > 0) {
      const a = editor.posToOffset(selections[0].anchor);
      const b = editor.posToOffset(selections[0].head);
      const from = Math.min(a, b);
      const to = Math.max(a, b);
      if (to > from) {
        return markerInRange(value, from, to);
      }
    }
    return markerAt(value, editor.posToOffset(editor.getCursor()));
  }

  private errorText(error: unknown): string {
    return error instanceof Error ? error.message : String(error);
  }

  // ------------------------------------------------------------------
  //  Actions
  // ------------------------------------------------------------------

  private async newSession(editor: Editor): Promise<void> {
    const selected = editor.getSelection();
    if (!selected.trim()) {
      return;
    }
    const id = generateId();
    const firstLine = selected.split("\n")[0].trim();
    const name = firstLine || this.settings.defaultSessionName;
    try {
      const result = await this.client().createSession(id, name);
      editor.replaceSelection(buildMarker(result.id, selected));
      new Notice(`Procoo session "${result.name}" opened.`);
    } catch (error) {
      new Notice(this.errorText(error));
    }
  }

  private async openSession(id: string): Promise<void> {
    try {
      await this.client().openSession(id);
    } catch (error) {
      new Notice(this.errorText(error));
    }
  }

  private confirmDelete(editor: Editor, marker: ProcooMarker): void {
    new ConfirmModal(this.app, "Delete this Procoo session and its chats?", () => {
      void this.deleteSession(editor, marker);
    }).open();
  }

  private async deleteSession(editor: Editor, marker: ProcooMarker): Promise<void> {
    try {
      await this.client().deleteSession(marker.id);
      // Remove only the marker; the highlighted text itself is untouched.
      editor.replaceRange(
        marker.inner,
        editor.offsetToPos(marker.start),
        editor.offsetToPos(marker.end),
      );
      new Notice("Procoo session deleted.");
    } catch (error) {
      new Notice(this.errorText(error));
    }
  }
}
