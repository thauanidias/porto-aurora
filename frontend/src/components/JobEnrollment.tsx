import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { CheckCircle2, FileText } from "lucide-react";
import { api, post, str, type Collection, type Row } from "../lib/api";
import { ErrorBox } from "./ui";

export function JobEnrollment({ job, invitationToken }: { job: Row; invitationToken?: string }) {
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const applications = useQuery({ queryKey: ["enrollment-existing", job.id], queryFn: () => api<Collection>("/applications?vacancy_id=" + job.id) });
  const documents = useQuery({ queryKey: ["application-cv"], queryFn: () => api<Collection>("/documents?type_name=CURRICULO&page_size=100") });
  const readiness = useQuery({ queryKey: ["application-readiness"], queryFn: () => api<{ ready: boolean; missing: string[]; cv_id: string | null }>("/candidates/me/application-readiness"), staleTime: 0 });
  const consent = useQuery({ queryKey: ["enrollment-consent"], queryFn: async () => {
    let page = 1;
    while (true) {
      const result = await api<Collection>("/privacy/my-consent-receipts?page_number=" + page);
      if (result.items.some(item => item.context === "CADASTRO")) return true;
      if (!result.items.length || page * result.page_size >= result.total) return false;
      page++;
    }
  } });
  if (applications.isPending || consent.isPending || documents.isPending || readiness.isPending) return <p role="status">Conferindo seu cadastro…</p>;
  if (applications.isError || consent.isError || documents.isError || readiness.isError) return <><ErrorBox error={applications.error ?? consent.error ?? documents.error ?? readiness.error} /><button className="button secondary" onClick={() => { void applications.refetch(); void consent.refetch(); void documents.refetch(); void readiness.refetch(); }}>Tentar novamente</button></>;
  const existing = applications.data?.items[0];
  if (existing) return <div className="job-enrollment"><CheckCircle2 size={30} aria-hidden="true" /><h3>Você já está inscrito nesta vaga</h3><p>Acompanhe as atualizações do seu processo seletivo na área do candidato.</p><Link className="button" to={"/candidato/candidaturas/" + existing.id}>Ver minha candidatura</Link></div>;
  if (!consent.data) return <div className="job-enrollment"><h3>Conclua seu primeiro acesso</h3><p>Leia e aceite o termo na área do candidato. Depois, você poderá se inscrever nas vagas usando o mesmo cadastro.</p><Link className="button" to={"/candidato/perfil?next=" + encodeURIComponent(location.pathname + "?candidatar=1")}>Continuar meu cadastro</Link></div>;
  if (!readiness.data?.ready) return <div className="job-enrollment"><h3>Complete seu perfil para se candidatar</h3><p>Preencha e salve as informações abaixo e anexe seu currículo.</p><ul>{readiness.data?.missing.map(field => <li key={field}>{field}</li>)}</ul><Link className="button" to={"/candidato/perfil?next=" + encodeURIComponent(location.pathname + "?candidatar=1")}>Completar Meu perfil</Link></div>;
  const resumes = documents.data?.items.filter(item => item.type_name === "CURRICULO" && item.status !== "REJECTED" && ["CLEAN", "NOT_CONFIGURED"].includes(str(item.scan_status))) ?? [];
  return <form className="job-enrollment" onSubmit={async event => {
    event.preventDefault();
    if (busy) return;
    const values = new FormData(event.currentTarget);
    setBusy(true); setError(undefined);
    try {
      const result = await post<Row>("/applications", { vacancy_id: job.id, enrollment: true, cv_id: values.get("cv_id") || null,
        ...(invitationToken ? { invitation_token: invitationToken } : {}),
        utm: Object.fromEntries([...new URLSearchParams(location.search)].filter(([key]) => ["utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term"].includes(key))),
      });
      await applications.refetch();
      navigate("/candidato/candidaturas/" + result.id);
    } catch (err) { setError(err); await applications.refetch(); } finally { setBusy(false); }
  }}>
    <h3>Candidate-se com seu perfil</h3><p>Seu cadastro já está pronto. Confirme sua participação nesta vaga usando os dados do seu perfil.</p>
    <p className="job-enrollment-consent"><CheckCircle2 size={18} aria-hidden="true" /> Termo de consentimento já aceito no seu cadastro.</p>
    <label className="field"><span><FileText size={16} aria-hidden="true" /> Currículo para esta vaga</span><select name="cv_id" aria-label="Currículo para esta vaga" defaultValue={str(resumes[0]?.id)} disabled={busy}>
      {resumes.map(item => <option key={item.id} value={item.id}>{str(item.filename)} · versão {str(item.revision)}</option>)}
    </select></label>
    <p className="muted">Cada vaga tem seu próprio acompanhamento. Você pode participar de mais de um processo seletivo.</p>
    <ErrorBox error={error} /><div className="resume-upload-actions"><button className="button" disabled={busy}>{busy ? "Enviando…" : "Confirmar candidatura"}</button><Link className="button secondary" to={"/candidato/perfil?next=" + encodeURIComponent(location.pathname + "?candidatar=1")}>Revisar meu perfil</Link></div>
  </form>;
}
