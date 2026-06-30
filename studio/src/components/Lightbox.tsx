import { useEffect, type ReactNode } from "react";

export function Lightbox({ onClose, children }: { onClose: () => void; children: ReactNode }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(8,7,5,0.86)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 100,
        padding: 40,
      }}
    >
      <div onClick={(e) => e.stopPropagation()} style={{ maxWidth: "92vw", maxHeight: "92vh" }}>
        {children}
      </div>
      <button
        className="ghost"
        onClick={onClose}
        style={{ position: "fixed", top: 24, right: 24 }}
      >
        Close
      </button>
    </div>
  );
}
