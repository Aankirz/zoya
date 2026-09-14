import { SayHi } from "./components/SayHi";
import { VisitorCount } from "./components/VisitorCount";
import { WaitlistForm } from "./components/WaitlistForm";
import { CONTACT_EMAIL, FOOTER, HERO, NAV, PROMISES } from "./copy";
import { getVisitorCount } from "@/lib/visitors";

// The visitor count is rendered on the server and refreshed at most once a minute.
export const revalidate = 60;

const HERO_FORM = "hero";

export default async function Home() {
  const visitorCount = await getVisitorCount();

  return (
    <>
      {/* The pill's link doubles as the skip link: it is the first stop and jumps to the email field. */}
      <header className="nav">
        <span className="nav-mark" aria-hidden="true">
          <span className="nav-wordmark">{NAV.wordmark}</span>
          <span className="nav-tag">{NAV.tag}</span>
        </span>
        <a className="nav-join" href={`#${HERO_FORM}-email`}>
          {NAV.join}
        </a>
      </header>

      <main className="stage">
        <section className="hero">
          <h1 className="hero-name">{HERO.name}</h1>
          <p className="chip">
            <span className="chip-dot" aria-hidden="true" />
            {HERO.chip}
          </p>
          <p className="hero-intro">{HERO.intro}</p>
          <p className="mono">{HERO.origin}</p>
          <SayHi />
          <WaitlistForm idPrefix={HERO_FORM} />
        </section>

        <section className="promises">
          <h2 className="mono">{PROMISES.title}</h2>
          <ol className="rows">
            {PROMISES.items.map((promise, i) => (
              <li key={promise.title}>
                <span className="row-number" aria-hidden="true">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <p className="row-title">{promise.title}</p>
                <p className="row-detail">{promise.detail}</p>
              </li>
            ))}
          </ol>
        </section>
      </main>

      <footer className="site-footer">
        <p>{FOOTER.copyright}</p>
        <VisitorCount initial={visitorCount} />
        <p>
          {FOOTER.contactLead} <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>
        </p>
        <p>{FOOTER.credit}</p>
      </footer>
    </>
  );
}
