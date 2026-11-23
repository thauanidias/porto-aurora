import { useEffect, useRef, useState } from "react";
import { Eraser, PenLine } from "lucide-react";

export function SignaturePad({ value, onChange, title }: { value: string; onChange: (value: string) => void; title: string }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const drawing = useRef(false);
  const [name, setName] = useState("");
  useEffect(() => {
    const node = canvas.current;
    const context = node?.getContext("2d");
    if (!node || !context) return;
    context.clearRect(0, 0, node.width, node.height);
    if (!value.startsWith("data:image/png;base64,")) return;
    const image = new Image();
    let current = true;
    image.onload = () => { if (current) context.drawImage(image, 0, 0, node.width, node.height); };
    image.src = value;
    return () => { current = false; };
  }, [value]);
  const finish = () => {
    if (!drawing.current) return;
    drawing.current = false;
    if (canvas.current) onChange(canvas.current.toDataURL("image/png"));
  };
  return <div className="signature-field" id="assinatura-eletronica">
    <h3>{title}</h3><p className="muted">Desenhe com o mouse ou com o dedo. Você também pode digitar seu nome para gerar a assinatura eletrônica.</p>
    <canvas ref={canvas} width={900} height={220} className="signature-canvas" aria-label="Área para desenhar assinatura" onPointerDown={event => {
      if (event.button !== 0) return;
      const node = event.currentTarget;
      const context = node.getContext("2d");
      if (!context) return;
      event.preventDefault(); node.setPointerCapture(event.pointerId); drawing.current = true;
      const rect = node.getBoundingClientRect();
      context.beginPath(); context.lineWidth = 3; context.lineCap = "round"; context.lineJoin = "round"; context.strokeStyle = "#182d49";
      context.moveTo((event.clientX - rect.left) * node.width / rect.width, (event.clientY - rect.top) * node.height / rect.height);
    }} onPointerMove={event => {
      if (!drawing.current) return;
      const node = event.currentTarget; const rect = node.getBoundingClientRect(); const context = node.getContext("2d");
      context?.lineTo((event.clientX - rect.left) * node.width / rect.width, (event.clientY - rect.top) * node.height / rect.height); context?.stroke();
    }} onPointerUp={finish} onPointerCancel={finish} />
    <div className="signature-tools"><button type="button" className="button secondary small" disabled={!value} onClick={() => { drawing.current = false; onChange(""); }}><Eraser size={16} />Limpar assinatura</button><span role="status">{value ? "Assinatura pronta para confirmar." : "Nenhuma assinatura registrada."}</span></div>
    <div className="signature-typed"><label className="field"><span>Nome para gerar assinatura</span><input value={name} maxLength={180} onChange={event => setName(event.target.value)} placeholder="Digite seu nome completo" /></label><button type="button" className="button secondary small" disabled={name.trim().length < 3} onClick={() => {
      const node = canvas.current; const context = node?.getContext("2d");
      if (!node || !context) return;
      context.clearRect(0, 0, node.width, node.height); context.fillStyle = "#182d49";
      const size = Math.min(54, 800 / Math.max(1, name.trim().length * .6));
      context.font = `italic ${size}px Georgia, serif`; context.fillText(name.trim(), 35, 125, 830);
      onChange(node.toDataURL("image/png"));
    }}><PenLine size={16} />Usar meu nome como assinatura</button></div>
  </div>;
}
