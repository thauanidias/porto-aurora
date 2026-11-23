import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ConsentTerm } from "../components/ConsentTerm";
import { Brand } from "../components/Brand";
import { newRequestId } from "../lib/id";

export function ConsentDocument() {
  const [request] = useState(() => {
    const id = new URLSearchParams(location.search).get("solicitacao");
    const key = "tgpm-term-" + id;
    const data = sessionStorage.getItem(key);
    return data
      ? (JSON.parse(data) as {
          id: string;
          name: string;
          email: string;
          context: "CADASTRO" | "CANDIDATURA";
        })
      : undefined;
  });
  const [accepted, setAccepted] = useState(false);
  const navigate = useNavigate();
  return (
    <main className="consent-document-page">
      <header className="consent-page-header">
        <Link className="brand" to="/carreiras">
          <Brand />
        </Link>
        <span>Privacidade e consentimento</span>
      </header>
      <form onSubmit={(event) => event.preventDefault()}>
        <ConsentTerm
          expanded
          identity={request}
          context={request?.context}
          accepted={accepted}
          onContinue={
            !request
              ? () => {
                  const id = newRequestId();
                  sessionStorage.setItem("tgpm-term-read-" + id, "true");
                  navigate("/cadastro?termo-lido=" + id);
                }
              : undefined
          }
          onAccept={
            request
              ? (receipt) => {
                  setAccepted(true);
                  if (request.context === "CADASTRO") {
                    sessionStorage.setItem(
                      "tgpm-signup-receipt-" + request.id,
                      JSON.stringify(receipt),
                    );
                    sessionStorage.removeItem("tgpm-term-" + request.id);
                  } else {
                    window.opener?.postMessage(
                      {
                        type: "tgpm-term-accepted",
                        requestId: request.id,
                        receipt,
                      },
                      location.origin,
                    );
                  }
                }
              : undefined
          }
        />
      </form>
      {accepted && request?.context === "CADASTRO" && (
        <button
          type="button"
          className="button"
          onClick={() => navigate("/cadastro?aceite=" + request.id)}
        >
          Continuar cadastro
        </button>
      )}
      {accepted && request?.context === "CANDIDATURA" && (
        <button
          type="button"
          className="button secondary"
          onClick={() => window.close()}
        >
          Voltar para continuar
        </button>
      )}
    </main>
  );
}
