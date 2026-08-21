import { Link } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import logo from "@/assets/kheti_setu_logo.png";

export function Logo({ className = "h-10" }: { className?: string }) {
  const { t } = useTranslation();

  return (
    <Link to="/" className="inline-flex shrink-0 items-center px-1 py-1" aria-label={t("nav.home")}>
      <img src={logo} alt={t("nav.logoAlt")} className={`${className} w-auto`} />
    </Link>
  );
}
