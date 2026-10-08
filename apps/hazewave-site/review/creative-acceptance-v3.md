# Hazewave — critérios de revisão criativa V3

Data da pesquisa: 2026-10-08. Escopo: VISUAL / WAVE, candidato de site. Esta é uma rubrica de revisão da implementação, não uma alteração da autoridade do Harness. A aprovação criativa final pertence ao owner.

## Referências consultadas

- Lusion, apresentação e portfólio: https://lusion.co/ — integração de design, movimento, 3D e desenvolvimento; referência de método, sem alegar equivalência de qualidade.
- Immersive Garden: https://immersive-g.com/ — mundos e percursos específicos para cada identidade.
- Awwwards, seleção de storytelling: https://www.awwwards.com/websites/storytelling/ — repertório curatorial; prêmio/estilo não substitui usabilidade.
- GSAP ScrollTrigger: https://gsap.com/docs/v3/Plugins/ScrollTrigger/ — progresso vinculado ao scroll, timelines e reversibilidade.
- GSAP matchMedia: https://gsap.com/docs/v3/GSAP/gsap.matchMedia()/ — adaptação e limpeza de animações por condições de viewport/movimento.
- W3C Animation from Interactions: https://www.w3.org/WAI/WCAG22/Understanding/animation-from-interactions — possibilidade de desativar movimento não essencial.
- web.dev INP: https://web.dev/articles/inp — resposta visual rápida às interações; boa referência de INP é até 200 ms, medida no percentil 75 de visitas reais. Teste local não equivale a esse dado.

## Critérios e evidência obrigatória

| Critério | Evidência | Reprovação |
|---|---|---|
| Identidade | Primeiro frame desktop e mobile sem explicação | Arte parece banner, card ou cenário genérico; demos ditam identidade |
| Hierarquia | Arte domina, caminhos óbvios, texto legível | Etiquetas permanentes competem com a imagem; controles sem função ocupam o hero |
| Causalidade | Gravação: contato → deslocamento da textura → artista revelado | Ripple decorativo, janela desconectada do sinal ou feedback imperceptível |
| Continuidade espacial | Mesma abertura antes, durante e depois de entrar | Portal fecha/reabre, centro salta, outra imagem apenas dá fade |
| Scrollytelling | Avançar, parar no meio, recuar e concluir; gestos nativos | Animação só dispara por tempo; scroll reverso não recompõe a cena; bloqueio da rolagem |
| Mundos autorais | Aquaverno e Hemorragia lado a lado e em movimento | Mesmo layout recolorido; títulos duplicados; material sem relação com a arte original |
| Mobile e acesso | 320–390 px, viewport curto, teclado, busca, Back, reduced motion, perda de WebGL | Sobreposição, alvo minúsculo, foco perdido, rota quebrada ou conteúdo inacessível |
| Integridade e desempenho | Originais preservados, build, tipos, navegador, orçamento JS | Música/fatos inventados, erro de shader, dependência de hardware não testado tratada como PASS |

## Regra de decisão

Falha em identidade, causalidade, continuidade, navegação ou acesso impede chamar a entrega de aprovada. As melhorias são avaliadas por comparação de evidência, sem nota numérica arbitrária. Screenshot não comprova movimento; testes funcionais não comprovam excelência visual. Ausência de faixas autorizadas e de ensaio em aparelho físico são limitações explícitas, nunca PASS implícito.

## Autoavaliação da primeira iteração

REJEITADA COMO FINAL. A composição ficou mais limpa, mas a revisão de código encontrou descontinuidade entre portal e travessia, eventos de ponteiro interferindo no centro da transição e falhas no ciclo de vida do percurso por scroll. Correções aplicadas; nova gravação e regressões exigidas antes da próxima decisão.

## Autoavaliação da iteração corrigida

- Composição: nomes permanentes e barra de áudio indisponível retirados do primeiro viewport; imagem original domina o campo. Capturas desktop e mobile revisadas visualmente.
- Descoberta: a textura real do artista aparece em uma abertura do próprio campo. O nome revelado tem uma ação direta; no percurso guiado essa ação é substituída pela instrução de scroll.
- Continuidade: origem da onda separada da origem de transição; mesma amostragem e limite de abertura usados no preview e na entrada. A captura intermediária mantém Hazewave em uma região enquanto Aquaverno toma o espaço.
- Scrollytelling: percurso curto opcional por rolagem nativa; avanço, pausa, retorno e conclusão reproduzidos no navegador. Busca e links diretos continuam disponíveis.
- Identidade: oceanografia gráfica e deslocamento amplo de Aquaverno contrastam com o emblema original e camadas ósseas sob pressão de Hemorragia. Os títulos duplicados foram removidos.
- Mobile: textos de orientação/ação ampliados; controles principais de 44–48 px; contraste inferior de Aquaverno revisto após reprovação da primeira composição.
- Acesso e navegação: execução final Playwright com 26 PASS, 2 skips exclusivos do desktop. Foco, histórico, busca, reduced motion, perda de GPU e encerramento/reentrada no percurso cobertos.
- Retorno: instruções e sinais do campo reaparecem somente ao fim da travessia reversa; o foco sai do botão de mundo antes de ele ficar inativo.
- Integridade: seis originais preservados byte a byte. Build e TypeScript PASS; core JS 25.931 bytes. Contratos do repositório PASS; suíte Python 196 PASS e uma falha preexistente de recuperação de supervisor, sem alterações nessa área.
- Revisão por agente: inspeção atualizada de fontes e capturas não encontrou outro bloqueio específico. A revisão não viu a gravação completa e não substitui a aprovação criativa do owner.

Decisão: candidato apto à revisão visual do owner no escopo testado. Não equivale a aprovação de produção, classificação estética objetiva, teste em A15/Safari ou comprovação de FPS de hardware. Reprodução imediata permanece indisponível até o fornecimento de faixas autorizadas.
