import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import { loadPortal } from "./lib/portal";
import { PortalBoundary } from "./components/PortalBoundary";
import { BrandSettings } from "./components/Brand";
import "./styles.css";
import "./brand.css";
import "./sidebar.css";
import "./workspace-background.css";
import "./process-workflow.css";
import "./rh-process-guide.css";
import "./register.css";
import "./login.css";
import "./careers-home.css";
import "./responsive.css";
const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false, staleTime: 15000 },
  },
});
loadPortal().then(() => ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <BrandSettings />
        <PortalBoundary><App /></PortalBoundary>
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
)).catch(() => {
  document.getElementById("root")!.textContent = "Não foi possível carregar o portal. Atualize a página para tentar novamente.";
});
