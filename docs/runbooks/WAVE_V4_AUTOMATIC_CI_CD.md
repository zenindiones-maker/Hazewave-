# HAZEWAVE WAVE — CI/CD automático e fail-closed

**Escopo:** desenvolvimento do site Hazewave no GitHub Actions, a partir da branch candidata `work/wave-v4-automatic-ci-cd-v1`. A arquitetura e as autoridades originais permanecem intactas. Política de código sem arte privada em GitHub: **obrigatória**.

## Objetivo: ninguém precisa lembrar os comandos

Após abrir a PR de desenvolvimento uma vez, cada novo commit sincroniza automaticamente as execuções:

1. **Hazewave CI** roda as validações de fonte e Python 3.12 / 3.14.
2. **WAVE Site CI** verifica a identidade exata do commit, integridade do repositório e testes Python, sintaxe JavaScript da V4, TypeScript, build Astro, orçamento de JS e Playwright/Chromium em desktop e celular.
3. **Auto-CD · reviewed WAVE V4 source only** só começa se **ambos** os jobs obrigatórios do WAVE Site CI terminarem `success`. Essa etapa empacota código original e manifestos, verifica SHA-256 e publica um **GitHub Actions artifact privado do run**, disponível na própria página do run por 14 dias.
4. **Auto-CD · visible verdict** exibe automaticamente resultados `success` / `failure` / `skipped` e bloqueios no **GitHub Actions → Summary**. Falhas ficam visíveis para correção. Não há retries cegos nem promoção de artefato baseado só em texto.

A PR #64 V4 é a base; a automação foi estendida na PR #66 V5. A regra `work/wave-v*` aceita próximas versões em PR e mantém o empacotador restrito a arquivos explicitamente autorizados. Nenhum merge é efetuado automaticamente. A branch pode receber commits sem recriar PR ou reescrever scripts de CI.

## O que será entregue a cada sucesso

O ZIP `wave-source-candidate.zip`, e o `*.receipt.json`, contém exclusivamente código, testes e documentação da travessia versionados na lista imutável do validador. Na V5 são **13 arquivos**: fontes V4, testes e os relatórios/recibos de investigação das sete referências. Nenhuma mídia privada é adicionada. O manifesto inclui:

- `reviewed_sha` e `reviewed_tree` exatos do Git;
- SHA-256 de cada arquivo fonte; verificação de igualdade entre bytes do working tree e blobs `HEAD:path`;
- classe `INTERNAL_SOURCE_CANDIDATE_ONLY`;
- `private_assets_present=false`, `media_bytes_embedded=0`;
- `real_browser_media_proven_by_this_artifact=false`, `existing_codespace_runtime_proven=false`;
- `production_approved=false`, `publication_attempted=false`, `merge_attempted=false`;
- SHA-256 de todo o ZIP no recibo externo.

`scripts/ci/wave_candidate_delivery.py` funciona em modo `package` e `verify`, sempre com SHA esperado explícito, sem rede, secrets, produção, segundo Codespace ou processamento no A15. Não usa `git push`, não instala nada e não sobrescreve pacotes antigos. A ordem de entrada e timestamp no ZIP são determinísticos.

## O que nunca acontece sem nova autorização

- merge para `main`, criação automática de PR, publicação de domínio, GitHub Pages ou CDN;
- upload de artes canônicas privadas, vídeos/referências de voz, áudio, credenciais ou arquivos da Library;
- desbloqueio falso de QA cinematográfico ou substituição de prova visual pelo pacote de código;
- abrir outro Codespace, expandir a máquina, reiniciar o Colibri/Reflex ou executar carga no Termux A15;
- instalar providers REA/Íris ou conectar agentes MCP sem prová-los.

**A limitação arquitetural é intencional:** as imagens aprovadas e a prova visual estão na Biblioteca privada; não são acessíveis a um GitHub runner público sem uma forma futura explícita e segura de fornecimento. O artefato automático só atesta **código**; a revisão visual original continua pendente. GitHub Actions artifact não é um site hospedado em produção.

## Links e operação

- Workflow: `.github/workflows/wave-site-ci.yml`
- Validador CD: `scripts/ci/wave_candidate_delivery.py`
- Testes negativos do CD: `tests/test_wave_candidate_delivery.py`
- GitHub → **Actions → WAVE Site CI**; selecionar a execução pelo SHA da branch.
- Em sucesso: abrir **Artifacts → wave-source-candidate-RUN_ID**. Verificar o ZIP localmente por `python scripts/ci/wave_candidate_delivery.py verify --package wave-source-candidate.zip --expected-sha SHA` (com o recibo ao lado).
- Em falha: abrir **Summary**, consultar o job identificado como bloqueado e corrigir a causa. Nunca usar um artefato antigo para representar HEAD novo.

## Critérios de promoção futura

Quando houver aprovação humana explícita, passar novamente por testes de staging utilizando as cinco imagens originais SHA-pinned e os sprites V3A, executar o navegador em 360×800/393×852, gravar vídeo vertical e obter aceite visual da travessia. Somente depois elaborar uma mudança **separada** de autorização de deploy, revisada por segurança e pelo Harness. Nenhum gatilho automático atual tem esse poder.

**Definição de sucesso desta fase:** uma PR de desenvolvimento atualizada dispara o CI, recebe status e, quando todos os gates passam, obtém um artefato **de código** imutável com recibo no próprio GitHub. Isso pode ser atestado só por um Actions run concluído, não pela presença do arquivo YAML.
