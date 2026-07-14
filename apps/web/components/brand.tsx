// Small brand marks for the quick-commerce apps. Rounded tiles with the brand
// colour + initial — recognizable without misusing official trademarks.

export type Platform = "blinkit" | "zepto" | "swiggy";

export const BRANDS: Record<
  Platform,
  { label: string; color: string; fg: string; letter: string }
> = {
  blinkit: { label: "Blinkit", color: "#F8CB46", fg: "#1a1a1a", letter: "b" },
  zepto: { label: "Zepto", color: "#7C3AED", fg: "#ffffff", letter: "Z" },
  swiggy: { label: "Swiggy", color: "#FC8019", fg: "#ffffff", letter: "S" },
};

export function BrandMark({
  platform,
  className = "h-8 w-8 text-sm",
}: {
  platform: Platform;
  className?: string;
}) {
  const b = BRANDS[platform];
  return (
    <span
      className={`grid place-items-center rounded-lg font-bold leading-none ${className}`}
      style={{ background: b.color, color: b.fg }}
      aria-hidden="true"
    >
      {b.letter}
    </span>
  );
}
