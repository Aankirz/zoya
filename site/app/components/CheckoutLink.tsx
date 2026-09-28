import { CHECKOUT } from "../copy";

// Dodo's hosted checkout, as a glossy pill. It stands where the waitlist form stands when checkout is off.
export function CheckoutLink({ id, href, label }: { id: string; href: string; label: string }) {
  return (
    <div className="checkout">
      <a className="pill-glossy checkout-link" id={id} href={href}>
        {label}
      </a>
      <p className="field-hint">{CHECKOUT.hint}</p>
    </div>
  );
}
