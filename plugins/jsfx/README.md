# Hazewave JSFX plugins (HAZE domain)

Plugins originais, open source (MIT, ver `LICENSE`), para REAPER.

| Plugin | Arquivo | O que faz |
|---|---|---|
| Hazewave FyahComp FET | `Hazewave FyahComp FET.jsfx` | Compressor de pico estilo FET: ataque 20–800 µs, release 50–1100 ms, ratios 4/8/12/20 e modo "All-buttons", topologia feedforward↔feedback, input/output, saturação assimétrica de saída, mix paralelo |
| Hazewave FyahTape | `Hazewave FyahTape.jsfx` | Máquina de fita: saturação com memória (histerese simplificada), head bump e perda de agudos por velocidade (7,5/15/30 ips), wow & flutter, hiss, bias, mix |

## Instalar
Copie os `.jsfx` para a pasta `Effects/` do REAPER (Options → Show REAPER resource path) e procure "Hazewave" no FX browser.

## Clean-room
Todo o DSP foi escrito do zero a partir de conhecimento público de circuitos analógicos e gravação magnética. **Não usa, não lê e não deriva de código de nenhum plugin comercial**, e nenhuma marca de terceiros aparece nos nomes. Detalhes em `docs/DSP_APPROACH.md`.

## Verificação offline
`verification/reference_dsp.py` é uma tradução linha a linha do DSP dos `.jsfx` para Python/numpy.
```bash
pip install numpy matplotlib pytest
python plugins/jsfx/verification/measure.py     # gera results/results.json e gráficos PNG
pytest plugins/jsfx/verification                 # testes de regressão
```
Status:
- UNIT PASS: 8/8 testes do modelo de referência (inclui regressão do alinhamento seco/molhado do FyahTape).
- HOST PASS (REAPER 7.82 de teste, Codespace, 2026-10-11): os dois `.jsfx` carregam (TrackFX_AddByName ≥ 0; 11 e 10 parâmetros), render offline de tom 1 kHz −6 dBFS pela cadeia FET→Tape bate com o Python: RMS −16,547 dBFS nos dois, diferença máx. 2,0e−5, residual −85,2 dB (ver `verification/results/host_vs_python.json`, scripts em `verification/host/`).
