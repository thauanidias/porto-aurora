import { CandidateFeedbackButton } from "../components/CandidateFeedback";
import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, post, str, rows, type Row, type Collection } from "../lib/api";
import { PageTitle, ErrorBox, DataTable } from "../components/ui";
import { OperationModal, type Operation } from "./Resources";
import { simpleSchema } from "../lib/forms";
import { MessageSquareHeart, ClipboardList, ArrowRight } from "lucide-react";

export function ReferralsPage() {
  const [operation, setOperation] = useState<Operation | null>(null);
  const query = useQuery({
    queryKey: ["referrals"],
    queryFn: () => api<Collection>("/referrals"),
  });
  const jobs = useQuery({
    queryKey: ["referral-jobs"],
    queryFn: () => api<Collection>("/internal/vacancies"),
  });
  return (
    <>
      <PageTitle
        title="Minhas indicações"
        subtitle="Indique profissionais. A participação depende do interesse e consentimento da pessoa indicada."
        actions={
          <button
            className="button"
            onClick={() =>
              setOperation({
                title: "Indicar profissional",
                schema: simpleSchema({
                  referral_vacancy_id: { type: "string", title: "Vaga" },
                  name: { type: "string", title: "Nome", minLength: 3 },
                  email: { type: "string", format: "email", title: "E-mail" },
                  comment: { type: "string", title: "Contexto profissional" },
                }),
                run: ({ referral_vacancy_id, ...data }) =>
                  post("/referrals", {
                    ...data,
                    vacancy_id: referral_vacancy_id,
                  }),
              })
            }
          >
            Nova indicação
          </button>
        }
      />
      <ErrorBox error={query.error} />
      <section className="surface padded">
        <DataTable
          data={query.data?.items ?? []}
          columns={["name", "email", "status", "created_at"]}
        />
        <Link to="/oportunidades-internas">
          Consultar oportunidades internas
        </Link>
        {jobs.error && <ErrorBox error={jobs.error} />}
      </section>
      <OperationModal
        operation={operation}
        onClose={() => setOperation(null)}
      />
    </>
  );
}
export function ImportPage() {
  const [preview, setPreview] = useState<Row | null>(null);
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const client = useQueryClient();
  return (
    <>
      <PageTitle
        title="Importar candidatos"
        subtitle="Revise os registros antes de confirmar a importação."
      />
      <section className="surface padded">
        <p>
          Envie um CSV UTF-8 com as colunas{" "}
          <code>name;email;phone;city;state</code>. Nome e e-mail são
          obrigatórios. Limite de 1.000 registros e 2 MB.
        </p>
        <p>
          Os registros importados permanecem sem consentimento para o banco de
          talentos até a autorização de cada candidato.
        </p>
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setMessage("");
            setError(undefined);
            try {
              setPreview(
                await api<Row>("/imports/candidates/preview", {
                  method: "POST",
                  body: new FormData(e.currentTarget),
                }),
              );
            } catch (err) {
              setError(err);
            } finally {
              setBusy(false);
            }
          }}
        >
          <label className="field">
            <span>Arquivo CSV</span>
            <input type="file" name="file" accept=".csv" required />
          </label>
          <button className="button secondary" disabled={busy}>
            Validar arquivo
          </button>
        </form>
        <ErrorBox error={error} />
        {message && (
          <p className="alert success" role="status">
            {message}
          </p>
        )}
        {preview && (
          <>
            <h2>Prévia · {str(preview.count)} registros válidos</h2>
            <DataTable
              data={rows(preview.items).map((r, i) => ({
                ...r,
                id: String(i),
              }))}
              columns={["name", "email", "phone", "city", "state"]}
            />
            {rows(preview.errors).map((r, i) => (
              <p role="alert" key={i}>
                Linha {str(r.line)}: {str(r.message)}
              </p>
            ))}
            <button
              className="button"
              disabled={!preview.can_confirm || busy}
              onClick={async () => {
                setBusy(true);
                try {
                  const result = await post<{ message: string }>(
                    "/imports/candidates/" + preview.id + "/confirm",
                  );
                  setMessage(result.message);
                  setPreview(null);
                  await client.invalidateQueries({ queryKey: ["candidates"] });
                } catch (err) {
                  setError(err);
                } finally {
                  setBusy(false);
                }
              }}
            >
              Confirmar importação
            </button>
          </>
        )}
      </section>
    </>
  );
}
export function SurveysPage() {
  const surveys = useQuery({
    queryKey: ["surveys"],
    queryFn: () => api<Collection>("/privacy/surveys"),
  });
  const [operation, setOperation] = useState<Operation | null>(null);
  return (
    <>
      <PageTitle
        title="Sua experiência"
        subtitle="Compartilhe sua percepção do processo seletivo."
      />
      <ErrorBox error={surveys.error} />
      <section className="surface experience-feedback-card">
        <header><span className="experience-icon"><MessageSquareHeart size={30} aria-hidden="true" /></span><div><span className="privacy-eyebrow">SUA OPINIÃO IMPORTA</span><h2>Como foi participar da nossa seleção?</h2><p>Conte o que foi bom e o que podemos melhorar. Seu relato será recebido pela equipe de RH.</p></div></header>
        <div className="experience-feedback-topics"><span>Elogios</span><span>Sugestões</span><span>Dificuldades</span></div>
        <footer><CandidateFeedbackButton /></footer>
      </section>
      {surveys.isPending && <p role="status">Carregando pesquisas disponíveis…</p>}
      {surveys.isError && <button className="button secondary" onClick={() => void surveys.refetch()}>Tentar novamente</button>}
      {Boolean(surveys.data?.items.length) && <section aria-label="Pesquisas disponíveis">
        <h2>Pesquisas disponíveis</h2>
        <ul className="experience-surveys">
          {surveys.data?.items.map(r => <li className="surface" key={r.id}>
            <span className="experience-icon"><ClipboardList size={24} aria-hidden="true" /></span>
            <div><h3>{str(r.name)}</h3><p>Compartilhe sua percepção do processo seletivo.</p></div>
            <button
              className="button"
              onClick={() =>
                setOperation({
                  title: str(r.name),
                  schema: simpleSchema({
                    answers: {
                      type: "object",
                      properties: {
                        ...Object.fromEntries(
                          (Array.isArray(
                            (r.data as Record<string, unknown>)?.questions,
                          )
                            ? (r.data as { questions: string[] }).questions
                            : []
                          ).map((q, i) => [
                            String(i),
                            { type: "string", title: q, minLength: 1 },
                          ]),
                        ),
                        nps: {
                          type: "integer",
                          minimum: 0,
                          maximum: 10,
                          title:
                            "De 0 a 10, quanto você recomenda este processo?",
                        },
                      },
                    },
                  }),
                  run: (data) =>
                    post("/privacy/surveys/" + r.id + "/respond", data),
                })
              }
            >
              Responder pesquisa <ArrowRight size={16} aria-hidden="true" />
            </button>
          </li>)}
        </ul>
      </section>}
      <OperationModal
        operation={operation}
        onClose={() => setOperation(null)}
      />
    </>
  );
}
