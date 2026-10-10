# Hazewave WAVE V7 — EffectCraft + FilmCraft na travessia

**Escopo único:** `zenindiones-maker/Hazewave-`. O site e a travessia V4/V5/V6 foram preservados; não há código nem infraestrutura de outros projetos neste PR.

## Operação real, não apenas catálogo

- **EffectCraft v0.6.0**, release oficial Linux x86_64 SHA256 `71810719903378cdab32a1fe328f23c874d38cd3d833abb19c6263dd2bad218c`, cria um projeto próprio do Hazewave `HAZEWAVE_SIGNAL_PORTAL`: comp de 420×820, 8 fps, duração 1 segundo, elipse da ruptura e animação keyframed de escala de 10→100→150%.
- Render de **8 PNGs progressivos de alta qualidade**, em tempo 0→0,875 s, com `--transparent`. Exigimos 420×820, verificação de assinatura PNG, SHA256 de cada frame e pelo menos cinco frames diferentes. O primeiro não pode ser reproduzido fraudulentamente como os oito.
- O EffectCraft também renderiza um `effectcraft-reference.webm` da mesma composição. **FilmCraft v0.4.0**, release Linux SHA256 `841790ff6649f0d49daa4a8ade1cb18d948e5ca43d00771046663e06c8d8ce83`, deve conseguir **probar/decodificar** esse arquivo sem erros. Ele faz *QC da mídia*; não afirmamos que editou o filme final ou gerou a animação.
- `artcraft_portal_pipeline.py` valida exatamente os binários, saídas, mídias e SHA. Os binários executam em **Docker sem rede**, filesystem somente leitura, sem privilégios, com CPU/RAM/PIDs limitados, sem credenciais e sem A15.
- `.github/workflows/wave-effectcraft-filmcraft-portal-proof.yml` publica um **artefato temporário de laboratório** somente se a geração E a decodificação real passarem. A prova contém oito frames, WebM, projeto EffectCraft, laudo FilmCraft, hashes e manifestos.

## Incorporação no produto de verdade

O site experimental `apps/hazewave-site/experiments/travessia-v4` agora contém o plano `#effectcraft-aperture` **atrás do aro portal original**, em profundidade separada da névoa, cidade e equipamento MPC. `travessia.js` carrega os frames apenas quando presentes em uma prévia privada qualificada, seleciona o frame de acordo com o mesmo `scroll progress` da travessia, e permite volta precisa ao início.

A animação externa **não manda no navegador**, não inicia áudio, não altera os 12 pads, oito knobs ou quatro alto-falantes; toda geometria causal permanece no motor original. Uma imagem gerada não substitui o movimento de câmera, portal nem as cinco obras canônicas. No modo leve ou com `prefers-reduced-motion`, a camada decorativa é omitida (sem esconder o destino ou a onda nativa).

Os compositores `build_standalone.py --effectcraft-proof /private/fx` e `integrate_private_astro.py --effectcraft-proof /private/fx` verificam os recibos antes de embutir/copy os bytes nas cópias privadas. **Sem saída real comprovada, a V7 abre a experiência existente sem o efeito**, de modo que CI sintético não finge ter gerado arte.

## Provas e limites

- `tests/test_wave_artcraft_portal_v7.py`: testes negativos e de integridade, sem executar CLI.
- `apps/hazewave-site/tests/wave-v4-seven-site-technique-regression.spec.ts`: testes reais Chromium para scroll, reversão, qualidade e fallback com frames **sintéticos explícitos**. A prova dos PNGs **reais** pertence exclusivamente ao job externo e seu recibo.
- A validação de uma prévia **com as obras privadas reais** requer os cinco masters aprovados fora do GitHub e o pacote FX já verificado.
- Os sete apps ArtCraft continuam externos. Este ciclo **implementa somente EffectCraft e FilmCraft**, além do VectorCraft comprovado na etapa anterior. Não dizer que os outros quatro foram integrados.
- **Não produzir/publicar** mídia do dono em `public/`, Actions ou GitHub; não modificar `main`, não criar Codespace, não aumentar máquina, não executar no A15, não introduzir fallback pago e não aprovar a experiência visual sem revisão do proprietário.

Referências de implementação: `storytold/effectcraft` `docs/agents.md` e `crates/automation/tests/qa/shapes.rs`; `storytold/filmcraft` `docs/agents.md`. Aprendemos as APIs públicas; não copiamos seus ativos e não abrimos autoridade MCP global.

## Continuação: fluidez cinematográfica e correção do modo leve

Na revisão de 09/10, a V7 usava `Math.floor(t*8)` e exibia os oito PNGs reais com *step changes*; apesar do render nativo bem-sucedido, isso não demonstrava uma borda contínua. A implementação passou a interpolar dois PNGs consecutivos, misturando `globalAlpha` no Canvas2D, com peso limitado a intervalos de 1/32 e cache do último par/peso para evitar pinturas desnecessárias. **O controle de câmera e as obras privadas permanecem iguais.**

A prova independente com o HTML privado autêntico, arte canônica e oito frames gerados pelas ferramentas reais percorreu três pontos `p=0,64;0,65;0,66` dentro do **mesmo par 4/5**: o peso aumentou continuamente e foram obtidos três PNGs do canvas distintos, em cada uma das resoluções 393×852, 360×800 e 1280×800. Houve ida e volta, zero overflow e zero erro JS. As evidências de screenshot e recibo estão exclusivamente na Biblioteca privada do proprietário, não no GitHub.

Um segundo defeito foi encontrado: a redução automática após cinco frames lentos era permanente e o botão não conseguia reativar os efeitos. Agora o controle explícito tem prioridade sobre a redução automática e o atributo de acessibilidade `aria-pressed` representa o **estado efetivo**, não apenas a última intenção de clique. O modo leve mantém a trajetória e o portal nativos. Testes de Chromium reproduzem as duas condições e garantem que o dono possa voltar a `FULL`.

Pesquisa técnica: [MDN Canvas drawImage/ImageBitmap](https://developer.mozilla.org/en-US/docs/Web/API/ImageBitmap), [web.dev Rendering Performance](https://web.dev/articles/rendering-performance), [MDN Long Animation Frame Timing](https://developer.mozilla.org/en-US/docs/Web/API/Performance_API/Long_animation_frame_timing). **Sem afirmar benchmark de GPU do Samsung A15 ou 60 fps garantidos**: os testes acima usam Chromium de máquina de prova; orçamento térmico/energia ainda depende de aparelho real.

