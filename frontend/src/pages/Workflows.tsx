import { approvalSchema, simpleSchema, submitSchema } from "../lib/forms";
import { ExamForm } from "../components/ExamForm";
import { CandidateActivityLinks } from "../components/CandidateActivityLinks";
import { CandidateTestQuestionnaires } from "../components/TestQuestionnaire";
import { useTestQuestionnaires } from "../lib/useTestQuestionnaires";
import { useActivityLinks } from "../lib/activityLinks";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  api,
  post,
  put,
  download,
  obj,
  rows,
  str,
  type Collection,
  type Row,
} from "../lib/api";
import { useSession } from "../lib/session";
import {
  Badge,
  DataTable,
  Empty,
  ErrorBox,
  Modal,
  PageTitle,
} from "../components/ui";
import { OperationModal, RecordDetail, type Operation } from "./Resources";
import { date } from "../lib/labels";
import { testAvailability } from "../lib/testAvailability";
import { StageGate } from "../components/CandidateJourney";

export function OffersPage({ candidate = false }: { candidate?: boolean }) {
  const query = useQuery({
    queryKey: ["offers"],
    queryFn: () => api<Collection>("/offers"),
  });
  const [operation, setOperation] = useState<Operation | null>(null);
  const [detail, setDetail] = useState<Row | null>(null);
  const [error, setError] = useState<unknown>();
  const client = useQueryClient();
  const session = useSession();
  const act = async (fn: () => Promise<unknown>) => {
    setError(undefined);
    try {
      await fn();
      await client.invalidateQueries();
    } catch (e) {
      setError(e);
    }
  };
  return (
    <>
      <PageTitle
        title={candidate ? "Minhas ofertas" : "Cartas oferta"}
        subtitle="Condições versionadas e decisões registradas."
        actions={
          !candidate &&
          session.data?.permissions.includes("offer.create") && (
            <button
              className="button"
              onClick={() =>
                setOperation({
                  title: "Gerar carta oferta",
                  form: "offer",
                  run: (data) => post("/offers", data),
                })
              }
            >
              Nova oferta
            </button>
          )
        }
      />
      <ErrorBox error={error ?? query.error} />
      <section className="surface">
        <DataTable
          data={query.data?.items ?? []}
          columns={["number", "application_id", "status", "expires_at"]}
          onOpen={setDetail}
          actions={(row) => (
            <>
              <button
                className="text-button"
                onClick={() =>
                  act(() =>
                    download("/offers/" + row.id + "/pdf", "carta-oferta.pdf"),
                  )
                }
              >
                Baixar PDF
              </button>
              {candidate && row.status === "SENT" && (
                <button
                  className="text-button"
                  onClick={() =>
                    setOperation({
                      title: "Responder à carta oferta",
                      schema: simpleSchema({
                        decision: {
                          enum: ["ACCEPTED", "DECLINED"],
                          title: "Sua decisão",
                        },
                        reason: {
                          type: "string",
                          title: "Comentário (opcional)",
                        },
                      }),
                      run: (data) =>
                        post("/offers/" + row.id + "/respond", {
                          ...data,
                          version: row.version,
                        }),
                    })
                  }
                >
                  Responder
                </button>
              )}
              {!candidate &&
                session.data?.permissions.includes("offer.create") &&
                ["DRAFT", "PENDING_APPROVAL", "APPROVED", "SENT"].includes(
                  str(row.status),
                ) && (
                  <button
                    className="text-button"
                    onClick={() =>
                      setOperation({
                        title: "Cancelar oferta",
                        schema: simpleSchema({
                          reason: {
                            type: "string",
                            title: "Justificativa",
                            minLength: 5,
                          },
                        }),
                        run: (data) =>
                          post("/offers/" + row.id + "/cancel", {
                            ...data,
                            version: row.version,
                          }),
                      })
                    }
                  >
                    Cancelar oferta
                  </button>
                )}
              {!candidate && row.status === "DRAFT" && (
                <button
                  className="text-button"
                  onClick={() =>
                    setOperation({
                      title: "Solicitar aprovação da oferta",
                      schema: submitSchema,
                      run: (data) =>
                        post("/offers/" + row.id + "/submit", {
                          ...data,
                          version: row.version,
                          status: "PENDING_APPROVAL",
                        }),
                    })
                  }
                >
                  Solicitar aprovação
                </button>
              )}
              {!candidate &&
                row.status === "PENDING_APPROVAL" &&
                session.data?.permissions.includes("offer.approve") && (
                  <button
                    className="text-button"
                    onClick={() =>
                      setOperation({
                        title: "Aprovar oferta",
                        schema: approvalSchema,
                        run: (data) =>
                          post("/offers/" + row.id + "/approve", {
                            ...data,
                            version: row.version,
                          }),
                      })
                    }
                  >
                    Decidir
                  </button>
                )}
              {!candidate && row.status === "APPROVED" && (
                <button
                  className="text-button"
                  onClick={() => act(() => post("/offers/" + row.id + "/send"))}
                >
                  Disponibilizar ao candidato
                </button>
              )}
            </>
          )}
        />
      </section>
      <OperationModal
        operation={operation}
        onClose={() => setOperation(null)}
      />
      <Modal
        open={Boolean(detail)}
        onOpenChange={(v) => !v && setDetail(null)}
        title="Condições da oferta"
      >
        {detail && (
          <>
            <RecordDetail value={obj(detail.terms)} />
            <p>
              O aceite registra sua manifestação. Não constitui assinatura
              digital certificada.
            </p>
          </>
        )}
      </Modal>
    </>
  );
}

export function CandidateTests() {
  const questionnaires = useTestQuestionnaires();
  const links = useActivityLinks("TEST");
  const [starting, setStarting] = useState("");
  const query = useQuery({
    queryKey: ["test-assignments"],
    queryFn: () => api<Collection>("/test-assignments"),
    refetchInterval: 15000,
  });
  const [attempt, setAttempt] = useState<Row | null>(null);
  const [error, setError] = useState<unknown>();
  const client = useQueryClient();
  return (
    <>
      <PageTitle
        title="Meus testes"
        subtitle="Acesse os links de testes disponibilizados pelo RH para sua candidatura."
      />
      <ErrorBox error={error ?? query.error} />
        <CandidateTestQuestionnaires />
      <CandidateActivityLinks kind="TEST" />
      <StageGate section="tests" title="Realização dos testes">
      {query.data?.items.map((row) => (
        <section className="surface padded test-assignment" key={row.id}>
          <h2>{str(obj(row.snapshot).name)}</h2>
          {Boolean(row.result) && <p>Resultado: <Badge value={row.result} /> · Nota máxima: 100% · Aprovação: {str(obj(row.snapshot).pass_score)}%</p>}
          <p className="muted">{row.stage_unlocked === false ? "Teste registrado pelo RH. Disponível após o avanço desta candidatura para testes." : "Teste liberado pelo RH. Confira o prazo antes de iniciar."}</p>
          <p>
            Disponível a partir de {date(row.opens_at)} · Prazo:{" "}
            {date(row.due_at)}
          </p>
          {rows(row.attempts).map((a) => (
            <p key={a.id}>
              Tentativa {str(a.number)} · <Badge value={a.status} />
              {a.score != null ? " · Nota: " + str(a.score) + "%" : ""}
            </p>
          ))}
          {str(obj(row.snapshot).external_url) ? (
            !testAvailability(row) && (
              <a className="button" href={str(obj(row.snapshot).external_url)} target="_blank" rel="noopener noreferrer">
                Acessar teste
              </a>
            )
          ) : (
          <button
            className="button"
            disabled={Boolean(testAvailability(row)) || starting === row.id}
            onClick={async () => {
              setStarting(row.id);
              try {
                setAttempt(
                  await post<Row>("/test-assignments/" + row.id + "/start"),
                );
                setError(undefined);
              } catch (e) {
                setError(e);
              } finally {
                setStarting("");
              }
            }}
          >
            Iniciar ou continuar
          </button>
          )}
          {testAvailability(row) && <p>{testAvailability(row)}</p>}
        </section>
      ))}
        {!query.isPending && !query.data?.items.length && !links.data?.items.length && !questionnaires.data?.items.length && (
        <Empty title="Aguardando liberação do RH">
          Após sua aprovação na etapa anterior e a liberação do RH,
          o link para realizar o teste aparecerá aqui, junto com o prazo e as orientações.
        </Empty>
      )}
      </StageGate>
      <Modal
        open={Boolean(attempt)}
        onOpenChange={(v) => !v && setAttempt(null)}
        title="Realização do teste"
      >
        {attempt && (
          <StageGate section="tests" title="Respostas do teste" allowed={query.data?.items.find(row => row.id === attempt.assignment_id)?.stage_unlocked === true}>
          <ExamForm
            key={attempt.id}
            attempt={attempt}
            onDone={async () => {
              setAttempt(null);
              await client.invalidateQueries();
            }}
          />
          </StageGate>
        )}
      </Modal>
    </>
  );
}
export function PrivacyPage({ admin = false }: { admin?: boolean }) {
  const [viewedAt] = useState(() => Date.now());
  const [termDetail, setTermDetail] = useState<Row | null>(null);
  const [openingTerm, setOpeningTerm] = useState("");
  const [downloadingTerm, setDownloadingTerm] = useState("");
  async function downloadTerm(id: string) {
    setDownloadingTerm(id);
    setError(undefined);
    try {
      await download("/privacy/consent-receipts/" + id + "/document", "termo-consentimento-assinado.docx");
    } catch (err) {
      setError(err);
    } finally {
      setDownloadingTerm("");
    }
  }
  const [preferenceSaved, setPreferenceSaved] = useState(false);
  const [savingPreference, setSavingPreference] = useState(false);
  const [receiptPage, setReceiptPage] = useState(1);
  const [consentPage, setConsentPage] = useState(1);
  const receipts = useQuery({
    queryKey: ["consent-receipts", admin, receiptPage],
    queryFn: () =>
      api<Collection>(
        (admin ? "/privacy/consent-receipts" : "/privacy/my-consent-receipts") +
          "?page_number=" +
          receiptPage,
      ),
  });
  const [operation, setOperation] = useState<Operation | null>(null);
  const [error, setError] = useState<unknown>();
  const client = useQueryClient();
  const requests = useQuery({
    queryKey: ["privacy-requests"],
    queryFn: () => api<Collection>("/privacy/requests"),
  });
  const consents = useQuery({
    queryKey: ["consents", consentPage],
    queryFn: () => api<Collection>("/privacy/consents?page_number=" + consentPage),
    enabled: !admin,
  });
  const notices = useQuery({
    queryKey: ["privacy-public"],
    queryFn: () => api<Collection>("/public/privacy"),
    enabled: !admin,
  });
  const privacyProfile = useQuery({
    queryKey: ["my-profile"],
    queryFn: () => api<Row | null>("/candidates/me"),
    enabled: !admin,
  });
  const consentUntil = str(privacyProfile.data?.talent_consent_until);
  const participating = Boolean(consentUntil && new Date(consentUntil).getTime() > viewedAt);
  return (
    <>
      <PageTitle
        title={admin ? "Solicitações de privacidade" : "Minha privacidade"}
        subtitle={
          admin
            ? "Analise os direitos dos titulares e registre as decisões."
            : "Gerencie suas preferências e seus dados pessoais."
        }
        actions={
          !admin && (
            <button
              className="button"
              onClick={() =>
                setOperation({
                  title: "Exercer um direito",
                  schema: simpleSchema({
                    kind: {
                      enum: ["COPY", "CORRECTION", "DELETION", "CLOSE_ACCOUNT"],
                      title: "Tipo de solicitação",
                    },
                    detail: {
                      type: "string",
                      title: "Descreva sua solicitação",
                    },
                  }),
                  run: (data) => post("/privacy/requests", data),
                })
              }
            >
              Nova solicitação
            </button>
          )
        }
      />
      <ErrorBox error={error ?? requests.error} />
      <section className="surface padded">
        <h2>
          {admin ? "Comprovantes de aceite" : "Meus termos e assinaturas eletrônicas"}
        </h2>
        <p>Consulte o termo aceito, o protocolo e o registro da assinatura eletrônica de cada aceite realizado no portal.</p>
        <ErrorBox error={receipts.error} />
        {receipts.isPending ? <p role="status">Carregando termos e comprovantes…</p> : receipts.isError ? <button className="button secondary" onClick={() => void receipts.refetch()}>Tentar novamente</button> : !receipts.data?.items.length ? <Empty title="Nenhum comprovante de assinatura vinculado a esta conta">Os registros de consentimento disponíveis aparecem no histórico abaixo.</Empty> : <div className="consent-receipt-list" aria-label="Termos e assinaturas">
          <p className="muted">{receipts.data.total} {receipts.data.total === 1 ? "termo registrado" : "termos registrados"}</p>
          {receipts.data.items.map(row => <article className="consent-receipt-card" key={row.id}>
            <header className="consent-receipt-heading">
              <div><p className="eyebrow">RECRUTAMENTO E SELEÇÃO · {str(row.document_code)}</p><h3>Termo de consentimento para uso de dados pessoais</h3></div>
              <span className="consent-receipt-status">Aceite registrado</span>
            </header>
            <dl className="consent-receipt-metadata">
              <div><dt>Nome do candidato</dt><dd>{str(row.name)}</dd></div>
              <div><dt>E-mail</dt><dd>{str(row.email)}</dd></div>
              <div><dt>Data e hora do aceite</dt><dd>{date(row.created_at)}</dd></div>
              <div><dt>IP do aceite</dt><dd>{str(row.ip) || "Não registrado"}</dd></div>
              <div><dt>Finalidade</dt><dd>{row.context === "CADASTRO" ? "Cadastro" : row.context === "CANDIDATURA" ? "Candidatura" : str(row.context)}</dd></div>
              <div className="consent-receipt-protocol"><dt>Protocolo de assinatura</dt><dd>{str(row.protocol)}</dd></div>
            </dl>
            <footer className="consent-receipt-actions">
              <button className="button secondary" disabled={Boolean(openingTerm)} onClick={async () => {
                setOpeningTerm(row.id); setError(undefined);
                try { setTermDetail(await api<Row>("/privacy/consent-receipts/" + row.id)); }
                catch (err) { setError(err); } finally { setOpeningTerm(""); }
              }}>{openingTerm === row.id ? "Abrindo…" : "Visualizar termo e assinatura"}</button>
              <button className="button" disabled={Boolean(downloadingTerm)} onClick={() => void downloadTerm(row.id)}>{downloadingTerm === row.id ? "Baixando…" : "Baixar termo assinado (Word)"}</button>
            </footer>
          </article>)}
        </div>}
        <button
          type="button"
          className="button secondary"
          disabled={receiptPage === 1}
          onClick={() => setReceiptPage(receiptPage - 1)}
        >
          Anterior
        </button>
        <button
          type="button"
          className="button secondary"
          disabled={receiptPage * 25 >= (receipts.data?.total ?? 0)}
          onClick={() => setReceiptPage(receiptPage + 1)}
        >
          Próxima
        </button>
      </section>
      {!admin && (
        <section className="surface padded privacy-talent">
          <div className="privacy-talent-heading">
            <div><span className="privacy-eyebrow">OPORTUNIDADES FUTURAS</span><h2>Banco de talentos</h2></div>
            {privacyProfile.isSuccess && <span className={"privacy-participation " + (participating ? "active" : "inactive")}>{participating ? "Participação ativa" : "Sem participação ativa"}</span>}
          </div>
          <p>
            Autorize o RH a manter seu perfil disponível para oportunidades
            futuras durante o prazo informado no aviso.
          </p>
          <form
            className="privacy-preference-form"
            onSubmit={async (e) => {
              e.preventDefault();
              setSavingPreference(true);
              setPreferenceSaved(false);
              setError(undefined);
              const data = new FormData(e.currentTarget);
              try {
                await post("/privacy/consents", {
                  notice_id: data.get("notice_id"),
                  purpose: "TALENT",
                  granted: data.get("granted") === "true",
                });
                await client.invalidateQueries();
                setPreferenceSaved(true);
              } catch (e) {
                setError(e);
              } finally {
                setSavingPreference(false);
              }
            }}
          >
            <label className="field">
              <span>Aviso de privacidade</span>
              <select name="notice_id" required disabled={notices.isPending || savingPreference}>
                {notices.data?.items.map((n) => (
                  <option key={n.id} value={n.id}>
                    {str(n.name)}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Sua participação</span>
              <select name="granted" key={String(participating)} defaultValue={participating ? "true" : "false"} disabled={privacyProfile.isPending || savingPreference}>
                <option value="true">Participar do banco de talentos</option>
                <option value="false">Não participar do banco de talentos</option>
              </select>
            </label>
            <button className="button" disabled={savingPreference || notices.isPending || notices.isError || !notices.data?.items.length || privacyProfile.isPending || privacyProfile.isError}>
              {savingPreference ? "Salvando…" : "Salvar preferência"}
            </button>
          </form>
          <ErrorBox error={notices.error ?? privacyProfile.error} />
          {participating && <p className="muted">Sua autorização está vigente até {date(consentUntil)}. Você pode alterar sua preferência a qualquer momento.</p>}
          {preferenceSaved && <p role="status">Preferência salva.</p>}
          <div className="privacy-data-export">
          <div><strong>Uma cópia dos seus dados</strong><p className="muted">Baixe seu perfil, candidaturas e registros de consentimento.</p></div>
          <button
            className="button secondary"
            onClick={async () => {
              try {
                const result = await api("/privacy/export");
                const blob = new Blob([JSON.stringify(result, null, 2)], {
                  type: "application/json",
                });
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = "meus-dados.json";
                a.click();
                URL.revokeObjectURL(url);
              } catch (e) {
                setError(e);
              }
            }}
          >
            Baixar cópia dos meus dados
          </button>
          </div>
          <div className="privacy-history-heading"><h3>Histórico de consentimentos</h3><p className="muted">Acompanhe as autorizações e alterações das suas preferências.</p></div>
          <ErrorBox error={consents.error} />
          {consents.isPending && <p role="status">Carregando autorizações…</p>}
          <div className="consent-history-cards">
            {(consents.data?.items ?? []).map(row => {
              const receiptId = str(obj(row.notice_snapshot).receipt_id);
              return <article className="consent-history-card" key={row.id}>
                <div className="consent-history-info"><span className={"privacy-participation " + (row.granted ? "active" : "inactive")}>{row.granted ? "Autorizado" : "Revogado"}</span><h4>{row.purpose === "TALENT" ? "Banco de talentos" : row.purpose === "RECRUITMENT" ? "Recrutamento e seleção" : str(row.purpose)}</h4><p>Registrado em {date(row.created_at)} <span>· Versão {str(row.notice_version)}</span></p></div>
                <div className="consent-history-actions">{!receiptId && <button className="button secondary" disabled={Boolean(openingTerm)} onClick={async () => {
                  if (!receiptId) { setTermDetail({ ...row, legacy_consent: true }); return; }
                  setOpeningTerm(row.id); setError(undefined);
                  try { setTermDetail(await api<Row>("/privacy/consent-receipts/" + receiptId)); }
                  catch (err) { setError(err); } finally { setOpeningTerm(""); }
                }}>{openingTerm === row.id ? "Abrindo…" : "Consultar aceite"}</button>}
                {receiptId && <button className="button" disabled={Boolean(downloadingTerm)} onClick={() => void downloadTerm(receiptId)}>{downloadingTerm === receiptId ? "Baixando…" : "Baixar termo assinado"}</button>}</div>
              </article>;
            })}
          </div>
          {consents.isSuccess && !consents.data?.items.length && <p className="muted">Você ainda não possui registros de consentimento.</p>}
          {(consents.data?.total ?? 0) > 25 && <div className="consent-history-pagination"><button className="button secondary" disabled={consentPage <= 1} onClick={() => setConsentPage(consentPage - 1)}>Anterior</button><span>Página {consentPage}</span><button className="button secondary" disabled={consentPage * 25 >= (consents.data?.total ?? 0)} onClick={() => setConsentPage(consentPage + 1)}>Próxima</button></div>}
        </section>
      )}
      <Modal open={Boolean(termDetail)} onOpenChange={open => { if (!open) setTermDetail(null); }} title="Termo e registro de aceite eletrônico">
        {termDetail && <div className="consent-record-detail">
          <ErrorBox error={error} />
          {!termDetail.legacy_consent && <>
            <button className="button" disabled={Boolean(downloadingTerm)} onClick={() => void downloadTerm(termDetail.id)}>{downloadingTerm === termDetail.id ? "Baixando…" : "Baixar termo assinado (Word)"}</button>
            <p>Modelo original com assinatura eletrônica registrada no portal e comprovante de aceite.</p>
          </>}
          {termDetail.legacy_consent ? <>
            <p><strong>Identificador do registro:</strong> {termDetail.id}</p>
            <p><strong>Protocolo:</strong> {str(obj(termDetail.notice_snapshot).receipt_protocol) || "Este registro não possui protocolo de assinatura vinculado."}</p>
            <p><strong>Data do registro:</strong> {date(termDetail.created_at)}</p>
            <p><strong>IP registrado:</strong> {str(termDetail.ip) || "Não registrado"}</p>
            <p><strong>Versão do aviso:</strong> {str(termDetail.notice_version)}</p>
            <p><strong>Manifestação:</strong> {termDetail.granted ? "Consentimento concedido" : "Consentimento revogado"}</p>
            <h3>Texto registrado no momento do consentimento</h3>
            <p className="consent-record-text">{str(obj(termDetail.notice_snapshot).text) || "Texto não disponível neste registro."}</p>
          </> : <>
            <p><strong>Documento:</strong> {str(termDetail.document_code)}</p>
            <p><strong>Protocolo:</strong> {str(termDetail.protocol)}</p>
            <h3>Assinatura eletrônica — registro de aceite</h3>
            <p><strong>Nome registrado:</strong> {str(termDetail.name)}</p>
            <p><strong>E-mail:</strong> {str(termDetail.email)}</p>
            <p><strong>Data e hora:</strong> {date(termDetail.created_at)}</p>
            <p><strong>IP registrado:</strong> {str(termDetail.ip) || "Não registrado"}</p>
            <p><strong>Identificação:</strong> {obj(termDetail.document_snapshot).identity === "AUTHENTICATED" ? "Conta autenticada" : "Nome e e-mail declarados no momento do aceite"}</p>
            <p><strong>SHA-256 do termo:</strong> {str(termDetail.document_sha256)}</p>
            <section className="consent-paper consent-signed-paper"><header className="consent-paper-header"><div className="consent-document-meta"><span>RECRUTAMENTO E SELEÇÃO</span><span>{str(termDetail.document_code)}</span></div><h2>Termo de consentimento para uso de dados pessoais</h2><p>Porto Aurora</p></header><div className="consent-copy">
            {Array.isArray(obj(termDetail.document_snapshot).paragraphs) && (obj(termDetail.document_snapshot).paragraphs as string[]).map((paragraph, index) => <p key={index}>{paragraph}</p>)}</div></section>
          </>}
        </div>}
      </Modal>
      {admin && <section className="surface padded">
        <h2>Solicitações recebidas</h2>
        <DataTable
          data={requests.data?.items ?? []}
          columns={["kind", "detail", "status", "response", "created_at"]}
          actions={(row) =>
            admin &&
            !["FULFILLED", "DENIED"].includes(str(row.status)) && (
              <button
                className="text-button"
                onClick={() =>
                  setOperation({
                    title: "Tratar solicitação do titular",
                    schema: simpleSchema({
                      status: { enum: ["IN_REVIEW", "FULFILLED", "DENIED"] },
                      response: {
                        type: "string",
                        title: "Resposta fundamentada",
                      },
                      anonymize_data: {
                        type: "boolean",
                        title: "Anonimizar dados e encerrar acesso do titular",
                      },
                    }),
                    run: (data) =>
                      put("/privacy/requests/" + row.id, {
                        ...data,
                        version: row.version,
                      }),
                  })
                }
              >
                Analisar
              </button>
            )
          }
        />
      </section>}
      <OperationModal
        operation={operation}
        onClose={() => setOperation(null)}
      />
    </>
  );
}
