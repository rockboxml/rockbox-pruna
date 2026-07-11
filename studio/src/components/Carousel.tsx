import { useState } from "react";

export function Carousel({ urls, render }: { urls: string[]; render: (url: string) => JSX.Element }) {
  const [i, setI] = useState(0);
  const n = urls.length;
  const go = (d: number) => setI((p) => (p + d + n) % n);
  return (
    <div style={{ position: "relative" }}>
      {render(urls[i])}
      {n > 1 && (
        <>
          <button className="ghost" onClick={() => go(-1)} style={navStyle("left")}>
            ‹
          </button>
          <button className="ghost" onClick={() => go(1)} style={navStyle("right")}>
            ›
          </button>
          <div className="mono" style={counterStyle}>
            {i + 1}/{n}
          </div>
        </>
      )}
    </div>
  );
}

const navStyle = (side: "left" | "right"): React.CSSProperties => ({
  position: "absolute",
  top: "50%",
  [side]: 8,
  transform: "translateY(-50%)",
  padding: "2px 10px",
  background: "rgba(14,13,11,0.7)",
});

const counterStyle: React.CSSProperties = {
  position: "absolute",
  bottom: 8,
  right: 10,
  fontSize: 11,
  color: "var(--cream)",
  background: "rgba(14,13,11,0.7)",
  padding: "2px 7px",
  borderRadius: 10,
};
