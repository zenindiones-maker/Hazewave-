# WAVE — Qualificação no Codespace real (sem instalar, sem reiniciar)

**Referência:** PR de desenvolvimento `work/wave-host-mcp-qualification-v1`. O Harness é a única autoridade. Este procedimento **não é aprovação de produção**.

## Escopo e bloqueios
- Reutilizar **somente** o Codespace já existente `hazewave-zero-cost-4jxp45676rq6279xx`, sem criar outro, alterar o tamanho ou habilitar cobrança.
- Não usar processamento no A15. Não interromper Colibri/Reflex, não mudar branches de trabalho ativos, não iniciar loops e não conectar o MCP global.
- Não instalar REA6, Íris, navegador ou Playwright sem nova qualificação de recursos. `--inventory` não instala.
- A identidade de Codespace deve ser atestada pelo próprio canal autenticado `gh codespace ssh -c`. O nome em `CODESPACE_NAME` é apenas uma declaração de ambiente, não identidade autenticada.
- **Até prova independente do agente:** `OWNER_AGENT_MCP_CONNECTED=NOT_PROVEN`.

## Procedimento pelo Work, usando seu ambiente autenticado (não A15)
Confira `gh auth status`, `gh codespace list` e conecte via `gh codespace ssh -c hazewave-zero-cost-4jxp45676rq6279xx`. Não inicialize outro Codespace. Faça todo o processamento **dentro** dele.

No shell do Codespace autenticado:

```bash
set -euo pipefail
cd /workspaces/Hazewave-
test "${CODESPACES:-}" = "true"
test -z "$(git status --porcelain --untracked-files=normal)" || {
  echo "ACTIVE_WORKTREE_DIRTY=STOP_PRESERVE_WIP"; exit 20;
}
git fetch --no-tags origin refs/heads/work/wave-host-mcp-qualification-v1
SHA="$(git rev-parse FETCH_HEAD)"
test "$(git ls-remote origin refs/heads/work/wave-host-mcp-qualification-v1 | awk 'NR==1 {print $1}')" = "$SHA"
WORKTREE="$HOME/.local/share/hazewave/research-qualification-${SHA:0:12}"
test ! -e "$WORKTREE"
git worktree add --detach "$WORKTREE" "$SHA"
cd "$WORKTREE"
export HAZEWAVE_RESEARCH_EXPECTED_SHA="$SHA"
bash scripts/codespaces/wave-research-priority-gates.sh --inventory
```

Se `--inventory` registrar ausência de REA6 ou Íris, **parar**. Usar seus instaladores existentes sob revisão específica e com orçamento de RAM/disco aprovado; não iniciar instalação em massa.

Somente depois do inventário real:

```bash
bash scripts/codespaces/wave-research-priority-gates.sh --prove
bash scripts/codespaces/wave-research-priority-gates.sh --client-probe
bash scripts/codespaces/wave-research-priority-gates.sh --wave-scroll
```

Esses três modos são separados: podem bloquear individualmente. O último exige `require("playwright")` e os navegadores já qualificados no Codespace. Saídas privadas ficam em `~/.local/state/hazewave/`, não em Git.

### Gate adicional: sessão de agente de verdade
A execução do `--client-probe` prova o protocolo MCP via um cliente independente, **não prova** que Hermes/Codex/Agent Office já carrega os tools. No cliente escolhido, após revisão explícita da configuração local, inicializar apenas a fachada `python3 -m hazewave.harness_research_mcp` apontando para o worktree SHA imutável, com argumentos de binários pinados e `--state-root` privado. Verificar **dentro do agente** o `initialize`, `tools/list` e o `tools/call` para os dois alvos próprios, com recibo do processo real. Não usar `iris mcp` ou `rea mcp` raw. Não inventar recibos ou promover `agent_mcp_session_connected` em dados gerados por fonte não confiável.

### Bloqueio de sites externos
`--wave-scroll` só observa `tests/fixtures/wave-scroll-owned.html`. Referências públicas ficam somente em pesquisa textual/arquitetural até haver revisão de permissão do alvo, autorização do Harness, navegador efêmero não privilegiado, contenção **no sistema operacional** de egress e verificação de redirecionamentos, WebSockets, Service Workers, DNS e requests externos. Interceptar rotas Playwright sozinho não é sandbox de rede.

### Resultado esperado e campos obrigatórios
```
SOURCE_OF_TRUTH=VERIFIED_OR_BLOCKED
REVIEWED_SHA=<git rev-parse HEAD>
REVIEWED_TREE=<git rev-parse HEAD^{tree}>
CODESPACE_IDENTITY=AUTHENTICATED_SSH_OR_UNVERIFIED
REA6_HOST=PROVEN_OR_BLOCKED
IRIS_HOST=PROVEN_OR_BLOCKED
WAVE_SCROLL_HOST=PROVEN_OR_BLOCKED
INDEPENDENT_MCP_CLIENT=PROVEN_OR_BLOCKED
OWNER_AGENT_SESSION=UNVERIFIED_UNTIL_DIRECT_PROOF
EXTERNAL_TARGETS=NOT_TESTED
PRODUCTION_APPROVED=FALSE
STOCK_HEALTH=NOT_CHECKED_UNLESS_READ_ONLY_PROBE
```

Preserve todos os WIPs. Não mesclar `main` nem publicar o site sem revisão artística e autorização humana.
