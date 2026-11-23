import { PlatformConfiguration, ConfigurationSection } from "./pages/PlatformConfiguration";
import { portalHome } from "./lib/portal";
import { lazy, Suspense } from "react";
import { Navigate, Outlet, Route, Routes, useLocation } from "react-router-dom";
import { isManager, useSession } from "./lib/session";
import { Layout } from "./components/Layout";
const ManagerAgenda = lazy(() => import("./pages/ManagerAgenda").then(m => ({ default: m.ManagerAgenda })));
const PublicProcessForm = lazy(() => import("./pages/PublicProcessForm").then(m => ({ default: m.PublicProcessForm })));
const EmployeePreviewPage = lazy(() => import("./pages/EmployeePreview").then(m => ({ default: m.EmployeePreviewPage })));
const ManagerRegisterPage = lazy(() => import("./pages/ManagerAccess").then(m => ({default: m.ManagerRegisterPage})));
const ManagerAccessPage = lazy(() => import("./pages/ManagerAccess").then(m => ({default: m.ManagerAccessPage})));
const ManagerAccessRequestsPage = lazy(() => import("./pages/ManagerAccess").then(m => ({default: m.ManagerAccessRequestsPage})));
const ConsentDocument = lazy(() =>
  import("./pages/ConsentDocument").then((m) => ({
    default: m.ConsentDocument,
  })),
);
const LoginPage = lazy(() =>
  import("./pages/Auth").then((m) => ({ default: m.LoginPage })),
);
const RegisterPage = lazy(() =>
  import("./pages/Auth").then((m) => ({ default: m.RegisterPage })),
);
const RecoverPage = lazy(() =>
  import("./pages/Auth").then((m) => ({ default: m.RecoverPage })),
);
const ConfirmPage = lazy(() =>
  import("./pages/Auth").then((m) => ({ default: m.ConfirmPage })),
);
const MessagesPage = lazy(() => import("./pages/Messages").then(m => ({ default: m.MessagesPage })));
const CandidateVacancies = lazy(() => import("./pages/CandidateVacancies").then(m => ({ default: m.CandidateVacancies })));
const ApplicationsDirectory = lazy(() => import("./pages/ApplicationsDirectory").then(m => ({ default: m.ApplicationsDirectory })));
const CandidateInterviews = lazy(() => import("./pages/CandidateInterviews").then(m => ({ default: m.CandidateInterviews })));
const CareersPage = lazy(() =>
  import("./pages/Careers").then((m) => ({ default: m.CareersPage })),
);
const InternalCareersPage = lazy(() => import("./pages/InternalCareers").then(m => ({ default: m.InternalCareersPage })));
const JobPage = lazy(() =>
  import("./pages/Careers").then((m) => ({ default: m.JobPage })),
);
const PublicPrivacy = lazy(() =>
  import("./pages/Careers").then((m) => ({ default: m.PublicPrivacy })),
);
const ResourcePage = lazy(() =>
  import("./pages/Resources").then((m) => ({ default: m.ResourcePage })),
);
const SettingsPage = lazy(() =>
  import("./pages/Management").then((m) => ({ default: m.SettingsPage })),
);
const AdminPage = lazy(() =>
  import("./pages/Management").then((m) => ({ default: m.AdminPage })),
);
const ReportsPage = lazy(() =>
  import("./pages/Management").then((m) => ({ default: m.ReportsPage })),
);
const VacancyPage = lazy(() =>
  import("./pages/Vacancy").then((m) => ({ default: m.VacancyPage })),
);
const ApplicationDetail = lazy(() =>
  import("./pages/Candidate").then((m) => ({ default: m.ApplicationDetail })),
);
const CandidateDetail = lazy(() =>
  import("./pages/Candidate").then((m) => ({ default: m.CandidateDetail })),
);
const DocumentsPage = lazy(() =>
  import("./pages/Candidate").then((m) => ({ default: m.DocumentsPage })),
);
const MyApplications = lazy(() =>
  import("./pages/Candidate").then((m) => ({ default: m.MyApplications })),
);
const ProfilePage = lazy(() =>
  import("./pages/Candidate").then((m) => ({ default: m.ProfilePage })),
);
const SessionsPage = lazy(() =>
  import("./pages/Candidate").then((m) => ({ default: m.SessionsPage })),
);
const CandidateTests = lazy(() =>
  import("./pages/Workflows").then((m) => ({ default: m.CandidateTests })),
);
const TestCandidatesPage = lazy(() => import("./pages/TestCandidates").then(m => ({ default: m.TestCandidatesPage })));
const OffersPage = lazy(() =>
  import("./pages/Workflows").then((m) => ({ default: m.OffersPage })),
);
const PrivacyPage = lazy(() =>
  import("./pages/Workflows").then((m) => ({ default: m.PrivacyPage })),
);

const ReferralsPage = lazy(() =>
  import("./pages/Intake").then((m) => ({ default: m.ReferralsPage })),
);
const AuditPage = lazy(() => import("./pages/Audit").then(m => ({ default: m.AuditPage })));
const VacancyReport = lazy(() => import("./pages/VacancyReport").then(m => ({ default: m.VacancyReport })));
const ImportPage = lazy(() =>
  import("./pages/Intake").then((m) => ({ default: m.ImportPage })),
);
const SurveysPage = lazy(() =>
  import("./pages/Intake").then((m) => ({ default: m.SurveysPage })),
);

function Protected({ internal = false, manager = false }: { internal?: boolean; manager?: boolean }) {
  const session = useSession();
  const location = useLocation();
  if (session.isPending)
    return (
      <main className="narrow-page" role="status">
        Carregando sua área…
      </main>
    );
  if (!session.data)
    return (
      <Navigate
        to={(location.pathname.startsWith("/oportunidades-internas/") ? "/entrar-colaborador?next=" : internal ? manager ? "/entrar-gestor?next=" : "/entrar-rh?next=" : "/entrar?next=") + encodeURIComponent(location.pathname + location.search)}
        replace
      />
    );
  const administrator = session.data.permissions.includes("system.manage");
  if (administrator) return <Outlet />;
  if (internal && session.data.user.kind !== "INTERNAL")
    return <Navigate to="/candidato" replace />;
  if (internal && isManager(session.data) !== manager) {
    const destination = isManager(session.data) ? "/gestor" : "/app";
    const suffix = location.pathname.replace(/^\/(app|gestor)/, "");
    const allowed = /^\/(vagas|candidatos|candidaturas|solicitacoes|mensagens)(\/|$)/.test(suffix);
    return <Navigate to={destination + (allowed ? suffix + location.search : "")} replace />;
  }
  return <Outlet />;
}
export default function App() {
  return (
    <Suspense
      fallback={
        <main className="narrow-page" role="status">
          Carregando…
        </main>
      }
    >
      <Routes>
        <Route path="/" element={<Navigate to={portalHome()} replace />} />
        <Route path="/carreiras" element={<CareersPage />} />
        <Route path="/carreiras/vagas/:slug" element={<JobPage />} />
        <Route path="/convite" element={<JobPage invitation />} />
        <Route path="/ficha-selecao" element={<PublicProcessForm />} />
        <Route path="/privacidade" element={<PublicPrivacy />} />
        <Route path="/termo-consentimento" element={<ConsentDocument />} />
        <Route path="/entrar" element={<LoginPage />} />
        <Route path="/entrar-colaborador" element={<LoginPage employee />} />
        <Route path="/oportunidades-internas" element={<InternalCareersPage />} />
        <Route path="/previa-colaborador" element={<EmployeePreviewPage />} />
        <Route path="/entrar-rh" element={<LoginPage internal />} />
        <Route path="/entrar-gestor" element={<LoginPage manager />} />
        <Route path="/cadastro" element={<RegisterPage />} />
        <Route path="/cadastro-gestor" element={<ManagerRegisterPage />} />
        <Route path="/cadastro-colaborador" element={<ManagerRegisterPage employee />} />
        <Route path="/recuperar" element={<RecoverPage />} />
        <Route path="/verificar-email" element={<RecoverPage verification />} />
        <Route path="/confirmar" element={<ConfirmPage />} />
        <Route element={<Protected />}>
          <Route path="/candidato" element={<Layout candidate />}>
            <Route path="vagas" element={<CandidateVacancies />} />
            <Route index element={<MyApplications />} />
            <Route path="perfil" element={<ProfilePage />} />
            <Route path="mensagens" element={<MessagesPage candidate />} />
            <Route
              path="candidaturas/:id"
              element={<ApplicationDetail candidate />}
            />
            <Route path="testes" element={<CandidateTests />} />
            <Route
              path="entrevistas"
              element={<CandidateInterviews />}
            />
            <Route path="ofertas" element={<OffersPage candidate />} />
            <Route path="documentos" element={<DocumentsPage />} />
            <Route path="privacidade" element={<PrivacyPage />} />
            <Route path="sessoes" element={<SessionsPage />} />
            <Route path="pesquisas" element={<SurveysPage />} />
          </Route>
          <Route
            path="/oportunidades-internas/:slug"
            element={<JobPage internal />}
          />
        </Route>
        <Route element={<Protected internal manager />}>
          <Route path="/gestor" element={<Layout />}>
            <Route path="entrevistas" element={<ManagerAgenda />} />
            <Route index element={<Navigate to="vagas" replace />} />
            <Route path="vagas" element={<ResourcePage kind="vacancies" />} />
            <Route path="vagas/:id" element={<VacancyPage />} />
            <Route path="solicitacoes" element={<ResourcePage kind="requests" />} />
            <Route path="candidatos" element={<ResourcePage kind="candidates" />} />
            <Route path="candidatos/:id" element={<CandidateDetail />} />
            <Route path="candidaturas/:id" element={<ApplicationDetail />} />
            <Route path="mensagens" element={<MessagesPage />} />
          </Route>
        </Route>
        <Route element={<Protected internal />}>
          <Route path="/app" element={<Layout />}>
            <Route path="candidaturas" element={<ApplicationsDirectory key="external" />} />
            <Route path="candidaturas-internas" element={<ApplicationsDirectory key="internal" internal />} />
            <Route index element={<Navigate to="vagas" replace />} />
            <Route path="gestores" element={<ManagerAccessPage />} />
            <Route path="acessos-gestores" element={<Navigate to="/app/gestores" replace />} />
            <Route path="solicitacoes-acesso-gestores" element={<ManagerAccessRequestsPage />} />
            <Route path="trabalho" element={<ResourcePage kind="tasks" />} />
            <Route path="vagas" element={<ResourcePage kind="vacancies" />} />
            <Route path="mensagens" element={<MessagesPage />} />
            <Route path="vagas/:id" element={<VacancyPage />} />
            <Route
              path="solicitacoes"
              element={<ResourcePage kind="requests" />}
            />
            <Route
              path="candidatos"
              element={<ResourcePage kind="candidates" />}
            />
            <Route path="candidatos/:id" element={<CandidateDetail />} />
            <Route path="candidaturas/:id" element={<ApplicationDetail />} />
            <Route path="banco" element={<ApplicationsDirectory key="archive" archive />} />
            <Route path="grupos-talentos" element={<ResourcePage kind="pools" />} />
            <Route
              path="entrevistas"
              element={<ResourcePage kind="interviews" />}
            />
            <Route
              path="avaliacoes"
              element={<ResourcePage kind="evaluations" />}
            />
            <Route path="testes" element={<TestCandidatesPage />} />
            <Route path="ofertas" element={<OffersPage />} />
            <Route path="documentos" element={<DocumentsPage />} />
            <Route path="documentos/:candidateId" element={<DocumentsPage />} />
            <Route path="privacidade" element={<PrivacyPage admin />} />
            <Route path="relatorios" element={<ReportsPage />} />
            <Route path="configuracao-plataforma" element={<PlatformConfiguration />} />
            <Route path="configuracao-plataforma/sistema" element={<ConfigurationSection><SettingsPage /></ConfigurationSection>} />
            <Route path="configuracao-plataforma/acessos" element={<ConfigurationSection><AdminPage /></ConfigurationSection>} />
            <Route path="configuracao-plataforma/privacidade" element={<ConfigurationSection><PrivacyPage admin /></ConfigurationSection>} />
            <Route path="configuracao-plataforma/auditoria" element={<ConfigurationSection><AuditPage /></ConfigurationSection>} />
            <Route path="configuracoes" element={<SettingsPage />} />
            <Route path="administracao" element={<AdminPage />} />
            <Route path="auditoria" element={<AuditPage />} />
            <Route path="indicacoes" element={<ReferralsPage />} />
            <Route path="importacao" element={<VacancyReport />} />
            <Route path="importacao-candidatos" element={<ImportPage />} />
          </Route>
        </Route>
        <Route
          path="*"
          element={
            <main className="narrow-page">
              <h1>Página não encontrada</h1>
              <a href="/carreiras">Voltar ao portal de carreiras</a>
            </main>
          }
        />
      </Routes>
    </Suspense>
  );
}
