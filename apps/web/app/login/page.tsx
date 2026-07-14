"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowRight,
  Check,
  Eye,
  EyeOff,
  Loader2,
  Lock,
  Mail,
  Sparkles,
  TriangleAlert,
} from "lucide-react";
import { useAuth } from "@/lib/auth";
import { ApiError } from "@/lib/api";
import { Logo, LogoMark } from "@/components/logo";
import { ThemeToggle } from "@/components/theme-toggle";
import { BRANDS, BrandMark, type Platform } from "@/components/brand";

const PERKS = [
  "Compare Blinkit, Zepto & Swiggy in one place",
  "Find the cheapest basket in seconds",
  "Fake-discount detection built in",
];

const PLATFORMS: Platform[] = ["blinkit", "zepto", "swiggy"];

export default function LoginPage() {
  const { login, register } = useAuth();
  const router = useRouter();

  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const isRegister = mode === "register";

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (isRegister) await register(email, password);
      else await login(email, password);
      router.push("/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-dvh flex-1">
      {/* Brand panel */}
      <aside className="aurora relative hidden w-[46%] flex-col justify-between overflow-hidden border-r border-border p-10 lg:flex">
        <Logo />
        <div className="max-w-md">
          <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-border bg-surface/60 px-3 py-1 text-xs text-muted backdrop-blur">
            <Sparkles className="h-3.5 w-3.5 text-primary" />
            AI-powered shopping assistant
          </div>
          <h2 className="text-3xl font-semibold leading-tight tracking-tight">
            One cart.
            <br />
            Every price.
            <br />
            <span className="text-primary">Instantly compared.</span>
          </h2>
          <ul className="mt-7 flex flex-col gap-3">
            {PERKS.map((p) => (
              <li key={p} className="flex items-center gap-3 text-sm text-muted">
                <span className="grid h-5 w-5 place-items-center rounded-full bg-primary/15 text-primary">
                  <Check className="h-3 w-3" />
                </span>
                {p}
              </li>
            ))}
          </ul>
        </div>
        <div className="flex items-center gap-3">
          {PLATFORMS.map((p) => (
            <div
              key={p}
              className="flex flex-col items-center gap-2 rounded-xl border border-border bg-surface/60 px-4 py-3 backdrop-blur"
            >
              <BrandMark platform={p} className="h-9 w-9 text-base" />
              <span className="inline-flex items-center gap-1.5 text-xs text-muted">
                <span
                  className="h-2 w-2 rounded-full"
                  style={{ background: BRANDS[p].color }}
                />
                {BRANDS[p].label}
              </span>
            </div>
          ))}
        </div>
      </aside>

      {/* Form panel */}
      <section className="relative flex flex-1 items-center justify-center p-6">
        <div className="absolute right-5 top-5">
          <ThemeToggle />
        </div>

        <div className="w-full max-w-sm">
          <div className="mb-8 flex flex-col items-center text-center lg:hidden">
            <LogoMark className="h-11 w-11" />
          </div>

          <h1 className="text-2xl font-semibold tracking-tight">
            {isRegister ? "Create your account" : "Welcome back"}
          </h1>
          <p className="mt-1.5 text-sm text-muted">
            {isRegister
              ? "Start comparing carts across every app."
              : "Log in to pick up where you left off."}
          </p>

          <form onSubmit={handleSubmit} className="mt-7 flex flex-col gap-3.5">
            <label className="flex flex-col gap-1.5">
              <span className="text-xs font-medium text-muted">Email</span>
              <div className="relative">
                <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-faint" />
                <input
                  type="email"
                  required
                  autoComplete="email"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full rounded-xl border border-border bg-surface py-2.5 pl-10 pr-3 text-sm outline-none transition-colors placeholder:text-faint focus:border-primary"
                />
              </div>
            </label>

            <label className="flex flex-col gap-1.5">
              <span className="text-xs font-medium text-muted">Password</span>
              <div className="relative">
                <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-faint" />
                <input
                  type={showPw ? "text" : "password"}
                  required
                  minLength={8}
                  autoComplete={isRegister ? "new-password" : "current-password"}
                  placeholder={isRegister ? "At least 8 characters" : "Your password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full rounded-xl border border-border bg-surface py-2.5 pl-10 pr-10 text-sm outline-none transition-colors placeholder:text-faint focus:border-primary"
                />
                <button
                  type="button"
                  onClick={() => setShowPw((s) => !s)}
                  aria-label={showPw ? "Hide password" : "Show password"}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 rounded-md p-1 text-faint transition-colors hover:text-text cursor-pointer"
                >
                  {showPw ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </label>

            {error && (
              <div className="flex items-start gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-500">
                <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={busy}
              className="group mt-1 inline-flex items-center justify-center gap-2 rounded-xl bg-primary py-2.5 text-sm font-semibold text-primary-fg shadow-sm transition-all hover:bg-primary-hover disabled:opacity-60 cursor-pointer"
            >
              {busy ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <>
                  {isRegister ? "Create account" : "Log in"}
                  <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
                </>
              )}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-muted">
            {isRegister ? "Already have an account?" : "New to CartIQ?"}{" "}
            <button
              onClick={() => {
                setMode(isRegister ? "login" : "register");
                setError(null);
              }}
              className="font-medium text-primary hover:underline cursor-pointer"
            >
              {isRegister ? "Log in" : "Create one"}
            </button>
          </p>
        </div>
      </section>
    </main>
  );
}
