import { useRef, useState } from "react";
import type { CastMember, Goal } from "../api/types";
import { ToneSelector } from "../components/ToneSelector";
import { CharacterPanel } from "../components/CharacterPanel";

export function GoalEntry({ onBegin }: { onBegin: (goal: Goal) => void }) {
  const [text, setText] = useState("A jazz musician finds a door to 1920s Paris in the back of a Harlem club…");
  const [tone, setTone] = useState("");
  const [cast, setCast] = useState<CastMember[]>([]);
  const [panel, setPanel] = useState<"character" | "location" | null>(null);
  const [stylePreview, setStylePreview] = useState<string | null>(null);
  const styleRef = useRef<HTMLInputElement>(null);

  const begin = () => {
    if (!text.trim()) return;
    const goal: Goal = {
      text,
      cast: cast.map((c) => ({ entity_id: c.entity_id })),
      constraints: { ...(tone ? { tone } : {}), hitl: "per_artifact" },
    };
    onBegin(goal);
  };

  return (
    <div className="app-shell">
      <div className="label" style={{ color: "var(--amber)", marginBottom: 18 }}>
        ∂ &nbsp;Studio · Goal
      </div>

      {/* prompt */}
      <div className="panel" style={{ padding: "26px 28px", display: "flex", gap: 14 }}>
        <span style={{ fontFamily: "var(--font-display)", color: "var(--amber)", fontSize: 26, lineHeight: 1 }}>∂</span>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={3}
          placeholder="Describe the film you want to make…"
          style={{ fontSize: 19, fontFamily: "var(--font-display)" }}
        />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 36, marginTop: 32 }}>
        {/* style reference */}
        <div>
          <div className="label" style={{ marginBottom: 10 }}>
            ▣ Style reference
          </div>
          <div style={{ display: "flex", gap: 16 }}>
            <button
              onClick={() => styleRef.current?.click()}
              style={{
                width: 92,
                height: 92,
                border: "1px dashed var(--hairline-strong)",
                borderRadius: "var(--r-tile)",
                backgroundImage: stylePreview ? `url(${stylePreview})` : undefined,
                backgroundSize: "cover",
                backgroundPosition: "center",
                flex: "0 0 auto",
              }}
            >
              {!stylePreview && <span className="label">+ Ref</span>}
            </button>
            <input
              ref={styleRef}
              type="file"
              accept="image/*"
              hidden
              onChange={(e) => {
                const f = e.target.files?.[0];
                setStylePreview(f ? URL.createObjectURL(f) : null);
              }}
            />
            <p style={{ color: "var(--muted)", fontStyle: "italic", margin: 0, alignSelf: "center" }}>
              Upload a frame, painting, or mood board to guide the visual style.
            </p>
          </div>
        </div>

        {/* characters */}
        <div>
          <div className="label" style={{ marginBottom: 10 }}>
            ⚇ Characters
          </div>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
            {cast.map((c) => (
              <div key={c.entity_id} style={castTile(c.referenceUrl)} title={c.name}>
                {!c.referenceUrl && <span className="label">{c.name.slice(0, 8)}</span>}
                <span className="label" style={castLabel}>
                  {c.name}
                </span>
              </div>
            ))}
            <button style={addTile} onClick={() => setPanel("character")}>
              <span style={{ fontSize: 20 }}>+</span>
              <span className="label">Lead</span>
            </button>
            <button style={addTile} onClick={() => setPanel("location")}>
              <span style={{ fontSize: 20 }}>⌖</span>
              <span className="label">Place</span>
            </button>
          </div>
        </div>
      </div>

      <div style={{ marginTop: 36 }}>
        <ToneSelector value={tone} onChange={setTone} />
      </div>

      <div style={{ marginTop: 44, display: "flex", justifyContent: "flex-end" }}>
        <button className="primary" onClick={begin} style={{ padding: "12px 30px", fontSize: 15 }}>
          Begin →
        </button>
      </div>

      {panel && (
        <CharacterPanel
          kind={panel}
          onClose={() => setPanel(null)}
          onCreated={(m) => {
            setCast((c) => [...c, m]);
            setPanel(null);
          }}
        />
      )}
    </div>
  );
}

const addTile: React.CSSProperties = {
  width: 92,
  height: 92,
  border: "1px dashed var(--hairline-strong)",
  borderRadius: "var(--r-tile)",
  display: "flex",
  flexDirection: "column",
  gap: 6,
  alignItems: "center",
  justifyContent: "center",
};
const castTile = (url?: string): React.CSSProperties => ({
  width: 92,
  height: 92,
  borderRadius: "var(--r-tile)",
  border: "1px solid var(--hairline-strong)",
  position: "relative",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  overflow: "hidden",
  backgroundImage: url ? `url(${url})` : undefined,
  backgroundSize: "cover",
  backgroundPosition: "center",
  background: url ? undefined : "var(--panel-2)",
});
const castLabel: React.CSSProperties = {
  position: "absolute",
  bottom: 0,
  left: 0,
  right: 0,
  padding: "3px 5px",
  background: "rgba(14,13,11,0.72)",
  fontSize: 9,
  textAlign: "center",
};
