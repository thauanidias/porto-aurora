import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, str } from "../lib/api";

const defaultName = "Porto Aurora Talentos";
const defaultColor = "#145c67";
const defaultIcon = "/assets/brand/talentos-icon.svg";

function useBranding() {
  return useQuery({
    queryKey: ["branding"],
    queryFn: () => api<Record<string, unknown>>("/public/branding"),
    staleTime: 60000,
  });
}

export function Brand({ inverse = false }: { inverse?: boolean }) {
  return (
    <span className={"brand-lockup" + (inverse ? " brand-inverse" : "")}>
      <span className="brand-mark aurora-logo-frame">
        <img className="official-logo aurora-logo" src="/assets/brand/porto-aurora-logo.png" alt="Porto Aurora" />
      </span>
      <span className="brand-product">Talentos</span>
    </span>
  );
}

export function BrandSettings() {
  const { data } = useBranding();
  useEffect(() => {
    if (!data) return;
    document.title = defaultName;
    localStorage.setItem(
      "tgpm_timezone",
      str(data.timezone) || "America/Belem",
    );
    let icon = document.querySelector<HTMLLinkElement>('link[rel="icon"]');
    if (!icon) {
      icon = document.createElement("link");
      icon.rel = "icon";
      document.head.append(icon);
    }
    icon.href = str(data.favicon_url) || defaultIcon;
    const color = str(data.brand_color) || defaultColor;
    document.documentElement.style.setProperty("--configured-brand", color);
    document
      .querySelector('meta[name="theme-color"]')
      ?.setAttribute("content", color);
  }, [data]);
  return null;
}
