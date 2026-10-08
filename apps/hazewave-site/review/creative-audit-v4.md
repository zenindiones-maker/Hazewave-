# HAZEWAVE — auditoria crítica V4

Data: 08/10/2026. Escopo: site WAVE; direção artística, interação, conteúdo, acesso, arquitetura e custo gráfico. Documento de avaliação, não política normativa do Harness.

**VEREDITO: V3 REPROVADO COMO PRODUTO FINAL.** A correção técnica salva nesta etapa não muda esse veredito. A próxima entrega artística exige reconstrução do palco e do percurso, não outro passe de polimento.

Repositório: `zenindiones-maker/Hazewave-`. Fonte auditada: `85781eabd8af4e6cec82fb5a1717ac587e48d626`. Correções em `work/wave-audit-reset-v4`. Branch ativo histórico e produção preservados. Nenhuma promoção/publicação tentada.

## O erro da avaliação anterior

A avaliação V3 foi permissiva. Mudança entre dois frames foi tratada como evidência suficiente de onda; a atmosfera muda sozinha e torna essa comparação fraca. Diferenças entre imagens foram tratadas como mundos diferentes; três artistas continuam usando o mesmo procedimento de composição. A identidade e a navegação existem, mas isso não comprova um campo espacial nem um produto musical completo. A rejeição do owner permanece vinculante.

## Método e limites

- Leitura do HTML, CSS, manifestos, shader, controle de interação e testes da entrada atual, vinculada ao SHA acima.
- Capturas novas em 1440×900, 390×844 com DPR2, 768×1024 e 320×568. Inspeção dos cinco artistas; comparação visual com os originais Hazewave e Aquaverno.
- Inspeção das capturas e quadros extraídos das gravações V3; não substitui observação contínua por usuário real. As gravações existentes usam Chromium real; codificação a 30 fps não mede FPS do aparelho.
- Dois revisores em paralelo: arte/experiência e implementação. O revisor artístico viu capturas e contact sheets; não assistiu ao vídeo contínuo. O técnico leu código e reproduziu a race de decode em ambiente controlado. O auditor principal confirmou-a também no navegador.
- Cenários adversariais novos: preferência de movimento durante decode, contato distante, interrupção durante entrada, arquivo secundário404 e viewport curto.
- Sem ensaio físico no A15, Safari, leitor de tela, usuário externo, INP de campo, consumo de energia ou profiler de GPU real. Contraste sobre todos os frames, zoom200%, forced-colors e reflow completo continuam sem qualificação. Não são PASS implícitos.

## Achados e decisão

P1: impede aceitar o objetivo criativo/funcional. P2: precisa ser resolvido ou qualificado antes da publicação. Severidade é prioridade deste produto, não score de vulnerabilidade.

| ID | Prioridade | Achado e evidência | Estado |
|---|---|---|---|
| A01 | P1 | **Campo ainda plano.** O renderer é um triângulo fullscreen; torre, cidade, céu e água são amostras da mesma textura. “Analytic depth” altera UV por fórmulas/luminância; não produz planos independentes, oclusão ou câmera espacial. O resultado em repouso lê como pôster com hotspots. | Reconstruir composição em camadas |
| A02 | P1 | **Materiais sem proteção.** A onda desloca a cena inteira; farol e assinaturas tipográficas podem se curvar junto da água. Esse comportamento parece lente sobre ilustração, com pouca causalidade material. | Máscaras por material e limites de deformação |
| A03 | P1 | **Identidade tipográfica diluída.** O lettering original Hazewave é removido pelo crop; interface usa Arial. AQUAVERNO original é cortado e substituído por Georgia. Barak, Indionesbala e Baazü recebem títulos duplicados sobre logos já presentes. Bytes originais intactos não significam identidade compositiva intacta. | Derivados rastreáveis de lettering e hierarquia própria |
| A04 | P1 | **Descoberta pouco legível.** Os sinais são cinco traços finos de1px, integrados a uma imagem já muito detalhada. Os nomes aparecem apenas depois do input. A promessa de descoberta depende de tentativa, não de uma presença clara no campo. | Redesenhar sinais ligados à luz/água/névoa |
| A05 | P1 | **Scrollytelling sem atos.** O progresso expande uma máscara de textura e muda três legendas. Existe reversibilidade, mas o percurso não desenvolve enquadramento, informação ou objetivo até a chegada. | Três atos com composição e função distintas |
| A06 | P1 | **Explore fixo em Aquaverno.** `signals[3]`, `preview(4)` e rota `aquaverno` são constantes no percurso guiado. Descobrir outro artista não muda o destino. | Percurso derivado do sinal selecionado |
| A07 | P1 | **Três mundos são variantes do mesmo palco.** Barak, Indionesbala e Baazü mudam crop, escala e cor; compartilham atmosfera e parallax. Identificadores `pressure-type`, `heat-type`, `blue-illustration` não governam sistemas de cena separados. | Composição e resposta específicas por artista |
| A08 | P1 | **Chegada sem ação musical.** Cada mundo termina em arte, Voltar e Outro sinal. Não há catálogo autorizado nem ligação ao engine/player antigo; LISTEN abre controles permanentemente disabled. A indisponibilidade é honesta, mas o loop musical não está implementado nem demonstrado. | Contrato de conteúdo e adapter; prova final depende de faixa autorizada |
| T01 | P1 | **Race de movimento comprovada.** Com imagens atrasadas1100ms, mudar a preferência para reduzir movimento terminou em `motion=reduced`, `runtime=webgl2`. `initialize()` reativava RAF após decode sem revalidar a preferência. | Corrigido nesta etapa; regressão acrescentada |
| T02 | P1 | **Interrupção perde a composição atual.** Instrumentação de uniforms: entrada0→4 em21,8%; ao voltar, nova cena começa4→0 em9,8%. A origem passa a ser Aquaverno completo, não a mistura visível. `from=this.to` confirma o salto estrutural. | Aberto; renderer/state machine de transição precisa preservar composição |
| T03 | P1 | **Revelação antecipa a onda.** Contato1920×1080 no canto inferior: distância normalizada0,5853; chegada calculada1064ms; revelação observada813ms. O timer estava limitado a750ms, sem relação integral com a propagação. | Corrigido; velocidade compartilhada com shader e regressão |
| T04 | P2 | **Falha secundária derruba o campo.** Interceptar só `baazu.png` com404 produz `css-fallback` para a experiência inteira. Todas as seis imagens são requeridas no `Promise.all`. | Aberto; campo inicial independente e carregamento por demanda |
| T05 | P2 | **Qualidade adaptativa desconectada.** Há limite de DPR, sem teto absoluto de pixels ou resposta ao tempo gráfico. 3840×2160 com DPR1,5 cria18.662.400 pixels por draw. Fence reduz fila, não custo por quadro. | Aberto; reconectar tiers e orçamento absoluto |
| T06 | P2 | **Carga gráfica ocultada pelo pequeno JS.** Seis originais:1.864.992 bytes transferidos; como RGBA,40.839.168 bytes (~38,95MiB) em texturas, antes de imagens DOM e framebuffer. Todos são carregados no início. Core26KB não mede custo da cena. | Aberto; decodes, texturas e render targets devem ter orçamento |
| U01 | P1 | **Instrução ausente em mobile curto.** Em320×568, regra CSS remove a frase de descoberta. Usuário vê traços sem explicação. Não havia overflow, mas acesso ao conceito foi perdido. | Corrigido sem sobrepor navegação; regressão |
| U02 | P2 | **Microtipografia insuficiente.** Medição: subtítulo8px no mobile; Santos9px; navegação10px; instrução11px; etapas/saída da travessia8px. Alvos de48–64px não tornam texto legível. | Redesenhar escala e eliminar metadados sem função |
| U03 | P2 | **Controle de movimento incompleto.** Respeitar preferência do sistema não oferece escolha explícita dentro do site. Shader não essencial continua animando em repouso. Precisa de mecanismo acessível para pausar/reduzir movimento, com avaliação da aplicação do SC2.2.2. | Aberto; não declarar WCAG conforme |
| Q01 | P1 | **Critérios de prova fracos.** `before != after` passa por movimento ambiente; rotas/DOM não verificam diferenciação artística. A suíte antiga não cobria decode race, distância da onda, interrupção ou404. | Três regressões novas; critérios visuais reconstruídos abaixo |

## Cobertura adicional do produto

**Conteúdo e proveniência:** seis arquivos conferidos novamente contra SHA-256/bytes do manifesto,6/6 PASS. Não há demos na entrada, biografias, lançamentos ou música inventada. A autoridade dos arquivos é preservada; o recorte/composição ainda pode diluir a identidade, conforme A03. Não foi feita uma nova análise de direitos de publicação.

**Navegação e acesso funcional:** busca por nome/acento, rota direta, Back/Forward, Escape, foco, fallback e ausência de JavaScript têm regressões existentes. Isso não cobre qualidade da descoberta nem todas as tecnologias assistivas. Art descriptions genéricas também precisam ser revistas junto da nova composição.

**Segurança da superfície:** os dois módulos novos usam IDs de artistas em allowlist e `textContent` para texto dinâmico; não foi encontrado `innerHTML`, `eval` ou envio de dados no fluxo auditado. Esse exame da superfície não é pentest, auditoria de dependências, CodeQL ou validação de infraestrutura de produção. Não alteramos autenticação, política, runtime HAZE ou promoção.

**Metadata e entrega:** título do documento muda no cliente, mas OG title/image do HTML continuam Hazewave para todos os `?artist=`. A identidade de compartilhamento por artista ainda não está implementada. Domínio canônico/publicação não foi fornecido; não inventar URLs. Preview local e ZIP não equivalem a deploy validado, cache/headers corretos ou SEO completo. Qualificar isso antes de publicar, após o loop principal.

**Orçamento e manutenção:** Astro/TypeScript estão mantidos; Three.js/GSAP e o antigo quality engine permanecem no repositório, mas não governam o novo renderer fullscreen. A nova experiência precisa reaproveitar suas capacidades quando úteis, sem carregar dependência só para citar tecnologia. Renderer e controlador concentrados em centenas de linhas dificultam cenários de interrupção e estado; dividir por responsabilidade durante a reconstrução, sem refactor cosmético isolado.

## O que a arte precisa se tornar

Reconstruir o palco a partir da imagem do owner, mantendo-a reconhecível. Separar vórtice/atmosfera, torre/cidade e água próxima por máscaras revisadas. Torre e lettering permanecem rígidos; água e névoa recebem movimento e refração. A profundidade precisa aparecer por deslocamento relativo e oclusão, não pelo comentário do código. Não acrescentar planetas, partículas genéricas ou nova lore.

O sinal deve existir como alteração localizada no material — uma quebra de luz, corrente ou abertura legível — antes de virar nome. Um caminho inicial pode ser visível; os demais surgem pelo contato e exploração. Não restaurar cinco chips permanentes nem tornar invisibilidade uma virtude estética.

A travessia precisa de três atos: **descobrir** (presença do artista no material), **atravessar** (câmera/planos/escala mudam preservando a origem) e **chegar** (identidade do artista e ação assumem a hierarquia). A rolagem controla esses estados; pausa e reversão recompõem a mesma cena. Nenhum ato depende de texto fictício.

Aquaverno: separar gravura de mar, rocha próxima, horizonte/lua e assinatura real. A câmera atravessa a água e encontra uma composição de chegada própria. Hemorragia: arame e ossos derivados da arte delimitam um espaço de pressão; recorte, oclusão e tensão têm ritmo diferente do oceano. Emblema protegido de deformação. Não reutilizar a mesma tomada com cor diferente. Os outros artistas precisam de estudo equivalente a partir de seus assets, sem inventar gênero ou biografia.

A navegação comum pode permanecer mínima. Identidade e distribuição da cena não precisam compartilhar o mesmo template. Remover índices e títulos duplicados que não ajudam a decidir. Recuperar lettering original por derivados com origem documentada, sem transformar o logo em decoração gigantesca.

A chegada musical fica explicitamente pendente de conteúdo autorizado. Pode-se preparar o contrato e o adapter sem fingir áudio. Somente uma faixa real permite validar play/pause, seek, volume, persistência e continuidade entre mundos.

## Critérios que substituem a aprovação permissiva

| Porta de revisão | Prova exigida | Reprovação imediata |
|---|---|---|
| Campo espacial | Repouso, parallax lateral e contato em desktop/mobile; comparação com original | Tudo move na mesma superfície; farol se curva como água |
| Descoberta | Primeiro viewport e primeira interação, sem explicação externa | Arte parece wallpaper; usuário depende de acertar traço invisível |
| Identidade | Originais e chegada lado a lado | Lettering autoral trocado por fonte genérica ou título duplicado |
| Causalidade | Contatos próximos e distantes em água, torre e sinal | Sinal aparece antes da onda; mesmo material em todo ponto |
| Scrollytelling |0/20/40/60/80/100%, ida, pausa e recuo por roda e dedo | Apenas máscara cresce; destino fixo apesar da escolha |
| Continuidade | Voltar/trocar aos20/50/80%, GPU rápida/lenta | Salto para destino não alcançado ou recomeço desconectado |
| Mundos | Aquaverno e Hemo sem labels; organização espacial e resposta comparadas | Só textura/paleta identifica o artista |
| Acesso |320/390/768/1440, orientação, zoom, contraste, teclado, screen reader e movimento | Instrução desaparece, foco perdido ou função só por gesto |
| Resiliência | Um asset falha, decode lento, loss de GPU, voltar/reentrar | Mundo secundário derruba campo; preferência não respeitada |
| Música | Faixa autorizada e persistência enquanto troca de mundo | Controles sem função tratados como capacidade pronta |
| Desempenho | Teto gráfico/tier; perfil em A15 físico e Safari | Só JS pequeno/headless usado como comprovação de fluidez |

Todos os bloqueios centrais precisam passar. Não há média numérica capaz de compensar uma falha de identidade, causalidade ou acesso. Não usar premiação, biblioteca gráfica ou número de shaders como prova de excelência.

## Bases de referência

- Lusion, The Turn Of The Screw: https://lusion.co/projects/the_turn_of_the_screw/ — referência de experiência audiovisual explorável, descrita pelo próprio estúdio; não prova equivalência de Hazewave.
- W3C, Target Size Minimum: https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html — distingue alvo de interação da avaliação de legibilidade.
- W3C, Pause Stop Hide: https://www.w3.org/WAI/WCAG22/Understanding/pause-stop-hide.html — critérios para movimento automático; conformidade exige avaliar a experiência completa.
- W3C, Animation from Interactions: https://www.w3.org/WAI/WCAG22/Understanding/animation-from-interactions.html — possibilidade de desativar movimento não essencial iniciado por interação.
- MDN, WebGL best practices: https://developer.mozilla.org/en-US/docs/Web/API/WebGL_API/WebGL_best_practices — orçamento gráfico, limites e redução do back buffer.
- web.dev, INP: https://web.dev/articles/inp — medir resposta às interações; não foi medido INP real nesta auditoria.

## Correções delimitadas nesta etapa

1. Inicialização compartilhada por promise evita concorrência durante decode; preferência de movimento é revalidada antes de publicar WebGL/RAF. Recursos já alocados podem ser reutilizados ao remover a preferência.
2. Timer de revelação usa a mesma velocidade radial do shader, sem teto antecipado750ms.
3. Instrução permanece no portrait curto e tem verificação de separação da navegação.
4. Três testes novos verificam esses comportamentos em desktop e mobile.

Essas correções não implementam novos mundos, câmera, áudio, tiers ou preservação de frame interrompido. Não se apresentam como novo marco artístico.

## Validação e estado final

- Astro build, TypeScript e orçamento JS: PASS. Core26.204 bytes, sem compressão; isso não atesta custo de GPU.
- Playwright final desktop/mobile:32 PASS,2 skips de casos mobile na execução desktop. Inclui3 regressões novas executadas em ambos os projetos.
- A primeira suíte pós-correção:31 PASS,1 FAIL por expectativa antiga que exigia esconder a instrução. A expectativa foi substituída por presença e separação da navegação; a suíte final acima passou. Não apagar esse resultado inicial.
- Revisão técnica adicional com decode controlado:full→reduce→full→reduce termina em fallback com0 RAF e1 contexto; opt-in depois de decode reutiliza o contexto. Nenhum novo problema específico nas três correções foi encontrado pelo revisor.
- Compilação Python e contratos do repositório: PASS. Suíte raiz:196 PASS,1 FAIL no mesmo teste preexistente de recuperação de supervisor (`test_boot_recovers_after_supervisor_sigkill_with_stale_pid_and_lock`, exit3). Essa área não foi alterada.
- Seis originais: SHA-256 e tamanho6/6 PASS;1.864.992 bytes.

**CREATIVE_ACCEPTANCE=REJECTED.** As correções verificadas removem três defeitos; os bloqueios artísticos/estruturais e a dependência de áudio continuam abertos. Não chamar essa branch de V4 artística concluída, produto ultra profissional ou pronto para publicar.
