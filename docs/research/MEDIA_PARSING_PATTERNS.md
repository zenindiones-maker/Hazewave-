# Padrões de parsing de mídia — RECON-REVENG-002

Inspeção de fonte: Eyevinn/mp4ff mp4/box.go; abema/go-mp4 box_info.go; Shaka lib/hls/hls_parser.js. Não equivale a 30 deep dives.

1. Validar magic/brand, nunca confiar somente na extensão.
2. ISO BMFF: size32 + FourCC, size=1 introduz largesize64, size=0 até fim do contêiner; validar cada avanço contra bounds.
3. Hierarquia moov/trak/mdia/minf/stbl e moof/traf, com orçamento de profundidade/contagem.
4. Metadata mvhd: timescale e ticks, não equivale automaticamente à duração audível de todas as pistas.
5. Sample description stsd informa FourCC; stco/co64 chunk offset; extração correta também requer stsc, stsz e stts.
6. HLS RFC 8216: playlist EXT M3U, EXTINF, EXT-X-STREAM-INF, URI UTF-8; nenhuma URL deve ser solicitada automaticamente.
7. Proteção CENC pssh/sinf, HLS EXT-X-KEY: detecção não autoriza descriptografar.
8. Falhar fechado em tamanho inválido, byte truncado, contagem ou offset exagerado.

Referências primárias:
https://www.iso.org/standard/85596.html
https://mp4ra.org/
https://www.rfc-editor.org/rfc/rfc8216
https://github.com/Eyevinn/mp4ff/blob/master/mp4/box.go
https://github.com/abema/go-mp4/blob/master/box_info.go
https://github.com/shaka-project/shaka-player/blob/main/lib/hls/hls_parser.js
