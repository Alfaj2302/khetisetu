import { Link } from "@tanstack/react-router";
import logo from "@/assets/kheti_setu_logo.png";

export function Logo({ className = "h-10" }: { className?: string }) {
  return (
    <Link to="/" className="inline-flex shrink-0 items-center px-1 py-1" aria-label="KhetiSetu home">
      <img src={logo} alt="KhetiSetu — From crop decisions to smart supply" className={`${className} w-auto`} />
    </Link>
  );
}
