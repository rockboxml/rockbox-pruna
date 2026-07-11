import { useState } from "react";
import type { MediaArtifact } from "../api/types";
import { artifactUrl } from "../api/client";
import { Carousel } from "./Carousel";
import { Lightbox } from "./Lightbox";

/**
 * Renders an artifact (or a carousel of regenerate attempts) inline, expandable
 * to a full-view Lightbox. Video/audio degrade to a placeholder on media error
 * (fakes emit non-playable bytes; real backends play normally).
 */
export function ArtifactView({ artifacts }: { artifacts: MediaArtifact[] }) {
  const [expanded, setExpanded] = useState(false);
  if (!artifacts.length) return null;
  const a = artifacts[0];

  const renderOne = (full: boolean) => {
    const style: React.CSSProperties = full
      ? { maxWidth: "92vw", maxHeight: "92vh", display: "block" }
      : { width: "100%", maxHeight: 320, objectFit: "cover", display: "block", borderRadius: 6 };

    if (a.media_type === "image") {
      const urls = artifacts.map(artifactUrl);
      const img = (url: string) => <img src={url} alt="" style={style} />;
      return artifacts.length > 1 ? <Carousel urls={urls} render={img} /> : img(urls[0]);
    }
    if (a.media_type === "video") {
      return <Media tag="video" url={artifactUrl(a)} style={style} />;
    }
    if (a.media_type === "audio") {
      return <Media tag="audio" url={artifactUrl(a)} style={{ width: full ? 480 : "100%" }} />;
    }
    return <Placeholder label="Text artifact" />;
  };

  return (
    <div style={{ marginTop: 12 }}>
      <div className="panel" style={{ overflow: "hidden", padding: a.media_type === "audio" ? 14 : 0 }}>
        {renderOne(false)}
      </div>
      <button className="ghost label" onClick={() => setExpanded(true)} style={{ marginTop: 8, border: "none", padding: 0 }}>
        Expand ⤢
      </button>
      {expanded && <Lightbox onClose={() => setExpanded(false)}>{renderOne(true)}</Lightbox>}
    </div>
  );
}

function Media({ tag, url, style }: { tag: "video" | "audio"; url: string; style: React.CSSProperties }) {
  const [failed, setFailed] = useState(false);
  if (failed) return <Placeholder label={`${tag} preview needs a real backend`} />;
  return tag === "video" ? (
    <video src={url} controls style={style} onError={() => setFailed(true)} />
  ) : (
    <audio src={url} controls style={style} onError={() => setFailed(true)} />
  );
}

function Placeholder({ label }: { label: string }) {
  return (
    <div
      className="label"
      style={{
        height: 120,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "var(--panel-2)",
        color: "var(--faint)",
      }}
    >
      {label}
    </div>
  );
}
