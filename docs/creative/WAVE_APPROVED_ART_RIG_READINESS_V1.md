# WAVE — Auditoria de fontes artísticas, transparência e prontidão para rigs V3

**Data:** 2026-10-09. **Status:** fontes verificadas, rigs físicos AINDA NÃO PRONTOS. **Autoridade:** NONE; somente o Hazewave Harness autoriza tarefas.

## Proveniência real

Foram acessados os **cinco arquivos originais** aprovados pelo proprietário na Biblioteca privada `/Hazewave/Living-Universe/V3-CANONICAL-ASSETS/APPROVED_ILLUSTRATED_LAYERS/`. A análise binária foi realizada em contêiner de auditoria do ChatGPT, **não** no Codespace e **não** sobre um site em produção. Os hashes SHA-256 de todas as imagens coincidiram com o manifesto original `HAZEWAVE_APPROVED_ILLUSTRATED_LAYERS_V3.json`.

| ID | Papel | Pixel dimensions | Alpha=0 | Alpha=255 | Partial alpha |
|---|---|---|---:|---:|---:|
| A01 | MPC flutuante, repouso | 1448×1086 | 36.935% | 0.028% | 63.038% |
| A02 | MPC ativada, cabos/pads | 1448×1086 | 39.223% | 0.040% | 60.737% |
| A03 | Metrópole musical | 1672×941 | 61.248% | 0.032% | 38.720% |
| A04 | Hub Indionesbala | 1672×941 | 38.056% | 0.041% | 61.903% |
| A05 | Névoa cósmica | 1672×941 | 34.575% | 0.003% | 65.422% |

As categorias cobrem todos os pixels. Valores arredondados para 0.001%. Hashes e dimensões originais estão em `knowledge/wave-approved-art-rig-readiness-v1.json`. Aprovação visual da arte ORIGINAL permanece válida; **não** foi convertida indevidamente em aprovação de animação, produto ou camada de produção.

## Interpretação profissional

- Ser RGBA e conter alfa diferente de zero **não basta** para concluir que pads, botões, knobs, display, cabos, chassis, plataformas e névoa existem como peças independentes.
- Porcentagens muito baixas de `alpha=255` não condenam sozinhas a qualidade visual; podem decorrer de bordas e pincéis translúcidos. Exigem inspeção de compósitos sobre fundos claros/escuros e halos, além de máscaras geometricamente separadas.
- Estes cinco originais preservados **não devem ser editados**. Criar derivados por peça, mantendo perspectiva/arte, com **cleanplates reais** onde houver oclusão. Evitar deslocar um PNG inteiro e anunciar “MPC articulada”.
- Falta uma prova de `pad_down`, `pad_energizing`, `pad_up`, controle de fader/knob, caminho da onda desenhado em SVG, cabos e três planos atmosféricos independentes e correto `z-order`.
- Antes de inserir no site, revisar as poses e o recorte com arte atual e logo originais. Nenhuma imagem de terceiro entra no produto.

## Verificação reproduzível dos arquivos completos, fora do Git

Sem tocar nos arquivos originais:

```bash
PYTHONPATH=src python -m hazewave.wave_art_rig_preflight \
  --source-root "/private/path/APPROVED_ILLUSTRATED_LAYERS" \
  --ledger "knowledge/wave-approved-art-rig-readiness-v1.json"
```

O módulo usa somente biblioteca padrão Python, verifica arquivos `RGBA/8-bit/non-interlaced`, assinatura PNG, chunks CRC, limites de descompressão, SHA, dimensões e proporções dos canais alfa. Ele não recorta, cria máscaras, reescreve arte, visita URLs ou registra agentes MCP. Um `PASS` significa **integridade dos PNGs originais**, não `RIG_READY`.

## Critério para habilitar a integração visual

1. Derivar manualmente ou via editor autorizado as máscaras de todas as partes; conferir cleanplates contra a pintura original.
2. Criar os estados físicos e fixar a topologia de rigs; `pad` deve reagir depois que a onda alcançá-lo, e a névoa deve realmente ocluir por profundidade.
3. Usar a infraestrutura de scroll já comprovada nos PRs #56–#58, **adaptando-a às camadas reais**. A fixture SVG de laboratório não substitui a arte aprovada.
4. Exigir forward/reverse frame-for-frame nos viewports 360×800, 393×852, desktop; capturas com os originais e states, teste de reduced-motion e comparação humana. Só então pedir aprovação artística do proprietário.

**Pendências não escondidas:** originais ainda estão na Biblioteca privada, não como assets binários versionados no GitHub; máscaras não entregues; execução Codespace e agente real ainda pendentes; produto final sem aprovação.
