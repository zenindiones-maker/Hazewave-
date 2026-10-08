# Living Resonance Field — reconstrução V5

Esta versão aplica a auditoria V4 à experiência WAVE. Não altera autoridade do Harness, produção ou branch histórico. A rejeição anterior do owner não é substituída por aprovação automática.

## Mudança de comportamento

A origem é a imagem original Hazewave. Céu, arquitetura e água recebem projeções distintas; a onda refrata a água e a atmosfera, protegendo o farol. O lettering vem dos pixels fornecidos, com recorte/composição em runtime. Os arquivos originais permanecem byte a byte intactos.

A descoberta abre uma janela de material do artista no campo. A travessia opcional tem descobrir, atravessar e chegar; segue o último artista descoberto, aceita rolagem nativa, pausa e reversão. Links diretos, busca, teclado e histórico permanecem alternativas ao gesto. Uma entrada interrompida usa a composição retida no framebuffer como origem da próxima transição.

Aquaverno ocupa a tela com mar, horizonte e rocha; Hemorragia Cósmica ocupa um espaço assimétrico de arame e ossos, com emblema rígido. Barak, Indionesbala e Baazü recebem procedimentos específicos derivados de suas artes. Não há biografia, gênero, lançamento ou faixa inventados.

O transporte usa um HTMLAudioElement persistente e catálogo validado. Abrir outro mundo não interrompe uma faixa selecionada. O catálogo continua vazio: visual fornecido não é autorização de música, e controles indisponíveis não são reprodução funcional demonstrada.

## Engenharia reaproveitada e limites

- Astro/TypeScript, routing/history, DOM semântico, fallback, testes e CI preservados. Three.js/GSAP existentes permanecem disponíveis; este palco usa WebGL2 diretamente.
- Texturas carregadas por demanda e redimensionadas em memória até 1024 px no maior eixo. A origem exige aproximadamente 2,8 MB de textura RGBA, sem incluir framebuffers. Falha de uma arte secundária não derruba a origem.
- Buffer limitado a aproximadamente 1,4 milhão de pixels desktop / 700 mil mobile; DPR máximo 1,5 / 1,25. GPU lenta reduz a resolução. Isto é um teto gráfico, não medição de fluidez em hardware físico.
- O shader é uma composição 2.5D com máscaras analíticas. Não há geometria 3D reconstruída ou mapa de profundidade anotado por artista. Parallax e oclusão devem ser julgados pela imagem em movimento, não pela implementação.
- Pausar movimento mantém navegação. Retomar aguarda a textura do mundo atual e a inicialização compartilhada antes de ativar o canvas; revalida preferência e disposal após await.

## Autoavaliação

As revisões de arte rejeitaram a borda retangular exposta, os recortes de lettering com fundo e a descoberta escura. Esses pontos foram iterados antes da captura final. A revisão técnica encontrou a retomada com textura ausente e a disputa de RAF durante inicialização; ambos foram corrigidos e receberam verificação dirigida.

Critérios de bloqueio mantidos: origem reconhecível; descoberta visível; mundos distintos; continuidade; acesso mobile/teclado; conteúdo autorizado; resiliência. Testes não substituem avaliação visual. Não atribuir nota fictícia, prêmio, aprovação do owner ou superlativo verificável.

Não há aprovação de lançamento: faltam faixa autorizada, ensaio físico A15/Safari, leitor de tela e métricas de campo. A falha preexistente da suite raiz na recuperação do supervisor FreeLLMAPI permanece fora deste escopo WAVE. As capturas/gravações e o checkpoint externo documentam a validação exata da candidata.
