// DRAFT FOR LEGAL REVIEW. Not reviewed by a lawyer; the words live in app/legal.ts, placeholders in OWNER_NEEDED.
import { LegalPage, legalMetadata } from "../components/LegalPage";
import { TERMS } from "../legal";

export const metadata = legalMetadata(TERMS);

export default function Terms() {
  return <LegalPage doc={TERMS} />;
}
