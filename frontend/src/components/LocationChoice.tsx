import { useId, useRef, useState } from "react";
import { ChevronDown } from "lucide-react";
import localities from "../data/localities.json";

const normalize = (text: string) =>
  text.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();

export function LocationChoice({ field, city, state, onChange }: {
  field: "city" | "state";
  city: string;
  state: string;
  onChange: (city: string, state: string) => void;
}) {
  const [search, setSearch] = useState<string | null>(null);
  const [browse, setBrowse] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const id = useId();
  const title = field === "city" ? "Cidade" : "Estado";
  const choices = field === "state"
    ? localities.states.map((item) => ({ value: item.code, label: `${item.name} (${item.code})` }))
    : localities.cities.filter((item) => !state || item.state === state)
      .map((item) => ({ value: String(item.id), label: item.name }));
  const selected = field === "state" ? state : String(localities.cities.find(
    (item) => item.name === city && (!state || item.state === state),
  )?.id ?? "");
  const selectedLabel = choices.find((item) => item.value === selected)?.label
    ?? (field === "city" ? city : state);
  const expanded = browse || Boolean(search?.trim());
  const visible = expanded
    ? choices.filter((item) => normalize(item.label).includes(normalize(search?.trim() ?? "")))
    : [];
  return (
    <div className="field location-choice" onBlur={(event) => {
      if (!event.currentTarget.contains(event.relatedTarget)) {
        setSearch(null);
        setBrowse(false);
      }
    }}>
      <label htmlFor={id + "-search"}>{title}</label>
      <div className="choice-input">
      <input
        ref={input}
        id={id + "-search"}
        type="search"
        aria-label={`Buscar ${title}`}
        placeholder={field === "state" ? "Busque por nome ou UF" : "Digite o nome da cidade"}
        aria-controls={expanded ? id : undefined}
        value={search ?? selectedLabel}
        onChange={(event) => {
          setSearch(event.target.value);
          setBrowse(false);
          if (!event.target.value) onChange("", field === "state" ? "" : state);
        }}
        onKeyDown={(event) => {
          if (event.key === "Escape" && expanded) {
            event.preventDefault();
            event.stopPropagation();
            setSearch(null);
            setBrowse(false);
          } else if (!expanded && event.key === "ArrowDown") {
            event.preventDefault();
            setBrowse(true);
          }
        }}
      />
      <button
        type="button"
        className="choice-toggle"
        aria-label={(expanded ? "Fechar opções de " : "Mostrar opções de ") + title}
        aria-expanded={expanded}
        aria-controls={expanded ? id : undefined}
        onMouseDown={(event) => event.preventDefault()}
        onClick={() => {
          setBrowse(!expanded);
          setSearch(null);
          input.current?.focus();
        }}
      ><ChevronDown size={18} aria-hidden="true" /></button>
      </div>
      {expanded && <select
        id={id}
        aria-label={title}
        size={5}
        value={selected}
        onChange={(event) => {
          if (field === "state") {
            const nextState = event.target.value;
            onChange(nextState === state ? city : "", nextState);
          } else {
            const next = localities.cities.find((item) => String(item.id) === event.target.value);
            onChange(next?.name ?? "", next?.state ?? state);
          }
          setSearch(null);
          setBrowse(false);
          input.current?.focus();
        }}
      >
        <option value="">{field === "state" ? "Todos os estados" : "Selecione uma cidade"}</option>
        {selected && !visible.some((item) => item.value === selected) && (
          <option value={selected}>{choices.find((item) => item.value === selected)?.label}</option>
        )}
        {visible.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
      </select>}
      {expanded && <small role="status">
        {visible.length ? `${visible.length} opções. Role a lista ou digite para buscar.` : "Nenhum resultado para esta pesquisa."}
        {field === "city" && city && ` Cidade selecionada: ${city}.`}
      </small>}
    </div>
  );
}
