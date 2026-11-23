import { useRef } from "react";
import { CalendarDays } from "lucide-react";

function localValue(value: string) {
  if (!value || !/(Z|[+-]\d{2}:\d{2})$/.test(value)) return value;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000)
    .toISOString().slice(0, 16);
}

function displayValue(value: string) {
  return localValue(value).replace(
    /^(\d{4})-(\d{2})-(\d{2})T(\d{2}:\d{2})(?::[\d.]+)?$/,
    "$3/$2/$1 $4",
  );
}

function parseValue(value: string) {
  const match = /^(\d{2})\/(\d{2})\/(\d{4}) (\d{2}):(\d{2})$/.exec(value);
  if (!match) return null;
  const [, day, month, year, hour, minute] = match;
  const iso = `${year}-${month}-${day}T${hour}:${minute}`;
  const date = new Date(iso);
  if (Number(year) < 1 || Number.isNaN(date.getTime()) ||
      date.getFullYear() !== Number(year) || date.getMonth() + 1 !== Number(month) ||
      date.getDate() !== Number(day) || date.getHours() !== Number(hour) ||
      date.getMinutes() !== Number(minute)) return null;
  return iso;
}

export function DeadlineInput({ title, value, onChange }: {
  title: string;
  value: string;
  onChange: (value: string) => void;
}) {
  const textInput = useRef<HTMLInputElement>(null);
  const picker = useRef<HTMLInputElement>(null);
  return (
    <span className="deadline-input">
      <input
        ref={textInput}
        aria-label={title}
        type="text"
        placeholder="dd/mm/aaaa hh:mm"
        maxLength={16}
        value={displayValue(value)}
        onChange={(event) => {
          const raw = event.target.value;
          const parsed = parseValue(raw);
          event.target.setCustomValidity(raw && !parsed
            ? "Informe uma data e hora válidas no formato dd/mm/aaaa hh:mm."
            : "");
          onChange(parsed ?? raw);
        }}
      />
      <input
        ref={picker}
        className="deadline-picker"
        type="datetime-local"
        lang="pt-BR"
        aria-label={`Selecionar ${title.toLowerCase()} no calendário`}
        tabIndex={-1}
        value={/^\d{4}-\d{2}-\d{2}T/.test(localValue(value)) ? localValue(value) : ""}
        onChange={(event) => {
          textInput.current?.setCustomValidity("");
          onChange(event.target.value);
        }}
      />
      <button
        type="button"
        className="deadline-calendar"
        aria-label={`Abrir calendário de ${title.toLowerCase()}`}
        onClick={() => picker.current?.showPicker()}
      >
        <CalendarDays size={18} aria-hidden="true" />
      </button>
    </span>
  );
}
