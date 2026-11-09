# Hazewave: Separar Stems (Demucs) — offline

Separação de stems **dentro do REAPER**, um botão, **zero custo**, só open source (Demucs / HTDemucs). Depois do primeiro download do modelo, funciona **offline**.

## O que faz

1. Abre um painel (lista de itens do projeto com checkbox).
2. Escolhe o modo: **6 stems** (padrão, `htdemucs_6s`), **4 stems** (`htdemucs`) ou **2 stems** (voz / instrumental).
3. Aperta o botão vermelho **SEPARAR STEMS**.
4. O Demucs roda em segundo plano (sem janela de Terminal). A barra de progresso fica no painel.
5. As stems entram em faixas novas sob a faixa original, alinhadas no tempo, com cores:
   - **Bateria** azul · **Baixo** verde · **Guitarra** oliva · **Teclado** roxo · **Outros** cinza · **Vocais** ciano
6. O áudio original fica **mudo**. Um único passo de **Desfazer** reverte tudo.
7. Arquivos em `<projeto>/HAZEWAVE_STEMS/`.

No app FYAHREAPER Remote: painel **⋯ → STEMS** (modo 6).

## Instalação (qualquer REAPER: Windows / Linux / macOS)

### 1. Python 3.10+ e FFmpeg

- Windows: instale Python pelo python.org (marque “Add to PATH”) e `winget install Gyan.FFmpeg`
- macOS: `brew install python ffmpeg`
- Linux: `sudo apt install python3 python3-venv ffmpeg`

### 2. Pacote Hazewave Stems + Demucs

No terminal, na pasta deste diretório:

```bash
bash install_stems.sh
```

Isso cria `~/.local/share/hazewave/stems-venv` com Demucs e copia os scripts para
`Scripts/Hazewave/Stems/` do REAPER.

### 3. Registrar a ação no REAPER

1. Abra o REAPER.
2. Actions → Show action list → ReaScript: Load →
   `Scripts/Hazewave/Stems/register_stems.lua` (ou deixe o `__startup.lua` registrar sozinho).
3. Procure **Hazewave_Separar_Stems** na lista de actions e rode uma vez.
4. (Opcional) Arraste a action para a toolbar **Fyah ARRANGE** / crie um botão grande.

### 4. Primeiro uso (baixa o modelo)

Na primeira separação o Demucs baixa o checkpoint (~几百 MB). Depois disso, **offline**.

## Uso no codespace / workstation FYAHREAPER

O mesmo pacote vive em `apps/fyahreaper_remote/reaper_touch/stems/`. ReaHub expõe
`POST /api/project/separate_stems` com `{"mode":"6"|"4"|"2"}` (allowlist). O app chama modo `6`.

## Requisitos

- REAPER 6/7 64-bit
- Python 3.10+ com o venv Hazewave (`demucs`, `torch` CPU ok)
- FFmpeg no PATH (para respeitar o trim do item)

## Limitações

- CPU no codespace free-tier é lento (vários minutos por minuto de áudio).
- `htdemucs_6s` é o mais pesado; use 4 ou 2 stems se precisar de velocidade.
- Sem GPU no free tier.
- Chord detection (marcadores) é opcional e só entra depois que a separação estiver estável.
