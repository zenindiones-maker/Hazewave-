# HAZE — Acervo de produções do proprietário e curadoria privada (V1)

**Estado:** DEVELOPMENT / PR draft; sem conexão comprovada às pastas do proprietário, sem curadoria real do catálogo privado executada.
**Autoridade:** HAZEWAVE_HARNESS. HAZE possui todo o áudio; WAVE permanece separada.
**Escopo:** somente leitura do acervo, extração acústica local de faixas aprovadas, preparação de referências para decisões futuras de produção/REAPER.

## O acervo não é uma playlist

Cada diretório de projeto é uma origem artística própria, possivelmente com vários estilos, versões e estados de produção. Não se inferem direitos, gênero, status de lançamento, autoria, mix final, excelência, popularidade ou preferência artística pela pasta, extensão, título ou por um modelo. O catálogo deve preservar *todas* as identidades criativas, inclusive estilos diferentes, sem colapsar gêneros em uma "assinatura" falsa.

O sistema registra, quando presentes:

- projetos REAPER: \`.rpp\` e \`.rpp-bak\`; MIDI; arquivos de áudio;
- origem por pasta, tamanho e (se expressamente optado) SHA256;
- duplicatas **exatamente iguais em bytes**, distinguindo-as de versões e mixagens;
- etiquetas de gênero/estilo e função de referência **fornecidas pelo proprietário**;
- sinais acústicos objetivos da fonte: EBU R128/true-peak do áudio completo, espectro/estéreo/transientes obtidos de **trecho central de no máximo 30 s**;
- versões/mix/stem/master/rascunho aprovadas e suas notas por revisão humana futura.

O Chromaprint pode ser candidato para quase-duplicatas e Essentia para descritores musicais em lote, mediante qualificação separada. O *fingerprint* não prova semelhança de gênero, e métricas de áudio não provam qualidade artística.

## A15 permanece exclusivamente controle

O catálogo **não** varre o A15, não instala scanners nele, não pede USB e não cria novos Codespaces. A mídia só poderá ser lida quando as pastas selecionadas estiverem acessíveis **de modo autorizado e somente leitura na workstation já existente**, ou forem disponibilizadas por um transporte privado posteriormente aprovado. Gmail não é sinônimo de autorização para enviar mensagens/anexos a terceiros. O sistema não faz login, acesso a e-mails, cópia para a nuvem, publicação, treinamento ou fine-tune.

Não executar scanners em qualquer diretório não delimitado. Projetos com WIP não devem ser alterados. Nenhum arquivo é renomeado, movido, apagado, substituído ou sincronizado automaticamente. **Não guardar JSON privado, amostras, stems, e-mails, nomes reais ou caminhos do proprietário dentro do repositório Git ou de artefatos públicos do CI.**

## Operação real: inventário, seleção e memória de estilo

As ordens abaixo se aplicam **somente à workstation autorizada onde a mídia estiver disponível**, não ao A15 nem ao GitHub Actions. Caminhos são ilustrativos; confirmar raiz montada e direitos antes de executar.

\`\`\`bash
# Executar dentro do checkout Hazewave autorizado, com PYTHONPATH apropriado.
# ROOT é uma pasta privada do acervo disponibilizada somente leitura na workstation.
ROOT=/path/privado/musicas
PRIVATE=/path/privado/recibos-haze

# Etapa 1: apenas estatísticas e índice de arquivos (sem ler bytes do áudio).
PYTHONPATH=src python -m hazewave.haze_catalog inventory \
  --root "$ROOT" --output "$PRIVATE/catalog-v1.json" \
  --allow-private-corpus --max-files 5000

# Caso precise detecção de arquivos byte-a-byte idênticos e memória acústica
# aprovada posteriormente, habilitar hashing limitado, sob nova saída privada.
PYTHONPATH=src python -m hazewave.haze_catalog inventory \
  --root "$ROOT" --output "$PRIVATE/catalog-hashed-v1.json" \
  --allow-private-corpus --max-files 5000 --hash-max-mb 256
\`\`\`

\`--hash-max-mb\` controla **o tamanho máximo de cada arquivo de áudio elegível ao hashing**; não transfere mídia. O padrão 0 executa apenas inventário estrutural, com custo baixo de leitura. Arquivos maiores permanecem indexados, mas sem digest e portanto sem admissão para análise de referência nessa versão. O limite de 5.000 arquivos falha fechado se ultrapassado: fracionar por projetos, **nunca** aceitar índice parcial como catálogo completo. Auditar espaço, CPU, RAM e disponibilidade do armazenamento antes do processamento.

Para criar a memória acústica, uma curadoria humana deverá preparar o arquivo **privado** \`$PRIVATE/approved-references.json\`. Os caminhos relativos têm de corresponder ao catálogo privado com SHA256 previamente calculado; tags e papéis são do proprietário:

\`\`\`json
[
  {
    "relative_path": "PROJETO_EXEMPLO/mix_aprovada.wav",
    "owner_genre": "ESTILO_DEFINIDO_PELO_PROPRIETARIO",
    "reference_role": "MIX_REFERENCE",
    "owner_approved": true,
    "rights_confirmed": true
  }
]
\`\`\`

\`\`\`bash
PYTHONPATH=src python -m hazewave.haze_catalog curate \
  --root "$ROOT" --catalog "$PRIVATE/catalog-hashed-v1.json" \
  --selections "$PRIVATE/approved-references.json" \
  --output "$PRIVATE/style-memory-v1.json" \
  --allow-private-corpus
\`\`\`

Papéis aceitos: \`MIX_REFERENCE\`, \`MASTER_REFERENCE\`, \`ARRANGEMENT_REFERENCE\`, \`BEAT_REFERENCE\`, \`SOUND_DESIGN_REFERENCE\`, \`VOCAL_REFERENCE\`. Até 16 referências por operação, apenas áudio local, nunca uma pasta inteira como treinamento implícito. O sistema valida hashes, diretórios, gêneros explícitos e permissão da pessoa responsável; acessos por links simbólicos são negados. A análise acústica usa a implementação existente \`reference_profile\` e \`audio_qc\`. Para arquivos longos, só o trecho central fornece feições espectrais/estéreo/transientes: **não inferir** que toda a faixa foi caracterizada por essas feições. Métricas EBU R128 são computadas a partir do programa completo conforme o analisador existente.

Todos os recibos são JSON local com permissões 0600, criados fora da pasta original com escrita atômica e sem sobrescrever arquivo pré-existente. Não há chamada de LLM, REAPER, ACE-Step ou acesso de rede por essas duas operações. A presença de uma referência aprovada **não significa** que o proprietário autorizou fine-tune, treinamento de peso neural, reprodução de obra, treinamento com vocais ou exportação privada.

## Curadoria profissional e competência futura no REAPER

1. Organizar **virtualmente**, preservando arquivos físicos: projeto → sessão → faixa/take → versão → função (demo, instrumental, stems, mix, master) → estilo declarado → fase/revisão humana. Nunca escolher automaticamente "a versão melhor" pelo nome \`final\` ou pelo LUFS.
2. Fazer revisão humana sobre exemplos variados de cada estilo, comparações niveladas (loudness-matched), consentimento de colaboradores e separação de faixas para validação cega. Distinguir produção original de referência externa ou sample licenciado.
3. Construir memória de decisões auditadas: o que o proprietário prefere, quando, por gênero, por intenção musical, com revisões aprovadas/rejeitadas e links para medições. Não reduzir todo o acervo a presets globais.
4. Somente depois acoplar a memória ao Harness para **propor** ações tipadas no REAPER: sessão real, snapshot, checkpoint, prévia, QC, A/B, rollback e revisão humana antes de modificar projeto real.
5. Só declarar aptidão artística/profissional após provas na DAW instalada, outputs reais e audições independentes. A superioridade ao Suno não foi demonstrada. Música generativa (ACE-Step) e mixagem/masterização no REAPER são capacidades distintas.

**Estado atual:** código de inventário e perfil de áudio para candidatos; nenhuma pasta do proprietário consumida, nenhuma música privada treinada, nenhum REAPER de proprietário modificado. PR draft até resultados de CI e revisão. 
