import { useEffect, useRef, useState } from "react";
import { Paperclip, FileText, Download, CheckCircle2 } from "lucide-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, download, str, type Collection, type Row } from "../lib/api";
import { date } from "../lib/labels";
import { ErrorBox } from "./ui";

export function ResumeUpload({ onSuggestions, onBusyChange }: {
  onSuggestions: (data: Record<string, unknown>) => void;
  onBusyChange: (busy: boolean) => void;
}) {
  const client = useQueryClient();
  const resume = useQuery({ queryKey: ["profile-resume"],
    queryFn: () => api<Collection>("/documents?type_name=CURRICULO&page_size=1") });
  const attached = resume.data?.items[0];
  const fileInput = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [filename, setFilename] = useState("");
  const [text, setText] = useState("");
  const [message, setMessage] = useState("");
  const [missing, setMissing] = useState<string[]>([]);
  const [uncertain, setUncertain] = useState<string[]>([]);
  const [found, setFound] = useState<string[]>([]);
  type Result = { suggestions: Record<string, unknown>; text: string; message: string; missing?: string[]; uncertain?: string[]; engine: string; pages?: number; ocr_pages?: number[] };
  type Job = { status: "QUEUED" | "RUNNING" | "COMPLETED" | "FAILED"; message?: string; result?: Result };
  const [jobId, setJobId] = useState("");
  const handled = useRef("");
  const callbacks = useRef({onSuggestions, onBusyChange});
  useEffect(() => {callbacks.current = {onSuggestions, onBusyChange};}, [onSuggestions, onBusyChange]);
  const job = useQuery({queryKey: ["resume-import", jobId], enabled: Boolean(jobId), queryFn: () => api<Job>(`/documents/${jobId}/profile-import`),
    refetchInterval: query => ["COMPLETED", "FAILED"].includes(query.state.data?.status ?? "") ? false : 2000,
    retry: 2,
  });
  const applyResult = (result: Result) => {
    callbacks.current.onSuggestions(result.suggestions); setText(result.text);
    const names: Record<string, string> = { name: "Nome", phone: "Telefone", city: "Cidade", state: "Estado", education: "Formação", experiences: "Experiências", skills: "Competências", certifications: "Certificações", courses: "Cursos", languages: "Idiomas", notes: "Observações profissionais", desired_position: "Cargo pretendido" };
    const professional = result.suggestions.profile && typeof result.suggestions.profile === "object" ? result.suggestions.profile as Record<string, unknown> : {};
    const personal = result.suggestions.personal as Record<string, unknown> | undefined;
    setFound([...Object.keys(result.suggestions).filter(key => !["profile", "personal"].includes(key)), ...Object.keys(professional)].map(key => names[key]).filter(Boolean).concat(personal ? Object.keys(personal).map(key => ({cpf: "CPF", birth_date: "Data de nascimento", email: "E-mail do currículo", address: "Endereço"}[key] ?? key)) : []));
    setMissing(result.missing ?? []); setUncertain(result.uncertain ?? []);
    setMessage(result.engine === "local-ai" && result.text.trim()
      ? Object.keys(result.suggestions).length
        ? "Leitura concluída. Confira as informações sugeridas no formulário abaixo. Os campos já preenchidos são mantidos; revise os dados e salve seu perfil para confirmar."
        : "Não localizamos informações suficientes para preencher os campos. Consulte o texto do currículo e preencha manualmente."
      : result.message);
    if (result.pages) setMessage(previous => `${previous} ${result.pages} página(s) lida(s)${result.ocr_pages?.length ? `; OCR utilizado em ${result.ocr_pages.length}` : ""}.`);
  };
  const resultRef = useRef(applyResult);
  useEffect(() => {resultRef.current = applyResult;});
  useEffect(() => {
    if (!jobId || handled.current === jobId) return;
    const state = job.data;
    if (!["COMPLETED", "FAILED"].includes(state?.status ?? "") && !job.isError) return;
    // Deliver the external job result after commit, when sibling form drafts exist.
    const timer = window.setTimeout(() => {
      if (handled.current === jobId) return;
      handled.current = jobId;
      if (state?.status === "COMPLETED" && state.result) resultRef.current(state.result);
      else {
        setError(job.error ?? new Error(state?.message || "Não foi possível ler o currículo. Tente novamente."));
        if (job.isError) setJobId("");
      }
      setBusy(false); callbacks.current.onBusyChange(false);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [jobId, job.data, job.error, job.isError]);
  const analyze = async (document: Row) => {
    handled.current = "";
    const state = await api<Job>(`/documents/${document.id}/profile-import`, {method: "POST"});
    client.setQueryData(["resume-import", document.id], state);
    setJobId(document.id);
    await client.invalidateQueries({queryKey: ["resume-import", document.id]});
  };
  const [downloading, setDownloading] = useState(false);
  const size = Number(attached?.size);
  const fileSize = size > 0 ? size >= 1048576 ? (size / 1048576).toLocaleString("pt-BR", { maximumFractionDigits: 1 }) + " MB" : Math.max(1, Math.round(size / 1024)) + " KB" : "";
  const canDownload = attached && ["CLEAN", "NOT_CONFIGURED"].includes(str(attached.scan_status));
  return <section className="surface padded resume-upload">
    <div className="resume-upload-heading"><span className="resume-upload-symbol" aria-hidden="true"><FileText size={25} /></span><div><h2>Seu currículo, seu próximo passo</h2><p>Use as informações do seu currículo para completar o perfil com mais facilidade.</p></div></div>
    <ol className="resume-upload-steps"><li><span>1</span>Envie seu currículo</li><li><span>2</span>Confira os dados preenchidos</li><li><span>3</span>Salve seu perfil</li></ol>
    <ErrorBox error={error} />
    <ErrorBox error={resume.error} />
    <input ref={fileInput} hidden aria-label="Adicionar currículo (PDF, DOC ou DOCX)" type="file" accept=".pdf,.doc,.docx" disabled={busy} onChange={async event => {
      const file = event.currentTarget.files?.[0];
      event.currentTarget.value = "";
      if (!file) return;
      if (!/\.(pdf|doc|docx)$/i.test(file.name) || file.size > 10 * 1024 * 1024 || !file.size) { setError(new Error("Envie um PDF, DOC ou DOCX de até 10 MB.")); return; }
      setBusy(true); onBusyChange(true); setError(undefined); setText(""); setMessage(""); setFilename("");
      try {
        const form = new FormData(); form.set("file", file); form.set("type_name", "CURRICULO");
        const document = await api<Row>("/documents", { method: "POST", body: form });
        setFilename(file.name);
        client.setQueryData<Collection>(["profile-resume"], previous => ({ items: [document], total: (previous?.total ?? 0) + 1, page: 1, page_size: 1 }));
        await Promise.all([client.invalidateQueries({ queryKey: ["documents"] }), client.invalidateQueries({ queryKey: ["application-cv"] }), client.invalidateQueries({ queryKey: ["profile-resume"] }), client.invalidateQueries({queryKey: ["my-profile"]})]);
        await analyze(document);
      } catch (err) { setError(err); setBusy(false); onBusyChange(false); }
    }} />
    <div className="resume-upload-actions"><button type="button" className={attached ? "button secondary" : "button"} disabled={busy} onClick={() => fileInput.current?.click()}>
      <Paperclip size={18} aria-hidden="true" />
      {busy ? "Analisando currículo…" : attached ? "Trocar currículo" : "Importar currículo em PDF"}
    </button>
    {attached && <button type="button" className="button" disabled={busy || !canDownload} onClick={async () => {
      setBusy(true); onBusyChange(true); setError(undefined); setMessage(""); setMissing([]); setUncertain([]);
      try { await analyze(attached); } catch (err) { setError(err); setBusy(false); onBusyChange(false); }
    }}>Preencher perfil com este currículo</button>}</div>
    <p className="muted resume-upload-formats">PDF, DOC ou DOCX · Até 10 MB · PDF com até 30 páginas · OCR para páginas digitalizadas</p>
    {resume.isPending && <p className="muted" role="status">Consultando currículo anexado…</p>}
    {attached && <div className="resume-attachment" aria-label="Currículo anexado">
      <span className="resume-attachment-icon" aria-hidden="true"><FileText size={25} strokeWidth={1.7} /></span>
      <div className="resume-attachment-details">
        <p className="resume-attachment-label"><CheckCircle2 size={14} aria-hidden="true" />Currículo anexado</p>
        <strong>{str(attached.filename)}</strong>
        <p className="muted">{[str(attached.filename).split(".").pop()?.toUpperCase(), fileSize, attached.revision ? "Versão " + str(attached.revision) : "", attached.created_at ? "Enviado em " + date(attached.created_at) : ""].filter(Boolean).join(" · ")}</p>
        {!canDownload && <small className="muted">O arquivo está aguardando validação para download.</small>}
      </div>
      <button type="button" className="button secondary" disabled={downloading || !canDownload} onClick={async () => {
        setDownloading(true); setError(undefined);
        try { await download("/documents/" + attached.id + "/download", str(attached.filename)); }
        catch (err) { setError(err); } finally { setDownloading(false); }
      }}><Download size={17} aria-hidden="true" />{downloading ? "Baixando…" : "Baixar currículo"}</button>
    </div>}
    <p className="resume-upload-note">Preenchemos campos vazios e completamos as listas sem duplicar registros. Seus dados existentes são preservados. Revise antes de confirmar o salvamento.</p>
    {busy && <p role="status">{job.data?.message || "Estamos lendo o currículo. A análise continua mesmo se você sair desta página."}</p>}
    {filename && <p className="alert success" role="status">{filename} salvo para análise do RH.</p>}
    {message && <p role="status">{message}</p>}
    {found.length > 0 && <p><strong>Informações encontradas:</strong> {found.join(", ")}.</p>}
    {missing.length > 0 && <p>Informações não localizadas: {missing.join(", ")}. Complete os campos manualmente.</p>}
    {message && <p className="muted">Períodos parciais e níveis de idioma são mantidos como escritos no currículo, sem estimar datas ou notas. O e-mail de acesso permanece o da sua conta. Os dados do perfil só serão salvos após sua confirmação.</p>}
    {uncertain.length > 0 && <details><summary>Informações que precisam da sua confirmação</summary><p>Estes trechos não foram usados no preenchimento. Confira o currículo e informe os dados corretos nos campos abaixo.</p><ul>{uncertain.map((item, index) => <li key={index}>{item}</li>)}</ul></details>}
    {text && <details><summary>Consultar texto do currículo para completar formação e experiências</summary><p className="preserve">{text}</p></details>}
  </section>;
}
