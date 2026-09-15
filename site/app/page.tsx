import { AppWindow } from "./components/AppWindows";
import { FolderWordmark } from "./components/FolderWordmark";
import { HelloWindow } from "./components/HelloWindow";
import { InstallCommand } from "./components/InstallCommand";
import { MenuBar } from "./components/MenuBar";
import { FolderIcon, HeroProps, TrashIcon } from "./components/Props";
import { Waveform } from "./components/Talk";
import { TypingBubble } from "./components/TypingBubble";
import { VisitorCount } from "./components/VisitorCount";
import { WaitlistForm } from "./components/WaitlistForm";
import { AppKind } from "./components/AppWindows";
import { ABILITIES, CHARGE, CONTACT_EMAIL, FAQ, FOOTER, GET_ZOYA, HERO, SKIP_LINK, TALK, WHY } from "./copy";
import { OutlinePlus } from "./icons/rune";
import { getVisitorCount } from "@/lib/visitors";

// The visitor count is rendered on the server and refreshed at most once a minute.
export const revalidate = 60;

const HERO_FORM = "hero";

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

        <section className="why" id="why">
          <p className="capsule" aria-hidden="true">
            {WHY.label}
          </p>
          <h2 className="section-title why-title">{WHY.title}</h2>
          <p className="why-body">{WHY.body}</p>
          <p className="why-closer">{WHY.closer}</p>
        </section>

        <section className="abilities" id="abilities">
          <h2 className="capsule">{ABILITIES.label}</h2>
          <FeatureRows rows={ABILITIES.items} />
        </section>

        <section className="abilities charge" id="charge">
          <h2 className="capsule">{CHARGE.label}</h2>
          <FeatureRows rows={CHARGE.items} />
        </section>

        <section className="abilities install" id="get-zoya">
          <p className="capsule" aria-hidden="true">
            {GET_ZOYA.label}
          </p>
          <h2 className="section-title">{GET_ZOYA.title}</h2>
          <p className="install-needs">{GET_ZOYA.needs}</p>
          <ol className="ability-list install-steps">
            {GET_ZOYA.steps.map((step, index) => (
              <li className="ability install-step" key={step.title}>
                <span className="capsule" aria-hidden="true">
                  {GET_ZOYA.stepLabel} {index + 1}
                </span>
                <h3 className="ability-title">{step.title}</h3>
                {step.showCommand ? <InstallCommand /> : null}
                <p className="ability-line">
                  {step.line}
                  {step.command ? (
                    <>
                      {" "}
                      <code className="inline-command">{step.command}</code>
                    </>
                  ) : null}
                </p>
              </li>
            ))}
          </ol>
          <p className="ability-line install-after">
            {GET_ZOYA.after} <code className="inline-command">{GET_ZOYA.afterCommand}</code>
          </p>
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
        <p>
          {FOOTER.iconsLead} <a href={FOOTER.iconsHref}>{FOOTER.iconsName}</a>
        </p>
        <p>{FOOTER.copyright}</p>
      </footer>
    </>
  );
}
