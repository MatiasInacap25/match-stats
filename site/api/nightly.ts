// Vercel Cron target. Once a day Vercel calls this route (GET); it triggers a
// Deploy Hook, and that build refreshes the data (see scripts/refresh-data.mjs).

export type NightlyEnv = {
  CRON_SECRET?: string;
  DEPLOY_HOOK_URL?: string;
};

export async function runNightly(
  request: Request,
  env: NightlyEnv,
  fetchImpl: typeof fetch = fetch,
): Promise<Response> {
  const secret = env.CRON_SECRET;
  const hook = env.DEPLOY_HOOK_URL;

  // Vercel sends "Authorization: Bearer <CRON_SECRET>" on cron calls.
  if (!secret || request.headers.get("authorization") !== `Bearer ${secret}`) {
    return Response.json({ ok: false, error: "unauthorized" }, { status: 401 });
  }
  if (!hook) {
    return Response.json({ ok: false, error: "DEPLOY_HOOK_URL is not set" }, { status: 500 });
  }

  const res = await fetchImpl(hook, { method: "POST" });
  if (!res.ok) {
    return Response.json({ ok: false, error: `deploy hook returned ${res.status}` }, { status: 502 });
  }
  return Response.json({ ok: true });
}

export function GET(request: Request): Promise<Response> {
  const env = (globalThis as { process?: { env: NightlyEnv } }).process?.env ?? {};
  return runNightly(request, env);
}
