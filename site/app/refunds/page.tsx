// DRAFT FOR LEGAL REVIEW. Not reviewed by a lawyer; the words live in app/legal.ts, placeholders in OWNER_NEEDED.
import { LegalPage, legalMetadata } from "../components/LegalPage";
import { REFUNDS } from "../legal";

export const metadata = legalMetadata(REFUNDS);

export default function Refunds() {
  return <LegalPage doc={REFUNDS} />;
}
