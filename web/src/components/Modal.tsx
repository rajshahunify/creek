import { ReactNode, useEffect, useRef } from "react";
import { Close } from "./Icons";

/** A dialog over the page: Esc or a click outside closes it, and focus comes back where it was. */
export function Modal({ title, onClose, children, className = "", hideTitle }: {
  title: string; onClose: () => void; children: ReactNode; className?: string; hideTitle?: boolean;
}) {
  const box = useRef<HTMLDivElement>(null);
  const close = useRef(onClose);
  close.current = onClose;
  useEffect(() => {
    const before = document.activeElement as HTMLElement | null;
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") { e.preventDefault(); close.current(); } };
    document.addEventListener("keydown", esc);
    box.current?.querySelector<HTMLElement>("input, button:not(.close), [tabindex]")?.focus();
    return () => { document.removeEventListener("keydown", esc); before?.focus?.(); };
  }, []);
  return (
    <div className="backdrop" onPointerDown={(e) => e.target === e.currentTarget && onClose()}>
      <div ref={box} className={`dialog ${className}`} role="dialog" aria-modal="true" aria-label={title}>
        {!hideTitle && (
          <header className="dialog-head">
            <h2>{title}</h2>
            <button className="icon small close" onClick={onClose} aria-label="Close"><Close /></button>
          </header>
        )}
        {children}
      </div>
    </div>
  );
}

export function Confirm({ title, yes, onYes, onClose, children }: {
  title: string; yes: string; onYes: () => void; onClose: () => void; children: ReactNode;
}) {
  return (
    <Modal title={title} onClose={onClose} className="confirm">
      <p>{children}</p>
      <div className="dialog-actions">
        <button className="btn" onClick={onClose}>Keep it</button>
        <button className="btn danger" onClick={onYes}>{yes}</button>
      </div>
    </Modal>
  );
}
