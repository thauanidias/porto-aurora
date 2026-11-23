import { useId, useState, type ComponentProps } from "react";
import { Eye, EyeOff } from "lucide-react";

export function PasswordInput({ id, disabled, ...props }: ComponentProps<"input">) {
  const generatedId = useId();
  const [visible, setVisible] = useState(false);
  const inputId = id ?? generatedId;
  const action = visible ? "Ocultar senha" : "Mostrar senha";

  return (
    <span className="password-input">
      <input {...props} id={inputId} disabled={disabled} type={visible ? "text" : "password"} />
      <button
        type="button"
        className="password-toggle"
        aria-label={action}
        title={action}
        aria-controls={inputId}
        aria-pressed={visible}
        disabled={disabled}
        onClick={() => setVisible((value) => !value)}
      >
        {visible ? <EyeOff size={19} aria-hidden="true" /> : <Eye size={19} aria-hidden="true" />}
      </button>
    </span>
  );
}
