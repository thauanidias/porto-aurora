export type PortalArea = "LOCAL" | "CANDIDATO" | "RH" | "GESTOR";
export const portal: { area: PortalArea; publicUrl: string } = { area: "LOCAL", publicUrl: "" };

export async function loadPortal() {
  const response = await fetch("/portal-config.json", { cache: "no-store" });
  if (!response.ok) throw new Error("Portal indisponível");
  const config = await response.json();
  if (!["LOCAL", "CANDIDATO", "RH", "GESTOR"].includes(config.area)) throw new Error("Portal inválido");
  if (config.area !== "LOCAL" && !/^https?:\/\//.test(config.publicUrl)) throw new Error("Endereço inválido");
  portal.area = config.area;
  portal.publicUrl = config.publicUrl;
}

export function portalHome() {
  return portal.area === "RH" ? "/app" : portal.area === "GESTOR" ? "/gestor" : "/carreiras";
}
