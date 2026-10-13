# ADR 0001 — local-first e orçamento fechado

- **Status:** aceito para MVP
- **Data:** 2026-10-13

## Contexto

O objetivo central é limitar custo externo e consumo de memória, sem tornar a qualidade incontrolável. Serviços pagos são opcionais e podem enviar dados a terceiros.

## Decisão

- Modo padrão `mock`; Ollama é ativado de forma explícita.
- Cloud desabilitado até existir catálogo de preço versionado e guardião de orçamento testado.
- Privacidade `local_only` nunca pode ser silenciosamente alterada.
- Um único modelo local e uma chamada concorrente por padrão.

## Consequências

O início do desenvolvimento é seguro e testável sem chave/API. A colaboração multi-provedor demora mais a chegar, mas não se acumula complexidade/custo antes de existir baseline.
