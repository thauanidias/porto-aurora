import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { ArrowRight, BriefcaseBusiness, Building2, FileText, MapPin } from "lucide-react";
import { api, str, type Collection } from "../lib/api";
import { label } from "../lib/labels";
import { Empty, ErrorBox, PageTitle } from "../components/ui";
import { useSession } from "../lib/session";

export function CandidateVacancies() {
  const session = useSession();
  const [params] = useSearchParams();
  const internal = Boolean(session.data?.permissions.includes("internal.view"));
  const [page, setPage] = useState(1);
  const query = useQuery({
    queryKey: ["candidate-available-vacancies", internal, page],
    queryFn: () => api<Collection>(`${internal ? "/internal/vacancies" : "/public/vacancies"}?page_number=${page}&page_size=25`),
    enabled: !session.isPending,
  });
  return <>
    <div className="candidate-opportunities">
    {params.get("selecionar") === "1" && <p className="alert" role="status">Perfil salvo. Selecione a vaga desejada abaixo para concluir sua inscrição.</p>}
    <header className="candidate-opportunities-header">
      <span className="candidate-opportunities-eyebrow">OPORTUNIDADES Porto Aurora</span>
      <PageTitle title={internal ? "Vagas internas disponíveis" : "Vagas disponíveis"} subtitle="Encontre seu próximo desafio. Explore as oportunidades e conheça os detalhes de cada vaga." />
      {query.isSuccess && <span className="candidate-opportunities-count"><BriefcaseBusiness size={16} aria-hidden="true" />{query.data.total} {query.data.total === 1 ? "vaga disponível" : "vagas disponíveis"}</span>}
    </header>
    <section aria-label="Oportunidades disponíveis" aria-busy={query.isPending}>
      <ErrorBox error={query.error} />
      {query.isPending ? <p role="status">Carregando vagas…</p> : query.isError ? <button className="button secondary" onClick={() => void query.refetch()}>Tentar novamente</button> : !query.data?.items.length ? <Empty title="Nenhuma vaga disponível no momento" /> : <ul className="candidate-vacancy-list">
        {query.data.items.map(job => <li key={job.id}>
          <span className="candidate-vacancy-icon" aria-hidden="true"><BriefcaseBusiness size={24} strokeWidth={1.6} /></span>
          <div className="candidate-vacancy-content">
            <h2>{str(job.title)}</h2>
            {(str(job.city) || str(job.state)) && <p className="candidate-vacancy-location"><MapPin size={16} aria-hidden="true" />{[str(job.city), str(job.state)].filter(Boolean).join(" · ")}</p>}
            <div className="candidate-vacancy-tags">
              {str(job.modality) && <span><Building2 size={14} aria-hidden="true" />{({ PRESENCIAL: "Presencial", REMOTO: "Remoto", HIBRIDO: "Híbrido" } as Record<string, string>)[str(job.modality)] ?? label(str(job.modality))}</span>}
              {str(job.contract_type) && <span><FileText size={14} aria-hidden="true" />{label(str(job.contract_type))}</span>}
            </div>
          </div>
          <Link className="button" to={(internal ? "/oportunidades-internas/" : "/carreiras/vagas/") + str(job.slug)} aria-label={"Ver detalhes da vaga: " + str(job.title)}>Ver detalhes <ArrowRight size={17} aria-hidden="true" /></Link>
        </li>)}
      </ul>}
      {(query.data?.total ?? 0) > 25 && <div className="pagination">
        <button className="button secondary small" disabled={page === 1} onClick={() => setPage(page - 1)}>Anterior</button>
        <span>Página {page}</span>
        <button className="button secondary small" disabled={page * 25 >= (query.data?.total ?? 0)} onClick={() => setPage(page + 1)}>Próxima</button>
      </div>}
    </section>
    </div>
  </>;
}
