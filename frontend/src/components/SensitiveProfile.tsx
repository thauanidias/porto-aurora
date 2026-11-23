import { useState } from "react";
import { put } from "../lib/api";
import { ErrorBox } from "./ui";
export function SensitiveProfile({ embedded = false }: { embedded?: boolean }) {
  const [error, setError] = useState<unknown>();
  const [saved, setSaved] = useState(false);
  const Container = embedded ? "div" : "section";
  return (
    <Container className={embedded ? "profile-accessibility" : "surface padded"}>
      <h2>Acessibilidade e informações opcionais</h2>
      <p>
        Estes dados têm acesso restrito e não participam do cálculo de
        aderência.
      </p>
      <ErrorBox error={error} />
      {saved && (
        <p className="alert success">
          Informações registradas com acesso restrito.
        </p>
      )}
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          const data = new FormData(e.currentTarget);
          try {
            await put("/candidates/me/sensitive", {
              purpose: data.get("purpose"),
              data: {
                accessibility_needs: data.get("accessibility_needs"),
                pcd: data.get("pcd"),
              },
              consent: data.get("consent") === "on",
            });
            setSaved(true);
            setError(undefined);
          } catch (err) {
            setError(err);
          }
        }}
      >
        <label className="field">
          <span>Necessidades de acessibilidade (opcional)</span>
          <textarea name="accessibility_needs" maxLength={2000} />
        </label>
        <label className="field">
          <span>Informação sobre deficiência (opcional)</span>
          <input name="pcd" maxLength={500} />
        </label>
        <label className="field">
          <span>Finalidade autorizada</span>
          <input
            name="purpose"
            required
            minLength={10}
            placeholder="Ex.: preparar adaptações para minha entrevista"
          />
        </label>
        <label className="check-field">
          <input type="checkbox" name="consent" required />
          <span>
            Autorizo o tratamento destas informações para a finalidade descrita.
          </span>
        </label>
        <button className="button secondary">
          Salvar informações opcionais
        </button>
      </form>
    </Container>
  );
}
