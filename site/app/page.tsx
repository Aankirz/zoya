import { AppWindow } from "./components/AppWindows";
import { CheckoutLink } from "./components/CheckoutLink";
import { DemoVideo } from "./components/DemoVideo";
import { FolderWordmark } from "./components/FolderWordmark";
import { HelloWindow } from "./components/HelloWindow";
import { MenuBar } from "./components/MenuBar";
import { FolderIcon, HeroProps, TrashIcon } from "./components/Props";
import { Waveform } from "./components/Talk";
import { TypingBubble } from "./components/TypingBubble";
import { VisitorCount } from "./components/VisitorCount";
import { WaitlistForm } from "./components/WaitlistForm";
import { AppKind } from "./components/AppWindows";
import { ABILITIES, CHARGE, CHECKOUT, CONTACT_EMAIL, DEMO, FAQ, FOOTER, HERO, HOW, PRICING, SKIP_LINK, TALK, WHY } from "./copy";
import { OutlinePlus } from "./icons/rune";
import { ctaFor, faqFor } from "@/lib/checkout";
import { getVisitorCount } from "@/lib/visitors";

// The visitor count is rendered on the server and refreshed at most once a minute.
export const revalidate = 60;

const HERO_FORM = "hero";
const PRICING_FORM = "pricing";

// Where the hero's call to action lands: the checkout pill, or the waitlist's email field.
const heroTarget = (checkout: boolean) => `#${HERO_FORM}-${checkout ? "checkout" : "email"}`;

type Row = { readonly say: string; readonly title: string; readonly line: string; readonly window: AppKind };

// heyclicky's feature row, stacked and centered: waveform, typing bubble, title, line, drawn window.
function FeatureRows({ rows }: { rows: readonly Row[] }) {
  return (
    <ul className="ability-list">
      {rows.map((row) => (
        <li className="ability" key={row.say}>
          <Waveform />
          <TypingBubble text={row.say} />
          <h3 className="ability-title">{row.title}</h3>
          <p className="ability-line">{row.line}</p>
          <AppWindow kind={row.window} className="feature-window" />
        </li>
      ))}
    </ul>
  );
}

export default async function Home() {
  const visitorCount = await getVisitorCount();
  const cta = ctaFor(process.env);
  const checkout = cta.kind === "checkout";
  const joinHref = heroTarget(checkout);

  return (
    <>
      <a className="skip-link" href={joinHref}>
        {checkout ? CHECKOUT.skipLink : SKIP_LINK}
      </a>
      <MenuBar joinHref={joinHref} joinLabel={checkout ? CHECKOUT.menu : undefined} />

      <main>
        <section className="hero desktop-dots">
          <HeroProps />
          <div className="hero-copy">
            <h1 className="hero-title">{HERO.title}</h1>
            <p className="hero-subline">{HERO.subline}</p>
            {checkout ? (
              <CheckoutLink id={`${HERO_FORM}-checkout`} href={cta.href} label={cta.label} />
            ) : (
              <WaitlistForm idPrefix={HERO_FORM} />
            )}
          </div>
        </section>

        <section className="hello-section">
          <HelloWindow />
        </section>

        <section className="abilities install" id="how">
          <p className="capsule" aria-hidden="true">
            {HOW.label}
          </p>
          <h2 className="section-title">{HOW.title}</h2>
          <ol className="ability-list install-steps">
            {HOW.steps.map((step, index) => (
              <li className="ability install-step" key={step.title}>
                <span className="capsule" aria-hidden="true">
                  {HOW.stepLabel} {index + 1}
                </span>
                <h3 className="ability-title">{step.title}</h3>
                <p className="ability-line">{step.line}</p>
              </li>
            ))}
          </ol>
        </section>

        <section className="why" id="why">
          <p className="capsule" aria-hidden="true">
            {WHY.label}
          </p>
          <h2 className="section-title why-title">{WHY.title}</h2>
          <p className="why-body">{WHY.body}</p>
          <p className="why-closer">{WHY.closer}</p>
        </section>

        <section className="abilities demo" id="demo">
          <p className="capsule" aria-hidden="true">
            {DEMO.label}
          </p>
          <h2 className="section-title">{DEMO.title}</h2>
          <DemoVideo />
          <p className="demo-link">
            <a href={DEMO.href}>{DEMO.linkLabel}</a>
          </p>
        </section>

        <section className="abilities" id="abilities">
          <h2 className="capsule">{ABILITIES.label}</h2>
          <FeatureRows rows={ABILITIES.items} />
        </section>

        <section className="abilities charge" id="charge">
          <h2 className="capsule">{CHARGE.label}</h2>
          <FeatureRows rows={CHARGE.items} />
        </section>

        <section className="abilities install" id="talk">
          <p className="capsule" aria-hidden="true">
            {TALK.label}
          </p>
          <h2 className="section-title">{TALK.title}</h2>
          <p className="install-needs">{TALK.line}</p>
          <Waveform />
          <ul className="ability-list phrase-list">
            {TALK.phrases.map((phrase) => (
              <li className="phrase" key={phrase.say}>
                <p className="bubble-glossy">{phrase.say}</p>
                <p className="ability-line">{phrase.result}</p>
              </li>
            ))}
          </ul>
        </section>

        <section className="abilities install" id="pricing">
          <p className="capsule" aria-hidden="true">
            {PRICING.label}
          </p>
          <h2 className="section-title">{PRICING.title}</h2>
          <p className="install-needs">{PRICING.line}</p>
          <ul className="ability-list install-steps">
            {PRICING.items.map((item) => (
              <li className="ability install-step" key={item.title}>
                <h3 className="ability-title">{item.title}</h3>
                <p className="ability-line">{item.line}</p>
              </li>
            ))}
          </ul>
          {/* The step row's centred grid, so the form sits centred like it does in the hero. */}
          <div className="ability install-step">
            {checkout ? (
              <CheckoutLink id={`${PRICING_FORM}-checkout`} href={cta.href} label={cta.label} />
            ) : (
              <WaitlistForm idPrefix={PRICING_FORM} />
            )}
          </div>
        </section>

        <section className="faq" id="faq">
          <p className="capsule" aria-hidden="true">
            {FAQ.label}
          </p>
          <h2 className="section-title">{FAQ.title}</h2>
          <div className="faq-list">
            {faqFor(cta).map((item) => (
              <details key={item.q}>
                <summary>
                  {item.q}
                  <OutlinePlus className="faq-plus" />
                </summary>
                <p>{item.a}</p>
              </details>
            ))}
          </div>
        </section>
      </main>

      <footer className="site-footer">
        <div className="footer-mark" aria-hidden="true">
          <TrashIcon className="footer-prop footer-trash" />
          <FolderWordmark />
          <FolderIcon className="footer-prop footer-folder" />
        </div>
        <p>{FOOTER.disclaimer}</p>
        <VisitorCount initial={visitorCount} />
        <p>
          {FOOTER.contactLead} <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>
        </p>
        <p>
          {FOOTER.iconsLead} <a href={FOOTER.iconsHref}>{FOOTER.iconsName}</a>
        </p>
        <p>{FOOTER.copyright}</p>
      </footer>
    </>
  );
}
