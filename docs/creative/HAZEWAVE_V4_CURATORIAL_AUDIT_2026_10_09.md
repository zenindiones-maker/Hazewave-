# HAZEWAVE — Curadoria adversarial da V4 (2026-10-09)

**Veredito: REPROVADA PARA PROMOÇÃO, NOTA DE CURADORIA 4,5/10.**

**Escopo:** `zenindiones-maker/Hazewave-`, branch `work/wave-rea6-traversal-v4`, HEAD observado `c77c45e8e39d44184f0c5df7f33040ab5bab36e6` (artefato visual V4 retido na biblioteca, NÃO integrado à árvore Git do site Astro). Avaliação independente conduzida pelo assistente; **não é parecer de profissional humano externo**.

## Fontes e provas reais

- `work/wave-rea6-traversal-v4`: auditoria da árvore GitHub, `apps/hazewave-site/src/pages/`, `docs/prototypes/wave-traversal-v4/model.js`, workflow `.github/workflows/wave-v4-rea6-owned.yml`.
- REA6 GitHub Actions #38007109066 (success; SHA do run `bcd12fd62ce6eddf46b20e5b78ed0112256b434c`): análise estática da fixture JS first-party. REA Evidence `ev_dc30e48088af4c3770fd8931b92b80f1fae06897b0207421b2e7f606291f2228`, 3 nós/1 módulo/2 arestas. Analisa **somente 1065 bytes de modelo**, não demonstra análise de todas as cenas, renderer ou aplicativos externos.
- Arquivos finais recuperados da biblioteca `/Hazewave/Living-Universe/Traversal-V4-REA6/`: HTML único 9.166.713 bytes e ZIP com 54 entradas (inclui 45 ativos HTML decodificados e 44 texturas/arquivos de imagem no pacote).
- O Chromium bloqueou `page.goto` em localhost (`ERR_BLOCKED_BY_ADMINISTRATOR`), mas foi possível abrir **exatamente o HTML independente** usando `page.set_content`, sem mudanças na implementação. Sessão Playwright headless em 360×800, 393×852 e 1280×720. Oito amostras de progresso 0/.2/.45/.7/.95/1/.45/0, com capturas reais em cada ponto. 45/45 tags de imagem carregadas, nenhum `pageerror` e nenhuma rolagem horizontal (0 px). Isso **não substitui** teste de toque e desempenho no A15 real.
- Em mobile393 o progresso de 0,45 apresentou 8 pads/6 knobs/2 speakers; em 0,7 mostrou 12/8/4; retorno a zero voltou 0/0/0. O traço revelou 0,458 em 0,45 e 1 em 0,95.
- Em teste separado sem preferência por redução de movimento, a névoa continuou oscilando após 650 ms com progresso constante. Em `prefers-reduced-motion: reduce` a oscilação parou, **mas a transformação/zoom/deslocamento da câmera permaneceu ativa** — alternativa acessível insuficiente.

## Notas curatorias, com pesos qualitativos

| Disciplina | Nota | Observação |
|---|---:|---|
| Identidade ilustrada e cores | 8,5 | Fonte aprovada reconhecível; estilo sombreado cósmico bem preservado. |
| Scrollytelling / acontecimentos | 3 | A história é sobretudo câmera sobre composições já completas. |
| Desenho nascendo pelo scroll | 3 | A linha SVG avança, porém a estrada luminosa **já está visível** na ilustração de fundo em 0%. |
| Mecânica MPC articulada | 6 | 24 peças ativas e reversíveis; movimento muito pequeno na escala real do celular. |
| Travessia / oclusão / profundidade | 4 | Objetos em planos e movimento de câmera existem, sem travessia entre espaços autorais realmente inéditos. |
| Clímax Indionesbala | 2 | Hub entra por `opacity`, `translate`, `scale` e glow; nada nele se abre ou se reorganiza. |
| Direção mobile e legibilidade | 4 | Texto compete com objetos/wordmarks; prioridade da arte não é respeitada na narrativa. |
| Reversibilidade mecânica | 8 | Estado normalizado e retorno 0 foram confirmados. |
| Entrega e governança | 4 | Preservação e REA6 reais, mas artefato visual V4 não está integrado/implantado no Astro. |

### Bloqueios visuais explícitos

**P0. A história nasce pronta.** No primeiro frame a estrada violeta já existe e o logotipo Indionesbala ocupa a região inferior do quadro. Fica impossível revelar o que a pessoa já viu. A animação de um traço SVG por cima não satisfaz a condição de 'desenho nascendo'. Criar *clean plates* ou estado inicial visualmente distinto **dos mesmos elementos**.

**P0. Clímax não transforma a ilustração.** `hub.webp` é um único grupo; a chegada aplica escala, posição, transparência e uma mancha emissiva. Requer peças/painéis do hub independentes, mecanismos físicos e no mínimo 3 estados intermediários ilustrados.

**P0. Logo duplicada na chegada.** O background já contém marca Indionesbala e o novo hub inclui mais uma marca oficial; no quadro final mobile as duas aparecem. O original não pode ser editado/destruído: limpar a duplicidade na *plate* publicada, preservar a marca oficial intacta numa única instância.

**P1. Scroll ainda é um passeio de câmera.** `deepSpace` e `worldScene` transitam por opacidade/scale/translate. A MPC desenhada movimenta-se bastante, mas o resto da maquinaria não se articula; a névoa desloca-se, não há sequência gráfica de dissipação/reconstituição complexa. Exigir prova visual de >3 objetos com mudança física/oclusão significativa sem movimento da câmera.

**P1. Narrativa visual de 5 atos é uma nomenclatura, não 5 acontecimentos.** Frases `01...05` mudam; as capturas de 0 e 20% são essencialmente a mesma composição, e `A INTERFERÊNCIA DESPERTA` contradiz a estrada já pintada. A rota da onda deve ser consistente com coordenadas do cenário e originar efetivamente a ativação.

**P1. `prefers-reduced-motion` incompleto.** Relógio de ambiente zero, mas transformações intensas do mundo via scroll persistem. Fornecer caminho alternativo estático/por etapas sem deslocamento excessivo, mantendo links e conteúdo.

**P1. Prioridade mobile incompleta.** Cabeçalho Hazewave sobreposto à assinatura Hazewave embutida na arte, rótulos grandes sobre equipamentos, e final com marca repetida. Ajustar composição e tipografia em 360 e 393 px sem sacrificar ação; testar gesto no aparelho real.

**P2. Desempenho e acesso.** HTML autônomo pesa 9,17 MB e inclui todas as texturas de uma vez. `requestAnimationFrame` roda indefinidamente e recalcula/atribui estilos de muitas peças. Ainda não há métricas confiáveis de FPS/INP/memória no A15, carregamento progressivo, fallback robusto sem WebGL ou URL pública e QR Code real. Não inferir 60 FPS do Chromium desktop headless.

**P2. REA6 não é parecer artístico.** O grafo REA6 refere-se ao modelo de progresso JS de 1065 B. A evidência é válida **para esse escopo limitado**. A afirmação 'REA6 aprovado' jamais equivale a 'website final aprovado'.

## Próxima decisão executiva

1. **Não ampliar mais assets antes de acertar a causalidade do primeiro minuto**: refazer estado visual 0% sem estrada/estação previamente reveladas e sem logo duplicada.
2. Criar 1 passagem **fisicamente demonstrável**: onda traçada expõe pela névoa uma MPC; pads, knobs, cabos e pelo menos uma estrutura do cenário mudam posição/forma; a câmera passa por trás de uma peça desenhada, além de pan/zoom. Reverte perfeitamente.
3. Construir 3 estados articulados do hub do Indionesbala antes de abrir o quinto ato.
4. Versionar fonte e assets usados pelo Astro V4 em uma **branch isolada**, junto de build e testes do **mesmo SHA**. Usar REA6 para análise estática do código próprio, e Playwright para comportamento visual da implementação real. Sem força bruta em branches divergentes; REA6 de outra branch não concede integração automática.
5. Gravar a experiência inteira em 360x800 e 393x852 e medir FPS/uso de memória no dispositivo, com caso `reduced-motion`. Submeter a curadoria visual humana independente e aprovação do proprietário antes de publicar.

**Resultado:** `TECHNICAL_MECHANISM_PROVEN=PARTIAL`, `MEA_SCROLL_REVERSE=PASS_IN_HEADLESS_BROWSER`, `REA6_STATIC=PASS_FOR_MODEL_ONLY`, `ARTISTIC_GATE=FAIL`, `A15_HARDWARE=NOT_TESTED`, `WEB_ASTRO_V4_DEPLOYED=FALSE`, `OWNER_APPROVED=FALSE`, `QR_PUBLIC=UNAVAILABLE`.