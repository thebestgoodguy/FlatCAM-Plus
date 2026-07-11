# Tasks — Cutout Auto Interior Detection

## Implementação

### Task 1: Criar função helper `_classify_contours`
- **Arquivo:** `appPlugins/ToolCutOut.py`
- **Localização:** Método da classe `CutOut`, antes de `on_freeform_cutout()`
- **Ação:** Implementar a função que recebe lista de geometrias e retorna set de índices interiores
- **Critério de aceite:** Função retorna set vazio para 1 polígono, retorna índices corretos para 2+ polígonos com containment

### Task 2: Modificar loop de processamento em `on_freeform_cutout()`
- **Arquivo:** `appPlugins/ToolCutOut.py`
- **Localização:** Bloco `else` (kind != 'single'), linhas ~790-798
- **Ação:** 
  - Adicionar chamada a `_classify_contours()` antes do loop
  - Converter `for geom_struct` em `for i, geom_struct in enumerate()`
  - Dentro do `if margin >= 0:`, bifurcar entre `.exterior` e `.interiors[0]` conforme classificação
  - Adicionar fallback com log warning para interiors vazio
- **Critério de aceite:** Gerber com outline + slot interno gera paths com offsets corretos (outside para exterior, inside para slot)

### Task 3: Adicionar import de `Polygon` no topo do arquivo
- **Arquivo:** `appPlugins/ToolCutOut.py`
- **Localização:** Bloco de imports (topo do arquivo)
- **Ação:** Verificar se `Polygon` da Shapely já está importado. Se não, adicionar.
- **Critério de aceite:** Sem ImportError ao usar `Polygon(geo.exterior)`

### Task 4: Testar com Gerber do usuário (Fusion 360 — engrenagem + slot triangular)
- **Ação:** 
  - Importar o Gerber de profile no FlatCAM Plus
  - Executar Cutout com Kind=Panel
  - Verificar visualmente que o contorno externo tem offset outside e o slot interno tem offset inside
- **Critério de aceite:** Ambos os toolpaths estão do lado correto conforme imagem de referência

### Task 5: Testar regressão — Gerber com polígono único
- **Ação:**
  - Importar Gerber de profile simples (retangular ou curvo, sem slots)
  - Executar Cutout com Kind=Panel e Kind=Single
  - Verificar que resultado é idêntico ao comportamento anterior
- **Critério de aceite:** Zero diferença no toolpath gerado vs versão sem a modificação

### Task 6: Testar regressão — Painel com múltiplas PCBs
- **Ação:**
  - Importar Gerber de painel com 2+ outlines lado a lado (sem containment)
  - Executar Cutout com Kind=Panel
  - Verificar que TODOS os contornos recebem offset outside
- **Critério de aceite:** Comportamento idêntico ao anterior para painéis reais

### Task 7: Testar edge case — Gerber com slot tocando borda
- **Ação:**
  - Criar ou encontrar Gerber com slot que intersecta o outline externo
  - Executar Cutout
  - Verificar que slot não é classificado como "interior"
- **Critério de aceite:** Slot tratado como contorno externo (offset outside)

---

## Ordem de Execução

```
Task 3 (import) → Task 1 (helper) → Task 2 (loop) → Task 4 (teste principal) → Task 5-7 (regressão)
```

---

## Estimativa

| Task | Esforço |
|------|---------|
| Task 1 | 15 min |
| Task 2 | 15 min |
| Task 3 | 2 min |
| Task 4 | 10 min |
| Task 5-7 | 15 min |
| **Total** | **~1 hora** |
