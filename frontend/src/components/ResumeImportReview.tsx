import { useState } from "react";
import { post, type Row } from "../lib/api";
import { RecordDetail } from "../pages/Resources";
import { ErrorBox, Modal } from "./ui";
import type { ResumePersonalRecord } from "./ResumePersonalFields";

export type ImportSnapshot = {candidate: Record<string, unknown>; personal: Record<string, unknown>; personal_version: number};
export function ResumeImportReview({ready, getSnapshot, onSaved}: {
  ready: boolean; getSnapshot: () => ImportSnapshot;
  onSaved: (result: {candidate: Row; personal: ResumePersonalRecord}) => void;
}) {
  const [snapshot, setSnapshot] = useState<ImportSnapshot | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  return <>
    <section className="surface padded resume-import-confirmation">
      <h2>Revise antes de salvar</h2>
      <p>A leitura só preenche os formulários. Confira os campos abaixo, corrija o que precisar e confirme para salvar os dados básicos, profissionais e pessoais juntos.</p>
      <button type="button" className="button" disabled={!ready} onClick={() => {setSnapshot(getSnapshot());setConfirmed(false);setError(undefined);}}>Revisar e salvar dados importados</button>
      <p className="muted">Essa confirmação não envia candidatura e não altera seu e-mail de acesso.</p>
    </section>
    <Modal open={Boolean(snapshot)} title="Confirmar dados importados do currículo" onOpenChange={open => {if (!open && !busy) setSnapshot(null);}}>
      {snapshot && <>
        <p>Estas são as informações que serão salvas. Dados ausentes no currículo não foram inventados. Para corrigir um campo, volte aos formulários.</p>
        <ErrorBox error={error} />
        <details open><summary>Dados básicos e profissionais</summary><RecordDetail value={Object.fromEntries(Object.entries(snapshot.candidate).filter(([key]) => key !== "version"))} /></details>
        <details><summary>Dados pessoais protegidos</summary><RecordDetail value={snapshot.personal} /></details>
        <label className="resume-import-consent"><input type="checkbox" checked={confirmed} disabled={busy} onChange={e => setConfirmed(e.target.checked)} />Conferi as informações e confirmo o salvamento no meu perfil.</label>
        <div className="actions"><button type="button" className="button secondary" disabled={busy} onClick={() => setSnapshot(null)}>Voltar e editar</button><button type="button" className="button" disabled={!confirmed || busy} onClick={async () => {
          setBusy(true);setError(undefined);
          try {
            const result = await post<{candidate: Row; personal: ResumePersonalRecord}>("/candidates/me/confirm-resume-import", {...snapshot, confirmed: true});
            onSaved(result);setSnapshot(null);
          } catch (failure) {setError(failure);} finally {setBusy(false);}
        }}>{busy ? "Salvando…" : "Confirmar e salvar perfil"}</button></div>
      </>}
    </Modal>
  </>;
}
