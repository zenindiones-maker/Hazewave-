# OBRIGAÇÃO DE ENGENHARIA REVERSA — RECON-REVENG-002

Status: DEVELOPMENT; ainda sem promoção canônica. Autoridade: somente HAZEWAVE_HARNESS; HAZE = áudio, WAVE = vídeo, BRIDGE sem acesso a inspeção.

## Capability candidate registry v1

- binary_header_inspector: ELF/PE/Mach-O header, arquitetura/entry fields, sem desassemblagem.
- media_container_deep_parser: ISO BMFF/MP4 boxes, offsets, tamanho, brand, mvhd, stsd, stco/co64; não decodifica vídeo.
- codec_stream_analyzer: PCM/WAV e AAC/ADTS headers; não extrai sample de contêiner.
- streaming_manifest_parser: HLS playlists; sem busca remota, DASH ainda não suportado.
- protection_detector: sinais pssh/sinf/schm/tenc ou EXT-X-KEY; apenas detecção, nunca bypass.

Implementação inicial: RECON-REVENG-002/v1. Limite 64 MiB; arquivo local regular, sem symlink; arquivos inválidos falham fechados. Saída JSON e receipt com SHA-256 da entrada e saída, tarefa, autorização, duração, custo monetário declarado 0 e sem publicação. Receipt não é assinatura independente nem autorização de publicação.

## Método obrigatório: estático → dinâmico → reconstrução

1. Estático: provenance/rights, hash, magic, header, endian, atom/box, offsets, codec, proteção; erros de bounds = BLOCKED.
2. Dinâmico: permitido somente após autorização explícita, sandbox descartável, sem segredos/rede e com evidência. Nunca executar binário desconhecido no inspector.
3. Reconstrução: correlacionar sample table, track e stream extraído contra parser independente; hashes, logs e commit SHA preservados.

## Gate de mídia nova

Toda mídia e binário novo DEVE passar por inspector antes de render. REGRA NORMATIVA, AINDA NÃO ENFORCED EM TODOS OS RENDERERS. Até integrar cada ponto de entrada, PRE_RENDER_GATE=BLOCKED. Recibos só valem para bytes idênticos ao artefato autorizado; nunca usar ausência de detecção como garantia de ausência de DRM. Acima de 64 MiB, versão atual bloqueia explicitamente e requer parser streaming.

## RE_MASTERY

RE_MASTERY=PASS apenas após parser nativo sem bibliotecas externas de contêiner REAL e extração correta de stream codec desse contêiner, conferida por ferramenta independente em CI no exato SHA, com hash de saída. Leitura de headers não equivale a extração de stream. Estado atual: RE_MASTERY=BLOCKED.

## Governança e direitos

Somente Harness autoriza execução. Nenhum agente promove/publica sem gate humano e receipt comprovado. É vedado bypass de DRM, copiar código de terceiros sem compatibilidade legal, alterar autoridade, criar outro repositório, executar bytes desconhecidos, ler PRIVATE_MEDIA sem autorização, usar serviço pago ou misturar projetos. Código dessa etapa é implementação stdlib independente INFORMADA por padrões públicos; nenhuma fonte externa foi incorporada literalmente.

## Aceite da missão

Exige cumulativamente: >=60 deep dives comprovados (30+30, licença validada, source/architecture/test/commit/CLI/logs), 5–10 capabilities com CI e receipt, ledger de execução real, documento versionado/registrado e vídeo de terminal de 30s de execução real. Sem todos os itens, RECON_REVENG_002=INCOMPLETE. Branch candidata não confere status canônico.
