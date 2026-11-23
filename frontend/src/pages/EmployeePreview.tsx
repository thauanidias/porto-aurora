import { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, BriefcaseBusiness, CheckCircle2, ClipboardList, FileText, MapPin, MessageCircle, Search, UserRound } from "lucide-react";
import { Brand } from "../components/Brand";
import { InternalRegistrationForm } from "../components/InternalRegistration";
import { Empty, Modal } from "../components/ui";

const jobs = [
  { id: "demo-1", title: "Analista de Operações", department: "Operações", city: "Barcarena · PA", modality: "Presencial", description: "Acompanhe os indicadores operacionais, proponha melhorias e contribua para a eficiência dos processos do terminal.", requirements: "Experiência em operações logísticas, organização e conhecimento de indicadores de desempenho." },
  { id: "demo-2", title: "Assistente Administrativo", department: "Administrativo", city: "Barcarena · PA", modality: "Presencial", description: "Apoie as rotinas administrativas, a organização de documentos e o atendimento às equipes internas.", requirements: "Ensino médio completo, conhecimento de planilhas e facilidade para trabalhar em equipe." },
];
const navigation = [
  { id: "jobs", label: "Vagas internas", icon: BriefcaseBusiness },
  { id: "applications", label: "Minhas inscrições", icon: ClipboardList },
  { id: "profile", label: "Meu perfil", icon: UserRound },
  { id: "documents", label: "Meus documentos", icon: FileText },
  { id: "messages", label: "Mensagens", icon: MessageCircle },
];

export function EmployeePreviewPage() {
  const [tab, setTab] = useState("jobs");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<(typeof jobs)[number] | null>(null);
  const [applications, setApplications] = useState<string[]>([]);
  const [consent, setConsent] = useState(false);
  const [profile, setProfile] = useState<Record<string, unknown>>({ personal: { name: "Colaborador de exemplo", email: "colaborador@exemplo.invalid" } });
  const name = String((profile.personal as Record<string, unknown>)?.name || "Colaborador de exemplo");
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState<string[]>([]);
  const [notice, setNotice] = useState("");
  const title = navigation.find(item => item.id === tab)?.label ?? "Vagas internas";
  return <div className="employee-preview">
    <div className="preview-banner"><span><strong>PRÉVIA SEM LOGIN</strong> Dados de exemplo · Inscrições e mensagens simuladas</span><Link to="/oportunidades-internas">Voltar ao portal <ArrowRight size={14} /></Link></div>
    <header className="preview-header"><Link className="brand" to="/previa-colaborador"><Brand /></Link><div className="preview-user"><span className="message-person-avatar" aria-hidden="true">CE</span><div><strong>{name}</strong><span>Área do colaborador · Demonstração</span></div></div></header>
    <div className="preview-layout"><aside><p className="eyebrow">MINHA CARREIRA</p><nav aria-label="Navegação da prévia">{navigation.map(item => <button key={item.id} className={tab === item.id ? "active" : ""} aria-current={tab === item.id ? "page" : undefined} onClick={() => { setTab(item.id); setNotice(""); }}><item.icon size={19} />{item.label}{item.id === "applications" && applications.length > 0 && <span>{applications.length}</span>}</button>)}</nav><p className="preview-help">Explore livremente. Os dados desta prévia são apagados ao recarregar a página.</p></aside>
      <main><div className="preview-page-heading"><p className="eyebrow">PORTAL INTERNO</p><h1>{title}</h1><p>{tab === "jobs" ? "Seu próximo desafio pode estar aqui. Explore novas possibilidades dentro do Porto Aurora." : "Conheça como funciona sua área de acompanhamento."}</p></div>
        {notice && <p className="alert" role="status">{notice}</p>}
        {tab === "jobs" && <><div className="preview-welcome"><div><p className="eyebrow">CRESÇA COM A GENTE</p><h2>Seu talento abre novos caminhos.</h2><p>Encontre uma oportunidade, consulte os requisitos e experimente o processo de inscrição.</p></div><BriefcaseBusiness size={64} aria-hidden="true" /></div><section className="surface vacancy-board"><div className="vacancy-board-filters"><label className="message-search"><Search size={18} /><input type="search" aria-label="Buscar vagas de exemplo" placeholder="Buscar por cargo" value={search} onChange={event => setSearch(event.target.value)} /></label></div><ul className="vacancy-board-list">{jobs.filter(job => job.title.toLocaleLowerCase("pt-BR").includes(search.toLocaleLowerCase("pt-BR"))).map(job => <li key={job.id}><div className="vacancy-board-identity"><span className="vacancy-board-code">VAGA INTERNA · EXEMPLO</span><button className="text-button" onClick={() => { setSelected(job); setConsent(false); }}>{job.title}</button><div className="vacancy-board-meta"><span><MapPin size={14} />{job.city}</span><span>{job.department} · {job.modality}</span></div></div><button className="button secondary small" onClick={() => { setSelected(job); setConsent(false); }}>{applications.includes(job.id) ? "Inscrição realizada" : "Ver oportunidade"}<ArrowRight size={16} /></button></li>)}</ul>{!jobs.some(job => job.title.toLocaleLowerCase("pt-BR").includes(search.toLocaleLowerCase("pt-BR"))) && <Empty title="Nenhuma vaga de exemplo encontrada">Tente buscar por outro cargo.</Empty>}</section></>}
        {tab === "applications" && <section className="surface padded"><h2>Acompanhe sua evolução</h2>{!applications.length ? <Empty title="Você ainda não simulou uma inscrição">Escolha uma vaga em Vagas internas para experimentar o processo.<p><button className="button secondary" onClick={() => setTab("jobs")}>Explorar vagas internas</button></p></Empty> : applications.map(id => <article className="preview-application" key={id}><span className="task-state done">Inscrição simulada</span><h3>{jobs.find(job => job.id === id)?.title}</h3><p>Etapa atual: <strong>Triagem curricular</strong></p><ol className="preview-progress"><li className="complete"><CheckCircle2 size={19} />Inscrição recebida</li><li><ClipboardList size={19} />Triagem curricular</li><li><MessageCircle size={19} />Entrevista</li></ol><p className="muted">Exemplo de acompanhamento. Esta inscrição não foi enviada ao RH.</p></article>)}</section>}
        {tab === "profile" && <InternalRegistrationForm preview initial={profile} onSubmit={async data => { setProfile(data); }} />}
        {tab === "documents" && <section className="surface padded"><h2>Documentos do colaborador</h2><p className="muted">Exemplo de checklist. Não envie documentos pessoais nesta demonstração.</p>{[{ title: "Currículo", sent: true }, { title: "Certificado de formação", sent: false }, { title: "Certificados complementares", sent: false }].map(doc => <div className="preview-document" key={doc.title}><FileText size={22} /><strong>{doc.title}</strong><span className={`task-state ${doc.sent ? "done" : "pending"}`}>{doc.sent ? "Enviado · exemplo" : "Não enviado"}</span></div>)}</section>}
        {tab === "messages" && <section className="surface padded"><h2>Conversa com o RH</h2><p className="muted">Conversa de exemplo. Nenhuma mensagem será enviada ao RH.</p><div className="preview-chat" role="log" aria-label="Mensagens simuladas"><p><strong>RH · Exemplo</strong><br />Olá! Por aqui você poderá acompanhar as orientações sobre sua inscrição interna.</p>{messages.map((text, index) => <p className="own" key={index}><strong>Você · Simulação</strong><br />{text}</p>)}</div><form onSubmit={event => { event.preventDefault(); if (message.trim()) { setMessages([...messages, message.trim()]); setMessage(""); } }}><label className="field"><span>Mensagem de exemplo</span><textarea required rows={3} maxLength={1000} value={message} onChange={event => setMessage(event.target.value)} /></label><button className="button" disabled={!message.trim()}>Simular envio</button></form></section>}
      </main></div>
    <Modal open={Boolean(selected)} onOpenChange={open => { if (!open) setSelected(null); }} title={selected?.title ?? "Oportunidade interna"}>{selected && <div className="preview-job"><span className="task-state pending">Vaga de exemplo</span><p><MapPin size={15} /> {selected.city} · {selected.modality}</p><h3>Sobre a oportunidade</h3><p>{selected.description}</p><h3>Requisitos</h3><p>{selected.requirements}</p>{applications.includes(selected.id) ? <p className="alert" role="status">Inscrição simulada realizada. Acompanhe em Minhas inscrições.</p> : <form onSubmit={event => { event.preventDefault(); if (!consent) return; setApplications([...applications, selected.id]); setSelected(null); setTab("applications"); setNotice("Inscrição simulada com sucesso. Nenhum cadastro foi enviado ao RH."); }}><label className="preview-consent"><input type="checkbox" required checked={consent} onChange={event => setConsent(event.target.checked)} />Entendi que esta inscrição é uma simulação com dados de exemplo.</label><button className="button" disabled={!consent}>Simular inscrição <ArrowRight size={16} /></button></form>}</div>}</Modal>
  </div>;
}
