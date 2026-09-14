import { clientIp, isRateLimited } from "@/lib/rate-limit";
import { isVisitorId } from "@/lib/validate";
import { recordVisitor } from "@/lib/visitors";

const VISITS_PER_WINDOW = 10;

export async function POST(request: Request) {
  if (isRateLimited(`visit:${clientIp(request)}`, VISITS_PER_WINDOW)) {
    return Response.json({ error: "rate_limited" }, { status: 429 });
  }
  const body: unknown = await request.json().catch(() => null);
  const id = body && typeof body === "object" ? (body as Record<string, unknown>).id : undefined;
  if (!isVisitorId(id)) return Response.json({ error: "invalid" }, { status: 400 });

  const count = await recordVisitor(id.toLowerCase());
  if (count === null) return Response.json({ error: "unavailable" }, { status: 503 });
  return Response.json({ count });
}
