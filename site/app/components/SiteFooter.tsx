import { CONTACT_EMAIL, FOOTER } from "../copy";
import { FolderWordmark } from "./FolderWordmark";
import { FolderIcon, TrashIcon } from "./Props";
import { VisitorCount } from "./VisitorCount";

// The folder wordmark footer every page ends with. The visitor count shows only where the page fetched one.
export function SiteFooter({ visitorCount }: { visitorCount?: number | null }) {
  return (
    <footer className="site-footer">
      <div className="footer-mark" aria-hidden="true">
        <TrashIcon className="footer-prop footer-trash" />
        <FolderWordmark />
        <FolderIcon className="footer-prop footer-folder" />
      </div>
      <p>{FOOTER.disclaimer}</p>
      {visitorCount === undefined ? null : <VisitorCount initial={visitorCount} />}
      <p>
        {FOOTER.contactLead} <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>
      </p>
      <p>
        {FOOTER.iconsLead} <a href={FOOTER.iconsHref}>{FOOTER.iconsName}</a>
      </p>
      <p>{FOOTER.copyright}</p>
    </footer>
  );
}
