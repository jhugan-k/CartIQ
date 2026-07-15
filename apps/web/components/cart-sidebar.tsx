"use client";

import { useState } from "react";
import {
  Minus,
  Plus,
  ShoppingCart,
  Sparkles,
  SquarePen,
  Trash2,
  X,
} from "lucide-react";
import { Logo } from "@/components/logo";
import { BrandMark, type Platform } from "@/components/brand";
import type { CartLineItem } from "@/lib/api";

const PLATFORMS: Platform[] = ["blinkit", "zepto", "swiggy"];

interface Props {
  items: CartLineItem[];
  onNewChat: () => void;
  onAdd: (name: string) => void;
  onUpdateQty: (id: string, qty: number) => void;
  onRemove: (id: string) => void;
  onClear: () => void;
  onCompare: () => void;
  onClose?: () => void; // mobile drawer close
}

export function CartSidebar({
  items,
  onNewChat,
  onAdd,
  onUpdateQty,
  onRemove,
  onClear,
  onCompare,
  onClose,
}: Props) {
  const [draft, setDraft] = useState("");
  const count = items.reduce((n, it) => n + it.quantity, 0);

  function submitAdd(e: React.FormEvent) {
    e.preventDefault();
    const name = draft.trim();
    if (!name) return;
    onAdd(name);
    setDraft("");
  }

  return (
    <div className="flex h-full w-72 shrink-0 flex-col border-r border-border bg-surface">
      {/* Brand + close (mobile) */}
      <div className="flex items-center justify-between px-4 py-4">
        <Logo />
        {onClose && (
          <button
            onClick={onClose}
            aria-label="Close menu"
            className="grid h-8 w-8 place-items-center rounded-lg text-muted hover:bg-elevated hover:text-text lg:hidden cursor-pointer"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* New chat */}
      <div className="px-3">
        <button
          onClick={onNewChat}
          className="flex w-full items-center gap-2 rounded-xl border border-border px-3 py-2.5 text-sm font-medium transition-colors hover:border-primary/50 hover:bg-elevated cursor-pointer"
        >
          <SquarePen className="h-4 w-4 text-primary" />
          New chat
        </button>
      </div>

      {/* Cart */}
      <div className="mt-5 flex min-h-0 flex-1 flex-col">
        <div className="flex items-center justify-between px-4 pb-2">
          <div className="flex items-center gap-2 text-sm font-semibold">
            <ShoppingCart className="h-4 w-4 text-primary" />
            Your cart
            <span className="rounded-full bg-primary/15 px-1.5 py-0.5 text-[11px] font-medium text-primary">
              {count}
            </span>
          </div>
          {items.length > 0 && (
            <button
              onClick={onClear}
              className="text-xs text-muted hover:text-red-500 cursor-pointer"
            >
              Clear
            </button>
          )}
        </div>

        {/* Item list */}
        <div className="min-h-0 flex-1 overflow-y-auto px-3">
          {items.length === 0 ? (
            <p className="px-1 py-6 text-center text-xs leading-relaxed text-muted">
              Your cart is empty. Add items below, or just ask —
              <span className="text-text"> &ldquo;add coke zero to my cart&rdquo;</span>.
            </p>
          ) : (
            <ul className="flex flex-col gap-2">
              {items.map((it) => (
                <li
                  key={it.id}
                  className="group flex items-center gap-2 rounded-xl border border-border bg-bg px-3 py-2"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5">
                      {it.platform && PLATFORMS.includes(it.platform) && (
                        <BrandMark
                          platform={it.platform}
                          className="h-4 w-4 shrink-0 text-[8px]"
                        />
                      )}
                      <span className="truncate text-sm capitalize">{it.name}</span>
                      {it.added_by === "assistant" && !it.platform && (
                        <span
                          title="Added by CartIQ"
                          className="inline-flex shrink-0 items-center gap-0.5 rounded bg-primary/15 px-1 py-0.5 text-[9px] font-medium text-primary"
                        >
                          <Sparkles className="h-2.5 w-2.5" />
                          AI
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => onUpdateQty(it.id, it.quantity - 1)}
                      disabled={it.quantity <= 1}
                      aria-label="Decrease quantity"
                      className="grid h-6 w-6 place-items-center rounded-md border border-border text-muted transition-colors hover:text-text disabled:opacity-40 cursor-pointer disabled:cursor-not-allowed"
                    >
                      <Minus className="h-3 w-3" />
                    </button>
                    <span className="w-5 text-center text-sm tabular-nums">
                      {it.quantity}
                    </span>
                    <button
                      onClick={() => onUpdateQty(it.id, it.quantity + 1)}
                      aria-label="Increase quantity"
                      className="grid h-6 w-6 place-items-center rounded-md border border-border text-muted transition-colors hover:text-text cursor-pointer"
                    >
                      <Plus className="h-3 w-3" />
                    </button>
                  </div>
                  <button
                    onClick={() => onRemove(it.id)}
                    aria-label={`Remove ${it.name}`}
                    className="grid h-6 w-6 place-items-center rounded-md text-faint opacity-0 transition-all hover:text-red-500 group-hover:opacity-100 cursor-pointer"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Add item + compare */}
        <div className="border-t border-border p-3">
          <form onSubmit={submitAdd} className="flex items-center gap-2">
            <input
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Add an item…"
              className="min-w-0 flex-1 rounded-lg border border-border bg-bg px-3 py-2 text-sm outline-none placeholder:text-faint focus:border-primary/60"
            />
            <button
              type="submit"
              disabled={!draft.trim()}
              aria-label="Add item"
              className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-primary text-primary-fg transition-colors hover:bg-primary-hover disabled:opacity-40 cursor-pointer disabled:cursor-not-allowed"
            >
              <Plus className="h-4 w-4" />
            </button>
          </form>
          <button
            onClick={onCompare}
            disabled={items.length === 0}
            className="mt-2 w-full rounded-lg border border-primary/40 bg-primary/10 py-2 text-sm font-medium text-primary transition-colors hover:bg-primary/20 disabled:opacity-40 cursor-pointer disabled:cursor-not-allowed"
          >
            Compare this cart
          </button>
        </div>
      </div>
    </div>
  );
}
