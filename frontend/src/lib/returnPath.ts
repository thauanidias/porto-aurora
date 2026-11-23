export function safeReturnPath(value: string | null | undefined) {
  if (!value || !value.startsWith("/") || value.startsWith("//") || value.includes("\\") || [...value].some((char) => char.charCodeAt(0) < 32)) return undefined;
  return value;
}

export function registrationReturnPath() {
  const params = new URLSearchParams(window.location.search);
  const next = safeReturnPath(params.get("next"));
  if (next) sessionStorage.setItem("tgpm-registration-return", next);
  let saved = next ?? safeReturnPath(sessionStorage.getItem("tgpm-registration-return"));
  if (saved?.startsWith("/candidato/perfil?")) {
    saved = safeReturnPath(new URLSearchParams(saved.split("?")[1]).get("next"));
  }
  return saved && /^(\/carreiras\/vagas\/|\/oportunidades-internas\/|\/convite)/.test(saved) ? saved : undefined;
}
