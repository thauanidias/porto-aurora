import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";

export function PostalCodeInput({ title, value, onChange, onAddress }: {
  title: string; value: string; onChange: (value: string) => void;
  onAddress: (address: Record<string, string>) => void;
}) {
  const [edited, setEdited] = useState(false);
  const [status, setStatus] = useState("");
  const apply = useRef(onAddress);
  apply.current = onAddress;
  useEffect(() => {
    if (!edited) return;
    const digits = value.replace(/\D/g, "");
    setStatus("");
    if (digits.length !== 8) return;
    let cancelled = false;
    const timer = setTimeout(async () => {
      setStatus("Consultando CEP…");
      try {
        const address = await api<Record<string, string>>("/public/postal-code/" + digits);
        if (!cancelled) {
          apply.current(address);
          setStatus("Bairro, cidade e estado consultados. Confira os dados e complete o que faltar.");
        }
      } catch { if (!cancelled) setStatus("Não foi possível localizar o endereço. Preencha os campos manualmente."); }
    }, 350);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [value, edited]);
  return <label className="field"><span>{title}</span><input aria-label={title} inputMode="numeric" autoComplete="postal-code" placeholder="00000-000" value={value} maxLength={9} onChange={event => {
    setEdited(true);
    const digits = event.target.value.replace(/\D/g, "").slice(0, 8);
    onChange(digits.length > 5 ? digits.slice(0, 5) + "-" + digits.slice(5) : digits);
  }} />{status && <small role="status">{status}</small>}</label>;
}
