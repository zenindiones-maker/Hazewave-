# HAZEWAVE · ArtCraft como ferramentas EXTERNAS de produção

**Escopo obrigatório:** `zenindiones-maker/Hazewave-` e somente o site WAVE. Nenhuma alteração, dependência, pasta, media ou autoridade é compartilhada com outros projetos. Os sete ArtCraft continuam nos repositórios públicos originais `storytold/*`, **não** serão copiados como subsistemas internos do Hazewave.

## Primeiro caso de uso real (VectorCraft)

O [VectorCraft v0.7.0](https://github.com/storytold/vectorcraft/releases/tag/v0.7.0) expõe `vectorcraft-cli convert IN.svg OUT.png`, documentado em `apps/vectorcraft-cli/src/main.rs`. Um artefato de release Linux x86_64 **exato** tem digest `d6b0ee57e1bdbd377b44c8524e8569ad2b4dff46b792fc10b0edbf8d74292acd`, conforme metadados de release GitHub consultados em 2026-10-10.

O código da WAVE `experiments/travessia-v4/index.html` já define a geometria própria `id="world-signal-path"`; em vez de copiar ilustrações ou bundles de terceiros, `artcraft_vector_bridge.py` extrai essa geometria em SVG independente. A etapa `render` aceita somente um binário explícito cujo SHA256 corresponda ao fornecido, roda `vectorcraft-cli convert` sem shell, valida a assinatura PNG, o canvas 420×820, a presença de bytes e registra hashes. A imagem gerada **não substitui o traço SVG progressivo no scroll**, não entra no bundle público e não recebe aprovação artística automática: é uma prova de ferramenta externa e um candidato a apoio offline para asset QA.

### Procedimento reproduzível

O workflow `.github/workflows/wave-vectorcraft-real-cli-proof.yml` tenta realizar a prova REAL a cada revisão do PR desta etapa. Ele:

1. faz checkout do HEAD exato do PR Hazewave;
2. prepara SVG somente de pixels/paths primeiro-partido da WAVE em diretório temporário fora do repo;
3. obtém tar.gz de release VectorCraft e compara SHA256 de arquivo inteiro;
4. rejeita membros perigosos, múltiplos CLIs e consumo excessivo na extração;
5. inicia o CLI REAL com `--network none`, `--read-only`, `--cap-drop ALL`, `no-new-privileges`, CPU/RAM/PIDs limitados, sem token nem credencial persistida e com fontes montadas `ro`;
6. requer PNG real, tamanho esperado e hashes. Só então gera arquivo `wave-vectorcraft-real-first-party-signal-RUN_ID`.

O CLI upstream nunca é instalado no A15, não roda na produção, não toca nas cinco artes canônicas da Biblioteca e não altera o site original. Se o executável não existir no tarball, faltar uma biblioteca ou a imagem não puder ser renderizada, `FAIL/BLOCKED`; nunca marcar como usado.

`tests/test_wave_artcraft_vector_bridge.py` contém um *test double* estritamente identificado, usado apenas para provar o fail-closed do adaptador em CI. **Teste duplo não prova execução do VectorCraft real.** A prova externa exige o workflow de acima com arquivo PNG.

## Próximos provedores e critérios

| Ferramenta externa | Uso possível no Hazewave | O que falta provar |
| --- | --- | --- |
| **VectorCraft** | render de trajetórias SVG originais, arte vetorial e fallback acessível | CLI real exporta arte original; fidelidade de cores e transparência |
| **EffectCraft** | composição de transições curtas e prévia frame exato | projeto sintético, render/metadata e ausência de arte privada no runner |
| **FilmCraft** | render e QC de reels e teasers dos artistas | pipeline de ingestão/render com A/V sync, codecs reais e comparação FFmpeg |
| **PhotoCraft** | tratamento de layers e máscaras de artes próprias | fidelidade de alpha, cor, PSD e reconstrução sem tocar em masters |
| **LightCraft** | tratamento não destrutivo de fotografias autorizadas de artistas | metadados, color management, RAW, export e reversibilidade |
| **PdfCraft** | press kits e PDFs de apresentação das bandas | PDF legível, fontes, a11y, links e render fiel |
| **DesignCraft** | edição de kits editoriais, fichas de artista e artes para lançamento | layout multipágina real com export PNG/PDF e fontes autorizadas |

Nenhum item desta tabela significa integração funcional do respectivo CLI; cada um exige prova de execução e revisão de licença. O projeto e a identidade de cada artista permanecem exclusivamente nas fontes canônicas Hazewave.

**Gates ainda bloqueados:** integração privada à experiência Astro real do Codespace, benchmarking de GPU no ambiente autorizado, PNG real do VectorCraft até o run terminar, aprovação humana e deploy. Não criar segundo Codespace, pagar capacidade, instalar no A15 ou promover candidatos automaticamente.
