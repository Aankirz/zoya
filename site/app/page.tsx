import { HearZoya } from "./components/HearZoya";
import { Orb } from "./components/Orb";
import { VisitorCount } from "./components/VisitorCount";
import { WaitlistForm } from "./components/WaitlistForm";
import {
  CLOSING,
  CONTACT_EMAIL,
  FAQ,
  FOOTER,
  HERO,
  PROMISES,
  SKIP_LINK,
  THINGS_TO_SAY,
  TRANSFORMATION,
} from "./copy";
import { getVisitorCount } from "@/lib/visitors";

// The visitor count is rendered on the server and refreshed at most once a minute.
export const revalidate = 60;

const HERO_FORM = "hero";

export default async function Home() {
  const visitorCount = await getVisitorCount();

  return (
    <>
      <header className="site-header">
        <a className="skip-link" href={`#${HERO_FORM}-email`}>
          {SKIP_LINK}
        </a>
        <span className="wordmark" aria-hidden="true">
          Zoya
        </span>
      </header>

      <main>
        <section className="hero">
          <div className="hero-copy">
            <h1 className="hero-title">
              <span>{HERO.titleLines[0]}</span> <span className="accent">{HERO.titleLines[1]}</span>
            </h1>
            <p className="lede">{HERO.lede}</p>
            <HearZoya />
            <WaitlistForm idPrefix={HERO_FORM} />
          </div>
          <Orb className="hero-orb" />
        </section>

        <section className="section band">
          <div className="section-inner">
            <h2>{PROMISES.title}</h2>
            <ol className="promises">
              {PROMISES.items.map((promise) => (
                <li key={promise.title}>
                  <h3>{promise.title}</h3>
                  <p>{promise.body}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section className="section band-deep">
          <div className="section-inner">
            <h2>{TRANSFORMATION.title}</h2>
            <p className="section-lead">{TRANSFORMATION.lead}</p>
            <div className="transform">
              <div className="said">
                <p className="kicker">{TRANSFORMATION.saidLabel}</p>
                <p className="spoken">{TRANSFORMATION.said}</p>
              </div>
              <div>
                <p className="kicker">{TRANSFORMATION.doneLabel}</p>
                <ol className="steps">
                  {TRANSFORMATION.steps.map((step) => (
                    <li key={step}>{step}</li>
                  ))}
                </ol>
              </div>
            </div>
            <p className="closer">
              <span className="closer-quiet">{TRANSFORMATION.closerQuiet}</span>{" "}
              {TRANSFORMATION.closerLoud}
            </p>
          </div>
        </section>

        <section className="section">
          <div className="section-inner">
            <h2>{THINGS_TO_SAY.title}</h2>
            <ul className="phrases">
              {THINGS_TO_SAY.items.map((item) => (
                <li key={item.say}>
                  <p className="phrase">{item.say}</p>
                  <p className="phrase-result">{item.does}</p>
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section className="section band">
          <div className="section-inner">
            <h2>{FAQ.title}</h2>
            <div className="faq">
              {FAQ.items.map((item) => (
                <details key={item.q}>
                  <summary>{item.q}</summary>
                  <p>{item.a}</p>
                </details>
              ))}
            </div>
          </div>
        </section>

        <section className="section closing">
          <div className="closing-copy">
            <h2>{CLOSING.title}</h2>
            <p className="section-lead">{CLOSING.body}</p>
            <WaitlistForm idPrefix="closing" />
          </div>
          <Orb className="closing-orb" />
        </section>
      </main>

      <footer className="site-footer">
        <p className="footer-brand">{FOOTER.brand}</p>
        <p>{FOOTER.credit}</p>
        <p>
          {FOOTER.contactLead} <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>
        </p>
        <VisitorCount initial={visitorCount} />
      </footer>
    </>
  );
}
