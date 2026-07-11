const TONES = ["Cinematic", "Noir", "Dreamlike", "Documentary", "Vibrant", "Melancholy"];

export function ToneSelector({ value, onChange }: { value: string; onChange: (t: string) => void }) {
  return (
    <div>
      <div className="label" style={{ marginBottom: 10 }}>
        ✦ Tone
      </div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {TONES.map((t) => {
          const active = value === t;
          return (
            <button
              key={t}
              className={active ? "primary" : "ghost"}
              onClick={() => onChange(active ? "" : t)}
              style={{ padding: "6px 14px", fontSize: 12 }}
            >
              {t}
            </button>
          );
        })}
      </div>
    </div>
  );
}
