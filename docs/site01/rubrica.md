# SITE 01 — Rubrica independente (estrita)

Cada critério vale 0–10. "10" = no nível do melhor benchmark para aquele critério, medido no A15 (412×915 css, 1080×2340, 915×412; CPU 4×).
Nota final = média ponderada. Critérios bloqueados por material do Luiz são marcados **[B]** e não podem passar de 6 sem esse material.

| # | Critério | Peso | Referência 10/10 | Nota v6 | Evidência / lacuna |
|---|---|---|---|---|---|
| 1 | Scroll é o pincel (traço literalmente gerado pelo scroll) | 15 | Who's Guilty, Ponpon | 9 | título, galáxia, estrada, ilha (3.158 traços), ícones, divisórias, cidade: tudo desenhado pelo scroll, reversível |
| 2 | Sensação de traço à mão (tremor, espessura variável, ordem) | 10 | Who's Guilty | 8 | tremor determinístico ±0,55 px, espessura por grupo (silhueta 1,45×, detalhe 0,7×) ±20%; falta afinar ponta (taper) |
| 3 | Direção de arte (2D chapado, neutro, sem neon) | 10 | SBS The Boat, NYT | 8 | paleta neutra + terracota/ocre/ardósia; arte IA ainda não aprovada |
| 4 | Profundidade / parallax em toda cena | 10 | NASA Prospect | 8 | céu 0,18× na jornada; camada de fundo + arte + texto em 3 velocidades nas seções |
| 5 | Coreografia de câmera (pan & zoom) | 10 | NASA Prospect | 8 | título→estrada→mergulho (easeInOutCubic)→passeio pelos pads (+38% zoom)→recuo para a cor |
| 6 | Ritmo / distâncias de scroll / transições | 8 | NYT Tomato Can | 8 | jornada 7 telas, seções 1,7, final 2,6; legendas por fase |
| 7 | Microinterações de toque | 5 | Genie / eSimple | 7 | balanço da arte ao tocar, botão afunda; sem som/feedback real |
| 8 | Tipografia e hierarquia | 6 | NYT | 8 | Bangers (título) + kicker numerado + texto 32ch |
| 9 | Estado de carregamento | 3 | — | 9 | onda desenhada em tinta (CSS puro) até o motor ficar pronto |
| 10 | Paridade paisagem | 6 | — | 8 | seções em 2 colunas; ilha com card à direita |
| 11 | Desempenho A15 | 10 | ≤16,8 ms p95, 0 long tasks | 8 | 0 long tasks no scroll; p95 oscila 16,8↔33,3 ms entre execuções (quantização vsync; baseline v5 também oscila) |
| 12 | Acessibilidade / reduced-motion | 4 | — | 9 | estado final estático, aria, foco, sem scroll horizontal |
| 13 | Conteúdo real (clipe, faixa, APK, plugins, loja, Pix) **[B]** | 8 | — | 2 | tudo "em breve"/PROVISÓRIO |
| 14 | Som **[B]** | 3 | — | 3 | gancho pronto, sem áudio |

Nota ponderada v6 ≈ **7,6/10** (sem os bloqueados: **8,3/10**).


## v7 (re-pontuação estrita)
Perf agora = rolagem de ponta a ponta (700 quadros), CPU 4×, **mediana de 5** (`tests/perf5-a15.mjs`).
Causa raiz dos quadros perdidos (perfil CDP, `tests/profile-scroll.mjs`): `getBoundingClientRect` por seção a cada quadro + leitura de `scrollY` depois das escritas = layout forçado (≈470 ms de 20 s). Corrigido com posições cacheadas no resize e uma leitura de scroll por quadro. Revelação de cor trocou `clip-path` (repaint) por duas camadas em contra-translação (só compositor).

| # | Critério | v6 | v7 | Por quê |
|---|---|---|---|---|
| 1 | Scroll é o pincel | 9 | 9 | + retraçado ao tocar |
| 2 | Traço à mão | 8 | 9 | pontas afinadas (14% inicial/final a 45% da espessura) + tremor + espessura variável |
| 3 | Direção de arte | 8 | 8 | teto atual = arte IA não aprovada / sem passe humano **[parcialmente B]** |
| 4 | Profundidade | 8 | 8,5 | 3 planos por cena; falta plano de primeiro plano (cabos) desenhado à mão |
| 5 | Câmera | 8 | 8,5 | passeio pelos pads; entre seções ainda não há câmera contínua (cada seção é um palco) |
| 6 | Ritmo / transições | 8 | 9 | revelação com borda de tinta; páginas entram com borda de onda sobreposta |
| 7 | Toque | 7 | 9 | anel de tinta + balanço + retraçado do desenho |
| 8 | Tipografia | 8 | 8,5 | |
| 9 | Carregamento | 9 | 9 | |
| 10 | Paisagem | 8 | 8,5 | jank mediano 23/700 quadros vs 3–6 em retrato |
| 11 | Desempenho | 8 | 9 | p95 mediano 16,8 ms nos 3 viewports, 0 long tasks (retrato); jank mediano 3 / 6 / 23 |
| 12 | Acessibilidade | 9 | 9 | |
| 13 | Conteúdo real **[B]** | 2 | 2 | |
| 14 | Som **[B]** | 3 | 3 | |

Ponderada v7 ≈ **7,9/10**; sem bloqueados ≈ **8,7/10**.
