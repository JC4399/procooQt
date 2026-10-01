import { App, PluginSettingTab, Setting } from "obsidian";
import type ProcooPlugin from "./main";

export interface ProcooSettings {
  /** Base URL of the Procoo control server. */
  serverUrl: string;
  /** API key sent as X-Api-Key; empty when the server disables auth. */
  apiKey: string;
  /** Name used when the highlighted text is empty. */
  defaultSessionName: string;
}

export const DEFAULT_SETTINGS: ProcooSettings = {
  serverUrl: "http://127.0.0.1:12841",
  apiKey: "",
  defaultSessionName: "Procoo session",
};

export class ProcooSettingTab extends PluginSettingTab {
  private readonly plugin: ProcooPlugin;

  constructor(app: App, plugin: ProcooPlugin) {
    super(app, plugin);
    this.plugin = plugin;
  }

  display(): void {
    const { containerEl } = this;
    containerEl.empty();

    new Setting(containerEl)
      .setName("Procoo server URL")
      .setDesc("Base URL of the Procoo control server (control_server.host/port).")
      .addText((text) =>
        text
          .setPlaceholder("http://127.0.0.1:12841")
          .setValue(this.plugin.settings.serverUrl)
          .onChange(async (value) => {
            this.plugin.settings.serverUrl = value.trim();
            await this.plugin.saveSettings();
          }),
      );

    new Setting(containerEl)
      .setName("API key")
      .setDesc("Sent as X-Api-Key. Leave empty when control_server.api_keys is unset.")
      .addText((text) =>
        text
          .setPlaceholder("optional")
          .setValue(this.plugin.settings.apiKey)
          .onChange(async (value) => {
            this.plugin.settings.apiKey = value.trim();
            await this.plugin.saveSettings();
          }),
      );

    new Setting(containerEl)
      .setName("Default session name")
      .setDesc("Used when the highlighted text is empty.")
      .addText((text) =>
        text
          .setPlaceholder("Procoo session")
          .setValue(this.plugin.settings.defaultSessionName)
          .onChange(async (value) => {
            this.plugin.settings.defaultSessionName = value.trim();
            await this.plugin.saveSettings();
          }),
      );
  }
}
