# Abordagem de DSP — clean-room

Modelado a partir de conhecimento público de circuitos analógicos (compressores de ganho controlado por FET, gravação magnética em fita) e de livros/artigos de DSP de áudio. Não foi usado código, binário, preset ou medição de nenhum plugin comercial.

## Hazewave FyahComp FET
- **Detector:** pico instantâneo (max |L|,|R|), sem RMS — o comportamento "pegajoso" dos compressores FET vem disso. Por isso, em senoides o ataque efetivo medido (63%) é maior que o parâmetro (o detector segue a forma de onda); ver `results.json`.
- **Topologia:** mistura feedforward (detecta a entrada) e feedback (detecta a saída da amostra anterior). No feedback o ganho do laço é compensado para manter a curva estática.
- **Curva estática:** limiar fixo em −18 dBFS (o ganho de entrada empurra o sinal contra o limiar, como nas unidades FET clássicas), joelho suave de 6 dB (12 dB no modo All-buttons).
- **All-buttons:** ratio 20, joelho largo, ataque 2× mais rápido e sobrecompressão (+0,25 dB de redução por dB acima de +6 dB de excesso), gerando a curva que "dobra para baixo".
- **Balística:** filtro de um polo no domínio dB com coeficientes distintos para ataque e release.
- **Saturação de saída:** `(tanh(d·y + b) − tanh(b))/d` com polarização `b` → harmônicos pares (assimetria de estágio classe A), misturada pelo controle de saturação.

## Hazewave FyahTape
- **Magnetização com memória:** `m += (tanh(drive·x + α·m) − m)·rate`. O termo `α·m` (realimentação de estado) cria um laço dependente da história do sinal (histerese simplificada, inspirada qualitativamente no modelo Jiles-Atherton); `rate` impõe slew. Menos bias → mais α e menos rate (mais memória, mais cor); mais bias → mais linear. O slew também atenua agudos (efeito de bias baixo).
- **Head bump:** peaking biquad (45 Hz +3 dB / 65 Hz +2,5 dB / 110 Hz +2 dB para 7,5/15/30 ips) + passa-altas a 0,35× a frequência do bump.
- **Perda de agudos:** passa-baixas 2ª ordem a 9 / 16 / 22 kHz (limitado a 0,45·fs).
- **Wow & flutter:** linha de atraso fracionária (2 ms base) modulada por 0,6 Hz (±1,5 ms) e 7 Hz (±0,2 ms). Observação: o sinal seco do Mix não é compensado nesses 2 ms.
- **Hiss:** ruído branco no nível escolhido.
