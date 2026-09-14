import { clientIp, isRateLimited } from "@/lib/rate-limit";
import { normalizeEmail } from "@/lib/validate";
import { addToWaitlist } from "@/lib/waitlist";

const WAITLIST_ATTEMPTS_PER_WINDOW = 5;

export async function POST(request: Request) {
  if (isRateLimited(`waitlist:${clientIp(request)}`, WAITLIST_ATTEMPTS_PER_WINDOW)) {
    return Response.json({ error: "rate_limited" }, { status: 429 });
  }
  const body: unknown = await request.json().catch(() => null);
  if (!body || typeof body !== "object") {
    return Response.json({ error: "invalid" }, { status: 400 });
  }
  const { email: rawEmail, website } = body as Record<string, unknown>;
  // Honeypot filled in: pretend success so bots learn nothing.
  if (website) return Response.json({ ok: true });

  const email = normalizeEmail(rawEmail);
  if (!email) return Response.json({ error: "invalid" }, { status: 400 });

  try {
    await addToWaitlist(email);
  } catch (error) {
    console.error("waitlist: insert failed:", error instanceof Error ? error.message : error);
    return Response.json({ error: "server" }, { status: 500 });
  }
  return Response.json({ ok: true });
}
