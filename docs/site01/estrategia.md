# SITE 01 — MODO CRÍTICO 10/10: estratégia (antes de qualquer código de produção)

Data: 11/10/2026 · Branch: `work/wave-site01-critico-v1` (criada a partir da branch da PR #72) · **Nada publicado.**
Escopo (ordem do Luiz): só **Hazewave + Indionesbala** (artista de teste). Os outros quatro artistas saíram do plano e do protótipo.
Regra de corte: só conta como referência válida o que for **desenho gerado literalmente pelo scroll** (o scroll é o pincel). Ilustração estática com parallax/fade não conta.

Evidência bruta (no box): `/workspace/site01/forensics/` (JSON de rede/DOM por site, bundles JS baixados, screenshots com wheel), `/workspace/site01/lh/` (Lighthouse mobile).

---

## 1. Autocrítica brutal

### PR #78 (site Hazewave v1, estático)
- O "scrollytelling" são **4 curvas genéricas** com `stroke-dashoffset`: nenhuma arte do Indionesbala é desenhada. É decoração, não narrativa. Nota contra os benchmarks: **2/10**.
- Ela passou no Lighthouse porque não faz quase nada. Uma nota 100 num site vazio não prova nada.
- Pôs cinco artistas, sendo que o Luiz agora quer só o Indionesbala. Os cards eram imagens estáticas, e o logo do Indionesbala aparecia **cortado** (o recorte quadrado comia as laterais).
- Os testes ficaram fracos: verificavam se "o número subiu", não a qualidade visual nem a sincronia com o traço.

### PR #72 (SITE 01 "o scroll é o pincel")
- A direção estava certa: os traços são SVG reais, o scrub é reversível e o reduced-motion mantém o desenho.
- Mas os **16 caminhos Bézier foram escritos pelo agente**. A própria PR admite: "não são strokes do artista". O pincel é nosso, não do Indionesbala.
- Ela depende de GSAP/ScrollTrigger, que **não é open source OSI** (ver §5), e de Astro, que é pesado para o que precisa ser.
- As 5 pinturas "originais" continuam **fora do repositório**. O site público não pode usar o que não está publicado.
- Ficou sem revisão no A15 real e sem medida de FPS sob throttling.

### PR #66 (forense de 7 sites)
- Admitia: "nenhum dos seis sites proprietários foi executado num Chromium" e "Genie: JS não analisado". **Agora foi.** As contradições estão na §3.

---

## 2. Dissecação dos 7 sites (Playwright headless + bundles baixados com curl + Lighthouse mobile, 11/10/2026)

| Site | Stack detectada (evidência) | É desenho gerado pelo scroll? | Técnica NZZ | Peso / LH mobile |
|---|---|---|---|---|
| **NASA Prospect** (nasaprospect.com, vivo) | jQuery + RequireJS + TweenMax + **Stellar.js** (parallax); compila **~60 arquivos .less no navegador** (XHR); SoundManager2; 280 imgs, **0 SVG, 0 canvas**. Long task de **16 s** no load (compilação Less) | **NÃO.** O scroll dispara gatilhos (o astronauta troca de pose/fade e o fundo muda de planeta) que tocam tweens por tempo | show-and-play + animated transition | 0,91 MB · perf **0,17**, LCP 12,7 s |
| **NYT Tomato Can Blues** (2013, vivo) | Prototype.js 1.7 + script.aculo.us + MMAMobile.js; **0 SVG, 0 canvas**; scroll nativo de 14.481 px; só 8 elementos com transform | **NÃO.** Ilustrações raster (Atilla Futaki) em painéis com parallax/fade | graphic sequence + pan (parallax) | 0,48 MB · perf **0,59** |
| **Who's Guilty** (promo.whoisguilty.com, vivo) | **GSAP + ScrollTrigger**, lottie-web (`loadAnimation`, `goToAndStop` ×28), **Lenis**, swup; HTML de **2,7 MB com 5.043 `<path>` inline** (traço de linha feito à mão); ~42 MP3 (4,9 MB) | **SIM, é o único caso puro.** Código: `tableTl = gsap.timeline({scrollTrigger:{trigger:pathFirst,start:"17% top",end:"72% bottom",scrub:true}})` e `z.forEach((Z,Q)=>tableTl.to(Z,{strokeDashoffset:0,duration:1},Q))`: cada path nasce em sequência, amarrado ao scroll. Já a fumaça (`smokeTls`) é loop por tempo, não scroll. **No celular em retrato o site bloqueia ("Please rotate your device").** | animated transition (scrub) + moviescroller (Lottie por frame) + show-and-play | 7,36 MB · perf **0,30**, TBT 2,4 s |
| **Ponpon Mania /about** (vivo) | Nuxt + **OGL (WebGL)** + GSAP + Lenis (scroll virtual: `scrollY` fica em 0); canvas 618×1372; 1,85 MB por fetch (texturas/atlas) | **NÃO é traço.** O único `strokeDashoffset` é o **preloader** (tween por tempo). O "flipbook" são planos/texturas WebGL movidos pela câmera ligada ao scroll | moviescroller + pan & zoom | 1,7 MB · perf **0,08**, TBT 8,6 s |
| **Genie Studio** (geniestudio.app, vivo) | GSAP ScrollTrigger (`pin:true, scrub:1`, end "120% top"), Lenis, **Rive** (runtime/wasm), 33 canvases, WebGL | **NÃO.** Pin + scrub de transformações e estados Rive; nenhum SVG com dasharray | animated transition + show-and-play | 1,85 MB · perf **0,48** |
| **eSimple** (esimple.it, vivo) | WordPress/Elementor, GSAP 3.14.1 + ScrollTrigger, three.js (`WebGLRenderer`), widget **typewriter do Elementor (por tempo)**, 4 ícones Lordicon (Lottie em hover/loop) | **NÃO.** A máquina de escrever é por tempo. O bundle tem código Lottie `bind_to_scroll` (frame = %viewport), mas **nenhum widget da página usa** | show-and-play | **31,6 MB** · perf **0,22**, TBT 10,2 s |
| **SBS The Boat** (sbs.com.au/theboat, vivo) | three.js + TweenMax + jQuery; "CLICK TO START"; painéis da HQ (Matt Huynh) giram/aproximam em 3D com o scroll; áudio e vídeo | **NÃO.** A arte pintada é estática; o scroll move a câmera e os painéis | pan & zoom + animated transition | 6,06 MB · perf **0,26**, TBT 9,7 s |

**Conclusão honesta:** dos 7, **só Who's Guilty gera o desenho com o scroll**. Os outros 6 são câmera, parallax, gatilhos ou animação por tempo. A descrição que chegou ao Luiz superestima NASA, NYT, Ponpon ("flipbook" é WebGL, não traço), eSimple (typewriter por tempo) e SBS. **Nenhum dos 7 passa num orçamento de A15** (perf entre 0,08 e 0,59).

### Contradições com a PR #66
- **Genie:** a #66 dizia "revelação no hover, JS não analisado". Na verdade é GSAP ScrollTrigger com pin+scrub, Rive e Lenis.
- **Who's Guilty:** a #66 citou "Lottie + código próprio". Confirmado, e falta o principal: **GSAP scrub em `strokeDashoffset` sobre SVG inline**, além de Lenis e swup, e o bloqueio em retrato.
- **eSimple:** "Web3D" confirmado (three.js), mas a #66 não registrou que o typewriter é por tempo.
- **Ponpon:** a pipeline WebGL citada pela #66 está confirmada; o `strokeDashoffset` é só o preloader.
- **Execução ao vivo:** a #66 disse que não havia execução ao vivo; agora houve, com rede real, no box.

---

## 3. Inventário de arte Hazewave / Indionesbala no repositório

| Arquivo | Formato real | Resolução | Vetorizável? |
|---|---|---|---|
| `apps/hazewave-site/public/media/artists/indionesbala.webp` | **JPEG com extensão .webp** (erro de extensão) | 1536×643 | **Sim, parcial**: letras chapadas em laranja. Pelo potrace saem **28 paths / 42 subcaminhos** (contornos, não linha central). Bom para nascer o contorno. |
| `apps/hazewave-site/public/media/worlds/indionesbala-v6.webp` | WebP | 1672×941 | **Não** (render pintado/fotográfico). Serve só como fundo para pan & zoom. |
| `apps/hazewave-site/public/media/hazewave-world.jpg` | JPEG | — | Não (fundo). |
| 5 pinturas citadas em `scripts/site01_owner_art_private_builder.py` | PNG | ? | **Fora do repo** (privadas). Não posso avaliar nem usar. |

**Falta crítica:** não há **nenhum desenho de traço à mão (line art) nem personagem** do Indionesbala no repo. Sem isso, o "scroll é o pincel" de verdade (nível Who's Guilty) é impossível: só dá para desenhar o contorno do logo.

---

## 4. Conceito
**"O traço acende a cidade."** O scroll é o pincel do Indionesbala:
1. o nome nasce traço por traço;
2. o personagem do artista atravessa a tela no ritmo do dedo;
3. a câmera percorre o mundo laranja até o hub (música, downloads, apoio).

Hazewave assina por cima, discreto. Sem HUD numérico (ordem da #72).

## 5. Narrativa por cenas (distâncias em viewport-heights, `vh`)
| # | Cena | Distância | O que o scroll faz | Técnica NZZ |
|---|---|---|---|---|
| 0 | Página em branco + "role" | 0–0,5 | nada | — |
| 1 | Nome INDIONESBALA nasce | 3 vh | 0–75%: contornos nascem da esquerda para a direita (overlap 2,5 paths); 75–95%: tinta preenche; 90–100%: textura raster entra | animated transition (scrub) |
| 2 | Personagem anda | 3 vh | x = t·(largura − personagem); 6 passadas por cena; bob vertical | moviescroller (ciclo de passada) |
| 3 | Pan pelo mundo | 4 vh | translateX de 0 a −(largura·zoom − viewport), zoom 1→1,18 | pan & zoom |
| 4 | Linhas da cidade | 3 vh | line art do artista nascendo sobre o fundo (**depende de desenho a fornecer**) | animated transition |
| 5 | Hub | — | música, downloads (em breve), apoie | show-and-play |
Total ≈ 13–14 vh (no A15, ≈ 12.000 px de scroll).

## 6. Arquitetura de cena
Cada cena é `<section style="height:N·100vh">` com um filho `position:sticky; top:0; height:100svh`. O progresso t = −rect.top / (rect.height − innerHeight), limitado a 0..1. É uma função pura de t, portanto **reversível por construção**. Um único listener de scroll passivo dispara um `requestAnimationFrame`, que escreve só `transform`, `opacity` e `stroke-dashoffset` (nada que cause relayout).

## 7. Sistema de animação e licenças
- **GSAP:** desde 2025 é gratuito, inclusive ScrollTrigger, DrawSVG e MorphSVG, sob a **"GSAP Standard License"**. Essa licença **não é OSI** e proíbe uso em ferramentas que concorram com a Webflow. Isso **viola a regra "open source" do Luiz**. Recomendo **não usar**.
- **Alternativas abertas:**
  - **motor próprio** (~3 KB, MIT; feito no protótipo): suficiente para scrub, pin e stroke;
  - **lottie-web (MIT)** com `goToAndStop(frame)` mapeado ao scroll (o mesmo que Who's Guilty e o Elementor fazem), para morphs de quadro-chave vindos do After Effects/Glaxnimate (aberto);
  - **Lenis (MIT)**, só se o scroll nativo do A15 mostrar tremor; hoje não precisa (o scroll nativo é mais acessível);
  - **Motion / `scroll()` (MIT)**: opcional, não necessário.
- **Recomendação:** motor próprio + lottie-web só para o ciclo do personagem quando houver quadros do artista. Nada de WebGL na v1, porque todos os sites WebGL medidos ficaram com perf ≤ 0,48.

## 8. Pipeline do traço à mão (Indionesbala)
1. O artista entrega o **line art em PNG ≥ 2000 px ou SVG**, de preferência em camadas: contorno, sombra, cor.
2. Binarizar e vetorizar: `potrace` (GPL, roda no CI, não vai para o site) para contorno; `vtracer` (MIT) para cor; **linha central** com `autotrace --centerline` ou skeletonize (scikit-image), para que o traço nasça como pincel e não como contorno duplo.
3. **Ordenação dos paths:** da esquerda para a direita, ou a ordem gravada do artista. O ideal é ele desenhar num app que exporte a ordem dos strokes (Krita/Inkscape guardam a ordem das camadas).
4. **Simplificar** (`svgo`) para no máximo ~1.500 paths por cena (Who's Guilty tem 5.043 num HTML de 2,7 MB: pesado demais).
5. **Wobble:** variar `stroke-width` por path (±15%) e um offset aleatório fixo, pré-calculado no build. Nada de `feTurbulence`/`feDisplacementMap` ao vivo, que é caro na GPU Mali do A15.
6. **Comprimento:** `getTotalLength()` uma vez no load; dasharray = L, dashoffset = L·(1−k).

## 9. Orçamento de performance (Samsung A15)
- JS ≤ 30 KB gz (protótipo: 2,8 KB); total da primeira carga ≤ 600 KB; imagens WebP ≤ 200 KB por cena, carregadas preguiçosamente fora da 1ª cena.
- ≤ 1.500 paths animados por cena; nunca animar filtros SVG.
- Metas: p95 do quadro ≤ 20 ms com CPU 4× throttled; 0 long tasks > 50 ms durante o scroll; LCP ≤ 2,5 s; CLS = 0; Lighthouse perf ≥ 0,9.
- Retrato **e** paisagem funcionando. Who's Guilty exige girar a tela, e nós não vamos exigir.

## 10. Reduced motion
`prefers-reduced-motion: reduce` deixa o traço completo, o personagem parado e o pan sem zoom. O conteúdo continua inteiro e legível (testado).

## 11. Protótipo-esqueleto (feito, não publicado): `apps/site01-critico/`
As 3 cenas pedidas pelo Luiz, com motor próprio:
1. o contorno do logo Indionesbala (potrace, 28 paths) nasce com o scroll e depois recebe a tinta;
2. um personagem **PROVISÓRIO** (boneco SVG marcado na tela, porque não existe desenho do artista) anda com o scroll;
3. pan & zoom do `indionesbala-v6`.

**Resultados (Playwright, CPU 4× throttled, headless sem GPU real):**
| Viewport | FPS médio | p95 quadro | quadros > 33 ms | long tasks | erros JS |
|---|---|---|---|---|---|
| 412×915 @2,625 (A15 CSS) | 60 | 16,7 ms | 0 | 0 | 0 |
| 1080×2340 @1 | 59,8 | 16,8 ms | 1 | 0 | 0 |
| 915×412 paisagem | 60 | 16,8 ms | 0 | 0 | 0 |

- **Scrub:** progresso monotônico em 14 posições. O **retrocesso** em t≈0,24 volta a deixar 11/28 paths não desenhados, ou seja, é reversível.
- **Reduced motion:** traço completo. ✔
- **Lighthouse mobile:** perf 0,99, a11y 1,0, LCP 2,3 s, TBT 0 ms, CLS 0, 236 KB. O SEO 0,54 vem do `noindex` intencional.
- **Ressalva:** o headless não tem a GPU Mali do A15. Os números são um teto otimista e falta prova no aparelho.

**Nota brutal do protótipo contra os 7 benchmarks (0–10):**
| Critério | Nota | Por quê |
|---|---|---|
| Traço gerado pelo scroll (ref.: Who's Guilty) | **4** | O mecanismo é igual ao deles (scrub em dashoffset sequencial), mas desenha **contorno de letreiro**, não line art à mão. Sem desenho do artista, o teto é 5. |
| Personagem / quadros (ref.: Ponpon, NASA) | **2** | Boneco provisório com rotação de membros. Sem quadros reais do artista. |
| Pan & zoom (ref.: SBS, NYT) | **5** | Funciona e é reversível, mas é uma camada só, sem profundidade nem multiplano. |
| Transições entre cenas (ref.: Genie, Who's Guilty) | **3** | As cenas cortam seco; entre a 1 e a 2 as duas legendas se sobrepõem por um instante. |
| Som (ref.: NASA, SBS, Who's Guilty) | **0** | Ainda não há. |
| Performance A15 | **9** | Muito acima de todos os 7 (perf 0,99 contra 0,08–0,59). |
| Acessibilidade / retrato | **9** | Retrato e paisagem funcionam, reduced-motion ok. Who's Guilty bloqueia em retrato. |
| **Média** | **≈4,6/10** | Ainda **não é** 10/10. O gargalo é arte, não código. |

## 12. Plano de implementação e critérios de aceite
- **F0 — Arte (Luiz/artista):** line art + personagem em quadros (8–12 por passada) + fundo em camadas (frente, meio, fundo). *Aceite:* arquivos no repo com permissão de publicação.
- **F1 — Pipeline de traço:** linha central, ordenação, wobble, svgo no CI. *Aceite:* ≤ 1.500 paths por cena; a ordem bate com o desenho; diff visual aprovado.
- **F2 — Cenas 1–3 com arte real:** *Aceite:* critério 1 ≥ 8 (traço do artista nasce reversível), critério 2 ≥ 7 (quadros reais), critério 3 ≥ 7 (≥ 3 planos).
- **F3 — Transições + cena 4 + hub:** *Aceite:* sem cortes secos; legendas nunca se sobrepõem (teste automático de interseção).
- **F4 — Som opcional** (só depois de toque, como SBS e NASA): *Aceite:* nada toca sozinho; botão visível.
- **F5 — Prova no A15 real:** Chrome remote debugging, trace de performance. *Aceite:* p95 ≤ 20 ms, sem long task > 50 ms.
- **F6 — CI:** HTML-validate, links, LHCI (perf ≥ 0,9), Playwright scrub com screenshots em 412×915, 1080×2340 e 915×412. *Aceite:* todos verdes.
- **Publicação:** somente com aprovação explícita do Luiz.

## 13. O que falta do Luiz
1. **Line art do Indionesbala** (PNG ≥ 2000 px ou SVG), de preferência na ordem em que ele desenha.
2. **Personagem:** o desenho e, se possível, os quadros de uma passada (8–12), ou autorização para animar por partes (cabeça, tronco, braços, pernas separados).
3. **Fundo em camadas** (frente, meio, fundo) ou autorização para usar `indionesbala-v6` como está.
4. Liberação de uma das 5 pinturas privadas, se quiser que entrem no site público.
5. Uma faixa de áudio do Indionesbala para a cena (opcional), com permissão.
6. Decidir se aceita lottie-web (MIT) para o personagem.

---

# ATUALIZAÇÃO (11/10, 12h50 PT): universo das ilhas-MPC — cada ilha é um artista

## A. Inventário rápido (a busca exaustiva foi interrompida por ordem nova)
- **Repo, branches de site** (`work/wave-v12…`, `work/hazewave-site-v1`): logo Indionesbala (raster 1536×643), `indionesbala-v6` (render 1672×941), mundos dos outros artistas (fora do escopo). **Não há line art nem personagem.** Na branch da PR #62 (`work/wave-canonical-art-rig-pilot-v1`), `git ls-tree` **não lista nenhum PNG/WEBP/JPG/SVG**: as "dez peças MPC pintadas" não estão versionadas (consistente com a regra "arte privada fora do GitHub"). A varredura de todas as 111 branches, LFS, releases e artifacts ficou **incompleta** (parada por ordem).
- **Google Drive** (conector): "Áudio de indionesbala" (MP3, 2,7 MB, 22/09/2026) e "hazewave_final-2.mp4" (200 MB, 16/04/2026). Ambos privados e não lidos. Nenhuma imagem Indionesbala encontrada por nome.
- **Codespace:** não inspecionado (ordem de parar a busca).
- **Referências enviadas pelo Luiz** (6 PNG, `/workspace/site01/refs/`, **privadas, fora do git**):

| Arquivo (prefixo) | Resolução | Conteúdo | Uso |
|---|---|---|---|
| 460eaf | 1448×1086 RGBA (fundo transparente) | ilha-MPC com caixas de som, cabos roxos, pads laranja | **ilha-herói Indionesbala** (camada de cor e fonte da line art) |
| 4d1cdc | 1448×1086 RGBA | ilha-MPC apagada/escura | **ilha bloqueada** (template "ILHA LIVRE") |
| 9f8619 | 1672×941 RGBA | arquipélago com feixes azuis e estrada roxa | plano médio (futuro) |
| b40285 | 941×1672 | vertical: céu, galáxia, logo HAZEWAVE, cidade ao fundo | plano céu/longe (futuro) |
| e5d1f0 | 1536×1024 RGBA | MPC com motores (versão "nave") | variação de ilha (futuro) |
| ff50ca | 941×1672 | vertical: logo, estrada de onda serpenteando até a MPC grande | **mundo/estrada da cena 1** |

Todas são **raster pixel-art-ish com cor**: não existe versão em traço (ink). A line art atual é **derivada** por detecção de bordas + potrace (611 paths). Ela não é traço de artista: os contornos saem duplos, as bordas são ruidosas e a ordem é de cima para baixo, não a de um desenhista.

## B. Pipeline de arte (o que precisa ser produzido)
O gerador de imagens **não está disponível neste executor**: o pai deve gerar ou encomendar. Para cada objeto-chave, em 3 versões alinhadas pixel a pixel (mesmo enquadramento):
1. **INK:** só o traço preto ou creme, linha central, espessura 2–4 px a 2000 px, fundo transparente. Vetoriza limpo com `autotrace --centerline` e vira stroke animável.
2. **COR** chapada, sem neon.
3. **NEON/LUZ** (pads laranja, cabos roxos, feixes azuis) como camada aditiva separada.

Objetos:
- ilha-MPC do artista (herói), com caixas, cabos e pads;
- ilha bloqueada genérica;
- estrada de onda roxa como path vetorial puro (desenhada direto em SVG, não rasterizada);
- caixas de som, cabos de frente e feixes de propulsão como sprites separados;
- planos: céu com galáxia e logo, ilhas distantes, ilhas médias, ilha-herói, cabos em primeiro plano;
- a cidade Indionesbala ao longe (destino da estrada).

Mais detalhe que as referências (mínimo exigido): resolução 2× (≥ 2000 px no lado maior), mais componentes de MPC (faders, knobs, telas), fiação com rotas e vida na cidade.
**Prompt-base sugerido:** "isometric floating MPC drum-machine island, speakers, purple glowing cables, orange neon pads, blue thruster beams, dark navy metal, detailed pixel-art-inspired illustration, transparent background, [INK ONLY: clean black centerline line art, no fill, no shading]".

## C. Arquitetura de cena (substitui a §5/§6 da versão anterior)
**Modelo de dados reutilizável:** `apps/site01-critico/islands.json` (schema `HazewaveIsland/v1`):
- `world` {image, width, height, road (path SVG da estrada no espaço da imagem)}
- `islands[]` {id, status: active|locked, name, roadT (posição 0..1 na estrada), colors {neon, energy, ink}, layers {line, color, width, height}, clips[], music[]}

Ilhas `locked` não têm nome: aparecem apagadas como "ILHA LIVRE". Nenhum artista foi inventado.

| Cena | Distância | Scroll faz |
|---|---|---|
| 1. Estrada | 7 vh | A câmera parte do logo HAZEWAVE e **segue a ponta da estrada roxa que o scroll vai desenhando** (stroke + brilho). As ilhas livres surgem apagadas quando a estrada passa por elas. |
| 2. Ilha do artista | 5 vh | 0–55%: line art da ilha nasce (611 traços, overlap 8%); 50–75%: a cor entra apagada; 72–85%: o neon acende (saturação/brilho); 82–95%: cartão com nome, clipes e música (PROVISÓRIO). |
| Futuro | — | A transição contínua estrada→ilha (zoom da câmera na ilha, sem corte), parallax com 5 planos e a cidade Indionesbala no fim. |

Adicionar um artista = uma entrada no JSON + 3 camadas de arte. O código não muda.

## D. Protótipo v2 (privado, não publicado)
`apps/site01-critico/` (o v1 foi para `v1/`). As camadas privadas ficam em `private-media/`, que está **no .gitignore**: só código e config vão para o git. **Sem as refs do Luiz o protótipo não renderiza a arte.**

**Resultados (Playwright, CPU 4× throttled):**
| Viewport | FPS médio | p95 | quadros > 33 ms | long tasks |
|---|---|---|---|---|
| 412×915 @2,625 | 60 | 16,7 ms | 0 | 0 |
| 1080×2340 @1 | 50,8 | **33,4 ms** | **10** | 0 |
| 915×412 | 58,1 | 16,8 ms | 3 | 0 |

- **Reversível:** voltando para t=0,75, 137 de 611 traços ficam não desenhados.
- **Reduced motion:** tudo desenhado. ✔
- **Ponto fraco:** o viewport 1080×2340 @1 tem jank. A imagem do mundo escalada fica com ~2370 px de largura e há blur no brilho da estrada. Remédio: brilho pré-renderizado em vez de `filter:blur`, e mundo em tiles.

**Nota brutal v2 (0–10) contra os 7 benchmarks:**
| Critério | v1 | v2 | Por quê |
|---|---|---|---|
| Traço gerado pelo scroll (Who's Guilty) | 4 | **6** | A estrada é desenhada pelo scroll e guia a câmera, e a ilha nasce em traço antes da cor. Mas a line art é derivada por bordas (contorno duplo e ruidoso), não ink de artista. Teto atual: 6. |
| Revelação de cor/luz | — | **6** | Traço → cor apagada → neon acende funciona, mas é um crossfade da imagem inteira, não por camada (pads, cabos e feixes separados). |
| Personagem/quadros (Ponpon, NASA) | 2 | **1** | Removido: o universo agora é de ilhas. Falta definir se haverá personagem. |
| Pan & zoom / profundidade (SBS, NYT) | 5 | **6** | A câmera segue a estrada pelo mundo vertical, mas é um plano só, sem parallax real. |
| Transições (Genie, Who's Guilty) | 3 | **3** | Corte seco estrada→ilha, e o cartão do fim se sobrepõe ao rodapé. |
| Som | 0 | **0** | Há um áudio do Indionesbala no Drive, ainda não usado (precisa de permissão e de toque do usuário). |
| Performance A15 | 9 | **8** | Jank no 1080×2340 @1. |
| Acessibilidade/retrato | 9 | **8** | Retrato ok e reduced-motion ok. As ilhas livres ainda não têm alternativa textual na lista. |
| Template reutilizável | — | **8** | Uma ilha por artista via JSON. Ilhas livres sem nomes inventados. |
| **Média** | 4,6 | **≈5,1/10** | A arte INK, as camadas de luz e os planos de parallax são o que falta para passar de 8. |

## E. Próximos passos
1. Gerar ou encomendar as versões INK/COR/NEON da ilha-herói, da ilha bloqueada e dos 5 planos (§B).
2. Estrada como SVG autoral alinhada à arte nova (não traçada sobre raster).
3. Zoom contínuo estrada→ilha, sem corte.
4. Brilho pré-renderizado, tiles no mundo e meta p95 ≤ 20 ms no 1080×2340.
5. Som opcional após toque, com o áudio do Indionesbala se autorizado.
