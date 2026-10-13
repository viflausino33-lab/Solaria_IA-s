# ADR 0002 — rotear antes de paralelizar

- **Status:** aceito para MVP
- **Data:** 2026-10-13

## Contexto

Enviar o mesmo prompt a todos os modelos maximiza a quantidade de opiniões, mas multiplica chamadas, contexto, latência total e requisitos de memória. Não é compatível com o princípio de usar os menores recursos possíveis.

## Decisão

A execução padrão usa uma chamada. A revisão sequencial é opcional e acionada por pedido, criticidade ou sinal de incerteza. MoA/paralelismo só será implementado após demonstrar melhoria em dados de avaliação; terá limites explícitos.

## Consequências

A arquitetura precisa observar o motivo de cada escalonamento e parar cedo quando a resposta atende aos critérios. Benchmarks devem comparar qualidade vs. recursos, não qualidade isolada.
