import { Link } from "react-router-dom";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { obj, str, put, type Row } from "../lib/api";
import { SchemaForm, type Schema } from "./SchemaForm";
import { StageGate } from "./CandidateJourney";

export function SelectionActivities({ application }: { application: Row }) {
  const client = useQueryClient();
  const [saved, setSaved] = useState(false);
  const allowed = obj(obj(application.candidate_access).permissions).consent === true;
  const schema: Schema = { type: "object", properties: {
    consent: { type: "boolean", title: "Li o termo e o aviso de privacidade e concordo com o tratamento para esta candidatura" },
  } };
  return <section className="surface padded selection-activities">
    <h2>Atividades da seleção de currículo</h2>
    <p>{allowed ? "Você avançou para a seleção. Preencha a ficha externa, registre o aceite do termo e confirme sua candidatura." : "A ficha externa e o termo estão visíveis. Aguarde o RH avançar esta candidatura para a seleção."}</p>
    <div className="candidate-progress-actions">
      <Link className="button secondary" to="/candidato/privacidade">Consultar termo de consentimento</Link>
      <Link className="button secondary" to="/candidato/perfil#ficha-externa">Consultar ficha externa</Link>
      <Link className="button secondary" to="/candidato/testes#perguntas">Consultar perguntas em Meus testes</Link>
    </div>
    <StageGate section="consent" title="Confirmação da candidatura" allowed={allowed}>
      {saved && <p className="alert success" role="status">Confirmação enviada ao RH. Acompanhe aqui o avanço da sua candidatura.</p>}
      <SchemaForm key={str(application.version)} schema={schema} initial={{ consent: false }} submitLabel="Confirmar candidatura" onSubmit={async data => {
        await put("/applications/" + application.id + "/selection", { ...data, answers: {}, version: application.version });
        setSaved(true);
        await client.invalidateQueries({ queryKey: ["application", application.id] });
        await client.invalidateQueries({ queryKey: ["my-applications"] });
      }} />
    </StageGate>
  </section>;
}
