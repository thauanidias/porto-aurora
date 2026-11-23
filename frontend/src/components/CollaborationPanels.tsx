import { UsersRound, Search, RefreshCw, ArrowRight, Sparkles, Columns3, CheckCircle2 } from "lucide-react";
import { CandidateCompatibility, compatibilityCategory } from "./CandidateCompatibility";
import { ProfilePhoto } from "./ProfilePhoto";
import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  api,
  post,
  put,
  obj,
  str,
  rows,
  type Row,
  type Collection,
} from "../lib/api";
import { useSession } from "../lib/session";
import { simpleSchema } from "../lib/forms";
import { Badge, ErrorBox, DataTable } from "./ui";
import {
  OperationModal,
  RecordDetail,
  type Operation,
} from "../pages/Resources";

export function ComparePanel({
  vacancyId,
  applications,
}: {
  vacancyId: string;
  applications: Row[];
}) {
  const [selected, setSelected] = useState<string[]>([]);
  const [confirmed, setConfirmed] = useState<string[]>([]);
  const query = useQuery({
    queryKey: ["compare", vacancyId, confirmed],
    queryFn: () =>
      api<Collection & { notice: string }>(
        "/vacancies/" + vacancyId + "/compare?ids=" + confirmed.join(","),
      ),
    enabled: confirmed.length >= 2,
  });
  return (
    <section className="surface padded compare-panel">
      <header className="rediscovery-heading"><span className="rediscovery-heading-icon"><Columns3 size={24} aria-hidden="true" /></span><div><h2>Comparar candidatos</h2><p>Escolha de 2 a 6 pessoas para conferir os critérios e resultados lado a lado.</p></div><span className="compare-selection-count" aria-live="polite">{selected.length} de 6 selecionados</span></header>
      {applications.length < 2 && <div className="compare-help"><UsersRound size={20} aria-hidden="true" /><p>{applications.length ? "Há apenas uma candidatura disponível. A comparação será liberada quando houver pelo menos duas." : "Os candidatos aparecerão aqui quando houver inscrições nesta vaga."}</p></div>}
      <div className="compare-candidate-grid">
        {applications.map(row => <label className={"compare-candidate-option" + (selected.includes(row.id) ? " is-selected" : "")} key={row.id}>
          <input type="checkbox" aria-label={"Selecionar " + str(obj(row.candidate).name)} checked={selected.includes(row.id)} disabled={selected.length >= 6 && !selected.includes(row.id)} onChange={event => { setSelected(event.target.checked ? [...selected, row.id] : selected.filter(id => id !== row.id)); setConfirmed([]); }} />
          <ProfilePhoto candidateId={str(row.candidate_id)} name={str(obj(row.candidate).name)} profileReady={!obj(row.candidate).blind} />
          <div className="compare-candidate-copy"><strong>{str(obj(row.candidate).name)}</strong><span>{str(row.stage_name) || "Candidatura nesta vaga"}</span><Badge value={row.status} /></div>
          {selected.includes(row.id) && <CheckCircle2 className="compare-selected-icon" size={19} aria-hidden="true" />}
        </label>)}
      </div>
      {applications.length > 0 && <div className="compare-selection-toolbar"><div><strong>{selected.length >= 2 ? "Tudo pronto para comparar" : "Selecione pelo menos 2 candidatos"}</strong><p>Você pode comparar até 6 pessoas por vez.</p></div><div className="actions"><button className="button secondary" disabled={!selected.length} onClick={() => { setSelected([]); setConfirmed([]); }}>Limpar seleção</button><button className="button" disabled={selected.length < 2 || query.isFetching} onClick={() => setConfirmed([...selected])}><Columns3 size={17} />{query.isFetching ? "Comparando…" : "Comparar selecionados"}</button></div></div>}
      <ErrorBox error={query.error} />
      {query.isFetching && <p role="status">Preparando comparação dos candidatos…</p>}
      {confirmed.length >= 2 && query.data && (
        <>
          <p className="alert">{query.data.notice}</p>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Critério</th>
                  {query.data.items.map((row) => (
                    <th key={row.id}>
                      <Link to={"/app/candidaturas/" + row.id}>
                        {str(obj(row.candidate).name)}
                      </Link>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {[
                  ["Situação", "status"],
                  ["Aderência objetiva", "objective"],
                  ["Nota composta", "total"],
                  ["Requisito eliminatório", "knockout"],
                ].map(([name, key]) => (
                  <tr key={key}>
                    <th>{name}</th>
                    {query.data.items.map((row) => (
                      <td key={row.id}>
                        {key === "status" ? (
                          <Badge value={row[key]} />
                        ) : row[key] == null ? (
                          "—"
                        ) : typeof row[key] === "boolean" ? (
                          row[key] ? (
                            "Não atendido"
                          ) : (
                            "Atendido"
                          )
                        ) : (
                          str(row[key]) + "%"
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
                <tr>
                  <th>Consenso</th>
                  {query.data.items.map((row) => (
                    <td key={row.id}>
                      {obj(row.consensus).sealed
                        ? "Aguardando pareceres"
                        : str(obj(row.consensus).mean) || "—"}
                    </td>
                  ))}
                </tr>
                <tr>
                  <th>Dispersão dos pareceres</th>
                  {query.data.items.map((row) => (
                    <td key={row.id}>
                      {str(obj(row.consensus).dispersion) || "—"}
                    </td>
                  ))}
                </tr>
                {rows(query.data.items[0]?.criteria).map((c) => (
                  <tr key={str(c.key)}>
                    <th>
                      {str(c.name)} · {str(c.weight)}%
                    </th>
                    {query.data.items.map((row) => {
                      const criterion = rows(row.criteria).find(
                        (v) => v.key === c.key,
                      );
                      return (
                        <td key={row.id}>
                          {str(criterion?.normalized) || "—"}%
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}
export function RediscoveryPanel({ vacancyId }: { vacancyId: string }) {
  const [page, setPage] = useState(1);
  const query = useQuery({
    queryKey: ["rediscover", vacancyId, page],
    queryFn: () =>
      api<Collection & { notice: string; model_version: number }>(
        "/vacancies/" + vacancyId + "/rediscover?page_number=" + page,
      ),
  });
  return (
    <section className="surface padded rediscovery-panel">
      <header className="rediscovery-heading"><span className="rediscovery-heading-icon"><Sparkles size={24} aria-hidden="true" /></span><div><h2>Redescobrir talentos</h2><p>Encontre perfis de processos anteriores compatíveis com esta oportunidade.</p></div>{query.isSuccess && <span className="rediscovery-total">{query.data.total} {query.data.total === 1 ? "perfil disponível" : "perfis disponíveis"}</span>}</header>
      <div className="rediscovery-guidance"><UsersRound size={18} aria-hidden="true" /><p>Consulte a compatibilidade, analise o perfil e escolha quem deseja considerar para a vaga.</p></div>
      <ErrorBox error={query.error} />
      {query.isPending ? <p role="status">Buscando talentos…</p> : !query.isError && !query.data?.items.length ? <div className="rediscovery-empty"><span className="rediscovery-empty-icon"><Search size={30} aria-hidden="true" /></span><h3>Nenhum talento disponível neste momento</h3><p>Aqui aparecem perfis com autorização vigente para o banco de talentos e que ainda não se candidataram a esta vaga.</p><p className="muted">Quem já está inscrito continua no acompanhamento da seleção.</p><div className="actions"><Link className="button" to="/app/candidatos">Consultar banco de candidatos<ArrowRight size={16} /></Link><button className="button secondary" disabled={query.isFetching} onClick={() => void query.refetch()}><RefreshCw size={16} />{query.isFetching ? "Buscando…" : "Buscar novamente"}</button></div></div> : null}
      <div className="rediscovery-list">{(query.data?.items ?? []).map(r => <article className={"rediscovery-card compatibility-" + compatibilityCategory(r)} key={r.id}>
        <div className="rediscovery-person"><ProfilePhoto candidateId={r.id} name={str(obj(r.candidate).name)} profileReady={!obj(r.candidate).blind} /><div><h3>{str(obj(r.candidate).name)}</h3><span className="muted">Perfil cadastrado em {new Date(str(r.registered_at)).toLocaleDateString("pt-BR")}</span></div></div>
        <div>{r.compatibility_rank != null && <strong>{str(r.compatibility_rank)}º no ranking</strong>}<CandidateCompatibility row={r} details /></div>
        <Link className="button secondary" to={"/app/candidatos/" + r.id}>Analisar perfil</Link>
      </article>)}</div>
      {query.isSuccess && <details className="rediscovery-details"><summary>Como os perfis são encontrados</summary><p>A compatibilidade usa os mesmos critérios profissionais desta vaga, com o perfil atual e autorização vigente. O RH decide quem considerar; aparecer nesta lista não cria uma candidatura.</p><small>Modelo de compatibilidade · versão {query.data.model_version ?? "—"}</small></details>}
      {Boolean(query.data?.total) && <footer className="task-footer"><span>{query.data?.total} perfis no banco de talentos</span><div className="pagination"><button className="button secondary small" disabled={page === 1} onClick={() => setPage(page - 1)}>Anterior</button><span>Página {page}</span><button className="button secondary small" disabled={page * 25 >= (query.data?.total ?? 0)} onClick={() => setPage(page + 1)}>Próxima</button></div></footer>}

    </section>
  );
}
export function ConsensusPanel({ applicationId }: { applicationId: string }) {
  const query = useQuery({
    queryKey: ["consensus", applicationId],
    queryFn: () => api<Row>("/applications/" + applicationId + "/consensus"),
  });
  return (
    <div>
      <h3>Painel de consenso</h3>
      <ErrorBox error={query.error} />
      {query.data?.sealed ? (
        <p className="alert">
          Os resultados permanecem lacrados até todos concluírem suas avaliações
          independentes.
        </p>
      ) : (
        <div className="metric-grid">
          {[
            ["Média", "mean"],
            ["Desvio padrão", "dispersion"],
            ["Maior divergência", "divergence"],
          ].map(([name, key]) => (
            <div className="metric" key={key}>
              <span>{name}</span>
              <strong>
                {query.data?.[key] == null
                  ? "—"
                  : Number(query.data[key]).toFixed(2)}
              </strong>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
export function CalibrationPanel() {
  const query = useQuery({
    queryKey: ["calibration"],
    queryFn: () =>
      api<Collection & { notice: string }>("/analytics/calibration"),
  });
  return (
    <section className="surface padded">
      <h2>Calibração de avaliadores</h2>
      <p>{query.data?.notice}</p>
      <ErrorBox error={query.error} />
      <DataTable
        data={query.data?.items ?? []}
        columns={[
          "name",
          "count",
          "mean",
          "dispersion",
          "peer_deviation",
          "comparable_count",
        ]}
      />
    </section>
  );
}
export function CandidateTools({ candidateId }: { candidateId: string }) {
  const client = useQueryClient();
  const session = useSession();
  const can = session.data?.permissions.includes("talent.manage");
  const [error, setError] = useState<unknown>();
  const [operation, setOperation] = useState<Operation | null>(null);
  const query = useQuery({
    queryKey: ["candidate-labels", candidateId],
    queryFn: () => api<Collection>("/candidates/" + candidateId + "/labels"),
    enabled: Boolean(can),
  });
  const processes = useQuery({
    queryKey: ["candidate-processes", candidateId],
    queryFn: () => api<Collection>("/candidates/" + candidateId + "/processes"),
  });
  return (
    <section className="surface padded">
      <h2>Histórico entre processos</h2>
      <ErrorBox error={processes.error} />
      <DataTable
        data={processes.data?.items ?? []}
        columns={["vacancy_title", "stage_name", "status", "created_at"]}
        actions={(r) => (
          <Link to={"/app/candidaturas/" + r.id}>Ver processo</Link>
        )}
      />
      {can && (
        <>
          <button
            className="button secondary"
            onClick={() =>
              setOperation({
                title: "Convidar para processo seletivo",
                schema: simpleSchema({
                  vacancy_id: { type: "string", title: "Vaga" },
                  reason: { type: "string", title: "Justificativa" },
                }),
                run: (data) =>
                  post("/vacancies/" + str(data.vacancy_id) + "/invite", {
                    candidate_id: candidateId,
                    reason: data.reason,
                  }),
              })
            }
          >
            Convidar para vaga
          </button>
          <h3>Tags e favoritos</h3>
          <ErrorBox error={error ?? query.error} />
          {query.data?.items.map((r) => (
            <span className="tag" key={r.id}>
              {str(r.label)}
              {r.user_id === session.data?.user.id && (
                <button
                  aria-label={"Remover " + str(r.label)}
                  onClick={async () => {
                    try {
                      await api("/candidate-labels/" + r.id, {
                        method: "DELETE",
                      });
                      await client.invalidateQueries({
                        queryKey: ["candidate-labels", candidateId],
                      });
                    } catch (e) {
                      setError(e);
                    }
                  }}
                >
                  ×
                </button>
              )}
            </span>
          ))}
          <button
            className="button secondary"
            onClick={() =>
              setOperation({
                title: "Adicionar ao banco de talentos",
                schema: simpleSchema({
                  pool_id: { type: "string", title: "Banco de talentos" },
                }),
                run: (data) =>
                  post(
                    "/talent-pools/" +
                      str(data.pool_id) +
                      "/members/" +
                      candidateId,
                  ),
              })
            }
          >
            Incluir em banco
          </button>
        </>
      )}
      <OperationModal
        operation={operation}
        onClose={() => setOperation(null)}
      />
    </section>
  );
}
export function NoteActions({ message }: { message: Row }) {
  const session = useSession();
  const [operation, setOperation] = useState<Operation | null>(null);
  const [history, setHistory] = useState<Collection | null>(null);
  const [error, setError] = useState<unknown>();
  if (message.visibility === "CANDIDATE") return null;
  return (
    <>
      <Badge value={message.visibility} />
      <ErrorBox error={error} />
      <div className="actions">
        {message.sender_id === session.data?.user.id && (
          <>
            <button
              className="text-button"
              onClick={() =>
                setOperation({
                  title: "Editar nota interna",
                  schema: simpleSchema({
                    body: { type: "string", title: "Nota" },
                    reason: { type: "string", title: "Justificativa" },
                  }),
                  initial: { body: message.body },
                  run: (data) =>
                    put("/messages/" + message.id, {
                      ...data,
                      version: message.version,
                    }),
                })
              }
            >
              Editar nota
            </button>
            {["TEAM", "RH"].includes(str(message.visibility)) && (
              <button
                className="text-button"
                onClick={() =>
                  setOperation({
                    title: "Mencionar pessoa da equipe",
                    schema: simpleSchema({
                      user_id: { type: "string", title: "Pessoa" },
                    }),
                    run: (data) =>
                      post("/messages/" + message.id + "/mentions", data),
                  })
                }
              >
                Mencionar
              </button>
            )}
          </>
        )}
        <button
          className="text-button"
          onClick={async () => {
            try {
              setHistory(
                await api<Collection>("/messages/" + message.id + "/history"),
              );
            } catch (e) {
              setError(e);
            }
          }}
        >
          Histórico da nota
        </button>
      </div>
      {history &&
        history.items.map((row) => (
          <details key={row.id}>
            <summary>{str(row.created_at)}</summary>
            <RecordDetail value={{ antes: row.before, depois: row.after }} />
          </details>
        ))}
      <OperationModal
        operation={operation}
        onClose={() => setOperation(null)}
      />
    </>
  );
}
