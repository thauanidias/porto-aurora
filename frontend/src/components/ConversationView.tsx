import { useEffect, useRef } from "react";
import { Check, LoaderCircle, MessageCircle, RefreshCw, Send } from "lucide-react";
import { str, type Collection } from "../lib/api";
import { date } from "../lib/labels";
import { Empty, ErrorBox } from "./ui";

type Props = {
  title: string; description: string; recipient: string; userId?: string;
  messages?: Collection; loading: boolean; failed: boolean; error: unknown;
  body: string; busy: boolean; sent: boolean; canSend: boolean; page: number;
  onBody: (value: string) => void; onSend: () => Promise<void>;
  onPage: (value: number) => void; onRetry: () => void;
};

export function ConversationView(props: Props) {
  const timeline = useRef<HTMLDivElement>(null);
  const nearBottom = useRef(true);
  const chronological = [...(props.messages?.items ?? [])].reverse();
  const latestId = chronological.at(-1)?.id;
  useEffect(() => {
    const node = timeline.current;
    if (node && nearBottom.current) node.scrollTop = node.scrollHeight;
  }, [latestId, props.page]);
  return <section className="surface conversation">
    <header className="conversation-header">
      <span className="conversation-header-icon"><MessageCircle size={24} aria-hidden="true" /></span>
      <div><h2>{props.title}</h2><p>{props.description}</p></div>
      <span className="conversation-refresh"><RefreshCw size={13} aria-hidden="true" /> Atualização automática</span>
    </header>
    <div className="conversation-errors"><ErrorBox error={props.error} /></div>
    {(props.messages?.total ?? 0) > 25 && <div className="pagination conversation-pagination">
      <button className="text-button" disabled={props.page * 25 >= (props.messages?.total ?? 0)} onClick={() => { nearBottom.current = true; props.onPage(props.page + 1); }}>Mensagens anteriores</button>
      <span>Página {props.page}</span>
      <button className="text-button" disabled={props.page === 1} onClick={() => { nearBottom.current = true; props.onPage(props.page - 1); }}>Mais recentes</button>
    </div>}
    <div ref={timeline} className="conversation-timeline" role="log" aria-label="Histórico da conversa" aria-live="polite" onScroll={event => {
      const node = event.currentTarget;
      nearBottom.current = node.scrollHeight - node.scrollTop - node.clientHeight < 90;
    }}>
      {props.loading ? <p className="conversation-loading" role="status"><LoaderCircle size={18} className="conversation-spinner" /> Carregando mensagens…</p> : props.failed ? <button className="button secondary" onClick={props.onRetry}>Tentar novamente</button> : !chronological.length ? <div className="conversation-empty"><MessageCircle size={36} aria-hidden="true" /><Empty title="Vamos iniciar a conversa?">Escreva sua primeira mensagem no campo abaixo.</Empty></div> : chronological.map((message, index) => {
        const own = message.sender_id === props.userId;
        const sender = own ? "Você" : str(message.sender_name) || props.recipient;
        const day = new Date(str(message.created_at)).toLocaleDateString("pt-BR", { day: "2-digit", month: "long", year: "numeric" });
        const previous = chronological[index - 1];
        const showDay = !previous || new Date(str(previous.created_at)).toDateString() !== new Date(str(message.created_at)).toDateString();
        return <div key={message.id}>
          {showDay && <div className="conversation-day"><span>{day}</span></div>}
          <article className={`conversation-message ${own ? "conversation-outgoing" : "conversation-incoming"}`}>
            {!own && <span className="conversation-avatar" aria-hidden="true">{sender.trim().split(/\s+/).slice(0, 2).map(part => part[0]).join("").toUpperCase()}</span>}
            <div className="conversation-bubble">
              <strong className="conversation-sender">{sender}</strong>
              {Boolean(message.subject) && message.subject !== "Conversa com o RH" && <span className="conversation-subject">{str(message.subject)}</span>}
              <p>{str(message.body)}</p>
              <div className="conversation-message-meta"><time dateTime={str(message.created_at)} title={date(message.created_at)}>{new Date(str(message.created_at)).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}</time>{own && <Check size={13} aria-label="Enviada" />}</div>
            </div>
          </article>
        </div>;
      })}
    </div>
    <form className="conversation-composer" onSubmit={event => { event.preventDefault(); nearBottom.current = true; void props.onSend(); }}>
      <label className="conversation-input"><span>Mensagem para {props.recipient}</span><textarea rows={2} maxLength={props.title.includes("gestor") ? 5000 : 10000} required value={props.body} disabled={props.busy || !props.canSend} onChange={event => props.onBody(event.target.value)} onKeyDown={event => {
        if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) { event.preventDefault(); event.currentTarget.form?.requestSubmit(); }
      }} placeholder="Escreva sua mensagem…" /></label>
      <button className="button conversation-send" aria-label={props.busy ? "Enviando…" : "Enviar mensagem"} title="Enviar mensagem" disabled={props.busy || !props.canSend || !props.body.trim()}>{props.busy ? <LoaderCircle size={19} className="conversation-spinner" /> : <Send size={19} aria-hidden="true" />}<span>{props.busy ? "Enviando…" : "Enviar"}</span></button>
      <div className="conversation-composer-footer"><span>Ctrl + Enter para enviar · Enter para nova linha</span>{props.sent && <span className="conversation-sent" role="status"><Check size={14} /> Mensagem enviada.</span>}</div>
    </form>
  </section>;
}
