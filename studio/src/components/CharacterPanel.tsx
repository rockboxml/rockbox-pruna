import { useRef, useState } from "react";
import { createCastMember } from "../api/client";
import type { CastMember } from "../api/types";

/** A small modal to define a Character or Location and upload a reference image. */
export function CharacterPanel({
  kind,
  onClose,
  onCreated,
}: {
  kind: "character" | "location";
  onClose: () => void;
  onCreated: (m: CastMember) => void;
}) {
  const [name, setName] = useState("");
  const [appearance, setAppearance] = useState("");
  const [style, setStyle] = useState("");
  const [voiceId, setVoiceId] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const pick = (f: File | null) => {
    setFile(f);
    setPreview(f ? URL.createObjectURL(f) : null);
  };

  const save = async () => {
    if (!name.trim()) return;
    setBusy(true);
    try {
      const res = await createCastMember({ name, type: kind, appearance, style, voice_id: voiceId, file });
      onCreated({
        entity_id: res.id,
        name,
        type: kind,
        referenceUrl: res.references?.[0]?.url,
      });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div onClick={onClose} style={overlay}>
      <div onClick={(e) => e.stopPropagation()} className="panel" style={modal}>
        <div className="label" style={{ color: "var(--amber)" }}>
          New {kind}
        </div>

        <div style={{ display: "flex", gap: 16, marginTop: 16 }}>
          <button
            onClick={() => fileRef.current?.click()}
            style={{
              ...refTile,
              backgroundImage: preview ? `url(${preview})` : undefined,
              backgroundSize: "cover",
              backgroundPosition: "center",
            }}
          >
            {!preview && <span className="label">+ Ref</span>}
          </button>
          <input
            ref={fileRef}
            type="file"
            accept="image/*"
            hidden
            onChange={(e) => pick(e.target.files?.[0] ?? null)}
          />
          <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 10 }}>
            <Field label="Name" value={name} onChange={setName} placeholder={kind === "character" ? "Maya" : "Neon Apartment"} />
            <Field label="Appearance" value={appearance} onChange={setAppearance} placeholder="short black hair, red bomber jacket" />
            <Field label="Style" value={style} onChange={setStyle} placeholder="cinematic neon" />
            {kind === "character" && (
              <Field label="Voice id" value={voiceId} onChange={setVoiceId} placeholder="optional (e.g. vx_maya)" />
            )}
          </div>
        </div>

        <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, marginTop: 20 }}>
          <button className="ghost" onClick={onClose}>
            Cancel
          </button>
          <button className="primary" disabled={busy || !name.trim()} onClick={save}>
            {busy ? "Saving…" : "Add to cast"}
          </button>
        </div>
      </div>
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  return (
    <label style={{ display: "block" }}>
      <div className="label" style={{ marginBottom: 4 }}>
        {label}
      </div>
      <input
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        style={{ borderBottom: "1px solid var(--hairline)", padding: "4px 0" }}
      />
    </label>
  );
}

const overlay: React.CSSProperties = {
  position: "fixed",
  inset: 0,
  background: "rgba(8,7,5,0.7)",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  zIndex: 50,
  padding: 24,
};
const modal: React.CSSProperties = { width: 560, maxWidth: "100%", padding: 24, background: "var(--panel-1)" };
const refTile: React.CSSProperties = {
  width: 96,
  height: 96,
  border: "1px dashed var(--hairline-strong)",
  borderRadius: "var(--r-tile)",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  flex: "0 0 auto",
};
