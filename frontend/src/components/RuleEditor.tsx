import { obj, str } from "../lib/api";
import { label } from "../lib/labels";

const fields = [
  "city",
  "state",
  "source",
  "experience_years",
  "education_level",
  "certifications",
  "skills",
  "availability",
  "shift",
  "org_unit_id",
  "quantity",
  "position",
  "request_type",
  "stage_id",
  "status",
  "test_score",
  "event_status",
];
export function RuleEditor({
  value,
  onChange,
  depth = 0,
}: {
  value: unknown;
  onChange: (value: Record<string, unknown>) => void;
  depth?: number;
}) {
  const rule = obj(value);
  const group = "and" in rule ? "and" : "or" in rule ? "or" : "";
  const children =
    group && Array.isArray(rule[group]) ? (rule[group] as unknown[]) : [];
  return (
    <div className="rule-editor">
      {!Object.keys(rule).length ? (
        <button
          className="button secondary small"
          type="button"
          onClick={() =>
            onChange({
              and: [{ field: "experience_years", op: "gte", value: 0 }],
            })
          }
        >
          Adicionar condição
        </button>
      ) : (
        <>
          <div className="inline-form">
            {group ? (
              <label className="field">
                <span>Combinação</span>
                <select
                  value={group}
                  onChange={(e) => onChange({ [e.target.value]: children })}
                >
                  <option value="and">Todas as condições (E)</option>
                  <option value="or">Qualquer condição (OU)</option>
                </select>
              </label>
            ) : (
              <>
                <label className="field">
                  <span>Campo</span>
                  <select
                    value={str(rule.field)}
                    onChange={(e) =>
                      onChange({ ...rule, field: e.target.value })
                    }
                  >
                    {fields.map((f) => (
                      <option key={f} value={f}>
                        {label(f)}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="field">
                  <span>Operação</span>
                  <select
                    value={str(rule.op)}
                    onChange={(e) =>
                      onChange({
                        ...rule,
                        op: e.target.value,
                        value: e.target.value === "in" ? [] : "",
                      })
                    }
                  >
                    {[
                      ["eq", "Igual a"],
                      ["in", "Está entre"],
                      ["contains", "Contém"],
                      ["gte", "Maior ou igual"],
                      ["lte", "Menor ou igual"],
                    ].map(([v, n]) => (
                      <option key={v} value={v}>
                        {n}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="field">
                  <span>
                    Valor{rule.op === "in" ? " (separe por vírgulas)" : ""}
                  </span>
                  <input
                    value={
                      Array.isArray(rule.value)
                        ? rule.value.join(", ")
                        : str(rule.value)
                    }
                    onChange={(e) => {
                      const value = e.target.value;
                      onChange({
                        ...rule,
                        value:
                          rule.op === "in"
                            ? value.split(",").map((s) => s.trim())
                            : ["gte", "lte"].includes(str(rule.op))
                              ? Number(value)
                              : value === "true"
                                ? true
                                : value === "false"
                                  ? false
                                  : value,
                      });
                    }}
                  />
                </label>
              </>
            )}
            <button
              className="text-button"
              type="button"
              onClick={() => onChange({})}
            >
              Limpar regra
            </button>
          </div>
          {group && (
            <>
              {children.map((child, i) => (
                <div className="rule-child" key={i}>
                  <RuleEditor
                    value={child}
                    depth={depth + 1}
                    onChange={(next) =>
                      onChange({
                        [group]: Object.keys(next).length
                          ? children.map((c, n) => (n === i ? next : c))
                          : children.filter((_, n) => i !== n),
                      })
                    }
                  />
                </div>
              ))}
              <div className="actions">
                <button
                  type="button"
                  className="button secondary small"
                  onClick={() =>
                    onChange({
                      [group]: [
                        ...children,
                        { field: "experience_years", op: "gte", value: 0 },
                      ],
                    })
                  }
                >
                  Adicionar condição
                </button>
                {depth < 4 && (
                  <button
                    type="button"
                    className="button secondary small"
                    onClick={() =>
                      onChange({
                        [group]: [
                          ...children,
                          {
                            and: [
                              { field: "skills", op: "contains", value: "" },
                            ],
                          },
                        ],
                      })
                    }
                  >
                    Adicionar grupo
                  </button>
                )}
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
