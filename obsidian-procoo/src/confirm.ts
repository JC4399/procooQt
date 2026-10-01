import { App, Modal } from "obsidian";

/** A simple yes/no confirmation dialog. */
export class ConfirmModal extends Modal {
  constructor(
    app: App,
    private readonly message: string,
    private readonly onConfirm: () => void,
  ) {
    super(app);
  }

  onOpen(): void {
    const { contentEl } = this;
    contentEl.createEl("p", { text: this.message });

    const row = contentEl.createDiv({ cls: "procoo-confirm-row" });
    row.style.display = "flex";
    row.style.justifyContent = "flex-end";
    row.style.gap = "8px";
    row.style.marginTop = "12px";

    const cancel = row.createEl("button", { text: "Cancel" });
    cancel.addEventListener("click", () => this.close());

    const confirm = row.createEl("button", { text: "Delete", cls: "mod-warning" });
    confirm.addEventListener("click", () => {
      this.close();
      this.onConfirm();
    });
  }

  onClose(): void {
    this.contentEl.empty();
  }
}
