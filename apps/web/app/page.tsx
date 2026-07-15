"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowUp,
  Layers,
  LogOut,
  Menu,
  Search,
  ShoppingCart,
  Shuffle,
  Sparkles,
  TriangleAlert,
} from "lucide-react";
import { useAuth } from "@/lib/auth";
import { api, ApiError, type CartLineItem, type ChatMessage } from "@/lib/api";
import { LogoMark } from "@/components/logo";
import { Markdown } from "@/components/markdown";
import { ThemeToggle } from "@/components/theme-toggle";
import { CartSidebar } from "@/components/cart-sidebar";
import { WishlistMenu } from "@/components/wishlist-menu";
import { LocationMenu } from "@/components/location-menu";
import { BrandStrip } from "@/components/brand";

const DEFAULT_PINCODE = "110063";

interface DisplayMessage extends ChatMessage {
  tools?: string[];
}

const SUGGESTIONS = [
  { icon: Layers, title: "Compare a basket", prompt: "Cheapest place for 2 butter and 1 milk?" },
  { icon: Search, title: "Check one product", prompt: "Compare paneer prices across apps" },
  { icon: Sparkles, title: "Spot fake discounts", prompt: "Any fake discounts on bread right now?" },
];

const TOOL_META: Record<string, { label: string; icon: typeof Search }> = {
  tool_search: { label: "Searched prices", icon: Search },
  tool_compare: { label: "Compared cart", icon: Layers },
  tool_alternatives: { label: "Found alternatives", icon: Shuffle },
  tool_add_to_cart: { label: "Updated cart", icon: ShoppingCart },
  tool_remove_from_cart: { label: "Updated cart", icon: ShoppingCart },
  tool_view_cart: { label: "Checked cart", icon: ShoppingCart },
};

function ToolBadges({ tools }: { tools: string[] }) {
  const seen = new Set<string>();
  const unique = tools.filter((t) => !seen.has(t) && seen.add(t));
  return (
    <div className="mt-2.5 flex flex-wrap gap-1.5">
      {unique.map((t) => {
        const meta = TOOL_META[t] ?? { label: t, icon: Sparkles };
        const Icon = meta.icon;
        return (
          <span
            key={t}
            className="inline-flex items-center gap-1.5 rounded-full border border-border bg-bg/60 px-2.5 py-0.5 text-[11px] font-medium text-muted"
          >
            <Icon className="h-3 w-3 text-primary" />
            {meta.label}
          </span>
        );
      })}
    </div>
  );
}

export default function ChatPage() {
  const { user, loading, logout } = useAuth();
  const router = useRouter();

  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cart, setCart] = useState<CartLineItem[]>([]);
  const [cartOpen, setCartOpen] = useState(false); // mobile drawer
  const [pincode, setPincode] = useState(DEFAULT_PINCODE);
  const bottomRef = useRef<HTMLDivElement>(null);
  const taRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  // Persist the chosen pincode across sessions.
  useEffect(() => {
    const saved = localStorage.getItem("cartiq_pincode");
    if (saved) setPincode(saved);
  }, []);
  const changePincode = (pin: string) => {
    setPincode(pin);
    localStorage.setItem("cartiq_pincode", pin);
  };

  const refreshCart = useCallback(async () => {
    try {
      const state = await api.cart.get();
      setCart(state.items);
    } catch {
      /* ignore — cart is best-effort */
    }
  }, []);

  useEffect(() => {
    if (user) refreshCart();
  }, [user, refreshCart]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  function autoGrow() {
    const el = taRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 160) + "px";
  }

  const send = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || sending) return;
      setError(null);
      setCartOpen(false);
      const history: ChatMessage[] = messages.map(({ role, text }) => ({ role, text }));
      setMessages((m) => [...m, { role: "user", text: trimmed }]);
      setInput("");
      if (taRef.current) taRef.current.style.height = "auto";
      setSending(true);
      try {
        const res = await api.chat(trimmed, history, pincode);
        setMessages((m) => [...m, { role: "model", text: res.reply, tools: res.tools_used }]);
        // The agent may have changed the cart — pull the latest.
        if (res.tools_used.some((t) => t.includes("cart"))) refreshCart();
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Request failed");
      } finally {
        setSending(false);
      }
    },
    [messages, sending, refreshCart, pincode]
  );

  // ---- Cart handlers (optimistic-ish: replace with server truth) ----
  const cartAdd = async (name: string) => setCart((await api.cart.add(name)).items);
  const cartQty = async (id: string, qty: number) => {
    if (qty < 1) return;
    setCart((await api.cart.updateQty(id, qty)).items);
  };
  const cartRemove = async (id: string) => setCart((await api.cart.remove(id)).items);
  const cartClear = async () => setCart((await api.cart.clear()).items);
  const cartCompare = () =>
    send("Compare everything currently in my cart and tell me which app is cheapest overall.");
  const newChat = () => {
    setMessages([]);
    setError(null);
    setCartOpen(false);
  };

  if (loading || !user) {
    return (
      <main className="grid flex-1 place-items-center">
        <LogoMark className="h-9 w-9 animate-pulse" />
      </main>
    );
  }

  const empty = messages.length === 0;

  const sidebar = (
    <CartSidebar
      items={cart}
      onNewChat={newChat}
      onAdd={cartAdd}
      onUpdateQty={cartQty}
      onRemove={cartRemove}
      onClear={cartClear}
      onCompare={cartCompare}
      onClose={() => setCartOpen(false)}
    />
  );

  return (
    <div className="flex h-dvh">
      {/* Desktop sidebar */}
      <div className="hidden lg:flex">{sidebar}</div>

      {/* Mobile drawer */}
      {cartOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div
            className="absolute inset-0 bg-black/50"
            onClick={() => setCartOpen(false)}
          />
          <div className="absolute left-0 top-0 h-full animate-fade-up">{sidebar}</div>
        </div>
      )}

      {/* Main column */}
      <main className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex items-center justify-between border-b border-border bg-bg/80 px-4 py-3 backdrop-blur-md sm:px-6">
          <button
            onClick={() => setCartOpen(true)}
            aria-label="Open menu and cart"
            className="grid h-9 w-9 place-items-center rounded-lg border border-border text-muted hover:bg-elevated hover:text-text lg:hidden cursor-pointer"
          >
            <Menu className="h-4 w-4" />
          </button>
          <div className="hidden lg:block" />
          <div className="flex items-center gap-2">
            <LocationMenu pincode={pincode} onChange={changePincode} />
            <WishlistMenu onAddToCart={cartAdd} />
            <ThemeToggle />
            <div className="hidden items-center gap-2 rounded-lg border border-border px-3 py-1.5 text-sm text-muted sm:flex">
              <span className="grid h-5 w-5 place-items-center rounded-full bg-primary/15 text-[10px] font-semibold text-primary">
                {user.email[0]?.toUpperCase()}
              </span>
              <span className="max-w-40 truncate">{user.email}</span>
            </div>
            <button
              onClick={logout}
              aria-label="Log out"
              className="grid h-9 w-9 place-items-center rounded-lg border border-border text-muted transition-colors hover:bg-elevated hover:text-text cursor-pointer"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </header>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-3xl px-4 py-6 sm:px-6">
            {empty ? (
              <div className="flex flex-col items-center pt-[8vh] text-center">
                <div className="aurora grid h-16 w-16 place-items-center rounded-2xl border border-border">
                  <LogoMark className="h-9 w-9" />
                </div>
                <h1 className="mt-5 text-2xl font-semibold tracking-tight">
                  What are we buying today?
                </h1>
                <p className="mt-2 max-w-md text-sm text-muted">
                  Ask in plain English. I&apos;ll check Blinkit, Zepto and Swiggy Instamart,
                  build your cart, and find the cheapest way to fill it.
                </p>
                <div className="mt-8 grid w-full gap-3 sm:grid-cols-3">
                  {SUGGESTIONS.map((s) => (
                    <button
                      key={s.prompt}
                      onClick={() => send(s.prompt)}
                      className="group flex flex-col gap-2 rounded-2xl border border-border bg-surface p-4 text-left transition-all hover:border-primary/50 hover:shadow-md cursor-pointer"
                    >
                      <span className="grid h-8 w-8 place-items-center rounded-lg bg-primary/15 text-primary">
                        <s.icon className="h-4 w-4" />
                      </span>
                      <span className="text-sm font-medium">{s.title}</span>
                      <span className="text-xs leading-snug text-muted">{s.prompt}</span>
                    </button>
                  ))}
                </div>
                <BrandStrip className="mt-8" />
              </div>
            ) : (
              <div className="flex flex-col gap-6">
                {messages.map((m, i) =>
                  m.role === "user" ? (
                    <div key={i} className="flex animate-fade-up justify-end">
                      <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-md bg-user px-4 py-2.5 text-sm text-user-fg shadow-sm">
                        {m.text}
                      </div>
                    </div>
                  ) : (
                    <div key={i} className="flex animate-fade-up gap-3">
                      <span className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg border border-border bg-surface">
                        <LogoMark className="h-5 w-5" />
                      </span>
                      <div className="min-w-0 flex-1 rounded-2xl rounded-tl-md border border-border bg-surface px-4 py-3 shadow-sm">
                        <Markdown>{m.text}</Markdown>
                        {m.tools && m.tools.length > 0 && <ToolBadges tools={m.tools} />}
                      </div>
                    </div>
                  )
                )}

                {sending && (
                  <div className="flex animate-fade-up gap-3">
                    <span className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg border border-border bg-surface">
                      <LogoMark className="h-5 w-5" />
                    </span>
                    <div className="flex flex-col gap-1.5">
                      <div className="flex w-fit items-center gap-1.5 rounded-2xl rounded-tl-md border border-border bg-surface px-4 py-3.5">
                        <span className="typing-dot" />
                        <span className="typing-dot" />
                        <span className="typing-dot" />
                      </div>
                      <span className="pl-1 text-[11px] text-faint">
                        QuickCommerce API may take longer to respond for multiple items.
                      </span>
                    </div>
                  </div>
                )}

                {error && (
                  <div className="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-500">
                    <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" />
                    <span>{error}</span>
                  </div>
                )}
                <div ref={bottomRef} />
              </div>
            )}
          </div>
        </div>

        {/* Composer */}
        <div className="border-t border-border bg-bg/80 px-4 py-4 backdrop-blur-md sm:px-6">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              send(input);
            }}
            className="mx-auto w-full max-w-3xl"
          >
            <div className="flex items-end gap-2 rounded-2xl border border-border bg-surface p-2 shadow-sm transition-colors focus-within:border-primary/60">
              <textarea
                ref={taRef}
                value={input}
                rows={1}
                onChange={(e) => {
                  setInput(e.target.value);
                  autoGrow();
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    send(input);
                  }
                }}
                placeholder="Ask about prices, or say “add milk to my cart”…"
                className="max-h-40 flex-1 resize-none bg-transparent px-2 py-1.5 text-sm outline-none placeholder:text-faint"
              />
              <button
                type="submit"
                disabled={sending || !input.trim()}
                aria-label="Send message"
                className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-primary text-primary-fg transition-all hover:bg-primary-hover disabled:opacity-40 cursor-pointer disabled:cursor-not-allowed"
              >
                <ArrowUp className="h-4 w-4" />
              </button>
            </div>
            <p className="mt-2 text-center text-[11px] text-faint">
              Prices are indicative and may vary. CartIQ can make mistakes.
            </p>
          </form>
        </div>
      </main>
    </div>
  );
}
