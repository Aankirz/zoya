// Zoya's orb: decorative only, its meaning lives in the page text.
// Clouds drift on transform alone; HearZoya drives --zoya-level on <html> while she speaks.
export function Orb({ className }: { className: string }) {
  return (
    <div className={`orb ${className}`} aria-hidden="true">
      <div className="orb-body">
        <span className="orb-cloud orb-cloud-1" />
        <span className="orb-cloud orb-cloud-2" />
        <span className="orb-cloud orb-cloud-3" />
        <span className="orb-cloud orb-cloud-4" />
        <span className="orb-voice" />
        <span className="orb-sheen" />
      </div>
    </div>
  );
}
