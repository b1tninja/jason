import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { postJson, resetServerSession } from "./api";

type Call = { url: string; token: string };

function reply(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

describe("a write after the server restarted", () => {
  const calls: Call[] = [];

  beforeEach(() => {
    calls.length = 0;
    resetServerSession();
    document.head.innerHTML = '<meta name="jason-token" content="stale-token">';
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    document.head.innerHTML = "";
    resetServerSession();
  });

  it("asks for a fresh token once and retries, instead of showing the refusal", async () => {
    vi.stubGlobal("fetch", async (url: string, init?: RequestInit) => {
      const token = (init?.headers as Record<string, string> | undefined)?.["X-Jason-Token"] ?? "";
      calls.push({ url, token });
      if (url === "/api/session") return reply(200, { header: "X-Jason-Token", token: "fresh-token" });
      return token === "fresh-token"
        ? reply(200, { ok: true })
        : reply(403, { error: "a write carries this server's token (X-Jason-Token, from GET /api/session)" });
    });
    const out = await postJson<{ ok: boolean }>("/api/write/example", { a: 1 });
    expect(out.ok).toBe(true);
    const writes = calls.filter((c) => c.url === "/api/write/example");
    expect(writes.map((c) => c.token)).toEqual(["stale-token", "fresh-token"]);
    expect(calls.filter((c) => c.url === "/api/session")).toHaveLength(1);
  });

  it("retries only once, so a server that keeps refusing is shown the refusal", async () => {
    vi.stubGlobal("fetch", async (url: string, init?: RequestInit) => {
      const token = (init?.headers as Record<string, string> | undefined)?.["X-Jason-Token"] ?? "";
      calls.push({ url, token });
      if (url === "/api/session") return reply(200, { header: "X-Jason-Token", token: "still-wrong" });
      return reply(403, { error: "a write carries this server's token (X-Jason-Token, from GET /api/session)" });
    });
    await expect(postJson("/api/write/example", {})).rejects.toThrow(/this server's token/);
    expect(calls.filter((c) => c.url === "/api/write/example")).toHaveLength(2);
  });

  it("does not retry a refusal that is about something else", async () => {
    vi.stubGlobal("fetch", async (url: string, init?: RequestInit) => {
      const token = (init?.headers as Record<string, string> | undefined)?.["X-Jason-Token"] ?? "";
      calls.push({ url, token });
      return reply(403, { error: "a write from http://other is not from this server's page" });
    });
    await expect(postJson("/api/write/example", {})).rejects.toThrow(/not from this server's page/);
    expect(calls.filter((c) => c.url === "/api/write/example")).toHaveLength(1);
  });
});
