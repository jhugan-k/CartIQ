"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Heart, Loader2, Plus, ShoppingCart, Trash2 } from "lucide-react";
import { api, type WishlistItem } from "@/lib/api";
import { useClickOutside } from "@/lib/use-click-outside";

interface Props {
  /** Add a wishlist item to the virtual cart. */
  onAddToCart: (name: string) => void;
}

export function WishlistMenu({ onAddToCart }: Props) {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<WishlistItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [draft, setDraft] = useState("");
  const ref = useRef<HTMLDivElement>(null);
  useClickOutside(ref, () => setOpen(false), open);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setItems(await api.wishlist.get());
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function add(e: React.FormEvent) {
    e.preventDefault();
    const name = draft.trim();
    if (!name) return;
    setDraft("");
    const created = await api.wishlist.add(name);
    setItems((xs) => [created, ...xs]);
  }

  async function remove(id: string) {
    setItems((xs) => xs.filter((x) => x.id !== id));
    try {
      await api.wishlist.remove(id);
    } catch {
      load(); // resync on failure
    }
  }

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        aria-label="Wishlist"
        className="relative grid h-9 w-9 place-items-center rounded-lg border border-border text-muted transition-colors hover:bg-elevated hover:text-text cursor-pointer"
      >
        <Heart className="h-4 w-4" />
        {items.length > 0 && (
          <span className="absolute -right-1 -top-1 grid h-4 min-w-4 place-items-center rounded-full bg-primary px-1 text-[10px] font-semibold text-primary-fg">
            {items.length}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 z-30 mt-2 w-72 animate-fade-up rounded-xl border border-border bg-surface shadow-lg">
          <div className="flex items-center gap-2 border-b border-border px-4 py-3 text-sm font-semibold">
            <Heart className="h-4 w-4 text-primary" />
            Wishlist
            {loading && <Loader2 className="ml-auto h-3.5 w-3.5 animate-spin text-muted" />}
          </div>

          <form onSubmit={add} className="flex items-center gap-2 p-3">
            <input
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Save a product… e.g. amul butter"
              className="min-w-0 flex-1 rounded-lg border border-border bg-bg px-3 py-2 text-sm outline-none placeholder:text-faint focus:border-primary/60"
            />
            <button
              type="submit"
              disabled={!draft.trim()}
              aria-label="Save to wishlist"
              className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-primary text-primary-fg transition-colors hover:bg-primary-hover disabled:opacity-40 cursor-pointer disabled:cursor-not-allowed"
            >
              <Plus className="h-4 w-4" />
            </button>
          </form>

          <div className="max-h-64 overflow-y-auto px-3 pb-3">
            {items.length === 0 ? (
              <p className="px-1 py-4 text-center text-xs text-muted">
                No saved products yet. Save things you buy often for quick access.
              </p>
            ) : (
              <ul className="flex flex-col gap-1.5">
                {items.map((it) => (
                  <li
                    key={it.id}
                    className="group flex items-center gap-2 rounded-lg border border-border bg-bg px-3 py-2"
                  >
                    <span className="min-w-0 flex-1 truncate text-sm capitalize">
                      {it.product_name}
                    </span>
                    <button
                      onClick={() => onAddToCart(it.product_query)}
                      title="Add to cart"
                      aria-label={`Add ${it.product_name} to cart`}
                      className="grid h-7 w-7 place-items-center rounded-md text-muted transition-colors hover:bg-primary/15 hover:text-primary cursor-pointer"
                    >
                      <ShoppingCart className="h-3.5 w-3.5" />
                    </button>
                    <button
                      onClick={() => remove(it.id)}
                      title="Remove"
                      aria-label={`Remove ${it.product_name} from wishlist`}
                      className="grid h-7 w-7 place-items-center rounded-md text-faint opacity-0 transition-all hover:text-red-500 group-hover:opacity-100 cursor-pointer"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
