<p align="center"><img src="frontend/public/assets/brand/porto-aurora-logo.png" alt="Porto Aurora" width="420"></p>

# Porto Aurora · Banco de Talentos

Plataforma de recrutamento e seleção apresentada no portfólio de **Thauani Dias**, com identidade fictícia e interface em português.

O projeto reúne portal de carreiras, cadastro de candidatos e áreas de RH e gestores para acompanhar vagas e processos seletivos.

Construído por **Thauani Dias com auxílio de inteligência artificial**, incluindo apoio na geração e nos ajustes de código, na identidade visual e na documentação. O projeto faz parte de um processo de aprendizado em desenvolvimento web.

## Funcionalidades

- Portal de vagas externas e oportunidades internas.
- Cadastro, currículo e acompanhamento de candidaturas.
- Gestão de vagas, etapas, avaliações e ofertas.
- Autenticação e controle de acesso por perfil.
- Modelos de e-mail com a identidade Porto Aurora.
- Relatórios, registros de auditoria e recursos de privacidade.

## Tecnologias

| Camada | Tecnologias |
|---|---|
| Interface | React, TypeScript, Vite, Tailwind CSS |
| API | Python, FastAPI, SQLAlchemy, Alembic |
| Dados | PostgreSQL, Redis |
| Tarefas | Celery |
| Execução | Docker Compose, Nginx |
| Testes | Pytest, Vitest, Playwright |

## Executar localmente

Requisitos: Docker com Compose e Python 3.12 ou superior. No Apple Silicon, o serviço ClamAV pode exigir `platform: linux/amd64` em um override local.

```bash
python3 scripts/init-env.py
docker compose up -d --build --wait
docker compose exec backend python -m app.bootstrap
```

O bootstrap solicita os dados do primeiro administrador. Não há credenciais padrão.

- Carreiras: http://localhost:8088/carreiras
- Painel do RH: http://localhost:8088/entrar-rh
- Oportunidades internas: http://localhost:8088/oportunidades-internas
- Prontidão dos serviços: http://localhost:8088/readiness

O envio de e-mails depende de configuração SMTP própria e começa desativado. A primeira inicialização do antivírus pode levar alguns minutos.

## Estrutura

```text
backend/    API, regras de negócio, migrations e testes
frontend/   Interface, estilos, componentes e testes
infra/      Configuração do proxy
scripts/    Inicialização e verificações
```

## Verificação

```bash
docker compose exec backend pytest
cd frontend
npm ci
npm run build
npm test
```

Alguns testes de integração exigem banco descartável e configuração específica. Consulte `scripts/test.ps1` antes de executá-los. Não use dados reais em testes.

## Sobre esta versão

Porto Aurora é uma identidade fictícia para demonstração. Esta cópia não inclui o `.env` local, senhas, certificados corporativos, uploads ou dados do banco em uso. As integrações precisam ser configuradas em cada ambiente. A avaliação de aderência utiliza critérios e pesos explícitos; não emprega IA para classificar candidatos.

Os identificadores técnicos legados foram mantidos onde são necessários à compatibilidade. As licenças de terceiros acompanham os respectivos componentes; a fonte Source Sans Pro inclui sua licença no diretório de assets.

## Demonstração pública, sem senha

A pasta `docs/` contém uma apresentação interativa e independente do banco de dados, preparada para GitHub Pages. As áreas de RH, candidato e gestor podem ser exploradas livremente com dados fictícios. As alterações são simuladas na memória do navegador e desaparecem ao atualizar a página. Esta demonstração não substitui todos os recursos da aplicação completa.

Após habilitar Pages em **Settings → Pages → Deploy from a branch → main → /docs**, a demonstração ficará em:

- [Escolher perfil](https://thauanidias.github.io/porto-aurora/)
- [RH](https://thauanidias.github.io/porto-aurora/#rh)
- [Candidato](https://thauanidias.github.io/porto-aurora/#candidato)
- [Gestor](https://thauanidias.github.io/porto-aurora/#gestor)
