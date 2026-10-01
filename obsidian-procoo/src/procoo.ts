// Minimal HTTP client for the Procoo control server.
//
// Obsidian's `requestUrl` is used instead of `fetch` so the request bypasses the
// browser CORS layer and works from the desktop app.

import { requestUrl, type RequestUrlResponse } from "obsidian";

export interface SessionResult {
  id: string;
  name: string;
  created?: boolean;
  open?: boolean;
}

export interface DeleteResult {
  id: string;
  name: string;
  deleted: boolean;
}

export class ProcooClient {
  constructor(
    private readonly serverUrl: string,
    private readonly apiKey: string,
  ) {}

  /** Create a session (upsert by id) and open its window. */
  createSession(id: string, name: string): Promise<SessionResult> {
    return this.post<SessionResult>("/sessions", { id, name });
  }

  /** Focus the window for a session. */
  openSession(id: string): Promise<SessionResult> {
    return this.post<SessionResult>("/sessions/open", { id });
  }

  /** Delete a session, its chats, and its window. */
  deleteSession(id: string): Promise<DeleteResult> {
    return this.post<DeleteResult>("/sessions/delete", { id });
  }

  private async post<T>(path: string, body: unknown): Promise<T> {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (this.apiKey) {
      headers["X-Api-Key"] = this.apiKey;
    }
    let response: RequestUrlResponse;
    try {
      response = await requestUrl({
        url: this.serverUrl.replace(/\/+$/, "") + path,
        method: "POST",
        headers,
        body: JSON.stringify(body),
      });
    } catch (error) {
      throw new Error("Procoo is not reachable. Is it running?");
    }
    if (response.status >= 400) {
      throw new Error(`Procoo rejected the request (${response.status}).`);
    }
    return response.json as T;
  }
}
