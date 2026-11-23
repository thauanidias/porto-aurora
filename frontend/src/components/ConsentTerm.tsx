import paragraphs from "../consent-term.json";
import { useState, useEffect, useRef } from "react";
import { post, type Row } from "../lib/api";
import { newRequestId } from "../lib/id";
import { useNavigate } from "react-router-dom";
import { ErrorBox } from "./ui";

function TermParagraph({ text }: { text: string }) {
  if (text.startsWith("Cláusula ")) {
    const boundary = text.indexOf(".");
    const heading = text.slice(0, boundary).replace(/\s*[-–]\s*/, " — ");
    return (
      <section className="consent-clause">
        <h3>{heading}</h3>
        <p>{text.slice(boundary + 1).trim()}</p>
      </section>
    );
  }
  if (text.startsWith("Parágrafo Primeiro:"))
    return (
      <p className="consent-subclause">
        <strong>Parágrafo Primeiro.</strong>{" "}
        {text.slice("Parágrafo Primeiro:".length).trim()}
      </p>
    );
  return <p>{text}</p>;
}

export function ConsentTerm({
  accepted = false,
  onAccept,
  identity,
  context = "CADASTRO",
  separatePage = false,
  sameTab = false,
  expanded = false,
  initialReceipt,
  onContinue,
  originalDocument = "/documents/termo-consentimento-rs.docx",
}: {
  accepted?: boolean;
  onAccept?: (receipt: Row) => void;
  identity?: { name: string; email: string };
  context?: "CADASTRO" | "CANDIDATURA";
  separatePage?: boolean;
  sameTab?: boolean;
  expanded?: boolean;
  initialReceipt?: Row;
  onContinue?: () => void;
  originalDocument?: string;
}) {
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [confirmedReading, setConfirmedReading] = useState(false);
  const [error, setError] = useState<unknown>();
  const [receipt, setReceipt] = useState<Row | undefined>(initialReceipt);
  const [reachedEnd, setReachedEnd] = useState(false);
  const endOfTerm = useRef<HTMLParagraphElement | null>(null);
  useEffect(() => {
    if (separatePage || !endOfTerm.current) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setReachedEnd(true);
          observer.disconnect();
        }
      },
      { threshold: 0, rootMargin: "0px 0px -24px 0px" },
    );
    observer.observe(endOfTerm.current);
    return () => observer.disconnect();
  }, [separatePage]);
  const pending = useRef<
    | {
        id: string;
        name: string;
        email: string;
        form: HTMLFormElement | null;
      }
    | undefined
  >(undefined);
  useEffect(() => {
    const receive = (event: MessageEvent) => {
      const request = pending.current;
      if (
        !request ||
        event.origin !== location.origin ||
        !event.source ||
        event.data?.type !== "tgpm-term-accepted" ||
        event.data?.requestId !== request.id
      )
        return;
      const values = request.form ? new FormData(request.form) : undefined;
      if (
        !identity &&
        (values?.get("name") !== request.name ||
          values?.get("email") !== request.email)
      ) {
        setError(
          new Error(
            "Os dados foram alterados. Abra o termo novamente para aceitar.",
          ),
        );
        return;
      }
      setReceipt(event.data.receipt);
      onAccept?.(event.data.receipt);
      sessionStorage.removeItem("tgpm-term-" + request.id);
      pending.current = undefined;
    };
    window.addEventListener("message", receive);
    return () => window.removeEventListener("message", receive);
  }, [identity, onAccept]);
  if (separatePage)
    return (
      <section aria-label="Termo de consentimento para uso de dados pessoais">
        <a
          className="text-button"
          href="/termo-consentimento"
          target={sameTab ? undefined : "_blank"}
          rel={sameTab ? undefined : "opener"}
          onClick={(event) => {
            const link = event.currentTarget;
            link.href = new URL("/termo-consentimento", location.origin).href;
            const form = link.closest("form");
            if (!identity && form) {
              for (const name of ["name", "email"]) {
                const input = form.elements.namedItem(name) as HTMLInputElement | null;
                if (input && !input.reportValidity()) {
                  event.preventDefault();
                  return;
                }
              }
            }
            const values = form ? new FormData(form) : undefined;
            const request = {
              id: newRequestId(),
              name: identity?.name ?? String(values?.get("name") ?? ""),
              email: identity?.email ?? String(values?.get("email") ?? ""),
              context,
            };
            const key = "tgpm-term-" + request.id;
            sessionStorage.setItem(key, JSON.stringify(request));
            if (!sameTab) pending.current = { ...request, form };
            link.href = new URL(
              "/termo-consentimento?solicitacao=" + request.id,
              location.origin,
            ).href;
            if (sameTab) {
              event.preventDefault();
              navigate("/termo-consentimento?solicitacao=" + request.id);
            }
          }}
        >
          Ler e aceitar o termo de consentimento ↗
        </a>
        {accepted && receipt && (
          <p role="status">
            Documento aceito. Protocolo: {String(receipt.protocol)}.
          </p>
        )}
        <ErrorBox error={error} />
      </section>
    );
  return (
    <section aria-label="Termo de consentimento para uso de dados pessoais">
      <details
        className={"consent-paper" + (expanded ? " consent-expanded" : "")}
        open={expanded || undefined}
      >
        <summary>
          Leia o termo de consentimento para uso de dados pessoais no
          recrutamento e seleção
        </summary>
        <header className="consent-paper-header">
          <div className="consent-document-meta">
            <span>RECRUTAMENTO E SELEÇÃO</span>
            <span>FORM-PPO-RH-002.09</span>
          </div>
          <h2>Termo de consentimento para uso de dados pessoais</h2>
          <p>Porto Aurora</p>
        </header>
        {(onAccept || onContinue) && (
          <p className="consent-reading-note">
            Leia todas as cláusulas. O botão de aceite será liberado ao chegar
            ao final do documento.
          </p>
        )}
        <div className="consent-copy">
          {paragraphs
            .filter((text) => text.trim())
            .slice(1)
            .map((text, index) => (
              <TermParagraph text={text} key={index} />
            ))}
        </div>
        <p ref={endOfTerm} className="muted">
          Fim do termo de consentimento.
        </p>
        <a
          className="text-button"
          href={originalDocument}
          download
        >
          Baixar o termo original
        </a>
        {(onAccept || onContinue) && (
          <div
            className={
              "consent-acceptance" + (accepted ? " consent-accepted" : "")
            }
          >
            <h3>{accepted ? "Aceite confirmado" : "Declaração de aceite"}</h3>
            <p>
              Ao aceitar, confirmo que li e concordo com este termo de
              consentimento.
            </p>
            {!accepted && <label className="check-field consent-reading-confirmation"><input type="checkbox" checked={confirmedReading} disabled={!reachedEnd || busy} onChange={event => setConfirmedReading(event.target.checked)} /><span>Li todo o termo de consentimento e concordo com as condições apresentadas.</span></label>}
            {!accepted && !onContinue && <p className="muted">O aceite será registrado eletronicamente com sua identificação, data, hora, IP e protocolo. Não é necessário desenhar uma assinatura.</p>}
            <button
              type="button"
              className="button"
              onClick={async (event) => {
                if (busy || !reachedEnd || !confirmedReading) return;
                if (onContinue) {
                  onContinue();
                  return;
                }
                const form = event.currentTarget.form;
                const values = form ? new FormData(form) : undefined;
                if (!identity && form) {
                  for (const field of ["name", "email"]) {
                    const input = form.elements.namedItem(
                      field,
                    ) as HTMLInputElement | null;
                    if (input && !input.reportValidity()) return;
                  }
                }
                setBusy(true);
                setError(undefined);
                try {
                  const result = await post<Row>("/public/consent-receipts", {
                    name: identity?.name ?? values?.get("name"),
                    email: identity?.email ?? values?.get("email"),
                    context,
                    accepted: true,
                    read_to_end: true,
                  });
                  setReceipt(result);
                  onAccept?.(result);
                } catch (e) {
                  setError(e);
                } finally {
                  setBusy(false);
                }
              }}
              disabled={accepted || busy || !reachedEnd || !confirmedReading}
            >
              {accepted
                ? "Documento aceito"
                : busy
                  ? "Registrando aceite…"
                  : onContinue
                    ? "Continuar para o cadastro"
                    : "Aceitar e assinar eletronicamente"}
            </button>
            {!reachedEnd && (
              <p role="status">
                Role até o final do termo para aceitar este documento.
              </p>
            )}
            {accepted && (
              <p role="status">
                Aceite registrado. Protocolo: {String(receipt?.protocol ?? "")}.
                Data e hora:{" "}
                {receipt &&
                  new Date(String(receipt.created_at)).toLocaleString("pt-BR", {
                    timeZone: "America/Fortaleza",
                  })}{" "}
                (UTC−3). IP: {String(receipt?.ip ?? "")}. O comprovante está
                disponível para o RH.
              </p>
            )}
            {accepted && typeof receipt?.download_url === "string" && <a className="button secondary" href={String(receipt.download_url)} download>Baixar termo assinado e comprovante</a>}
            <ErrorBox error={error} />
          </div>
        )}
      </details>
    </section>
  );
}

