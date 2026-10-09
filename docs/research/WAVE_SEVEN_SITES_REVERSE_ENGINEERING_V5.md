# REA / WAVE — Engenharia reversa aprofundada de sete referências

**Data:** 09/10/2026. **Projeto:** somente `zenindiones-maker/Hazewave-`. **Autoridade:** HAZEWAVE_HARNESS. **Material externo proprietário copiado:** nenhum.

## Resultado real: código-fonte, documentação técnica e lacunas

Pesquisa pública realizada nas sete referências, seguida de implementação e avaliação do **motor da própria WAVE**. Diferenciar `CODE_DIRECTLY_INSPECTED`, `AUTHORED_TECHNICAL_EXPLANATION`, `PUBLIC_SITE_DESCRIPTION` e `HISTORICAL_REFERENCE` é obrigatório; uma página textual pública não prova o comportamento atual de seu renderizador.

| Referência | Evidência realmente consultada | Mecânica relevante | Resultado na WAVE |
| --- | --- | --- | --- |
| **NASA Prospect** | Repositório MIT `collinhover/nasaprospect`, módulos de navegação, seções e loop | gatilhos ordenados por posição/direção; inicialização e descarte por seção; redefinição dos triggers após regressão; detecção de desempenho lento e degradação opcional | **NOVO** mapa de cinco atos com seek reversível e modo leve, original e sem dependências |
| **Ponpon Mania** | artigo assinado pelos próprios criadores no Codrops | exportação de planos, atlas de texturas, compactação GPU, shader de transição, câmera acoplada ao `ScrollTrigger` | V4 já tem camadas/rig/câmera; **atlas WebGL não comprovado nem copiado** |
| **Who's Guilty** | site original, CSS Design Awards e relatório da REB8T | Lottie combinado com código próprio, som opcional e episódios ilustrados | V4 tem coreografia original de peças; não importa Lottie nem os desenhos do site |
| **NYT / Tomato Can Blues** | entrevistas e análise editorial histórica | HQ em parallax 2.5D, câmera que atravessa os planos e opção de narração | V4 já desloca planos; sem provar a execução atual da página de 2013 |
| **SBS / The Boat** | recursos educacionais do próprio SBS e estudos da HQ | ilustração pintada, movimento de profundidade e desenho sonoro | original Hazewave em planos de névoa; áudio contextual ainda depende de consentimento e teste |
| **Genie Studio App** | site geniestudio.app e apresentação autoral | revelação no hover e linguagem visual de microinterações | navegação de atos nativamente utilizável por teclado e toque; implementação JS da origem **não analisada** |
| **Esimple** | própria agência define sua história como scrollytelling Web3D | travessia de câmera em ambiente tridimensional | V4 implementa 2.5D de arte original; **Web3D/WebGL e geometria volumétrica genuína não atestados** |

### Prova direta, com hashes, do NASA Prospect

`collinhover/nasaprospect`, branch `master`, licença [MIT](https://github.com/collinhover/nasaprospect/blob/master/LICENSE.md). Arquivos públicos verificados pelo conector GitHub:

- `js/app/navigator.js`, Git blob SHA-1 `e3479a31ad7b3ea5f249252116361f8965f4ee91`. Inspecionadas: `CheckTriggers` com direção da rolagem, gatilhos ordenados/contínuos, `AddTriggers`, `RemoveTriggers`, `TargetScroll` e cancelamento de deslocamento programático quando usuário interage.
- `js/app/section.js`, Git blob SHA-1 `6981d4e9d5b52540f45a54422b1fae533fe3c2f0`. Entrar/sair adiciona/remove atualização da seção; ativação/desativação altera triggers. Ao desativar, gatilhos persistentes podem ser reinicializados para o scroll reverso.
- `js/main.js`, Git blob SHA-1 `e6e436ef887a67efd27453a46cfde01874074f7f`. Acompanha deltas entre frames, filtra grandes picos isolados e estabelece modo de baixo desempenho, com possibilidade de retorno manual.
- Fontes legadas incluem jQuery, Stellar, TweenMax, SoundManager2, RequireJS e Flash. **Não importar essa pilha de 2012** para a WAVE moderna. Em vez de copiar código, reimplementamos o comportamento útil com JS nativo e CSS.

O licenciamento MIT refere-se ao código do repositório NASA. **Não concede licença dos fonogramas e obras de terceiros**: o site discrimina músicas com seus titulares. Nenhuma imagem, som ou script do projeto foi incorporado.

### Ponpon Mania, diretamente dos criadores

[Artigo técnico em Codrops](https://tympanus.net/codrops/2025/10/07/ponpon-mania-how-webgl-and-gsap-bring-a-comic-sheeps-dream-to-life/): fluxo Photoshop/Illustrator → imagens por camada → atlas → textura compactada GPU → planos OGL WebGL → GSAP ScrollTrigger → custom shader `mix` de duas cenas. Esse pipeline de produção exige artes separadas desde a origem. **Um PNG achatado movendo-se em tela não substitui as camadas.**

Na WAVE, a câmera já se move entre MPC, ruptura da névoa e hub original; o futuro atlas da própria arte exige teste de consumo de GPU e preservação da qualidade do pincel. O texto público permite estudar o conceito; os [termos de Ponpon Mania](https://ponpon-mania.com/legal) não autorizam duplicar seus assets.

### O que foi construído agora na travessia Hazewave

A pesquisa desta rodada produziu mudanças funcionais dentro de `apps/hazewave-site/experiments/travessia-v4`, sem modificar `public/`:

1. **Cinco pontos reais de navegação:** botões de ato `01–05` acessíveis por teclado e toque. Cada destino se converte em `scrollTop` calculado pelo tamanho real da jornada. Os estados de peças, luz, câmera e portal continuam usando o mesmo progresso; não existe imagem de outro site na UI.
2. **Volta reversível:** o botão do ato 1 leva ao progresso `0`, não apenas a um capítulo anterior. A seleção `aria-current="step"` acompanha a rolagem normal e por clique.
3. **Compositor adaptativo:** o modo leve remove exclusivamente sombras de GPU e superfícies de brilho decorativas; nenhum pad, câmera ou região pintada é descartado. Uma sequência de cinco frames amostrados acima de 44 ms reduz efeitos; picos únicos e pausas longas não bastam.
4. **Teste independente real:** navegador Chromium com 46 imagens originais decodificadas, 393×852, 360×800 e 1280×800; sequência `0→1→2→3→4→2→0`; sem erro JS nem overflow; portal volta a raio 0% e hub aparece no último ato. O teste de CI com imagem sintética não substitui essa prova de arte real.
5. **Sem autoridade nova:** `productionApproved=false`; não há autoplay de som, scraping, extensões com privilégios, alterações de Codespace, configuração de agentes ou upload de arte à GitHub.

## Limites técnicos que permanecem

Nenhum dos **seis sites proprietários** foi executado diretamente num Chromium com tráfego de rede por este agente: o contêiner local não resolve esses domínios. A consulta foi feita a páginas públicas e fontes dos criadores. NASA recebeu inspeção direta de código-fonte público via GitHub. **Não há prova de equivalência binária, performance dos sites originais ou engenharia reversa completa dos seis.**

As animações V4 são 2.5D e precisam de revisão visual humana; a nova navegação e o modo leve não concluem a direção cinematográfica ou a integração final. Uma avaliação em 360/393 móveis com as imagens canônicas é evidência de browser em contêiner, **não** do A15.

Próximas disciplinas: atlas original sem perda da arte, fallback sem WebGL, áudio só após interação, medição de memória da GPU e transição contínua de câmera sem popping. A reprodução dinâmica dos seis alvos externos requer uma sessão de navegador autorizado com permissão do destino e isolamento de rede do sistema, que não deve baixar bundles privados, burlar proteções ou reutilizar conteúdo proprietário.

## Referências verificáveis

- [NASA Prospect — página](https://nasaprospect.com/) e [código MIT](https://github.com/collinhover/nasaprospect)
- [Ponpon Mania — relato técnico dos próprios autores](https://tympanus.net/codrops/2025/10/07/ponpon-mania-how-webgl-and-gsap-bring-a-comic-sheeps-dream-to-life/)
- [REB8T — bastidores de Who's Guilty](https://www.linkedin.com/posts/rebooot_who-is-guilty-a-project-we-launched-to-activity-7449810975068712960-5gNf)
- [Columbia Journalism Review — entrevista NYT Tomato Can Blues](https://www.cjr.org/behind_the_news/qa_andrew_kueneman_and_steve_d.php)
- [SBS Learn — A refugee story: The Boat](https://www.sbs.com.au/learn/resources/a-refugee-story-the-boat/)
- [Genie Studio](https://geniestudio.app/) e [apresentação de design](https://dribbble.com/shots/26612978-Unveiling-the-New-Genie-Website)
- [Esimple — história em Web3D](https://www.esimple.it/)

Machine-readable confidence/rights ledger: `knowledge/wave-seven-site-forensics-v5.json`. Documento de pesquisa, **não** outra autoridade concorrente do Harness.
