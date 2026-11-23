import { useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, imageData, type Collection } from "../lib/api";
import { ErrorBox } from "./ui";

export function ProfilePhoto({
  candidateId,
  name,
  editable = false,
  profileReady = true,
}: {
  candidateId?: string;
  name: string;
  editable?: boolean;
  profileReady?: boolean;
}) {
  const client = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [message, setMessage] = useState("");
  const photo = useQuery({
    enabled: profileReady,
    queryKey: ["profile-photo", candidateId ?? "me"],
    queryFn: async () => {
      const list = await api<Collection>(
        "/documents?type_name=FOTO_PERFIL" +
          (candidateId
            ? "&candidate_id=" + encodeURIComponent(candidateId)
            : ""),
      );
      const latest = list.items[0];
      return latest ? imageData("/documents/" + latest.id + "/download") : null;
    },
  });
  async function save(file: File) {
    setError(undefined);
    setMessage("");
    if (
      file.size > 5 * 1024 * 1024 ||
      !["image/jpeg", "image/png", "image/webp"].includes(file.type)
    ) {
      setError(new Error("Escolha uma foto JPG, PNG ou WebP de até 5 MB."));
      return;
    }
    setBusy(true);
    try {
      const data = new FormData();
      data.set("file", file);
      data.set("type_name", "FOTO_PERFIL");
      await api("/documents", { method: "POST", body: data });
      await client.invalidateQueries({ queryKey: ["profile-photo"] });
      setMessage("Foto do perfil atualizada.");
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div
      className={
        editable
          ? "profile-photo-editor surface padded"
          : "profile-photo-display"
      }
    >
      <div className="profile-photo-avatar">
        {photo.data ? (
          <img src={photo.data} alt={"Foto de " + name} />
        ) : (
          <span aria-label="Sem foto de perfil">
            {name
              .replace(/^\[TESTE\]\s*/, "")
              .split(/\s+/)
              .filter(Boolean)
              .slice(0, 2)
              .map((part) => part[0])
              .join("") || "?"}
          </span>
        )}
      </div>
      {editable && (
        <div className="profile-photo-controls">
          <h2>Foto do perfil</h2>
          {!profileReady && (
            <p role="status">Salve seus dados no formulário abaixo para adicionar sua foto.</p>
          )}
          <p className="muted">Opcional · JPG, PNG ou WebP · Até 5 MB</p>
          <p className="muted">
            A foto fica disponível para o RH, respeitando as etapas de seleção
            sem identificação.
          </p>
          <input
            ref={input}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            aria-label="Escolher foto do perfil"
            hidden
            disabled={busy || !profileReady}
            onChange={(e) => {
              const file = e.target.files?.[0];
              e.target.value = "";
              if (file) void save(file);
            }}
          />
          <div className="actions">
            <button
              className="button secondary"
              type="button"
              disabled={busy || !profileReady || photo.isPending}
              onClick={() => input.current?.click()}
            >
              {busy
                ? "Salvando…"
                : photo.data
                  ? "Trocar foto"
                  : "Adicionar foto"}
            </button>
            {photo.data && (
              <button
                type="button"
                className="button secondary"
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  setError(undefined);
                  setMessage("");
                  try {
                    await api("/candidates/me/photo", { method: "DELETE" });
                    await client.invalidateQueries({
                      queryKey: ["profile-photo"],
                    });
                    setMessage("Foto removida.");
                  } catch (e) {
                    setError(e);
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Remover foto
              </button>
            )}
          </div>
          {message && <p role="status">{message}</p>}
        </div>
      )}
      {error || photo.error ? <ErrorBox error={error ?? photo.error} /> : null}
    </div>
  );
}
