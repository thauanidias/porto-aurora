import { useEffect, useRef, useState } from "react";
import { getDocument, GlobalWorkerOptions } from "pdfjs-dist";
import workerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import { ErrorBox } from "./ui";

GlobalWorkerOptions.workerSrc = workerUrl;

export default function ResumePreview({ data }: { data: Uint8Array }) {
  const container = useRef<HTMLDivElement>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>();
  useEffect(() => {
    const host = container.current;
    if (!host) return;
    let cancelled = false;
    const task = getDocument({ data: data.slice() });
    async function render() {
      try {
        const pdf = await task.promise;
        for (let number = 1; number <= pdf.numPages; number++) {
          if (cancelled) return;
          const page = await pdf.getPage(number);
          if (cancelled) return;
          const canvas = document.createElement("canvas");
          const viewport = page.getViewport({ scale: 1.8 });
          canvas.width = Math.ceil(viewport.width);
          canvas.height = Math.ceil(viewport.height);
          canvas.setAttribute("role", "img");
          canvas.setAttribute("aria-label", `Currículo, página ${number} de ${pdf.numPages}`);
          const context = canvas.getContext("2d");
          if (!context) throw new Error("Não foi possível visualizar o currículo. Use Baixar currículo para abrir o arquivo.");
          await page.render({ canvas, canvasContext: context, viewport }).promise;
          if (cancelled) return;
          host!.appendChild(canvas);
          const text = await page.getTextContent();
          if (cancelled) return;
          canvas.setAttribute("aria-label", `Currículo, página ${number} de ${pdf.numPages}. ` + text.items.map(item => "str" in item ? item.str : "").join(" "));
          page.cleanup();
        }
        if (!cancelled) setLoading(false);
      } catch (err) {
        if (!cancelled) { setLoading(false); setError(err); }
      }
    }
    void render();
    return () => { cancelled = true; host.replaceChildren(); void task.destroy(); };
  }, [data]);
  return <div className="resume-preview">
    {loading && <p role="status">Carregando currículo…</p>}
    <ErrorBox error={error} />
    <div ref={container} className="resume-preview-pages" aria-label="Páginas do currículo" />
  </div>;
}
