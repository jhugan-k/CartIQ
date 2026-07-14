"use client";

import { useRef, useState } from "react";
import { Check, MapPin } from "lucide-react";
import { useClickOutside } from "@/lib/use-click-outside";

interface Props {
  pincode: string;
  onChange: (pincode: string) => void;
}

export function LocationMenu({ pincode, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState(pincode);
  const ref = useRef<HTMLDivElement>(null);
  useClickOutside(ref, () => setOpen(false), open);

  function save(e: React.FormEvent) {
    e.preventDefault();
    const pin = draft.replace(/\D/g, "").slice(0, 6);
    if (pin.length === 6) {
      onChange(pin);
      setOpen(false);
    }
  }

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => {
          setDraft(pincode);
          setOpen((o) => !o);
        }}
        aria-label="Set delivery pincode"
        className="flex items-center gap-1.5 rounded-lg border border-border px-2.5 py-1.5 text-sm text-muted transition-colors hover:bg-elevated hover:text-text cursor-pointer"
      >
        <MapPin className="h-4 w-4 text-primary" />
        <span className="tabular-nums">{pincode}</span>
      </button>

      {open && (
        <div className="absolute right-0 z-30 mt-2 w-64 animate-fade-up rounded-xl border border-border bg-surface p-3 shadow-lg">
          <p className="mb-2 text-xs font-medium text-muted">
            Delivery pincode — prices &amp; availability are location-specific.
          </p>
          <form onSubmit={save} className="flex items-center gap-2">
            <input
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              inputMode="numeric"
              maxLength={6}
              placeholder="e.g. 110063"
              className="min-w-0 flex-1 rounded-lg border border-border bg-bg px-3 py-2 text-sm tabular-nums outline-none placeholder:text-faint focus:border-primary/60"
            />
            <button
              type="submit"
              disabled={draft.replace(/\D/g, "").length !== 6}
              aria-label="Save pincode"
              className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-primary text-primary-fg transition-colors hover:bg-primary-hover disabled:opacity-40 cursor-pointer disabled:cursor-not-allowed"
            >
              <Check className="h-4 w-4" />
            </button>
          </form>
        </div>
      )}
    </div>
  );
}
