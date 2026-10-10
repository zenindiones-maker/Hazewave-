# HAZEWAVE — WAVE TRAVESSIA V4 · engenharia reversa causal

**Status:** primeira travessia original executável, **exclusivamente privada / não aprovada**. Não é uma página da homepage, não publica conteúdo e não altera `main` ou o Codespace.

## Por que V3A e V1 não bastavam

A V3A de referência (Actions head `8c6d06335af6733ecdaa048a42d64ed360d60e2f`) contém 12 pads, 8 knobs e quatro cones móveis, mas sua câmera permanece no mesmo palco. O vídeo anterior V1 tinha somente nove pads; jamais utilizá-lo para atestar V3A ou V4.

## Engenharia implementada, medida em browser

`index.html` + `travessia.css` + `travessia.js`: uma única jornada de rolagem nativa, **780svh**, com **cinco atos e geometrias diferentes**, sem crossfade puro nem pôster único.

| Ato | Transformação causal observável | Gate técnico |
| --- | --- | --- |
| 01 Cosmologia | Original cosmic fog + profundidade e entrada de máquina à distância | Estrelas/névoa reais, câmera em perspectiva |
| 02 Traço | Dois `SVGPathElement` com comprimentos reais e dashoffset variável | Progressão efetiva de 0 a 1, reversible |
| 03 Máquina | 24 texturas V3A originais, pad pressionado, knob girado, membrana deformada, câmera cruzando máquina e chassi separado por `clip-path` | 12/8/4; split medido em px; close-up REAL |
| 04 Ruptura | Névoa pintada em três planos e duas folhas, afastadas pela própria onda; porta circular recortando metrópole ilustrada ORIGINAL | Portal cresce de raio 0% a 69%; separação horizontal maior que 1.5× viewport |
| 05 Destino | Câmera entra na metrópole e chega ao hub original Indionesbala | Segunda região representada por arte diferente e DOM independente |

Tudo depende de **um único** `scroll progress p ∈ [0,1]` (funções monotônicas `smoothstep`), incluindo sobreposição, profundidade, cortes de chassis, máscaras, rastro da onda, pads, knob, alto-falantes e posição da câmera. O retorno até p=0 restaura todos os estados. O experimento não bloqueia o scroll nativo nem baixa scripts de terceiros. Suporta redução de movimento porque as cenas dependem do scroll, não de autoplay.

### Proveniência de arte imutável

Cinco imagens **exatas** da Biblioteca privada, confrontadas por SHA-256 com o manifesto aprovado, mais 24 sprites artísticos V3A reconstruídos do ZIP oficial do [GitHub Actions 37996866861](https://github.com/zenindiones-maker/Hazewave-/actions/runs/37996866861). Arquivo ZIP original SHA-256 **`5cff7ae24fc0461dbaa70827d8a16b21b0a3bade792a16c37c1d705e2c871de4`**. Entrada V3A da prova SHA `8c6d06335af6733ecdaa048a42d64ed360d60e2f`.

**Nenhum arquivo artístico privado foi inserido em GitHub, `public/`, Actions ou assets de produção.** Estes scripts contém apenas fonte e provas de proveniência.

### Reconstruir no ambiente autorizado (não no A15)

Primeiro, verificar a identidade remota do **Codespace existente** e usar um worktree destacado; jamais criar outro ou subir a máquina. O operador precisa materializar o pacote de imagens originais da Biblioteca, e obter o ZIP exato do Actions anterior por canal autenticado. Reutilizar apenas bibliotecas já autorizadas. Parar, sem instalar automaticamente, se faltarem Pillow ou Chromium.

```bash
python build_assets.py \
  --approved-art-root /private/APPROVED_ILLUSTRATED_LAYERS \
  --v3a-actions-zip /private/v3a-site-static-exact.zip \
  --output /private/new-wave-v4-media

python build_standalone.py \
  --source . \
  --media /private/new-wave-v4-media \
  --output /private/HAZEWAVE_TRAVESSIA_V4_ABRIR.html
```

Abrir o HTML localmente em browser isolado. Os códigos do GitHub não funcionam visualmente sem os pixels privados materializados. **Isso é intencional; nenhum fallback falso é autorizado.** O próprio arquivo autocontido completo e vídeo foram preservados na Biblioteca privada `/Hazewave/Living-Universe/V4-TRAVESSIA-ENGENHARIA/`.

### Provas reais já executadas fora do Codespace

Chromium headless real, URLs externas bloqueadas e 43 texturas SHA-bound. Script independente `browser_verify_manual.py`. 11 poses de ida e volta em cada viewport:

| Viewport | Δ RGB médio máquina vs início | Δ RGB portal vs máquina | Δ RGB destino vs portal | Δ RGB reset vs início |
| --- | ---: | ---: | ---: | ---: |
| 393×852 | 54.019 | 42.812 | 33.734 | 0.462 |
| 360×800 | 53.079 | 42.276 | 33.192 | 0.000 |
| 1280×800 | 58.257 | 43.831 | 36.718 | 0.019 |

Estas são diferenças de **frames realmente renderizados**, não estimativas. Vídeo real do browser: 12,72 s, H.264 a 25 fps, **viewport 393×852 / codificação 392×852** (alinhamento do encoder), SHA-256 `38601f2225c2ef1404cd26010c024afd606fd7b362701ab290ba5ec021ba8c5d`. Arquivos e recibos completos estão no **ZIP privado**, não no repositório.

### Pesquisa reversa legítima

- [Autores de Ponpon Mania](https://tympanus.net/codrops/2025/10/07/ponpon-mania-how-webgl-and-gsap-bring-a-comic-sheeps-dream-to-life/): técnicas de separar planos de ilustração, atlas GPU e sincronização GSAP / câmera por scroll. Aplicamos **a técnica**, não suas imagens ou código.
- [GSAP ScrollTrigger](https://gsap.com/docs/v3/Plugins/ScrollTrigger/): progressivo `scrub`, pin nativo e travessia reversible.
- [MDN Scroll-driven animation timelines](https://developer.mozilla.org/en-US/docs/Web/CSS/Guides/Scroll-driven_animations/Timelines): progresso acoplado ao movimento de scroll, com atenção a performance e acessibilidade.

O projeto **não** afirma ter inspecionado bundles privados de terceiros nem feito engenharia reversa completa de todos os sete sites externos.

### Gates ainda fechados

- Revisão humana de continuidade, composição, cortes de máscara, tipografia, legibilidade e ritmo: **PENDING / NOT APPROVED**.
- Execução na worktree real do Codespace e sessão MCP dos agentes: **NOT PROVEN**.
- Benchmark nativo de GPU/termal em Android A15: **NOT EXECUTED** (A15 deve continuar somente como controle).
- Otimização de sprites e adesão ao site completo, cinco mundos de artistas, áudio acessível: **INCOMPLETE**.
- Promoção para `apps/hazewave-site/public/`, `main`, GitHub Pages, domínio público ou publicação: **FORBIDDEN without owner approval**.

**Owner's original resources remain immutable. V4 is a genuine experimental traversal but not a professionally accepted site.**

## Integração executada em um build Astro real (somente cópia privada)

A integração não é mais apenas um HTML independente: `integrate_private_astro.py` recompôs **78 arquivos** em um diretório de prévia privada, partindo do ZIP de build exato `5cff7ae24fc0461dbaa70827d8a16b21b0a3bade792a16c37c1d705e2c871de4`. A saída preserva `artists/indionesbala/index.html`, contém `/experimental/travessia-v4/index.html`, 43 texturas originais derivadas, a folha CSS, motor JS e manifesto, e coloca um link de entrada na **cópia** da homepage. O site de origem não foi escrito, implantado ou publicado.

Com a árvore de mídia privada já reconstruída, execute:

```bash
python integrate_private_astro.py \\
  --astro-dist-zip /private/v3a-site-static-exact.zip \\
  --engine . \\
  --private-media /private/new-wave-v4-media \\
  --output /private/new-wave-v4-astro-preview
```

O pacote executado é `HAZEWAVE_V4_PRIVATE_ASTRO_INTEGRATED_SITE.zip` na Biblioteca privada `/Hazewave/Living-Universe/V4-TRAVESSIA-ENGENHARIA/`. É preciso abri-lo **somente em localhost dentro do Codespace autorizado ou ambiente de revisão equivalente**, jamais em host público. Não há upload automático de arte para Git ou infra paga. `productionApproved=false` e `codespaceHostAttested=false` permanecem.

## V11 isolated remediation: five approved artworks, scroll-painted causal motion

Previously the V4 private manifest tracked all five owner-approved paintings,
but the DOM did not render **A01 station** or **A02 controller** at all.
V11 inserts four spatially clipped owner-art plates (two rest/charged pairs)
that move with the 12-pad, 8-knob, four-speaker V3A rig. A02 is exposed using
the moving signal's scroll-dependent gradient matte. A05 fog source halves
also separate *and change contours* as the wave crosses. A03 city and A04
Indionesbala hub remain independent existing illustrated regions.
The end now preserves the destination while revealing a dominant HAZEWAVE
wordmark and subordinate Indionesbala signature. Visible numeric prototype HUD
has been reduced to decorative stage dots; semantic act navigation survives.

The exact-hash private art build still requires `build_assets.py` inputs;
we do not commit PRIVATE_MEDIA to GitHub or claim the synthetic CI test shows
owner pixels. The tests remain explicitly synthetic, and artistic approval,
independent mobile review, and private-site publication remain PENDING.

Research: https://tympanus.net/codrops/2025/10/07/ponpon-mania-how-webgl-and-gsap-bring-a-comic-sheeps-dream-to-life/
and https://gsap.com/docs/v3/Plugins/ScrollTrigger/ and
https://developer.mozilla.org/en-US/docs/Web/SVG/Reference/Attribute/stroke-dashoffset
are relevant to the multi-plane editorial animation technique.
Existing verified first-party EffectCraft/FilmCraft remain optional FX tools,
not their own creative authority, and no Adobe license bypass is involved.
