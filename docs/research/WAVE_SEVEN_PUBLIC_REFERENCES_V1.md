# WAVE — Sete referências públicas: pesquisa com evidências e direitos preservados

**Data da pesquisa:** 2026-10-09. **Autoridade:** NONE. **Harness:** HAZEWAVE_HARNESS.

Este documento registra pesquisa em páginas públicas e fontes secundárias, **não** uma sessão browser/MCP no Codespace e **não** uma engenharia reversa completa. As observações são somente de texto público e relatos técnicos; até prova contrária, interação real no navegador de origem, assets privados, bundles e visual DOM/WebGL não foram inspecionados.

Catálogo tipado: `knowledge/wave-reference-source-registry-v1.json`.

## Evidências por referência

1. **NASA Prospect** — [site](https://nasaprospect.com/). A página pública instrui a começar rolando e sustenta uma narrativa espacial ilustrada. Hipótese para WAVE: usar posição de scroll para revelar e movimentar uma história em perspectiva. Não confundir texto publicado com curva de animação mensurada.
2. **NYT / Attila Futaki — Tomato Can Blues** — [link histórico](https://www.nytimes.com/projects/2013/tomato-can-blues/), corroborado pelo [Nieman Lab](https://www.niemanlab.org/2013/09/the-new-york-times-tomato-can-blues-lovely-editorial-design-kinda-boring-ads/) e [Columbia Journalism Review](https://www.cjr.org/behind_the_news/qa_andrew_kueneman_and_steve_d.php). Jornalismo em HQ com rolagem e áudio. A página histórica não foi verificada no navegador atual, e robôs restringem a leitura programática. Nenhum código/arte será copiado.
3. **Who's Guilty** — [site oficial](https://promo.whoisguilty.com/), [CSS Design Awards](https://www.cssdesignawards.com/sites/who-is-guilty/47321/). Existe narrativa ilustrada pública sobre um designer e um desenvolvedor, efeitos sonoros e cenas. Hipótese WAVE: transições e microencenações no scroll.
4. **Ponpon Mania** — [site](https://ponpon-mania.com/), [relato técnico pelos criadores](https://tympanus.net/codrops/2025/10/07/ponpon-mania-how-webgl-and-gsap-bring-a-comic-sheeps-dream-to-life/). O artigo descreve camadas exportadas separadamente, atlas de texturas, planos WebGL reconstruindo cenas e GSAP ScrollTrigger sincronizando scroll, cena e câmera. Esse **processo geral** é transferível para a arte ORIGINAL do Hazewave. [Termos](https://ponpon-mania.com/legal): sem licença concedida para reutilização de imagens, códigos, animações ou personagens.
5. **Genie Studio App** — [site verificado](https://geniestudio.app/) e [apresentação do criativo](https://dribbble.com/shots/26612978-Unveiling-the-New-Genie-Website). Interações leves de revelação, composições ilustradas e hierarquia acolhedora. Não confundir com o serviço diferente `geniestudio.io`.
6. **Esimple** — [site oficial](https://www.esimple.it/) e [explicação de sites Web3D](https://www.esimple.it/marketing-3d/). Descreve experiências 3D por rolagem. A mecânica e os frames reais não foram aferidos em nosso navegador.
7. **SBS The Boat** — [URL histórica](https://www.sbs.com.au/theboat/), [SBS Learn](https://www.sbs.com.au/learn/resources/a-refugee-story-the-boat/) e [One Page Love](https://onepagelove.com/the-boat). É uma adaptação de conto de Nam Le com ilustrações de Matt Huynh e experiência de som/parallax/autoscroll relatada. A página original pode ter sido desativada; sem prova atual de browser, manter status histórico.

## Engenharia que a WAVE pode incorporar sem reproduzir obra de terceiros

- **Modelo único de progresso `p∈[0,1]`**: traço SVG nasce com `stroke-dasharray/dashoffset`; MPC reage somente quando energia do sinal chega ao pad; cables não são imagens estáticas.
- **Cenas com peças separadas**: primeiro extrair, da arte ORIGINAL aprovada, layers de horizonte/névoa/cidade/máquina/pads/linhas/hub; preservar pincel e perspectiva. Gerar cleanplates e mattes verdadeiros, sem recortar retângulos inteiros de screenshots.
- **Rig e camera separáveis**: `p` governa as transformações das peças, a máscara da névoa e câmera; sons ficam no domínio HAZE, consumidos por BRIDGE tipado, nunca por algoritmo autônomo não autorizado.
- **Performance**: atlas somente para camadas próprias com direitos de uso, LOD / resoluções por aparelho, evitar empilhar PNGs de tela cheia opacos e subir tudo para GPU ao mesmo tempo.
- **Aceitação causal**: documentar progressos `0, .15, .4, .7, .95, 1, .4, 0`, hashes visuais reversíveis, mobile 360×800 e 393×852, desktop 1280×720, reduced-motion, teclado, toque, domínio artista correto, tempo de resposta e ausência de cartão/cassete antigos.

## Limites de prova e próximo gate

A cadeia REA6 estático + 24 capturas Chromium + aprendizado (PRs #56–#58) prova `FIRST_PARTY_OWNED_FIXTURE`. O executor no Codespace e a conexão de *agentes reais* continuam não atestados; o PR #59 fornece um preflight específico, sem instalação automática.

Para cada referência externa, só admitir estudo dinâmico depois de verificar permissão de acesso, URL literal autorizada, redes e redirecionamentos, limite de recursos, isolamento de browser em sandbox de sistema operacional, sem credenciais e com recibo de visita realmente capturada. `web.run` com texto público **não** satisfaz esse gate. Não baixar em massa assets, nem reconstruir assets/código proprietários. Guardar hipóteses como `DISCOVERY`, não `PROVEN`.

A etapa artística só é aceita se aplicar os mecanismos observados às **artes canônicas e aos artistas reais do Hazewave**, com aprovação humana. Este documento não altera produção.
