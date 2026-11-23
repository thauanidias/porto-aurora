import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api, post, put, str, type Collection } from "../lib/api";
import { Brand } from "../components/Brand";
import { Badge, DataTable, Empty, ErrorBox, PageTitle } from "../components/ui";
import { Plus, Search, Users, ShieldCheck, ClipboardList } from "lucide-react";
import { OperationModal, type Operation } from "./Resources";
import { simpleSchema } from "../lib/forms";
import { EmployeeRegisterPage } from "./EmployeeRegister";

export function ManagerRegisterPage({ employee = false }: { employee?: boolean }) {
  return employee ? <EmployeeRegisterPage /> : <AccessRegisterPage />;
}

function AccessRegisterPage() {
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<unknown>();
  return <main className="narrow-page">
    <Link className="brand" to="/oportunidades-internas"><Brand /></Link>
    <p><Link className="back-link" to="/oportunidades-internas">← Voltar ao portal interno</Link></p>
    <h1>Acesso para gestores</h1><p>Cadastre-se para solicitar vagas para sua equipe e acompanhar a análise do RH.</p>
    {sent ? <section className="surface padded" role="status"><h2>Solicitação de acesso enviada</h2><p>O RH vai conferir seus dados e liberar o acesso. Após a aprovação, você receberá por e-mail um link para criar sua senha.</p><Link className="button secondary" to="/entrar-gestor">Voltar para a entrada</Link></section> : <form className="surface padded" onSubmit={async event => {
      event.preventDefault(); setBusy(true); setError(undefined);
      const data = Object.fromEntries(new FormData(event.currentTarget));
      try { await post("/auth/register-manager", data); setSent(true); }
      catch (err) { setError(err); } finally { setBusy(false); }
    }}><ErrorBox error={error} />
      <label className="field"><span>Nome completo</span><input name="name" required minLength={3} maxLength={180} autoComplete="name" /></label>
      <label className="field"><span>E-mail corporativo</span><input aria-label="E-mail corporativo" name="email" type="email" required maxLength={320} autoComplete="email" placeholder="seu.nome@portoaurora.example" onChange={e => {
        const value = e.currentTarget.value.trim().toLowerCase();
        e.currentTarget.setCustomValidity(value && value.split("@")[1] !== "portoaurora.example" ? "Use seu e-mail corporativo @portoaurora.example." : "");
      }} /><small>Cadastro exclusivo para e-mails @portoaurora.example.</small></label>
      <label className="field"><span>Setor ou departamento</span><input name="department" required minLength={2} maxLength={180} /></label>
      <p className="muted">O cadastro será analisado pelo RH antes da liberação das funções de gestor.</p><button className="button" disabled={busy}>{busy ? "Enviando…" : "Solicitar acesso"}</button>
    </form>}
    <p>Já possui acesso? <Link to="/entrar-gestor">Entrar como gestor</Link></p>
    <p>Quer participar de uma vaga interna? <Link to="/oportunidades-internas">Área do colaborador</Link></p>
  </main>;
}
export function ManagerAccessPage() {
  const [operation, setOperation] = useState<Operation | null>(null);
  const [notice, setNotice] = useState("");
  const [search, setSearch] = useState("");
  const [active, setActive] = useState("");
  const [page, setPage] = useState(1);
  const query = useQuery({ queryKey: ["registered-managers", search, active, page],
    queryFn: () => api<Collection>("/registered-managers?" + new URLSearchParams({ q: search, page_number: String(page), ...(active ? { active } : {}) })),
    refetchInterval: 15000,
  });
  return <>
    <PageTitle title="Gestores" subtitle="Gerencie os responsáveis pelas equipes, seus setores e o acesso ao portal do gestor." actions={<button className="button" onClick={() => setOperation({
      title: "Cadastrar gestor", submitLabel: "Cadastrar gestor",
      schema: { type: "object", properties: {
        name: { type: "string", title: "Nome completo", minLength: 3, maxLength: 180 },
        email: { type: "string", title: "E-mail corporativo", format: "email", description: "Use o e-mail corporativo @portoaurora.example." },
        org_unit_id: { type: "string", title: "Setor do gestor" },
        password: { type: "string", format: "password", title: "Senha inicial", minLength: 6, maxLength: 6, description: "Use 6 caracteres, combinando letras, números ou símbolos. Informe a senha ao gestor pelo canal interno utilizado pela empresa." },
      }, required: ["name", "email", "org_unit_id", "password"] },
      run: async data => { await post("/users", { ...data, email: str(data.email).trim().toLowerCase(), roles: ["GESTOR"], auth_source: "LOCAL" }); setNotice("Gestor cadastrado. O acesso já está disponível no portal do gestor com o e-mail e a senha inicial informados."); },
    })}><Plus size={18} aria-hidden="true" />Cadastrar gestor</button>} />
    <nav className="manager-module-nav" aria-label="Áreas de gestores">
      <Link className="active" aria-current="page" to="/app/gestores"><Users size={19} aria-hidden="true" /><span>Gestores cadastrados<small>Contas, setores e acessos</small></span></Link>
      <Link to="/app/solicitacoes-acesso-gestores"><ShieldCheck size={19} aria-hidden="true" /><span>Pedidos de acesso<small>Aprovar novos gestores</small></span></Link>
      <Link to="/app/solicitacoes"><ClipboardList size={19} aria-hidden="true" /><span>Solicitações de vagas<small>Consultar demandas das equipes</small></span></Link>
    </nav>
    {notice && <p className="alert success" role="status">{notice}</p>}
    <section className="surface candidate-directory registered-managers">
      <div className="list-toolbar"><label className="search-field"><Search size={18} aria-hidden="true" /><input type="search" aria-label="Buscar gestor" placeholder="Buscar por nome, e-mail ou setor" value={search} onChange={event => { setSearch(event.target.value); setPage(1); }} /></label><label className="field"><span>Situação do acesso</span><select value={active} onChange={event => { setActive(event.target.value); setPage(1); }}><option value="">Todos os cadastrados</option><option value="true">Ativos</option><option value="false">Inativos</option></select></label></div>
      <ErrorBox error={query.error} />
      {query.isPending ? <p role="status">Carregando gestores cadastrados…</p> : query.data?.items.length ? <DataTable data={query.data.items} total={query.data.total} page={page} pageSize={query.data.page_size ?? 25} onPage={setPage} columns={["name", "email", "org_unit_name", "active", "created_at"]} columnLabels={{ name: "Gestor", org_unit_name: "Setor", active: "Situação do acesso", created_at: "Cadastrado em" }} cells={{ active: row => <Badge value={row.active ? "ACCOUNT_ACTIVE" : "ACCOUNT_INACTIVE"} /> }} actions={row => <button className="text-button" onClick={() => setOperation({
        title: (row.active ? "Desativar" : "Ativar") + " acesso de " + str(row.name), submitLabel: row.active ? "Desativar acesso" : "Ativar acesso",
        schema: { ...simpleSchema({ reason: { type: "string", title: "Motivo", minLength: 5 } }), required: ["reason"] },
        run: data => put("/users/" + row.id + "/status", { active: !row.active, version: row.version, reason: data.reason }),
      })}>{row.active ? "Desativar acesso" : "Ativar acesso"}</button>} /> : !query.error && <Empty title={search || active ? "Nenhum gestor encontrado" : "Nenhum gestor cadastrado"}>{search || active ? "Ajuste os filtros para consultar os gestores." : "Cadastre um gestor ou aprove um pedido de acesso para começar."}</Empty>}
    </section>
    <OperationModal operation={operation} onClose={() => setOperation(null)} />
  </>;
}

export function ManagerAccessRequestsPage() {
  const query = useQuery({ queryKey: ["manager-access-requests"], queryFn: () => api<Collection>("/manager-access-requests") });
  const [operation, setOperation] = useState<Operation | null>(null);
  const [setupUrl, setSetupUrl] = useState("");
  return <>
    <PageTitle title="Pedidos de acesso de gestores" subtitle="Analise os pedidos de cadastro e libere o acesso após conferir os dados." actions={<Link className="button secondary" to="/app/gestores">Ver gestores cadastrados</Link>} />
    <ErrorBox error={query.error} />
    {setupUrl && <p className="alert">E-mail desativado neste ambiente. <Link to={setupUrl}>Abrir link de criação de senha para teste</Link></p>}
    <section className="surface padded">
      <p>Ao aprovar, o sistema cria o usuário com perfil de gestor e envia o link de acesso. Ele poderá solicitar vagas para o setor selecionado.</p>
      {query.isPending ? <p role="status">Carregando pedidos…</p> : <DataTable data={query.data?.items ?? []} columns={["name", "email", "department", "status", "created_at", "reason"]} actions={row => row.status === "PENDING" ? <>
        <button className="text-button" onClick={() => setOperation({title: "Aprovar acesso de " + str(row.name), schema: simpleSchema({org_unit_id: {type: "string", title: "Centro de custo"}}), run: async data => {
          const result = await post<{test_setup_url?: string}>("/manager-access-requests/" + row.id + "/review", {...data, version: row.version, approve: true});
          setSetupUrl(result.test_setup_url ?? ""); return result;
        }})}>Aprovar acesso</button>
        <button className="text-button" onClick={() => setOperation({title: "Recusar acesso de " + str(row.name), schema: simpleSchema({reason: {type: "string", minLength: 5, title: "Motivo da recusa"}}), run: data => post("/manager-access-requests/" + row.id + "/review", {...data, version: row.version, approve: false})})}>Recusar</button>
      </> : null} />}
    </section>
    <OperationModal operation={operation} onClose={() => setOperation(null)} />
  </>;
}
