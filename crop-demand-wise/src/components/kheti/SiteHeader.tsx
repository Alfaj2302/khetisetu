import { Link } from "@tanstack/react-router";
import { Menu, Sprout, X } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { LanguageSwitcher } from "./LanguageSwitcher";
import { Logo } from "./Logo";

const NAV = [
  { to: "/farmer", labelKey: "nav.farmer" },
  { to: "/business", labelKey: "nav.business" },
  { to: "/how-it-works", labelKey: "nav.howItWorks" },
  { to: "/reliability", labelKey: "nav.reliability" },
  { to: "/ask", labelKey: "nav.ask" },
] as const;

export function SiteHeader() {
  const [open, setOpen] = useState(false);
  const { t } = useTranslation();

  return (
    <header className="sticky top-0 z-40 border-b border-border bg-card/90 backdrop-blur">
      <div className="mx-auto grid max-w-7xl grid-cols-[minmax(0,1fr)_auto] items-center gap-3 px-4 py-3 md:px-6">
        <div className="flex min-w-0 items-center gap-6">
          <Logo className="h-9 md:h-11" />
          <nav aria-label={t("nav.main")} className="hidden items-center gap-1 lg:flex">
            {NAV.map((item) => (
              <Link
                key={item.to}
                to={item.to}
                className="rounded-md px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                activeProps={{ className: "bg-muted text-primary" }}
              >
                {t(item.labelKey)}
              </Link>
            ))}
          </nav>
        </div>

        <div className="flex items-center gap-2">
          <LanguageSwitcher />
          <Link
            to="/farmer"
            className="hidden items-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground shadow-card transition-colors hover:bg-primary-dark active:bg-primary-dark md:inline-flex"
          >
            <Sprout className="h-4 w-4" aria-hidden />
            {t("common.findBestCrops")}
          </Link>
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
            aria-label={open ? t("nav.closeMenu") : t("nav.openMenu")}
            className="inline-flex h-11 w-11 items-center justify-center rounded-lg border border-border text-foreground lg:hidden"
          >
            {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
      </div>

      {open && (
        <nav
          aria-label={t("nav.mobile")}
          className="border-t border-border bg-card px-4 py-3 lg:hidden"
        >
          <ul className="flex flex-col gap-1">
            {NAV.map((item) => (
              <li key={item.to}>
                <Link
                  to={item.to}
                  onClick={() => setOpen(false)}
                  className="block rounded-lg px-3 py-3 text-base font-medium text-foreground hover:bg-muted"
                  activeProps={{ className: "bg-muted text-primary" }}
                >
                  {t(item.labelKey)}
                </Link>
              </li>
            ))}
            <li className="pt-2">
              <Link
                to="/farmer"
                onClick={() => setOpen(false)}
                className="flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 py-3 text-base font-semibold text-primary-foreground"
              >
                <Sprout className="h-4 w-4" aria-hidden /> {t("common.findBestCrops")}
              </Link>
            </li>
          </ul>
        </nav>
      )}
    </header>
  );
}
