# Etapa 02 — Arquitetura (agente: Arquiteto)

- HTML + CSS + ~1 KB de JS puro em `site/`. Sem framework, sem build, sem fontes externas, sem rastreadores, sem CDN.
- Imagens WebP locais (total < 400 KB), `loading="lazy"`, dimensões explícitas (sem CLS).
- Scrollytelling: um `<svg>` com caminhos; JS calcula `getTotalLength()` e mapeia o progresso do scroll em `strokeDashoffset` via `requestAnimationFrame`. `prefers-reduced-motion` → traço completo.
- Acessível: landmarks, skip link, contraste AA, foco visível, `lang="pt-BR"`, alt em todas as imagens.
- Orçamento Lighthouse mobile (CI): performance ≥ 0.9, acessibilidade ≥ 0.95, best-practices ≥ 0.9, SEO ≥ 0.9; peso total < 600 KB.
- Hospedagem: GitHub Pages via `actions/deploy-pages` (grátis). Deploy só por `workflow_dispatch` após aprovação humana (ordem da PR #72: nada público sem aprovação).
