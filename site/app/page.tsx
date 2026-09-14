import { FolderWordmark } from "./components/FolderWordmark";
import { HelloWindow } from "./components/HelloWindow";
import { MenuBar } from "./components/MenuBar";
import { FolderIcon, HeroProps, TrashIcon } from "./components/Props";
import { Waveform } from "./components/Talk";
import { TypingBubble } from "./components/TypingBubble";
import { VisitorCount } from "./components/VisitorCount";
import { WaitlistForm } from "./components/WaitlistForm";
import { CONTACT_EMAIL, FAQ, FOOTER, HERO, PROMISES, SKIP_LINK } from "./copy";
import { OutlinePlus } from "./icons/rune";
import { getVisitorCount } from "@/lib/visitors";

// The visitor count is rendered on the server and refreshed at most once a minute.
export const revalidate = 60;

const HERO_FORM = "hero";

export default async function Home() {
  const visitorCount = await getVisitorCount();

  return (
    <>
      <a className="skip-link" href={`#${HERO_FORM}-email`}>
        {SKIP_LINK}
      </a>
      <MenuBar joinHref={`#${HERO_FORM}-email`} />

      <main>
        <section className="hero desktop-dots">
          <HeroProps />
          <div className="hero-copy">
            <h1 className="hero-title">{HERO.title}</h1>
            <p className="hero-subline">{HERO.subline}</p>
            <WaitlistForm idPrefix={HERO_FORM} />
          </div>
        </section>

        <section className="hello-section">
          <HelloWindow />
        </section>

        <section className="promises" id="promises">
          <h2 className="capsule">{PROMISES.label}</h2>
          <ul className="promise-list">
            {PROMISES.items.map((promise) => (
              <li className="promise" key={promise.say}>
                <Waveform />
                <TypingBubble text={promise.say} />
                <h3 className="promise-title">{promise.title}</h3>
                <p className="promise-line">{promise.line}</p>
              </li>
            ))}
          </ul>
        </section>

        <section className="faq" id="faq">
          <p className="capsule" aria-hidden="true">
            {FAQ.label}
          </p>
          <h2 className="section-title">{FAQ.title}</h2>
          <div className="faq-list">
            {FAQ.items.map((item) => (
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
        <p>{FOOTER.credit}</p>
        <p>
          {FOOTER.iconsLead} <a href={FOOTER.iconsHref}>{FOOTER.iconsName}</a>
        </p>
        <p>{FOOTER.copyright}</p>
      </footer>
    </>
  );
}
