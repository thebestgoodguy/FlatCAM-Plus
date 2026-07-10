# Cutout Tool — Detecção Automática de Contornos Internos

## Contexto

O Cutout Tool do FlatCAM Plus gera toolpaths para cortar PCBs do material. Quando um Gerber de profile contém múltiplos contornos (ex: outline externo + slot/recorte interno), o tool atual aplica offset "outside" uniformemente em todos os polígonos.

Isso resulta em recortes internos cortados pelo lado errado — a fresa remove material da placa em vez de abrir o furo no tamanho correto.

### Problema Visual

```
Comportamento ATUAL (errado para slots internos):
┌─────────────────────┐
│  PCB                │
│    ┌─────┐          │
│    │SLOT │←fresa    │  ← Fresa FORA do slot = tira material da placa
│    └─────┘          │
│                     │
└─────────────────────┘
     ↑ fresa          ← Fresa FORA do contorno = correto para exterior

Comportamento DESEJADO:
┌─────────────────────┐
│  PCB                │
│    ┌─────┐          │
│    │fresa→│         │  ← Fresa DENTRO do slot = abre o furo corretamente
│    └─────┘          │
│                     │
└─────────────────────┘
     ↑ fresa          ← Fresa FORA do contorno = correto para exterior
```

### Causa Raiz

Em `ToolCutOut.py`, no bloco `kind != 'single'` (Panel mode), o código itera cada polígono e aplica:
```python
geom_struct = (geom_struct.buffer(margin + abs(cut_dia / 2))).exterior
```

Usa `.exterior` para TODOS os polígonos, sem distinguir se o contorno é exterior (borda da placa) ou interior (furo/slot).

---

## Requisitos Funcionais

### REQ-01: Detecção automática de contornos internos
Quando o Cutout Tool processa um Gerber com múltiplos polígonos (Kind=Panel), deve automaticamente identificar quais polígonos são contornos internos (contidos dentro de outro polígono maior) e quais são contornos externos.

### REQ-02: Offset invertido para contornos internos
Contornos classificados como internos devem receber offset para DENTRO do furo (usar `.interiors[0]` do buffer em vez de `.exterior`), garantindo que o recorte fique no tamanho exato do design.

### REQ-03: Zero regressão para polígono único
Quando o Gerber contém apenas um polígono (caso mais comum — outline simples sem slots), o comportamento deve ser idêntico ao atual. Nenhum contorno é classificado como "interior" quando há apenas um polígono.

### REQ-04: Zero regressão para painéis reais
Quando o Gerber contém múltiplos polígonos que NÃO estão contidos um dentro do outro (painel com várias PCBs lado a lado), todos devem continuar sendo tratados como exteriores — comportamento idêntico ao atual.

### REQ-05: Transparência — sem mudança de UI
A detecção deve ser automática e sempre ativa no modo Panel com >1 polígono. Não requer checkbox, radio button, ou qualquer configuração adicional do usuário.

### REQ-06: Fallback seguro
Se a geometria de um contorno interno não produz `.interiors` válidos após o buffer (edge case de geometria aberta ou degenerada), deve fazer fallback para `.exterior` e emitir um log warning — nunca falhar silenciosamente nem crashar.

### REQ-07: Suporte a múltiplos slots
Uma placa pode ter mais de um recorte interno (ex: 2 slots + 1 outline). Todos os slots devem ser detectados e processados corretamente.

---

## Requisitos Não-Funcionais

### REQ-08: Performance
A detecção de containment deve completar em tempo imperceptível para o usuário. PCBs típicas têm 2-5 polígonos no profile — complexidade O(n) é suficiente.

### REQ-09: Compatibilidade
- Não deve alterar o comportamento de Kind=Single
- Não deve alterar o comportamento quando margin < 0 (já funciona diferente)
- Não deve afetar outros plugins (Isolation, Milling, etc.)
- Deve funcionar com Gerbers de qualquer CAD (Fusion 360, KiCad, EasyEDA, EAGLE)

### REQ-10: Manutenibilidade
O código adicionado deve ser isolado em uma função helper (ex: `_classify_interior_exterior()`) para facilitar testes e manutenção futura.

---

## Cenários de Teste

| Cenário | Input | Resultado Esperado |
|---------|-------|-------------------|
| Outline simples (1 polígono) | Gerber com 1 contorno | Offset outside, idêntico ao atual |
| Outline + 1 slot interno | Gerber com 2 contornos (externo contém interno) | Externo: offset outside. Interno: offset inside |
| Outline + 3 slots internos | Gerber com 4 contornos | Externo: outside. 3 internos: inside |
| Painel (2 PCBs lado a lado) | Gerber com 2 contornos sem containment | Ambos: offset outside |
| Slot tocando a borda | Gerber com slot que intersecta o outline | Slot não está "contido" → tratado como externo |
| Polígono único + margin negativo | 1 contorno com margin < 0 | Comportamento atual (usa .interiors) — sem mudança |
| Gerber com geometry aberta | Path não fechado | Fallback para .exterior com warning |

---

## Fora de Escopo

- Detecção de nesting multinível (contorno dentro de contorno dentro de contorno) — limitar a 1 nível
- Mudanças na UI (nenhum widget novo)
- Mudanças no parser de Gerber
- Mudanças no Kind=Single
- Suporte a painel com detecção automática de PCBs individuais (isso é outra feature)
