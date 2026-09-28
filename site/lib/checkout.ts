// The Dodo Payments checkout switch. NEXT_PUBLIC_DODO_CHECKOUT_URL is the product's static payment link, copied
// from the Dodo dashboard (Products → share) and used as is: https://docs.dodopayments.com/guides/payment-links-guide
// Unset, the site is the waitlist it was before checkout existed.
import { CHECKOUT, FAQ } from "../app/copy.ts";

type Env = Record<string, string | undefined>;

export type Cta = { kind: "waitlist" } | { kind: "checkout"; href: string; label: string };

// Only an https link becomes a checkout; anything else (empty, a typo, a javascript: URL) keeps the waitlist.
export function checkoutUrl(env: Env): string | null {
  const raw = env.NEXT_PUBLIC_DODO_CHECKOUT_URL?.trim();
  if (!raw) return null;
  try {
    return new URL(raw).protocol === "https:" ? raw : null;
  } catch {
    return null;
  }
}

export function ctaFor(env: Env): Cta {
  const href = checkoutUrl(env);
  return href ? { kind: "checkout", href, label: CHECKOUT.cta } : { kind: "waitlist" };
}

// With checkout on, "when can i get it?" answers "now" and the key question joins the list.
export function faqFor(cta: Cta) {
  if (cta.kind === "waitlist") return FAQ.items;
  return [...FAQ.items.map((item) => (item.q === CHECKOUT.when.q ? CHECKOUT.when : item)), CHECKOUT.key];
}
