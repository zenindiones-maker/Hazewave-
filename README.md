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

## Estado de implementação

O Hazewave separa explicitamente **capacidade executável atual** de **arquitetura/canon em desenvolvimento**.

Hoje:

- HAZE possui runtime executável para ACE-Step 1.5 e Demucs/HTDemucs;
- Hazewave Harness possui routing e autorização project-local para HAZE/WAVE/BRIDGE;
- o runtime Termux usa releases imutáveis por SHA;
- HAZE_STATE e WAVE_STATE possuem contratos JSON Schema versionados;
- o Hazewave Asset Manifest define a base de provenance de mídia/artefatos;
- WAVE/Living Resonance está em desenvolvimento arquitetural e ainda não deve ser tratado como engine completa de produção.

## Governança e documentação

Antes de modificar o projeto, leia:

- `AGENTS.md` — contrato operacional para agentes;
- `config/project-profile-v2.json` — autoridade, segurança, domínios e runtime;
- `docs/HAZEWAVE_SYSTEM_INDEX.md` — navegação humana;
- `docs/DOCUMENTATION_REGISTRY_V2.json` — registry machine-readable;
- `docs/architecture/DOCUMENTATION_GOVERNANCE_V1.md` — classes e precedência documental.

Validação mínima de uma mudança material:

```bash
python -m compileall -q src
python scripts/validate_repository_contracts.py
pytest
```

No Termux:

```bash
bash scripts/hazewave_termux_control.sh doctor
```

## FreeLLMAPI — Governed Free Fabric

Hazewave integra FreeLLMAPI como **gateway subordinado de inferência**, nunca como autoridade do projeto.

Baseline aceito:

- upstream: `tashfeenahmed/freellmapi`;
- release: `v0.13.4`;
- commit exato: `716948f20b12ec1c9b7c6fcebd22a3e7233cda1b`;
- endpoint local: `http://127.0.0.1:3001/v1`.

A autoridade permanece:

```text
HAZEWAVE_HARNESS=AUTHORITY
FREELLMAPI=AUTHORITY_NONE
```

O Governed Free Fabric adiciona uma camada Hazewave de elegibilidade antes de qualquer egress para provider:

```text
Harness authorization
→ capability/domain
→ data classification
→ zero-cost policy
→ provider trust lane
→ explicit provider-qualified model
→ FreeLLMAPI
```

Invariantes:

```text
PAID_FALLBACK=FORBIDDEN
UNKNOWN_COST=DENY
CREDENTIAL_EGRESS=DENY
PRIVATE_MEDIA_DEFAULT_EGRESS=DENY
UNREVIEWED_PROVIDER=QUARANTINED
```

Superfícies implementadas, quando existe provider gratuito elegível e configurado:

- chat e streaming;
- OpenAI Responses;
- legacy completions;
- Anthropic Messages;
- Gemini `/v1beta`;
- Ollama `/api/chat`;
- tool-call proposal transport;
- vision;
- embeddings;
- image generation;
- video generation;
- TTS;
- transcription;
- Fusion governado;
- cache/compression/session hints;
- MCP read-only para observabilidade.

Governed calls não usam `model=auto` irrestrito. Hazewave seleciona um provider/model explicitamente elegível e verifica a rota retornada.

O registry de política é:

`config/freellmapi-provider-eligibility-v1.json`

Private media continua local por padrão. Egress remoto exige `HazewaveMediaEgressGrant/v1` bound à task/asset/provider/modality.

Operação:

```bash
hazewave freellmapi inventory
hazewave freellmapi eligible
hazewave freellmapi health
hazewave freellmapi quota
hazewave freellmapi probe
hazewave freellmapi probe-all
```

`probe-all` é deliberadamente quota-conservador: executa um único live text proof e reporta elegibilidade das demais superfícies sem consumir quotas gratuitas de imagem/vídeo/áudio.

Arquitetura normativa:

- `docs/architecture/decisions/ADR-0006-governed-zero-cost-provider-fabric.md`;
- `docs/reference/HAZEWAVE_FREE_FABRIC_V1.md`;
- `docs/runbooks/FREELLMAPI_PROVIDER_V1.md`.

O código upstream continua pinado e application update checking continua desligado. O catálogo assinado do FreeLLMAPI pode ser usado como descoberta, mas **catálogo não concede elegibilidade Hazewave**.

## 9Router — sidecar local governado

Hazewave usa o **9Router** como gateway local subordinado para uma lane remota de inferência **zero-cost, fail-closed e otimizada pelo próprio Harness**.

Baseline pinado:

- upstream: `decolua/9router`;
- version: `0.5.95`;
- commit: `a99cf57239ff778b61e434c2786009d5ed1c412c`;
- endpoint: `http://127.0.0.1:20128/v1`;
- autoridade do gateway: `NONE`;
- autoridade de roteamento: `HAZEWAVE_HARNESS`;
- auto-update/cloud/tunnel/tailscale: desligados;
- paid/cheap fallback e custo desconhecido: negados;
- 9Router Combos e capacity-adapter fallback: proibidos;
- OpenCode Free: catálogo dinâmico + prova semântica por modelo;
- receipt de otimização: TTL de 24h;
- RTK: forçado durante execução governada;
- Headroom: desligado até existir runtime local gerenciado e benchmark próprio;
- respostas do executor: non-stream para preservar accounting de tokens.

### Operação

```bash
bash scripts/hazewave_termux_control.sh 9router install
bash scripts/hazewave_termux_control.sh 9router start
bash scripts/hazewave_termux_control.sh 9router doctor

# Descoberta sem inferência
bash scripts/hazewave_termux_control.sh 9router catalog

# Benchmark de todo o pool OpenCode Free e geração de receipt v2
bash scripts/hazewave_termux_control.sh 9router optimize

# Estado do pool, ranking, freshness e cooldowns
PYTHONPATH=src python -m hazewave.cli 9router status

# Seleção automática do melhor modelo provado + fallback somente no pool Free
PYTHONPATH=src python -m hazewave.cli 9router execute \
  --capability reason.general \
  --domain HAZE \
  --prompt "Explique o problema."

# Histórico público de agente/tool_result, permitindo ao RTK comprimir contexto
PYTHONPATH=src python -m hazewave.cli 9router execute \
  --capability code.review \
  --domain HAZE \
  --messages-file /path/to/public-messages.json
```

O optimizer benchmarka no máximo 16 modelos e admite apenas os que devolverem prova semântica. Para `reason.general` e código, o optimizer usa **3 amostras por modelo**, calcula medianas e ranqueia por **tokens × latência**, penalizado pela taxa de sucesso. Para `reason.deep`, prioriza primeiro **reasoning comprovado** e depois o score balanceado. Execuções reais alimentam EWMA de tokens/latência para o ranking se adaptar ao A15 em uso. Falhas transitórias `429/5xx` entram em cooldown exponencial local (60s até 15min), evitando martelar uma rota degradada.

Catálogo não é autoridade. Receipt presente também não significa receipt válido: freshness, capability, data class, modelo e política zero-cost são revalidados pelo Harness em cada execução.


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
