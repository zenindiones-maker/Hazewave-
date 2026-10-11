# Padrões de análise binária — RECON-REVENG-002

Fontes de código lidas: LIEF src/ELF/Parser.cpp e icedland/iced src/rust/iced-x86/src/decoder.rs; não constitui deep dive de todos os repos.

1. Header: magic, version/class, endianness sempre antes de interpretar campos.
2. ELF 32/64: machine, entry point e separação de program headers, section headers, segments.
3. PE: validar MZ, e_lfanew e PE signature; distinguir COFF, optional header e RVA.
4. Mach-O: magic + endian + width; load commands precisam de validação de bounds.
5. Disassembler depende de ISA, modo, estado de decoder, prefixos e comprimento de instrução.
6. Observação (bytes, offsets) diferente de inferência (comportamento/algoritmo).
7. Execução dinâmica: só isolada, autorizada e sem credenciais; identificar um binário não autoriza executá-lo.

Fontes: https://github.com/lief-project/LIEF/blob/main/src/ELF/Parser.cpp
https://github.com/icedland/iced/blob/master/src/rust/iced-x86/src/decoder.rs
