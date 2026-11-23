import { useId, useRef, useState } from "react";
import { ChevronDown } from "lucide-react";

export function SearchSelect({ title, value, options, onChange, loading = false, error = false, allowClear = true, allowCustom = false, placeholder }: {
  allowCustom?: boolean;
  placeholder?: string;
  title: string;
  value: string;
  options: { value: string; label: string }[];
  onChange: (value: string) => void;
  loading?: boolean;
  error?: boolean;
  allowClear?: boolean;
}) {
  const id = useId();
  const input = useRef<HTMLInputElement>(null);
  const [search, setSearch] = useState<string | null>(null);
  const [active, setActive] = useState(-1);
  const [browse, setBrowse] = useState(false);
  const normalize = (text: string) => text.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  const open = browse || Boolean(search?.trim());
  const visible = open ? options.filter((option) => normalize(option.label).includes(normalize(search?.trim() ?? ""))) : [];
  const choose = (next: string) => {
    onChange(next);
    setSearch(null);
    setBrowse(false);
    setActive(-1);
    input.current?.focus();
  };
  return (
    <div className="search-select" onBlur={(event) => {
      if (!event.currentTarget.contains(event.relatedTarget)) {
        setSearch(null);
        setBrowse(false);
        setActive(-1);
      }
    }}>
      <div className="choice-input">
      <input
        ref={input}
        type="text"
        role="combobox"
        aria-label={title}
        aria-autocomplete="list"
        aria-expanded={open}
        aria-controls={open ? id : undefined}
        aria-activedescendant={open && active >= 0 ? `${id}-${active}` : undefined}
        autoComplete="off"
        placeholder={placeholder ?? "Selecione ou digite para buscar"}
        value={search ?? options.find((option) => option.value === value)?.label ?? (allowCustom ? value : "")}
        onFocus={() => { if (allowCustom) setBrowse(true); }}
        onChange={(event) => {
          setSearch(event.target.value);
          setBrowse(false);
          setActive(-1);
          if (allowCustom) onChange(event.target.value);
          if (!event.target.value && allowClear) onChange("");
        }}
        onKeyDown={(event) => {
          if (event.key === "Escape" && open) {
            event.preventDefault();
            event.stopPropagation();
            setSearch(null);
            setBrowse(false);
            setActive(-1);
          } else if (!open && event.key === "ArrowDown") {
            event.preventDefault();
            setSearch(null);
            setBrowse(true);
            setActive(options.length ? 0 : -1);
          } else if (open && (event.key === "ArrowDown" || event.key === "ArrowUp")) {
            event.preventDefault();
            const next = Math.max(0, Math.min(visible.length - 1, active + (event.key === "ArrowDown" ? 1 : -1)));
            setActive(visible.length ? next : -1);
            document.getElementById(`${id}-${next}`)?.scrollIntoView?.({ block: "nearest" });
          } else if (open && event.key === "Enter") {
            event.preventDefault();
            const option = visible[active >= 0 ? active : 0];
            if (active >= 0 || !allowCustom) { if (option) choose(option.value); }
            else { setSearch(null); setBrowse(false); }
          }
        }}
      />
      <button
        type="button"
        className="choice-toggle"
        aria-label={(open ? "Fechar opções de " : "Mostrar opções de ") + title}
        aria-expanded={open}
        aria-controls={open ? id : undefined}
        onMouseDown={(event) => event.preventDefault()}
        onClick={() => {
          setBrowse(!open);
          setSearch(null);
          setActive(-1);
          input.current?.focus();
        }}
      ><ChevronDown size={18} aria-hidden="true" /></button>
      </div>
      {open && <>
        <div id={id} role="listbox" aria-label={title} className="search-select-options">
          {visible.map((option, index) => (
            <button
              type="button"
              role="option"
              id={`${id}-${index}`}
              key={option.value}
              tabIndex={-1}
              aria-selected={option.value === value}
              className={active === index ? "active" : ""}
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => choose(option.value)}
            >{option.label}</button>
          ))}
        </div>
        {!visible.length && <small role="status">{loading ? "Carregando opções…" : error ? "Não foi possível carregar as opções." : allowCustom ? "Você pode usar o texto digitado." : "Nenhum resultado para esta pesquisa."}</small>}
      </>}
    </div>
  );
}
