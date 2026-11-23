import { PasswordInput } from "./PasswordInput";
import { PostalCodeInput } from "./PostalCodeInput";
import { VacancyPositionInput } from "./VacancyPositionInput";
import { SignaturePad } from "./SignaturePad";
import { RuleEditor } from "./RuleEditor";
import { DeadlineInput } from "./DeadlineInput";
import { LocationChoice } from "./LocationChoice";
import { SearchSelect } from "./SearchSelect";
import { ErrorBox } from "./ui";
import { mergeResumeValues } from "../lib/resumeMerge";
import { useEffect, useId, useRef, useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, BriefcaseBusiness, GraduationCap, BookOpen, BadgeCheck, Languages, Sparkles, Link2 } from "lucide-react";
import { api, download, obj, str, type Collection, type Row } from "../lib/api";
import { label } from "../lib/labels";

const profileCollections = {
  "profile.experiences": { icon: BriefcaseBusiness, item: "experiência", hint: "Conte onde trabalhou, seu cargo e as atividades que realizou." },
  "profile.education": { icon: GraduationCap, item: "formação", hint: "Informe sua escolaridade, o curso e a instituição de ensino." },
  "profile.courses": { icon: BookOpen, item: "curso", hint: "Inclua cursos complementares e treinamentos relevantes." },
  "profile.certifications": { icon: BadgeCheck, item: "certificação", hint: "Adicione certificações, licenças e seus comprovantes." },
  "profile.languages": { icon: Languages, item: "idioma", hint: "Indique os idiomas e seu nível de leitura, escrita e conversação." },
  "profile.skills": { icon: Sparkles, item: "competência", hint: "Destaque conhecimentos e ferramentas que você domina." },
  "profile.links": { icon: Link2, item: "link profissional", hint: "Compartilhe seu LinkedIn, portfólio ou outros trabalhos." },
};

export type Schema = {
  booleanChoice?: boolean;
  examples?: string[];
  placeholder?: string;
  readOnly?: boolean;
  type?: string;
  title?: string;
  description?: string;
  format?: string;
  default?: unknown;
  enum?: unknown[];
  properties?: Record<string, Schema>;
  required?: string[];
  items?: Schema;
  $ref?: string;
  $defs?: Record<string, Schema>;
  anyOf?: Schema[];
  minimum?: number;
  maximum?: number;
  minLength?: number;
  maxLength?: number;
  minItems?: number;
  maxItems?: number;
  additionalProperties?: Schema | boolean;
};
function defaultValue(schema: Schema, root: Schema): unknown {
  if (schema.default !== undefined) return structuredClone(schema.default);
  if (schema.anyOf?.some(item => item.type === "null")) return null;
  const s = resolve(schema, root);
  if (s.default !== undefined) return structuredClone(s.default);
  if (s.type === "object")
    return Object.fromEntries(
      Object.entries(s.properties ?? {}).map(([k, v]) => [
        k,
        defaultValue(v, root),
      ]),
    );
  if (s.type === "array") return [];
  if (s.type === "boolean") return false;
  if (s.enum) return s.enum[0];
  return "";
}
function resolve(schema: Schema, root: Schema): Schema {
  if (schema.$ref)
    return root.$defs?.[schema.$ref.split("/").at(-1) ?? ""] ?? schema;
  if (schema.anyOf)
    return resolve(schema.anyOf.find((s) => s.type !== "null") ?? {}, root);
  return schema;
}
function matchesSearch(value: string, search: string) {
  const normalize = (text: string) =>
    text.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  return normalize(value).includes(normalize(search.trim()));
}
const relationPaths: Record<string, string> = {
  vacancy_template_id: "/configuration/vacancy-templates",
  roles: "/roles",
  pool_id: "/talent-pools",
  user_id: "/users",
  delegate_id: "/users",
  referral_vacancy_id: "/referral-vacancies",
  org_unit_id: "/org",
  parent_id: "/org",
  recruiter_id: "/recruiters",
  manager_id: "/managers",
  evaluator_id: "/users",
  assigned_to: "/users",
  approver_id: "/users",
  interviewers: "/users",
  vacancy_id: "/vacancies",
  application_id: "/applications",
  application_ids: "/applications",
  scorecard_id: "/configuration/scorecards",
  template_id: "/configuration/interview-templates",
  workflow_id: "/configuration/workflows",
  request_workflow_id: "/vacancy-request-workflows",
  notice_id: "/public/privacy",
  checklist_id: "/configuration/checklists",
};
function Relation({
  field,
  value,
  onChange,
  multiple = false,
  searchable = false,
}: {
  field: string;
  value: unknown;
  onChange: (v: unknown) => void;
  multiple?: boolean;
  searchable?: boolean;
}) {
  const [search, setSearch] = useState("");
  const [typed, setTyped] = useState<string | null>(null);
  const choicesId = useId();
  const path = relationPaths[field];
  const query = useQuery({
    queryKey: ["options", path],
    queryFn: async () => {
      const first = await api<Collection>(path + "?page_size=100");
      const items = [...first.items];
      let pageNumber = 2;
      while (
        items.length < (first.total ?? items.length) &&
        first.items.length
      ) {
        const next = await api<Collection>(
          path + "?page_size=100&page_number=" + pageNumber++,
        );
        if (!next.items.length || next.page !== pageNumber - 1) break;
        items.push(...next.items);
      }
      return { ...first, items };
    },
    staleTime: 60000,
  });
  const allOptions = query.data?.items ?? [];
  const hasCostCenters = field === "org_unit_id" && allOptions.some(row => row.kind === "COST_CENTER" && row.active !== false);
  const relationOptions = hasCostCenters ? allOptions.filter(row => (row.kind === "COST_CENTER" && row.active !== false) || str(row.id) === str(value)) : allOptions;
  const visible = relationOptions.filter((row) => {
    const selected = multiple
      ? Array.isArray(value) && value.map(String).includes(str(row.id))
      : str(value) === str(row.id);
    return selected || matchesSearch(str(row.title ?? row.name ?? row.id), search);
  });
  if (field === "recruiter_id" && searchable) {
    const selected = query.data?.items.find((row) => str(row.id) === str(value));
    const entered = typed ?? str(selected?.name);
    const exact = query.data?.items.find(
      (row) => str(row.name).localeCompare(entered, "pt-BR", { sensitivity: "base" }) === 0,
    );
    return (
      <div className="searchable-choice">
        <input
          type="text"
          list={choicesId}
          autoComplete="off"
          aria-label={label(field)}
          placeholder="Digite o nome do RH"
          value={entered}
          onChange={(event) => {
            const text = event.target.value;
            setTyped(text);
            const match = query.data?.items.find(
              (row) => str(row.name).localeCompare(text, "pt-BR", { sensitivity: "base" }) === 0,
            );
            onChange(match ? str(match.id) : "");
          }}
        />
        <datalist id={choicesId}>
          {query.data?.items.map((row) => (
            <option key={row.id} value={str(row.name)} />
          ))}
        </datalist>
        {entered && !exact && <small>Escolha um nome do RH sugerido.</small>}
      </div>
    );
  }
  if (searchable && !multiple)
    return <SearchSelect
      title={label(field)}
      value={str(value)}
      options={relationOptions.map((row) => ({
        value: field === "roles" ? str(row.name) : str(row.id),
        label: str(row.title ?? row.name ?? obj(row.candidate).name ?? row.vacancy_title ?? row.id),
      }))}
      onChange={onChange}
      loading={query.isPending}
      error={Boolean(query.error)}
    />;
  return (
    <div className="searchable-choice">
      {searchable && (
        <input
          type="search"
          aria-label={"Buscar " + label(field)}
          placeholder="Digite para buscar"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      )}
      <select
      aria-label={label(field)}
      multiple={multiple}
      value={
        multiple ? (Array.isArray(value) ? value.map(String) : []) : str(value)
      }
      onChange={(e) =>
        onChange(
          multiple
            ? Array.from(e.target.selectedOptions).map((o) => o.value)
            : e.target.value,
        )
      }
    >
      {!multiple && <option value="">Selecione</option>}
      {visible?.map((row) => (
        <option key={row.id} value={field === "roles" ? str(row.name) : row.id}>
          {str(
            row.title ??
              row.name ??
              obj(row.candidate).name ??
              row.vacancy_title ??
              row.id,
          )}
        </option>
      ))}
      </select>
    </div>
  );
}
function EnumChoice({
  title,
  choices,
  value,
  onChange,
  searchable,
}: {
  title: string;
  choices: unknown[];
  value: string;
  onChange: (value: string) => void;
  searchable: boolean;
}) {
  if (searchable)
    return <SearchSelect
      title={title}
      value={value}
      options={choices.map((item) => ({ value: str(item), label: label(str(item)) }))}
      onChange={onChange}
      allowClear={false}
    />;
  return (
    <div className="searchable-choice">
      <select aria-label={title} value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">Selecione</option>
        {choices.map((item) => (
          <option key={str(item)} value={str(item)}>
            {label(str(item))}
          </option>
        ))}
      </select>
    </div>
  );
}
function CertificatePdf({
  documentId,
  onChange,
  onBusyChange,
}: {
  documentId: string;
  onChange: (id: string) => void;
  onBusyChange: (busy: boolean) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const fileInput = useRef<HTMLInputElement>(null);
  const client = useQueryClient();
  const documents = useQuery({
    queryKey: ["documents"],
    queryFn: () => api<Collection>("/documents"),
    enabled: Boolean(documentId),
  });
  const filename = str(
    documents.data?.items.find((item) => item.id === documentId)?.filename,
  );
  return (
    <div className="field wide certificate-pdf">
      <span>PDF do certificado</span>
      <input
        ref={fileInput}
        aria-label="PDF do certificado"
        type="file"
        hidden
        accept=".pdf,application/pdf"
        disabled={busy}
        onChange={async (event) => {
          const file = event.target.files?.[0];
          if (!file) return;
          setError(undefined);
          if (
            !file.name.toLowerCase().endsWith(".pdf") ||
            file.size > 10 * 1024 * 1024
          ) {
            setError(new Error("Selecione um PDF de até 10 MB."));
            event.target.value = "";
            return;
          }
          setBusy(true);
          onBusyChange(true);
          const data = new FormData();
          data.set("type_name", "CERTIFICADO");
          data.set("file", file);
          try {
            const row = await api<Row>("/documents", {
              method: "POST",
              body: data,
            });
            onChange(row.id);
            await client.invalidateQueries({ queryKey: ["documents"] });
          } catch (cause) {
            setError(cause);
          } finally {
            setBusy(false);
            onBusyChange(false);
            event.target.value = "";
          }
        }}
      />
      <button
        type="button"
        className="button small"
        disabled={busy}
        onClick={() => fileInput.current?.click()}
      >
        {busy
          ? "Enviando PDF…"
          : documentId
            ? "Substituir PDF"
            : "Selecionar PDF"}
      </button>
      <small>
        {busy
          ? "Enviando e validando PDF…"
          : documentId
            ? "PDF anexado. Salve o perfil para vincular à certificação."
            : "Opcional. Envie um PDF de até 10 MB."}
      </small>
      {documentId && (
        <button
          type="button"
          className="text-button"
          onClick={async () => {
            try {
              await download(
                "/documents/" + documentId + "/download",
                filename || "certificado.pdf",
              );
            } catch (cause) {
              setError(cause);
            }
          }}
        >
          {filename ? "Baixar " + filename : "Baixar PDF anexado"}
        </button>
      )}
      <ErrorBox error={error} />
    </div>
  );
}
function prepare(schema: Schema, value: unknown, root: Schema): unknown {
  const s = resolve(schema, root);
  if (
    schema.anyOf?.some((v) => v.type === "null") &&
    (value === "" || value == null)
  )
    return null;
  if (s.type === "object")
    return Object.fromEntries(
      Object.entries(obj(value)).map(([k, v]) => {
        let child =
          s.properties?.[k] ??
          (typeof s.additionalProperties === "object"
            ? s.additionalProperties
            : {});
        if ((k === "expected" || k === "correct") && !child.type) {
          const kind = str(obj(value).kind);
          child =
            kind === "BOOLEAN"
              ? { type: "boolean" }
              : ["NUMBER_MIN", "LEVEL", "NUMBER"].includes(kind)
                ? { type: "number" }
                : child;
        }
        return [k, prepare(child, v, root)];
      }),
    );
  if (s.type === "boolean") return s.booleanChoice && (value === "" || value == null) ? null : value === true || value === "true";
  if (s.type === "array")
    return (Array.isArray(value) ? value : []).map((v) =>
      prepare(s.items ?? {}, v, root),
    );
  if (s.type === "integer" || s.type === "number")
    return value === "" ? null : Number(value);
  if (s.format === "date-time" && value)
    return new Date(String(value)).toISOString();
  return value;
}
export function SchemaForm({
  schema,
  initial,
  onSubmit,
  submitLabel = "Salvar",
  busy = false,
  searchableSelects = false,
  layout,
  suggestions,
  onValuesChange,
  lockedFields = [],
}: {
  schema: Schema;
  initial?: Record<string, unknown>;
  onSubmit: (data: Record<string, unknown>) => Promise<unknown> | void;
  submitLabel?: string;
  busy?: boolean;
  searchableSelects?: boolean;
  layout?: "vacancy";
  suggestions?: Record<string, unknown>;
  onValuesChange?: (values: Record<string, unknown>) => void;
  lockedFields?: string[];
}) {
  const [submitError, setSubmitError] = useState<unknown>();
  const [uploadsInProgress, setUploadsInProgress] = useState(0);
  const { control, setValue, getValues, handleSubmit, formState, reset } = useForm<
    Record<string, unknown>
  >({
    defaultValues: { ...obj(defaultValue(schema, schema)), ...initial },
  });
  const values = useWatch({ control });
  const serializedValues = JSON.stringify(values);
  useEffect(() => {
    onValuesChange?.(JSON.parse(serializedValues));
  }, [serializedValues, onValuesChange]);
  useEffect(() => {
    if (!suggestions) return;
    const apply = (patch: Record<string, unknown>, prefix = "") => {
      for (const [key, value] of Object.entries(patch)) {
        const path = prefix ? `${prefix}.${key}` : key;
        if (value && typeof value === "object" && !Array.isArray(value)) {
          apply(value as Record<string, unknown>, path);
        } else {
          const current = getValues(path);
            const merged = mergeResumeValues(current, value, key);
            if (JSON.stringify(merged) !== JSON.stringify(current)) setValue(path, merged, { shouldDirty: true });
        }
      }
    };
    apply(suggestions);
  }, [suggestions, getValues, setValue]);
  useEffect(() => {
    const warn = (e: BeforeUnloadEvent) => {
      if (formState.isDirty) {
        e.preventDefault();
      }
    };
    const navigation = (e: MouseEvent) => {
      const link = (e.target as HTMLElement).closest("a[href]");
      if (
        formState.isDirty &&
        link &&
        !link.getAttribute("target") &&
        !window.confirm(
          "Há alterações não salvas. Deseja sair deste formulário?",
        )
      ) {
        e.preventDefault();
        e.stopPropagation();
      }
    };
    window.addEventListener("beforeunload", warn);
    document.addEventListener("click", navigation, true);
    return () => {
      window.removeEventListener("beforeunload", warn);
      document.removeEventListener("click", navigation, true);
    };
  }, [formState.isDirty]);
  const update = (path: string, value: unknown) => {
    if (lockedFields.some(field => path === field || path.startsWith(field + "."))) return;
    setValue(path, value, { shouldDirty: true });
  };
  function render(
    raw: Schema,
    value: unknown,
    path: string,
    key: string,
    parent: Record<string, unknown> = {},
  ): React.ReactNode {
    if (raw.readOnly || ["salary_range", "blind", "confidential", "featured"].includes(key)) return null;
    let s = resolve(raw, schema);
    if (layout === "vacancy" && path === "details.accessibility") s = { ...s, description: "Descreva os recursos e as adaptações disponíveis no ambiente de trabalho ou na seleção. Exemplo: Local com rampas e elevador. Informe ao RH se precisar de adaptação para a entrevista. Preencha com informações confirmadas pela empresa." };
    if (layout === "vacancy" && path === "details.affirmative") s = { ...s, description: "Indique se a oportunidade é direcionada a algum grupo específico. Exemplos: Vaga destinada a pessoas com deficiência (PcD) ou Vaga afirmativa para mulheres. Se a vaga não for afirmativa, deixe este campo em branco." };
    if (key === "desired_position") return <VacancyPositionInput key={path} title={raw.title ?? "Cargo pretendido"} value={str(value)} onChange={next => update(path, next)} />;
    if (key === "postal_code") return <PostalCodeInput key={path} title={raw.title ?? "CEP"} value={str(value)} onChange={next => update(path, next)} onAddress={address => {
      const prefix = path.includes(".") ? path.slice(0, path.lastIndexOf(".") + 1) : "";
      for (const field of ["neighborhood", "city", "state"]) if (address[field]) update(prefix + field, address[field]);
    }} />;
    if (s.format === "signature") return <SignaturePad key={path} title={raw.title ?? "Assinatura eletrônica"} value={str(value)} onChange={image => update(path, image)} />;
    const title = path === "profile" ? "Informações profissionais" : layout === "vacancy" && path === "details.responsibilities"
      ? "Principais atividades"
      : raw.title &&
      (raw.title.toLowerCase() !== key.replaceAll("_", " ").toLowerCase() || /^[A-Z]{2,8}$/.test(raw.title))
        ? raw.title
        : label(key);
    if (layout === "vacancy" && (path === "city" || path === "state"))
      return <LocationChoice
        key={path === "city" ? "city-" + str(values.state) : path}
        field={path}
        city={str(values.city)}
        state={str(values.state)}
        onChange={(city, state) => { update("city", city); update("state", state); }}
      />;
    if (s.examples?.length) return <div className="field" key={path}><span>{title}</span><SearchSelect title={title} value={str(value)} options={s.examples.map(option => ({ value: option, label: option }))} onChange={next => update(path, next)} allowCustom placeholder={s.placeholder} />{s.description && <small>{s.description}</small>}</div>;
    if (layout === "vacancy" && path === "contract_type") {
      const options = ["CLT", "Temporário", "Estágio", "Aprendiz"];
      const current = str(value);
      return (
        <label className="field" key={path}>
          <span>Contrato</span>
          <SearchSelect
            title="Contrato"
            value={current}
            options={options.map((option) => ({ value: option, label: option }))}
            onChange={(option) => update(path, option)}
            allowClear={false}
          />
        </label>
      );
    }
    if (layout === "vacancy" && path === "details.experience") {
      const options = ["Com experiência", "Sem experiência"];
      const current = str(value);
      return (
        <label className="field" key={path}>
          <span>Experiência</span>
          <select
            aria-label="Experiência"
            value={current}
            onChange={(event) => update(path, event.target.value)}
          >
            <option value="">Selecione</option>
            {current && !options.includes(current) && <option value={current}>{current}</option>}
            {options.map((option) => <option key={option} value={option}>{option}</option>)}
          </select>
        </label>
      );
    }
    if (key === "document_id" && path.startsWith("profile.certifications."))
      return (
        <CertificatePdf
          key={path}
          documentId={str(value)}
          onChange={(id) => update(path, id)}
          onBusyChange={(uploading) =>
            setUploadsInProgress((count) => count + (uploading ? 1 : -1))
          }
        />
      );
    if (relationPaths[key])
      return (
        <label className="field" key={path}>
          <span>{label(key)}</span>
          <Relation
            field={key}
            value={value}
            onChange={(v) => update(path, v)}
            multiple={s.type === "array"}
            searchable={searchableSelects}
          />
        </label>
      );
    if ((key === "expected" || key === "correct") && !s.type) {
      const kind = str(parent.kind);
      s =
        kind === "BOOLEAN"
          ? { type: "boolean" }
          : ["NUMBER", "NUMBER_MIN", "NUMBER_RANGE", "LEVEL"].includes(kind)
            ? kind === "NUMBER_RANGE"
              ? { type: "array", items: { type: "number" } }
              : { type: "number" }
            : ["MULTIPLE", "MULTI_CHOICE"].includes(kind)
              ? { type: "array", items: { type: "string" } }
              : { type: "string" };
    }
    if (
      s.type === "object" &&
      ["conditions", "filters", "rules"].includes(key) &&
      !Object.keys(s.properties ?? {}).length
    )
      return (
        <fieldset key={path} className={"form-section" + (path === "profile" ? " profile-form-section" : "")} disabled={lockedFields.includes(path)}>
          <legend>{title}</legend>
          <RuleEditor value={value} onChange={(v) => update(path, v)} />
        </fieldset>
      );
    if (s.type === "object") {
      const properties = s.properties ?? {};
      const availabilityFields = path === "profile"
        ? ["availability", "travel", "relocation", "shift", "expected_salary"].filter((field) => field in properties)
        : [];
      if (!Object.keys(properties).length)
        return (
          <KeyValues
            key={path}
            title={title}
            value={obj(value)}
            numeric={key === "composition"}
            onChange={(v) => update(path, v)}
          />
        );
      return (
        <fieldset key={path} className={"form-section" + (path === "profile" ? " profile-form-section" : "")} disabled={lockedFields.includes(path)}>
          <legend>{title}</legend>
          {lockedFields.includes(path) && <p className="stage-gate-status locked">Bloqueado: formação, experiências e competências serão liberadas na etapa de recrutamento.</p>}
          {raw.description && <p className="muted">{raw.description}</p>}
          <div className="form-grid">
            {Object.entries(properties).filter(([child]) => !availabilityFields.includes(child)).map(([child, childSchema]) =>
              render(
                childSchema,
                obj(value)[child],
                path ? path + "." + child : child,
                child,
                obj(value),
              ),
            )}
            {availabilityFields.length > 0 && (
              <fieldset className="profile-availability">
                <legend>Disponibilidade e pretensão salarial</legend>
                <p className="muted">Informe suas preferências e marque as opções que se aplicam a você.</p>
                <div className="profile-availability-options">
                  {availabilityFields.filter((field) => ["availability", "travel", "relocation"].includes(field)).map((field) =>
                    render(properties[field], obj(value)[field], path + "." + field, field, obj(value)),
                  )}
                </div>
                <div className="form-grid">
                  {availabilityFields.filter((field) => ["shift", "expected_salary"].includes(field)).map((field) =>
                    render(properties[field], obj(value)[field], path + "." + field, field, obj(value)),
                  )}
                </div>
              </fieldset>
            )}
          </div>
        </fieldset>
      );
    }
    if (s.type === "array") {
      const list = Array.isArray(value) ? value : [];
      const collection = profileCollections[path as keyof typeof profileCollections];
      const CollectionIcon = collection?.icon;
      const addButton = <button type="button" className="button secondary small" onClick={() => update(path, [...list, defaultValue(s.items ?? { type: "string" }, schema)])} disabled={s.maxItems !== undefined && list.length >= s.maxItems}>
        <Plus size={16} aria-hidden="true" />Adicionar {collection?.item ?? title.toLowerCase()}
      </button>;
      return (
        <fieldset key={path} className={"array-field" + (collection ? " profile-collection" : "")}>
          <legend>{title}</legend>
          {collection && CollectionIcon && <div className="profile-collection-header">
            <span className="profile-collection-icon"><CollectionIcon size={21} aria-hidden="true" /></span>
            <div className="profile-collection-intro"><div className="profile-collection-title"><h3>{title}</h3><span>{list.length ? `${list.length} ${list.length === 1 ? "item" : "itens"}` : "Opcional"}</span></div><p>{collection.hint}</p></div>
            {addButton}
          </div>}
          {raw.description && <p className="muted">{raw.description}</p>}
          {list.map((item, index) => (
            <div className="array-item" key={index}>
              {render(
                s.items ?? { type: "string" },
                item,
                path + "." + index,
                (collection ? collection.item.charAt(0).toUpperCase() + collection.item.slice(1) : title) + " " + (index + 1),
                obj(item),
              )}
              <button
                type="button"
                className="icon-button danger-text"
                aria-label={"Remover " + title + " " + (index + 1)}
                onClick={() =>
                  update(
                    path,
                    list.filter((_, i) => i !== index),
                  )
                }
              >
                <Trash2 size={16} />
              </button>
            </div>
          ))}
          {!collection && addButton}
        </fieldset>
      );
    }
    if (s.type === "boolean" && s.booleanChoice) return <label className="field" key={path}><span>{title}</span><select aria-label={title} value={value === true ? "true" : value === false ? "false" : ""} onChange={event => update(path, event.target.value === "" ? null : event.target.value === "true")}><option value="">Selecione</option><option value="true">Sim</option><option value="false">Não</option></select></label>;
    if (s.type === "boolean")
      return (
        <label className="check-field" key={path}>
          <input
            type="checkbox"
            checked={Boolean(value)}
            onChange={(e) => update(path, e.target.checked)}
          />
          <span>{title}</span>
        </label>
      );
    if (s.enum)
      return (
        <label className="field" key={path}>
          <span>{title}</span>
          <EnumChoice
            title={title}
            choices={s.enum}
            value={str(value ?? s.default ?? "")}
            onChange={(choice) => update(path, choice)}
            searchable={searchableSelects}
          />
        </label>
      );
    const type =
      s.format === "date-time"
        ? "datetime-local"
        : s.format === "date"
          ? "date"
          : s.type === "integer" || s.type === "number"
            ? "number"
            : key === "password"
              ? "password"
              : key === "email"
                ? "email"
                : "text";
    const Input = type === "password" ? PasswordInput : "input";
    const long = [
      "description",
      "text",
      "body",
      "justification",
      "reason",
      "comment",
      "benefits",
      "conditions",
      "responsibilities",
      "requirements",
      "desirable",
      "accessibility",
      "experience",
      "education",
      "notes",
      "rejection_email_body",
    ].includes(key);
    let display = str(value);
    if (type === "datetime-local" && display.includes("Z")) {
      const d = new Date(display);
      display = new Date(d.getTime() - d.getTimezoneOffset() * 60000)
        .toISOString()
        .slice(0, 16);
    }
    return (
      <label className={"field " + (long || (layout === "vacancy" && path === "title") ? "wide" : "")} key={path}>
        <span>{title}</span>
        {key === "deadline" && type === "datetime-local" ? (
          <DeadlineInput title={title} value={str(value)} onChange={(next) => update(path, next)} />
        ) : long ? (
          <textarea
            aria-label={title}
            rows={4}
            value={display}
            onChange={(e) => update(path, e.target.value)}
            maxLength={s.maxLength}
          />
        ) : (
          <Input
            aria-label={title}
            placeholder={s.placeholder}
            type={type}
            minLength={s.minLength}
            value={display}
            min={s.minimum}
            max={s.maximum}
            step={s.type === "integer" ? 1 : "any"}
            maxLength={s.maxLength}
            onChange={(e) =>
              update(
                path,
                type === "number"
                  ? e.target.value === ""
                    ? ""
                    : Number(e.target.value)
                  : e.target.value,
              )
            }
          />
        )}{" "}
        {s.description && <small>{s.description}</small>}
      </label>
    );
  }
  return (
    <form
      data-dirty={formState.isDirty ? "true" : "false"}
      onSubmit={handleSubmit(async (data, event) => {
        if (uploadsInProgress) return;
        const submitter = (event?.nativeEvent as SubmitEvent | undefined)?.submitter;
        const draft = layout === "vacancy" && submitter instanceof HTMLButtonElement && submitter.value === "draft";
        const submitted = draft ? { ...data, publish_on_save: false } : data;
        setSubmitError(undefined);
        try {
          await onSubmit(obj(prepare(schema, submitted, schema)));
          reset(submitted);
        } catch (error) {
          setSubmitError(error);
        }
      })}
      className={"schema-form" + (layout === "vacancy" ? " vacancy-form" : "")}
    >
      <ErrorBox error={submitError} />
      {layout === "vacancy" ? (
        <div className="vacancy-sections">
          {[
            { title: "Oportunidade", fields: ["title", "state", "city", "description"] },
            { title: "Principais atividades", fields: ["details.responsibilities"] },
            { title: "Requisitos", fields: ["details.requirements", "details.desirable", "details.education", "details.experience"] },
            { title: "Benefícios", fields: ["details.benefits"] },
            { title: "Dados internos da vaga", fields: ["quantity", "org_unit_id"] },
            { title: "Responsáveis", fields: ["recruiter_id", "manager_id"] },
            { title: "Contratação e remuneração", fields: ["modality", "contract_type", "details.position", "details.level", "details.salary", "details.hide_salary"] },
            { title: "Inclusão e acessibilidade", fields: ["details.accessibility", "details.affirmative"] },
            { title: "Configurações do processo", fields: ["deadline", "details.sla_hours"] },
            { title: "Publicação", fields: ["audience", "publish_on_save"] },
            { title: "Outras informações", fields: Object.keys(schema.properties ?? {}).filter((key) => !["version", "title", "quantity", "vacancy_template_id", "org_unit_id", "recruiter_id", "manager_id", "city", "state", "modality", "contract_type", "description", "deadline", "blind", "audience", "confidential", "publish_on_save", "details"].includes(key)) },
          ].map((section) => {
            const fields = section.fields.flatMap((path) => {
              const [key, child] = path.split(".");
              const raw = schema.properties?.[key];
              const fieldSchema = child && raw ? resolve(raw, schema).properties?.[child] : raw;
              if (!fieldSchema) return [];
              const parent = child ? obj(values[key]) : obj(values);
              return [render(fieldSchema, parent[child ?? key], path, child ?? key, parent)];
            });
            return fields.length ? (
              <fieldset className="vacancy-section" key={section.title}>
                <legend>{section.title}</legend>
                <div className="form-grid">{fields}</div>
              </fieldset>
            ) : null;
          })}
        </div>
      ) : <div className="form-grid">
        {Object.entries(schema.properties ?? {})
          .filter(([key]) => !["version"].includes(key))
          .map(([key, s]) => render(s, values[key], key, key, obj(values)))}
      </div>}
      <div className="form-actions">
        {layout === "vacancy" && schema.properties?.publish_on_save && !initial?.version && <button type="submit" name="save_mode" value="draft" className="button secondary" disabled={busy || formState.isSubmitting || uploadsInProgress > 0}>Salvar rascunho</button>}
        <button
          className="button"
          disabled={busy || formState.isSubmitting || uploadsInProgress > 0}
        >
          {uploadsInProgress > 0
            ? "Enviando PDF…"
            : busy || formState.isSubmitting
              ? "Salvando…"
              : submitLabel}
        </button>
        {formState.isDirty && (
          <span className="muted">Alterações não salvas</span>
        )}
      </div>
    </form>
  );
}
function KeyValues({
  title,
  value,
  onChange,
  numeric = false,
}: {
  title: string;
  value: Record<string, unknown>;
  numeric?: boolean;
  onChange: (v: Record<string, unknown>) => void;
}) {
  return (
    <fieldset className="array-field">
      <legend>{title}</legend>
      {Object.entries(value).map(([key, val]) => (
        <div className="key-value" key={key}>
          <label className="field">
            <span>Campo</span>
            <input
              value={key}
              onChange={(e) => {
                const next = { ...value };
                delete next[key];
                next[e.target.value] = val;
                onChange(next);
              }}
            />
          </label>
          <label className="field">
            <span>Valor</span>
            <input
              type={numeric ? "number" : "text"}
              value={str(val)}
              onChange={(e) =>
                onChange({
                  ...value,
                  [key]: numeric ? Number(e.target.value) : e.target.value,
                })
              }
            />
          </label>
          <button
            type="button"
            className="icon-button"
            aria-label={"Remover " + key}
            onClick={() => {
              const next = { ...value };
              delete next[key];
              onChange(next);
            }}
          >
            <Trash2 size={16} />
          </button>
        </div>
      ))}
      <button
        type="button"
        className="button secondary small"
        onClick={() =>
          onChange({
            ...value,
            ["campo_" + (Object.keys(value).length + 1)]: "",
          })
        }
      >
        <Plus size={16} />
        Adicionar campo
      </button>
    </fieldset>
  );
}
export function RemoteForm({
  name,
  initial,
  onSubmit,
  submitLabel,
}: {
  name: string;
  initial?: Record<string, unknown>;
  onSubmit: (data: Record<string, unknown>) => Promise<unknown> | void;
  submitLabel?: string;
}) {
  const query = useQuery({
    queryKey: ["form", name],
    queryFn: () => api<Schema>("/forms/" + name),
  });
  if (query.isPending) return <p role="status">Carregando formulário…</p>;
  if (query.error) return <p role="alert">{query.error.message}</p>;
  return (
    <SchemaForm
      schema={query.data}
      initial={initial}
      onSubmit={onSubmit}
      submitLabel={submitLabel}
      searchableSelects={name === "vacancy"}
      layout={name === "vacancy" ? "vacancy" : undefined}
    />
  );
}
