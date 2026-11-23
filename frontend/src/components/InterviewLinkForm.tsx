import { useRef, useState } from "react";
import { Link2 } from "lucide-react";
import { ErrorBox } from "./ui";

type Content = { title: string; url: string; description: string };

export function InterviewLinkForm({ onSubmit, kind = "INTERVIEW" }: { onSubmit: (content: Content) => Promise<void>; kind?: "INTERVIEW" | "TEST" }) {
  const [values, setValues] = useState<Content>({ title: kind === "TEST" ? "Teste da vaga" : "Entrevista com o RH", url: "", description: "" });
  const [errors, setErrors] = useState<Partial<Content>>({});
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(false);
  const formRef = useRef<HTMLFormElement>(null);
  function update(field: keyof Content, value: string) {
    setValues(current => ({ ...current, [field]: value }));
    setErrors(current => ({ ...current, [field]: undefined }));
    setError(undefined);
  }
  return <form ref={formRef} className="interview-link-form" noValidate onSubmit={async event => {
    event.preventDefault();
    if (busy) return;
    const content = { title: values.title.trim(), url: values.url.trim(), description: values.description.trim() };
    const invalid: Partial<Content> = {};
    if (content.title.length < 3) invalid.title = "Informe um título com pelo menos 3 caracteres.";
    if (!content.url) invalid.url = `Informe o link ${kind === "TEST" ? "do teste" : "da entrevista"}.`;
    else {
      try {
        const url = new URL(content.url);
        if (!["https:", "http:"].includes(url.protocol) || !url.hostname || url.username || url.password) throw new Error();
      } catch { invalid.url = "Informe um link válido, começando com https:// ou http://."; }
    }
    if (content.description.length < 3) invalid.description = "Escreva uma legenda com pelo menos 3 caracteres.";
    setErrors(invalid);
    setError(undefined);
    const first = Object.keys(invalid)[0];
    if (first) { formRef.current?.querySelector<HTMLElement>(`[name="${first}"]`)?.focus(); return; }
    setBusy(true);
    try { await onSubmit(content); }
    catch (cause) { setError(cause); }
    finally { setBusy(false); }
  }}>
    <p className="muted">Adicione o endereço de acesso e as orientações que o candidato verá no portal.</p>
    <ErrorBox error={error} />
    <fieldset disabled={busy} className="interview-link-fields">
      <label className="field"><span>Título do link <span aria-hidden="true">*</span></span>
        <input aria-label="Título do link" name="title" required maxLength={180} value={values.title} onChange={event => update("title", event.target.value)}
          aria-invalid={Boolean(errors.title)} aria-describedby={errors.title ? "interview-title-error" : undefined} />
        {errors.title && <small id="interview-title-error" className="interview-field-error" role="alert">{errors.title}</small>}
      </label>
      <label className="field"><span>Link {kind === "TEST" ? "do teste" : "da entrevista"} <span aria-hidden="true">*</span></span>
        <input aria-label={`Link ${kind === "TEST" ? "do teste" : "da entrevista"}`} name="url" type="url" required maxLength={2048} placeholder="https://…" value={values.url}
          onChange={event => update("url", event.target.value)} aria-invalid={Boolean(errors.url)}
          aria-describedby={errors.url ? "interview-url-error" : "interview-url-help"} />
        {errors.url ? <small id="interview-url-error" className="interview-field-error" role="alert">{errors.url}</small>
          : <small id="interview-url-help">Cole o endereço da plataforma {kind === "TEST" ? "do teste" : "da entrevista"}.</small>}
      </label>
      <label className="field"><span>Legenda e orientações <span aria-hidden="true">*</span></span>
        <textarea aria-label="Legenda e orientações" name="description" required maxLength={5000} rows={4} value={values.description}
          placeholder={kind === "TEST" ? "Ex.: Realize o teste até dia 20 às 18h. Reserve 30 minutos em um local tranquilo." : "Ex.: Entrevista dia 20 às 10h. Acesse o link cinco minutos antes."}
          onChange={event => update("description", event.target.value)} aria-invalid={Boolean(errors.description)}
          aria-describedby={errors.description ? "interview-description-error" : "interview-description-help"} />
        {errors.description ? <small id="interview-description-error" className="interview-field-error" role="alert">{errors.description}</small>
          : <small id="interview-description-help">Informe a data, o horário e como participar.</small>}
      </label>
      <div className="interview-link-form-footer"><button className="button" type="submit" disabled={busy}>
        <Link2 size={16} aria-hidden="true" />{busy ? "Salvando…" : "Salvar link e legenda"}
      </button><small>O candidato receberá um aviso após salvar.</small></div>
    </fieldset>
  </form>;
}
