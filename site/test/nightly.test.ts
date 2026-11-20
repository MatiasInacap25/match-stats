import { describe, expect, it, vi } from "vitest";
import { runNightly } from "../api/nightly";

const env = { CRON_SECRET: "s3cret", DEPLOY_HOOK_URL: "https://hooks.example/deploy" };
const req = (auth?: string) =>
  new Request("https://site.example/api/nightly", {
    headers: auth ? { authorization: auth } : {},
  });

describe("runNightly", () => {
  it("rejects a call without the cron secret", async () => {
    const fetchMock = vi.fn();
    const res = await runNightly(req(), env, fetchMock);
    expect(res.status).toBe(401);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("rejects a wrong secret", async () => {
    const res = await runNightly(req("Bearer nope"), env, vi.fn());
    expect(res.status).toBe(401);
  });

  it("rejects everything when CRON_SECRET is not configured", async () => {
    const res = await runNightly(req("Bearer undefined"), { DEPLOY_HOOK_URL: env.DEPLOY_HOOK_URL }, vi.fn());
    expect(res.status).toBe(401);
  });

  it("reports a missing deploy hook", async () => {
    const res = await runNightly(req("Bearer s3cret"), { CRON_SECRET: "s3cret" }, vi.fn());
    expect(res.status).toBe(500);
  });

  it("posts to the deploy hook when authorized", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("{}", { status: 201 }));
    const res = await runNightly(req("Bearer s3cret"), env, fetchMock);
    expect(fetchMock).toHaveBeenCalledWith(env.DEPLOY_HOOK_URL, { method: "POST" });
    expect(res.status).toBe(200);
  });

  it("returns 502 when the deploy hook fails", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("", { status: 500 }));
    const res = await runNightly(req("Bearer s3cret"), env, fetchMock);
    expect(res.status).toBe(502);
  });
});
