# HAZEWAVE — revisão criativa e engenharia V6

Documento de avaliação do site WAVE. Não altera política normativa do Harness e não equivale a aprovação do owner, certificação de acessibilidade ou autorização de produção.

## Identificação e escopo

- Repositório: zenindiones-maker/Hazewave-.
- Branch candidato: work/wave-cinematic-worlds-v6.
- Base: 59e7b34db8328c715b800a72ebbeacfd4e3a2471.
- REAL_HEAD e CANDIDATE_SHA: definidos no comprovante externo de entrega, evitando um SHA autorreferente dentro do próprio commit.
- Capability: WAVE / site, composição visual, arte ambiental, interação e validação; adapter de áudio respeita catálogo autorizado existente.
- Promoção canônica/publicação: NÃO TENTADA. Branches históricos e arte original preservados; sem reset ou force-push.
- Estado: candidato em validação. A rejeição da V3 continua no histórico; a V6 não é aprovada por herança de testes técnicos.

## Problema e reconstrução

A V3 era visualmente um pôster com sinais, com três artistas tratados como variantes do mesmo palco. A V6 amplia o campo Hazewave, conecta os cinco mundos em percurso nativo reversível e reconstrói cenografia específica. A composição deve ser julgada pela captura e interação reais: mais código, novas imagens ou testes verdes não provam qualidade artística.

A origem é uma reinterpretação ambiental ampliada: amostra o cromatismo do vórtice canônico no shader e reutiliza seu lettering; não é a composição original inteira convertida em geometria3D. A presença do farol/vórtice conecta a extensão ao cânone. A arte original não foi apagada nem reclassificada como fixture. Letterings dos artistas são compostos no DOM a partir dos mesmos arquivos do owner, com máscaras SVG. Isso reutiliza a fonte de pixels do lettering original; as máscaras não demonstram recorte alfa pixel a pixel idêntico ao contorno original. Não chamar o método de fonte vetorial reconstruída.

## Arquitetura e percurso

Astro serve HTML semântico e TypeScript aprimora a experiência. O caminho gráfico ativo é raw WebGL2. Three.js e GSAP permanecem disponíveis no projeto, mas não são o renderer/timeline ativos desta entrada. Shader amostra imagens e aplica materiais, atmosfera e transição; não alegar geometria3D/câmeraThree onde existem apenas composição e deslocamento de textura.

O scroll nativo está disponível na origem. Percurso de cinco capítulos: **Baazü → Barak Ozama Beats → Indionesbala → Aquaverno → Hemorragia Cósmica**. A pista tem650svh. Pares de cenas definidos pelo capítulo são passados a scrubBetween; cada capítulo reserva68% para travessia e32% para permanência. O progresso determina o estado, permitindo avançar, parar e retornar sem uma timeline temporal concorrente. Busca, sinais e URLs diretas continuam disponíveis. O capítulo inicial e a seleção explícita não devem ser confundidos com uma obrigação de percorrer a sequência inteira.

Interrupções de transição conservam composição por snapshot de framebuffer. A inicialização compartilha promessa de decode; ao retomar movimento, carrega o destino atual e verifica preferência, contexto e disposal. Context loss mantém fallback; pagehide limpa listeners/recursos e BFCache persistido recarrega o documento. Estes mecanismos precisam de regressões, sobretudo com imagens lentas e entradas concorrentes.

## Autoridade artística, factual e musical

Seis ambientes conceituais foram criados com image_gen para este candidato, seguindo a autorização de reconstrução artística. São cenografia, não documentos de biografia, lore, lançamentos, eventos ou catálogo musical. O manifesto world-art-provenance-v6.json identifica fonte gerada, SHA256, dimensões e encoding. Originais e owner-art-provenance.json continuam preservados.

| Ambiente | WebP bytes |
|---|---:|
| Hazewave | 274984 |
| Baazü | 326688 |
| Barak Ozama Beats | 322726 |
| Indionesbala | 338590 |
| Aquaverno | 388392 |
| Hemorragia Cósmica | 427090 |
| Total confirmado em disco e manifesto | **2078470** |

Arquivos ambientais:1672×941, WebP qualidade88. Transferência de todos os ambientes não é a memória gráfica total e não representa necessariamente carga inicial. Os assets canônicos não foram deletados. Demo artists não têm autoridade visual na nova entrada.

O catálogo autorizado está vazio. Nenhum status de produção de faixa foi inferido; a superfície informa áudio indisponível. Controles de reprodução permanecem disabled e o transport apresenta indisponibilidade real. O adapter implementa contratos/controles convencionais para futuras fontes autorizadas; isso não demonstra reprodução pública de música real hoje. Nenhuma faixa, voz ou sucesso de playback foi inventado.

## Critérios criativos — dez dimensões

Avaliação independente final e notas: **PENDENTES**. Não inserir90/100, aprovação automática ou prêmio presumido.

| Critério | Evidência exigida |
|---|---|
| 01 — ART DIRECTION | Composição original, coesa e profissional |
| 02 — FIRST IMPRESSION | Identidade memorável nos primeiros segundos |
| 03 — VISUAL STORYTELLING | Progressão e transformação compreensíveis |
| 04 — MOTION QUALITY | Ritmo, continuidade, timing e materiais intencionais |
| 05 — WORLD COHERENCE | Origem Hazewave conecta mundos convincentemente |
| 06 — ARTIST EXPRESSION | Lettering original e mundos reais materialmente distintos |
| 07 — INTERACTION DESIGN | Descoberta causal, exploração responsiva e acesso direto |
| 08 — MOBILE EXPERIENCE | Composição, gestos, alvos e reduced motion deliberados |
| 09 — TECHNICAL EXECUTION | Cadência, lifecycle, navegação e fallback confiáveis |
| 10 — ORIGINALITY | Linguagem própria, sem template ou cópia de referência |

Um blocker em identidade, continuidade, acesso ou autoridade reprova a entrega mesmo com média numérica alta. Screenshots não provam toda a interação; gravações devem ser da aplicação real. Critério09 não recebe PASS físico a partir de SwiftShader ou FPS de vídeo exportado.

## Verificação e provas

| Verificação | Resultado disponível neste relatório |
|---|---|
| Python compileall | PASS informado pelo executor principal |
| Contratos do repositório | PASS informado pelo executor principal |
| Root pytest |196PASS /1FAIL preexistente: supervisor SIGKILL recovery, installer exit3 supervisor_not_running; não resolvido pelo site |
| Astro build/TypeScript V6 final | PASS: tsc --noEmit e build Astro 6 páginas estáticas; telemetria desativada |
| Browser V6 final | Antes do último hardening:48PASS/2SKIP/0FAIL. Nova execução final será registrada no comprovante externo, sem reutilizar números antigos |
| Desktop/mobile/reveal/transition/cinco mundos | Capturas e screencasts reais produzidos; arquivos finais/hashes no comprovante externo |
| Avaliação independente criativa | PENDENTE; escopo e limitações devem acompanhar qualquer nota |
| A15 físico/Safari/consumo/VRAM total | NÃO QUALIFICADOS |
| Core Web Vitals em campo | NÃO MEDIDOS |
| WCAG completo | NÃO CERTIFICADO; verificações específicas não equivalem a conformidade completa |

Provas mínimas do checkpoint: campo desktop, campo mobile, onda na arte, artista real revelado, travessia de mundo, segundo universo com identidade distinta. Acrescentar sequência real dos cinco capítulos com parada/reverse e lettering original. REAL_HEAD e CANDIDATE_SHA devem corresponder ao código que gerou os arquivos, com manifesto de hashes se houver distribuição.

## Reprodução local

Na raiz do app apps/hazewave-site, com as dependências do lockfile instaladas:

```bash
ASTRO_TELEMETRY_DISABLED=1 npm run build
ASTRO_TELEMETRY_DISABLED=1 npm run preview -- --host 127.0.0.1 --port 4321
```

Abrir http://127.0.0.1:4321/. Rolagem nativa avança o percurso; subir reverte. SEARCH seleciona outro artista; VOLTAR AO CAMPO retorna à origem; preferência reduced e botão de movimento oferecem percurso sem movimento.

URLs diretas estáticas (além da query compatível):

- /artists/baazu
- /artists/barak-ozama-beats
- /artists/indionesbala
- /artists/aquaverno
- /artists/hemorragia-cosmica

Os cinco paths são gerados estaticamente por Astro; a query artist mantém compatibilidade com links antigos. Baazü é nome de exibição; baazu é slug. Não afirmar que uma variação de nome não implementada funciona como URL direta.

## Fontes e limites de medição

Documentação oficial verificada: GSAP ScrollTrigger (https://gsap.com/docs/v3/Plugins/ScrollTrigger/), GSAP matchMedia (https://gsap.com/docs/v3/GSAP/gsap.matchMedia()/), Three WebGLRenderer (https://threejs.org/docs/pages/WebGLRenderer.html), Astro lifecycle (https://docs.astro.build/en/guides/view-transitions/), MDN WebGL budgets (https://developer.mozilla.org/en-US/docs/Web/API/WebGL_API/WebGL_best_practices), Google Web Vitals (https://web.dev/articles/vitals), W3C pause (https://www.w3.org/WAI/WCAG22/Understanding/pause-stop-hide.html) e animação de interação (https://www.w3.org/WAI/WCAG22/Understanding/animation-from-interactions.html).

CWV: metas LCP<=2.5s, INP<=200ms, CLS<=0.1 no percentil75 de campo, mobile/desktop separados. Lighthouse TBT é proxy e não substitui INP. Meta interna de cadência deve declarar hardware/tier e distribuição de frame times; >=30fps mobile é objetivo do projeto, não norma WCAG. SC2.3.3 é AAA. Pausar a atmosfera é medida concreta, não certificado.

## Handoff e pendências

Arquivos materiais: src/data/realArtists.ts; src/experience/fieldShader.ts, fieldRenderer.ts, livingField.ts; src/experience/audio/AuthorizedTransport.ts; src/data/authorizedTracks.ts; src/pages/index.astro; src/styles/living-field.css; public/media/worlds; world-art-provenance-v6.json; testes afetados e documentação de revisão. O diff exato do checkpoint determina quais foram alterados nesta etapa versus preservados da base.

Pendentes antes de alegar aceite: resultados finais vinculados ao SHA, inspeção visual independente dos cinco mundos e percurso, relatório de limitações do ambiente e aprovação do owner. Antes de publicação: corrigir/qualificar toda reprovação criativa, validar Safari/aparelho físico quando disponível e obter conteúdo musical autorizado para demonstrar o loop sonoro. Nenhuma promoção canônica ou publicação foi tentada.

```text
OLD_CASSETTE_PRIMARY_UI=REMOVED_FROM_NEW_DIRECTION
OLD_CLICK_WHEEL_PRIMARY_UI=REMOVED_FROM_NEW_DIRECTION
DEMO_ART_DIRECTION_AUTHORITY=FALSE
OWNER_ARTWORK_WORLD_AUTHORITY=TRUE
REAL_ARTIST_VISUAL_AUTHORITY=TRUE
REAL_MUSIC_PLAYBACK=UNAVAILABLE_NO_AUTHORIZED_TRACKS
OWNER_APPROVAL=PENDING
```
