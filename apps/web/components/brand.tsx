// Recreated brand marks for the quick-commerce apps — pure CSS/SVG, no embedded
// images. Rounded, softly ringed so they blend onto the dark background.

import { MapPin } from "lucide-react";

export type Platform = "blinkit" | "zepto" | "swiggy";

export const BRANDS: Record<Platform, { label: string; color: string }> = {
  blinkit: { label: "Blinkit", color: "#F8CB46" },
  zepto: { label: "Zepto", color: "#7C3AED" },
  swiggy: { label: "Swiggy", color: "#FC8019" },
};

const BACKGROUNDS: Record<Platform, string> = {
  blinkit: "#F8CB46",
  zepto: "radial-gradient(circle at 50% 32%, #c39bff 0%, #7c3aed 46%, #4a1d96 100%)",
  swiggy: "#1466F0",
};

export function BrandMark({
  platform,
  className = "h-8 w-8 text-sm",
}: {
  platform: Platform;
  className?: string;
}) {
  return (
    <span
      className={`relative grid shrink-0 place-items-center overflow-hidden rounded-[28%] font-black leading-none shadow-sm ring-1 ring-black/10 dark:ring-white/10 ${className}`}
      style={{ background: BACKGROUNDS[platform] }}
      aria-hidden="true"
    >
      {platform === "blinkit" && <span style={{ color: "#141414" }}>b</span>}
      {platform === "zepto" && <span style={{ color: "#ffffff" }}>Z</span>}
      {platform === "swiggy" && (
        <MapPin
          className="h-[58%] w-[58%]"
          style={{ color: "#FC8019" }}
          fill="#FC8019"
          strokeWidth={0}
        />
      )}
    </span>
  );
}

/** Inline "Compares prices across [b][Z][S]" strip. */
export function BrandStrip({ className = "" }: { className?: string }) {
  return (
    <div
      className={`flex items-center justify-center gap-2 text-xs text-muted ${className}`}
    >
      <span>Compares prices across</span>
      <span className="flex items-center gap-1.5">
        {(Object.keys(BRANDS) as Platform[]).map((p) => (
          <BrandMark key={p} platform={p} className="h-6 w-6 text-[11px]" />
        ))}
      </span>
    </div>
  );
}
