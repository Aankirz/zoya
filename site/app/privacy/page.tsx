// DRAFT FOR LEGAL REVIEW. Not reviewed by a lawyer; the words live in app/legal.ts, placeholders in OWNER_NEEDED.
import { LegalPage, legalMetadata } from "../components/LegalPage";
import { PRIVACY } from "../legal";

export const metadata = legalMetadata(PRIVACY);

export default function Privacy() {
  return <LegalPage doc={PRIVACY} />;
}
