import type { Metadata } from "next";
import { CONTACT_EMAIL, META } from "../copy";
import { LEGAL_COMMON, type LegalDoc, type LegalSection } from "../legal";
import { ZoyaMark } from "./MenuBar";
import { SiteFooter } from "./SiteFooter";

const HOME_PATH = "/";

export function legalMetadata(doc: LegalDoc): Metadata {
  return { title: `zoya · ${doc.title}`, description: META.description, alternates: { canonical: doc.path } };
}

function Section({ section }: { section: LegalSection }) {
  return (
    <section className="legal-section">
      <h2 className="legal-heading">{section.heading}</h2>
      {section.body?.map((line) => <p key={line}>{line}</p>)}
      {section.list ? (
        <ul className="legal-list">
          {section.list.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

// One legal document on the site's plain page: the mark home, the words, the shared footer.
export function LegalPage({ doc }: { doc: LegalDoc }) {
  return (
    <>
      <header className="legal-bar">
        <a className="legal-home" href={HOME_PATH}>
          <ZoyaMark className="legal-mark" />
          {LEGAL_COMMON.home}
        </a>
      </header>
      <main className="legal">
        <p className="capsule" aria-hidden="true">
          {LEGAL_COMMON.capsule}
        </p>
        <h1 className="section-title">{doc.title}</h1>
        <p className="legal-draft" role="note">
          {LEGAL_COMMON.draft} {LEGAL_COMMON.effective}
        </p>
        <p className="legal-lead">{doc.lead}</p>
        {doc.sections.map((section) => (
          <Section key={section.heading} section={section} />
        ))}
        <section className="legal-section">
          <h2 className="legal-heading">{LEGAL_COMMON.contactHeading}</h2>
          <p>
            {LEGAL_COMMON.contactLead} <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>.
          </p>
          <p>{LEGAL_COMMON.postal}</p>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}
