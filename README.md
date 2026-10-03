# Hazewave

Hazewave é um projeto independente de música generativa, processamento neural de áudio e sistemas visuais interativos.

## Domínios canônicos

Hazewave agora é organizado em dois domínios complementares:

### HAZE — som

Tudo que nasce, existe ou evolui através de áudio.

Inclui geração musical, stems, timbre, voz, ritmo, síntese, DSP, análise, composição e memória sonora.

O runtime atual do repositório já pertence a este domínio:

- ACE-Step 1.5;
- Demucs / HTDemucs;
- geração por prompt;
- referência de áudio;
- cover/remix.

### WAVE — imagem

Tudo que nasce, existe ou evolui através de imagem, movimento, luz, geometria, simulação e memória visual.

A fundação inicial é o **Living Resonance Engine**, um sistema generativo inspirado por fenômenos reais de ressonância, mas com linguagem visual própria do Hazewave.

Direção técnica:

- WebGPU-first;
- WebGL2 fallback;
- Three.js WebGPURenderer;
- partículas e campos;
- memória visual persistente;
- HazeMatter;
- site interativo e visualizador compartilhando o mesmo motor.

O contrato canônico está em:

`canon/hazewave-domain-v1.json`

A especificação inicial de WAVE está em:

`docs/wave/WAVE_LIVING_RESONANCE_ENGINE_V1.md`

## HAZEWAVE

HAZE cria o sinal.

WAVE dá forma.

HAZEWAVE é onde os dois viram um único sistema.

```text
HAZE STATE
    ↓
Hazewave Translation Layer
    ↓
WAVE STATE
```

A camada de tradução deve usar informação musical estruturada — não apenas amplitude — para controlar matéria, ressonância, topologia, movimento e memória.

## NEANDERCAUS

**HAZEWAVE — NEANDERCAUS** é a primeira obra canônica planejada sobre os dois domínios.

Tese:

> From breath to latent space.

A obra conecta uma história musical e visual desde formas primordiais de som humano até modelos generativos, distinguindo explicitamente evidência histórica de especulação artística.

Fundação:

`apps/neandercaus/README.md`

## ACE-Step 1.5 — geração instrumental

O Hazewave integra o **ACE-Step 1.5** como engine local para prompt → instrumental, prompt + áudio de referência, e cover/remix de áudio existente.

O runtime externo fica em `.hazewave/runtime/ACE-Step-1.5` e não é versionado. O upstream está pinado em `ca1e85fe9430179831e6bc6be790c332190a3866` para evitar mudanças silenciosas.

### Requisitos

- Python 3.10+
- Git
- FFmpeg
- `uv`
- GPU recomendada para geração prática

### Instalação do Hazewave

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[separation]"
```

### Baixar e instalar ACE-Step

```bash
hazewave acestep install
```

Para também baixar antecipadamente o snapshot oficial `ACE-Step/Ace-Step1.5`:

```bash
hazewave acestep install --prefetch-models
```

### Iniciar a API local

```bash
hazewave acestep serve
```

Em outro terminal:

```bash
hazewave acestep status
```

### Instrumental somente por prompt

```bash
hazewave acestep generate \
  --mode text \
  --prompt "dark Brazilian psychedelic rock, tribal percussion, distorted guitar, deep bass, cinematic build" \
  --duration 210 \
  --format wav
```

### Prompt + WAV como referência

```bash
hazewave acestep generate "meu-instrumental-limpo.wav" \
  --mode reference \
  --prompt "organic Brazilian psychedelic rock, tribal percussion, distorted guitar, deep bass, raw live drums" \
  --duration 210 \
  --format wav
```

### Cover/remix preservando mais a composição

```bash
hazewave acestep generate "meu-instrumental-limpo.wav" \
  --mode cover \
  --cover-strength 0.85 \
  --prompt "Brazilian psychedelic instrumental rock, heavier drums, analog guitar, no vocals" \
  --format wav
```

O Hazewave força a intenção instrumental enviando `lyrics=[Instrumental]` e acrescentando ao prompt: `Instrumental only. No vocals, no singing, no choir, no spoken words.`

No modo `cover`, o WAV é enviado à API oficial como `src_audio`. No modo `reference`, é enviado como `reference_audio`.

## Demucs / HTDemucs — stems e limpeza

O módulo de separação usa Demucs / HTDemucs para separar voz e instrumental por stems neurais.

```bash
hazewave separate "minha-musica.mp3" --output-dir output
```

Somente instrumental:

```bash
hazewave separate "minha-musica.mp3" --output-dir output --instrumental-only
```

## Fluxo atual de HAZE

```text
Áudio existente
    ↓
Demucs / limpeza
    ↓
instrumental limpo
    ↓
ACE-Step 1.5 + prompt
    ↓
novo instrumental
```

## Escopo

Este repositório é independente e não compartilha runtime, pipeline ou estado com outros projetos.
