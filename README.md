# Hazewave

Hazewave é um projeto independente focado em processamento de áudio.

## Primeiro módulo: separação vocal/instrumental

O MVP usa **Demucs / HTDemucs** para separar uma faixa em:

- `vocals`: voz isolada;
- `instrumental`: mix sem a stem vocal (`no_vocals`).

Isso é separação neural de stems — não cancelamento de canal central.

### Requisitos

- Python 3.10+
- FFmpeg disponível no PATH

### Instalação

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[separation]"
```

### Uso

```bash
hazewave separate "minha-musica.mp3" --output-dir output
```

Por padrão o modelo é `htdemucs`. O resultado fica em `output/<nome-da-faixa>/` com:

- `instrumental.wav`
- `vocals.wav`

Para manter somente o instrumental:

```bash
hazewave separate "minha-musica.mp3" --output-dir output --instrumental-only
```

## Escopo

Este repositório é independente e não compartilha runtime, pipeline ou estado com outros projetos.
