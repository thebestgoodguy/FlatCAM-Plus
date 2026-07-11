# Design — Cutout Auto Interior Detection

## Arquitetura da Solução

A mudança é localizada em um único arquivo (`appPlugins/ToolCutOut.py`) e consiste em:
1. Uma função helper de classificação
2. Modificação do loop de processamento no bloco `kind != 'single'`

Nenhuma mudança estrutural no projeto. Nenhuma dependência nova.

---

## Componentes Afetados

```
appPlugins/ToolCutOut.py
  └── class CutOut
       ├── _classify_contours(object_geo) → dict[int, bool]    [NOVO]
       └── on_freeform_cutout()                                 [MODIFICADO]
```

---

## Função Helper: `_classify_contours`

```python
def _classify_contours(self, geometries: list) -> set:
    """
    Classifica polígonos como internos (contidos dentro de outro polígono maior).
    
    Args:
        geometries: Lista de polígonos (output de flatten_shapely_geometry)
    
    Returns:
        Set de índices dos polígonos classificados como internos.
        Polígonos não presentes no set são considerados externos.
    """
```

### Algoritmo

```
1. Se len(geometries) <= 1:
     return set()  # Nada a classificar

2. Para cada polígono, calcular a área do Polygon preenchido (Polygon(geo.exterior))
   - Isso transforma a "faixa estreita" (buffered LineString) em polígono sólido

3. Encontrar o polígono com MAIOR área preenchida → exterior_candidate

4. Criar versão preenchida do exterior: exterior_filled = Polygon(exterior_candidate.exterior)

5. Para cada outro polígono (index i):
   a. Obter representative_point() do polígono
   b. Se exterior_filled.contains(representative_point):
        → Marcar index i como INTERIOR
   c. Senão:
        → Manter como EXTERIOR (não adicionar ao set)

6. Retornar set de índices interiores
```

### Por que `representative_point()` em vez de `contains(polygon)`

Os polígonos do Gerber são faixas estreitas (LineString bufferizada com aperture width ≈ 0.254mm). O `Polygon.contains(other_polygon)` pode retornar False porque a faixa do slot interno pode ter partes fora do exterior preenchido (nas bordas, devido ao buffer). Usar `representative_point()` (ponto garantidamente dentro do polígono) é mais robusto para testar "este polígono está geograficamente dentro do outro?".

### Por que `Polygon(geo.exterior)` para preencher

A solid_geometry do Gerber de profile é uma faixa oca (anel fino). Para testar containment, precisamos de um polígono PREENCHIDO (sem furo no meio). `Polygon(geo.exterior)` cria o polígono sólido a partir do contorno externo da faixa.

---

## Modificação do Loop de Processamento

### Código Atual (linhas ~790-798 de ToolCutOut.py)

```python
object_geo = flatten_shapely_geometry(object_geo)
for geom_struct in object_geo:
    if cutout_obj.kind == 'gerber':
        if margin >= 0:
            geom_struct = (geom_struct.buffer(margin + abs(cut_dia / 2))).exterior
        else:
            geom_struct_buff = geom_struct.buffer(-margin + abs(cut_dia / 2))
            geom_struct = geom_struct_buff.interiors
```

### Código Proposto

```python
object_geo = flatten_shapely_geometry(object_geo)

# Classificar contornos internos vs externos
interior_indices = self._classify_contours(object_geo)

for i, geom_struct in enumerate(object_geo):
    if cutout_obj.kind == 'gerber':
        if margin >= 0:
            buffered = geom_struct.buffer(margin + abs(cut_dia / 2))
            if i in interior_indices:
                # Recorte interno: offset para dentro do furo
                if buffered.interiors:
                    geom_struct = buffered.interiors[0]
                else:
                    # Fallback: se não tem interiors, usar exterior com warning
                    self.app.log.warning(
                        "Cutout: interior contour %d has no interiors after buffer. "
                        "Using exterior as fallback." % i)
                    geom_struct = buffered.exterior
            else:
                # Contorno externo: offset para fora da placa
                geom_struct = buffered.exterior
        else:
            geom_struct_buff = geom_struct.buffer(-margin + abs(cut_dia / 2))
            geom_struct = geom_struct_buff.interiors
```

---

## Diagrama de Fluxo

```
on_freeform_cutout()
    │
    ├── kind == 'single' → fluxo atual (sem mudança)
    │
    └── kind != 'single' (Panel)
         │
         ├── flatten_shapely_geometry(object_geo)
         │
         ├── _classify_contours(object_geo) → interior_indices  [NOVO]
         │
         └── for i, geom_struct in enumerate(object_geo):
              │
              ├── margin >= 0:
              │    ├── i in interior_indices → buffered.interiors[0]  [NOVO]
              │    └── i NOT in interior_indices → buffered.exterior  [EXISTENTE]
              │
              └── margin < 0: → fluxo atual (sem mudança)
```

---

## Tratamento de Edge Cases

| Case | Detecção | Ação |
|------|----------|------|
| 1 polígono | `len(geometries) <= 1` | Return set() → zero mudança |
| Múltiplos polígonos sem containment (painel) | `contains()` retorna False para todos | Set vazio → todos tratados como exteriores |
| Slot tocando borda | `representative_point()` pode estar fora do exterior | Tratado como externo (correto) |
| Geometry aberta (sem interiors após buffer) | `buffered.interiors` é vazio | Fallback para `.exterior` + log warning |
| Polígonos degenerados | `representative_point()` levanta exceção | try/except → tratado como externo |

---

## Impacto em Outros Fluxos

| Fluxo | Impacto |
|-------|---------|
| Kind = Single | NENHUM — código não é alcançado |
| Margin < 0 | NENHUM — branch separado, não afetado |
| Mouse bites | NENHUM — processado depois, usa mesma lógica sem _classify |
| Gaps/Bridges | NENHUM — aplicados depois via any_cutout_handler() |
| Geometry (não Gerber) | NENHUM — branch `else` separado, não afetado |
| geo_init (gerar CNCJob) | NENHUM — recebe solid_geo já processado |

---

## Dependências

- **Shapely >= 2.0** (já em uso): `Polygon`, `representative_point()`, `contains()`
- Nenhuma dependência nova

---

## Riscos Residuais

1. **Gerber com polígono "interno" que na verdade é uma marca/logo:** Raro em layer de profile, mas possível. Mitigação: funciona corretamente se o polígono está contido — o offset inside é semanticamente correto para qualquer shape que deve ser "recortada" da placa.

2. **Performance com muitos polígonos:** Teórico — PCBs com >20 slots no profile são extremamente raros. Se necessário no futuro, usar STRtree para queries espaciais O(log n).
