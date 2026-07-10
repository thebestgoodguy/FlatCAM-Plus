---
inclusion: auto
---

# FlatCAM Plus — Log de Cognição Evolutiva

Este arquivo é um registro vivo de descobertas feitas durante o uso do FlatCAM Plus.
Cada entrada documenta uma diferença, comportamento inesperado, workaround ou
insight que não estava mapeado nos steerings anteriores.

---

## Como Usar Este Log

**Para o agente:**
- Quando o usuário descobrir algo novo (diferença, bug, workaround, recurso oculto),
  adicione uma entrada aqui seguindo o template abaixo.
- Periodicamente, entradas maduras devem ser consolidadas nos steerings principais
  (`flatcam-feature-map.md` ou `flatcam-plus-optimizations.md`).
- Marque entradas consolidadas com `[CONSOLIDADO]` no status.

**Para o usuário:**
- Diga "aprenda isso" ou "registra essa diferença" quando quiser que eu adicione ao log.
- Diga "o que já aprendemos?" para eu listar as entradas ativas.
- Diga "consolida o log" para eu mover entradas maduras para os steerings principais.

---

## Template de Entrada

```
### EVO-XXX: [Título curto]

- **Data:** YYYY-MM-DD
- **Status:** ATIVO | CONSOLIDADO | OBSOLETO
- **Contexto:** Como foi descoberto (pergunta do usuário, tentativa, erro, etc.)
- **Versão 8.994:** [Como era / como fazia no antigo — ou "N/A" se não existia]
- **FlatCAM Plus:** [Como é / como funciona no Plus]
- **Diferença-chave:** [A diferença prática em uma frase]
- **Otimização?** SIM/NÃO — [Se SIM, qual OPT-XX relaciona ou sugerir novo]
- **Impacto:** ALTO / MÉDIO / BAIXO
- **Tags:** #ui #workflow #cnc #isolation #probe #gcode #preferences #bug #workaround
```

---

## Entradas

### EVO-001: Seção Mouse Settings oculta no Preferences

- **Data:** 2026-07-04
- **Status:** ATIVO
- **Contexto:** Usuário queria trocar o botão de pan (RMB → MMB). A opção existe no código mas está escondida com `.hide()` na UI simplificada.
- **Versão 8.994:** Preferences → General → App Settings → Pan Button (MMB/RMB) — visível e acessível.
- **FlatCAM Plus:** A seção "Mouse Settings" (Pan Button, Cursor Shape, Multi-Selection) foi ocultada no commit `6c7afe2` como parte da simplificação da UI. O código funciona, só não aparece.
- **Diferença-chave:** Preferências de mouse existem mas estão ocultas. Alterar via arquivo `current_defaults_1.1.0.FlatConfig` em `%APPDATA%\FlatCAM\`.
- **Otimização?** NÃO — é uma regressão de acessibilidade na UI.
- **Impacto:** MÉDIO
- **Tags:** #preferences #ui #workaround
- **Workaround:** Editar `global_pan_button` de `"2"` para `"3"` diretamente no arquivo `C:\Users\<user>\AppData\Roaming\FlatCAM\current_defaults_1.1.0.FlatConfig`. Ou descomentar `.hide()` em `GeneralAPPSetGroupUI.py` linhas do `m_frame` e `mouse_lbl`.

---

### EVO-002: Build standalone falha com OR-Tools (_pywrapcp)

- **Data:** 2026-07-04
- **Status:** ATIVO
- **Contexto:** Após recompilar com `build_standalone.ps1`, o exe falha com "DLL load failed while importing _pywrapcp".
- **Versão 8.994:** Não usa OR-Tools. Build mais simples.
- **FlatCAM Plus:** `camlib.py` importa `ortools.constraint_solver.pywrapcp`. O PyInstaller não empacota as DLLs nativas do OR-Tools corretamente.
- **Diferença-chave:** O exe antigo (`dist\windows\x64\`) funciona; o rebuild (`dist\standalone\`) não. São diretórios diferentes.
- **Otimização?** NÃO — problema de build/packaging.
- **Impacto:** ALTO (impede uso do exe recompilado)
- **Tags:** #build #bug #workaround
- **Workaround:** Usar o exe pré-compilado em `dist\windows\x64\FlatCAMPlus\FlatCAMPlus.exe`. Para rodar dos fontes, usar o venv de build (`c:\temp\fcvenv\Scripts\python.exe flatcam.py`) — o venv local do projeto não tem PyQt6 instalado.

---

### EVO-003: Venv local não tem dependências instaladas

- **Data:** 2026-07-04
- **Status:** ATIVO
- **Contexto:** Tentativa de rodar `venv\Scripts\python.exe flatcam.py` falha com "No module named 'PyQt6'".
- **Versão 8.994:** N/A
- **FlatCAM Plus:** O `build_standalone.ps1` cria um venv separado em `c:\temp\fcvenv` com todas as deps. O `venv\` local do repositório está vazio/incompleto.
- **Diferença-chave:** Para rodar dos fontes, usar `c:\temp\fcvenv\Scripts\python.exe flatcam.py` (se o build foi executado pelo menos uma vez) ou instalar deps no venv local com `pip install -r requirements.txt`.
- **Otimização?** NÃO
- **Impacto:** BAIXO
- **Tags:** #build #workaround

---

### EVO-004: Preferences salvas em arquivo versionado

- **Data:** 2026-07-04
- **Status:** ATIVO
- **Contexto:** Ao procurar onde as preferências são salvas para edição manual.
- **Versão 8.994:** `%APPDATA%\FlatCAM\current_defaults.FlatConfig` (JSON)
- **FlatCAM Plus:** `%APPDATA%\FlatCAM\current_defaults_1.1.0.FlatConfig` (JSON versionado)
- **Diferença-chave:** O nome do arquivo inclui a versão. Factory defaults também: `factory_defaults_1.1.0.FlatConfig`.
- **Otimização?** NÃO — apenas mudança de nomenclatura.
- **Impacto:** BAIXO
- **Tags:** #preferences #filesystem

---

### EVO-005: Generate With Copper — detecção automática de pours

- **Data:** 2026-07-04
- **Status:** ATIVO
- **Contexto:** Usuário perguntou se "Generate With Copper" cria copper pours do nada.
- **Versão 8.994:** Não existia. Isolation sempre gerava paths ao redor de tudo.
- **FlatCAM Plus:** `_is_copper_pour_geometry()` detecta pours por critérios geométricos: polígono ≥55% da largura/altura da placa, ou com interiors (clearance holes) e ≥8% da área total. Isola apenas clearances internos e filtra frames.
- **Diferença-chave:** Não cria pours — reconhece pours existentes no Gerber e evita fresar suas bordas externas desnecessariamente.
- **Otimização?** SIM — OPT-05
- **Impacto:** MÉDIO
- **Tags:** #isolation #workflow #copper

---

### EVO-007: Conexão CNC persistente em arquivo JSON separado

- **Data:** 2026-07-04
- **Status:** ATIVO
- **Contexto:** Usuário perguntou se a configuração de IP da CNC é persistente.
- **Versão 8.994:** N/A — não tinha conexão CNC.
- **FlatCAM Plus:** As configurações de conexão são salvas em `%APPDATA%\FlatCAM\cnc_connection_settings.json`. Inclui modo (serial/tcp/web), profile, host, porta, baudrate, auto_connect. Persiste entre sessões.
- **Diferença-chave:** Arquivo separado das preferences principais. Não fica dentro do `current_defaults_1.1.0.FlatConfig`.
- **Otimização?** NÃO — apenas informação de localização.
- **Impacto:** BAIXO
- **Tags:** #cnc #preferences #filesystem

---

### EVO-016: Fix definitivo para OR-Tools — testar DefaultRoutingSearchParameters() no import

- **Data:** 2026-07-06
- **Status:** ATIVO
- **Contexto:** O except no topo de camlib.py só pegava ModuleNotFoundError no import de pywrapcp/routing_enums_pb2. Mas esses imports passam — o que falha é DefaultRoutingSearchParameters() internamente por falta de routing_parameters_pb2. O except Exception no caller deveria pegar mas por alguma razão no exe não pega.
- **Versão 8.994:** Não usava OR-Tools.
- **FlatCAM Plus:** Fix aplicado em camlib.py: adicionado `pywrapcp.DefaultRoutingSearchParameters()` no bloco try do import. Se falhar (qualquer Exception), HAS_ORTOOLS=False e o código usa RTree automaticamente para qualquer opt_type B ou M.
- **Diferença-chave:** Com o fix no fonte, rodar via `c:\temp\fcvenv\Scripts\python.exe flatcam.py` funciona sem OR-Tools. O exe pré-compilado não é afetado (fontes empacotados internamente).
- **Otimização?** NÃO — fix de bug.
- **Impacto:** ALTO (desbloqueia drilling para rodar dos fontes)
- **Tags:** #drilling #bug #ortools #fix #camlib
- **Arquivo modificado:** `c:\dsn\CNC\FlatCAM-Plus\camlib.py` (bloco HAS_ORTOOLS no topo)

---

### EVO-017: Cutout com contorno não-retangular — workflow correto (REVISADO)

- **Data:** 2026-07-09 (revisado)
- **Status:** ATIVO
- **Contexto:** Usuário tentou cortar placa pelo contorno real (não retangular) usando Cutout Tool. Investigação do código-fonte (`ToolCutOut.py`) revelou comportamento condicional.
- **Versão 8.994:** Cutout Tool com Gerber profile funcionava direto para contornos não-retangulares (opção Outside explícita).
- **FlatCAM Plus:** O Cutout Tool **funciona** para contornos não-retangulares MAS com condição: o Gerber precisa ser um **Polygon único** (não MultiPolygon). Se `isinstance(object_geo, MultiPolygon)` → o código faz `box()` (bounding box retangular). Se é Polygon simples → faz `buffer(margin + cut_dia/2)` no contorno real, preservando a forma.
- **Diferença-chave:** O Cutout Tool do Plus funciona para formas não-retangulares se o Gerber de contorno for um único polígono fechado. Um arquivo Edge_Cuts.gbr bem feito (contorno único) funciona corretamente. MultiPolygon (múltiplos contornos) vira bounding box.
- **Workflow correto:** Tools → Cutout, Source = Gerber profile (Edge_Cuts), Kind = Single, Margin = 0, Multi-Depth = ativado, Depth per pass = 0.5-0.6mm. Com margin=0, o buffer aplica `cut_dia/2` para fora → peça fica no tamanho exato do Gerber.
- **CORREÇÃO sobre Isolation:** A sugestão anterior de usar Isolation Routing como workaround é **incorreta para cutout** porque Isolation NÃO tem multi-depth nativo. O Cutout Tool tem (`tools_cutout_mdepth` + `tools_cutout_depthperpass`). Usar Isolation para cutout obrigaria passada única = risco de quebrar fresa.
- **Otimização?** NÃO — mas é importante saber que Cutout > Isolation para profile cut.
- **Impacto:** ALTO (workflow fundamental para PCBs não-retangulares)
- **Tags:** #cutout #workflow #workaround #multidepth
- **Código-fonte confirmado:** `ToolCutOut.py` linhas 750-753 (MultiPolygon → box) e 755-757 (Polygon → buffer correto). Geo_init nas linhas 893-894 confirma `tools_mill_multidepth` e `tools_mill_depthperpass` passados ao Milling.

---

### EVO-016: Janela maximizada corta conteúdo dos lados (DPI/geometry bug)

- **Data:** 2026-07-06
- **Status:** ATIVO
- **Contexto:** Ao rodar dos fontes via venv, a janela maximizada excede os limites da tela, cortando conteúdo dos lados. Minimizar e maximizar novamente corrige.
- **Versão 8.994:** Não tinha esse problema (PyQt5, DPI handling diferente).
- **FlatCAM Plus:** PyQt6 com QSettings salvando geometry de janela que pode não respeitar DPI scaling. O estado salvo no registro `HKCU\Software\Open Source\FlatCAM_Plus` pode conter dimensões inválidas.
- **Diferença-chave:** PyQt6 lida com DPI de forma diferente do PyQt5. Geometry salva pode ficar inconsistente.
- **Otimização?** NÃO — bug de UI/DPI.
- **Impacto:** BAIXO (workaround simples: minimizar/maximizar)
- **Tags:** #ui #bug #workaround #dpi
- **Workaround:** Limpar geometry salva: `Remove-ItemProperty -Path 'HKCU:\Software\Open Source\FlatCAM_Plus' -Name 'geometry'` e `windowState`. Ou forçar DPI override no atalho: Compatibilidade → "Substituir comportamento de dimensionamento de DPI alto" → "Aplicativo".

---

### EVO-015: Preferences EXCELLON não expõe Optimization Type na UI

- **Data:** 2026-07-06
- **Status:** ATIVO
- **Contexto:** Ao procurar Optimization Type nas Preferences → EXCELLON para resolver EVO-014 pela UI.
- **Versão 8.994:** Preferences → Excellon → Optimization Type era visível (opções: MetaHeuristic, Basic, TSA, R-Tree).
- **FlatCAM Plus:** A opção foi removida/oculta da UI simplificada. Preferences → EXCELLON mostra apenas: Plot Options, Excellon Format, Mill Holes, Export Options. Não há como trocar o tipo de otimização de drill path pela interface.
- **Diferença-chave:** Combinada com EVO-014, torna impossível resolver o crash de OR-Tools sem: (1) editar FlatConfig com app fechado + criar projeto novo, ou (2) editar o factory_defaults, ou (3) editar fonte.
- **Otimização?** NÃO — regressão de acessibilidade.
- **Impacto:** ALTO (bloqueia drilling para projetos existentes)
- **Tags:** #preferences #excellon #drilling #ui #bug

---

### EVO-014: OR-Tools quebrado no exe — drill optimization falha com 'B'

- **Data:** 2026-07-06
- **Status:** ATIVO
- **Contexto:** Ao gerar CNC Job de drilling, erro "No module named 'ortools.constraint_solver.routing_parameters_pb2'". O exe pré-compilado tem OR-Tools incompleto.
- **Versão 8.994:** Usava TSA (nearest-neighbor) por padrão. Sem dependência de OR-Tools.
- **FlatCAM Plus:** Default `excellon_optimization_type: "B"` (OR-Tools Basic). Falha no exe empacotado. Alternativas que funcionam: `"T"` (TSA nearest-neighbor) ou `"N"` (sem otimização).
- **Diferença-chave:** Trocar `excellon_optimization_type` de `"B"` para `"T"` no FlatConfig resolve. Diferença prática mínima para PCBs com <100 furos.
- **Otimização?** NÃO — workaround para bug de packaging.
- **Impacto:** ALTO (impede geração de CNC Job de drilling sem o fix)
- **Tags:** #drilling #bug #workaround #ortools
- **Workaround:** Editar `C:\Users\<user>\AppData\Roaming\FlatCAM\current_defaults_1.1.0.FlatConfig` e trocar `"excellon_optimization_type": "B"` para `"excellon_optimization_type": "R"` (RTree, não toca OR-Tools). **IMPORTANTE:** Fechar o FlatCAM ANTES de editar o arquivo — o app sobrescreve o FlatConfig ao sair com os valores em memória. Sequência: fechar app → editar arquivo → abrir app. **ATENÇÃO:** Projetos .FlatPrj e tool data carregam o valor de opt_type salvo por tool no momento da criação, ignorando o FlatConfig. Se o projeto foi criado com "B", o fix no FlatConfig não ajuda para objetos existentes. **Solução definitiva:** Criar projeto novo após alterar FlatConfig — novos objetos herdam o default correto. Projetos antigos continuam com "B" nos tool data internos.
- **Análise técnica (CONFIRMADA):** O exe distribuído (`dist\windows\x64\`) tem o diretório `_internal\ortools\constraint_solver\` com APENAS `_pywrapcp.pyd` (binário nativo). Faltam TODOS os wrappers Python: `__init__.py`, `pywrapcp.py`, `routing_enums_pb2.py`, `routing_parameters_pb2.py`, etc. O PyInstaller que gerou o exe original não incluiu os `.py` do pacote ortools — bug de empacotamento do autor. O import de `pywrapcp` no topo de camlib.py não falha porque o PyInstaller redireciona para o `.pyd`, mas quando dentro do `.pyd` ele tenta `import routing_parameters_pb2` como módulo Python irmão, falha porque o `.py` não existe na pasta.
- **Solução definitiva (CONFIRMADA):** O exe distribuído (`dist\windows\x64\`) tem packaging incompleto — faltam os módulos Python do OR-Tools e do google.protobuf. Duas soluções:
  1. **Rodar dos fontes (imediato):** `c:\temp\fcvenv\Scripts\python.exe c:\dsn\CNC\FlatCAM-Plus\flatcam.py` — funciona perfeitamente, OR-Tools completo.
  2. **Rebuild correto do exe:** Adicionar `"--collect-all", "ortools"` e `"--collect-all", "google.protobuf"` no `build_standalone.ps1` antes de rodar o PyInstaller. O build original não coletava esses pacotes. Após o fix, rodar `powershell -ExecutionPolicy Bypass -File build_standalone.ps1` gera um exe funcional em `dist\standalone\`.

---

### EVO-013: Seleção de tools no Excellon movida para plugin Drilling

- **Data:** 2026-07-04
- **Status:** ATIVO
- **Contexto:** Usuário queria desativar tools (brocas) no Excellon. Na tela de Properties não há checkboxes na Tools Table.
- **Versão 8.994:** Properties do Excellon (aba Selected) tinha coluna "P" (plot/process) clicável para marcar/desmarcar quais tools processar no CNC Job.
- **FlatCAM Plus:** A Tools Table em Properties do Excellon é apenas informativa (mostra diâmetro, drills, slots). A seleção de quais tools incluir no CNC Job é feita dentro do plugin **Drilling** (seção "Plugins" abaixo da table → botão "Drilling").
- **Diferença-chave:** No 8.994, selecionava tools direto na tabela do objeto. No Plus, precisa abrir o plugin Drilling para escolher.
- **Otimização?** NÃO — mudança de UI que pode confundir quem vem do 8.994.
- **Impacto:** MÉDIO
- **Tags:** #ui #excellon #drilling #workflow

---

### EVO-012: Seção Auto Level só aparece após conectar ao controller

- **Data:** 2026-07-04
- **Status:** ATIVO
- **Contexto:** Usuário não encontrava onde ligar o auto-level. A seção fica dentro do CNC Control e provavelmente só fica visível após conectar.
- **Versão 8.994:** N/A
- **FlatCAM Plus:** A seção Auto Level está no painel CNC Control, empilhada entre "Job Setup / Zero" e "G-Code Preview / Terminal". Contém: Fit Area, Rows/Columns, Safe Z, Probe Depth/Feed, Slow Probe Feed, Auto Zero Z, botões Probe/Stop/Clear/3D. O checkbox "Enable" (Use Map) ativa compensação Z no streaming. A seção pode não ser visível sem conexão ativa.
- **Diferença-chave:** Auto Level não é um tool/plugin separado — é uma seção do dashboard CNC Control que requer conexão ativa para aparecer e funcionar.
- **Otimização?** NÃO — informação de localização na UI.
- **Impacto:** ALTO (funcionalidade importante que não é óbvia de encontrar)
- **Tags:** #cnc #autolevel #ui #probe

---

### EVO-011: Telnet é preferível a HTTP para streaming; não conflita com pendant

- **Data:** 2026-07-04
- **Status:** ATIVO
- **Contexto:** Usuário perguntou se deve usar Telnet ou HTTP para trabalhar com o FlatCAM Plus.
- **Versão 8.994:** N/A
- **FlatCAM Plus:** Telnet (porta 23) é melhor para streaming/jog/probe: menor latência, conexão persistente, não conflita com pendant (que usa WebSocket na porta 80). HTTP é necessário apenas para Flash File System. Telnet aceita múltiplas conexões simultâneas no FluidNC.
- **Diferença-chave:** Telnet para operação diária (streaming, probe, jog). HTTP só quando precisa gerenciar arquivos na flash. Não usar ambos ao mesmo tempo para enviar comandos.
- **Otimização?** SIM — complementa OPT-06: a combinação Telnet + FlatCAM Plus é o setup ideal para PCB com auto-level.
- **Impacto:** MÉDIO
- **Tags:** #cnc #connection #fluidnc #streaming #pendant

---

### EVO-010: Streaming vs Upload — compensação Z só funciona em streaming

- **Data:** 2026-07-04
- **Status:** ATIVO
- **Contexto:** Usuário perguntou se G-Code enviado é gravado no SD card.
- **Versão 8.994:** N/A
- **FlatCAM Plus:** Três modos de envio: (1) Streaming via Start Queue — linha a linha, sem gravar, permite compensação Z com Use Map. (2) Upload via Flash File System (HTTP) — grava na flash do ESP32, roda como SD job, sem compensação. (3) SD card físico — sem compensação.
- **Diferença-chave:** A compensação Z bicúbica do auto-level SÓ funciona em modo streaming. Se gravar o arquivo no SD/flash e rodar como job, o G-Code vai sem compensação.
- **Otimização?** SIM — reforça OPT-01: streaming integrado é obrigatório para auto-level funcionar.
- **Impacto:** ALTO
- **Tags:** #cnc #autolevel #streaming #gcode

---

### EVO-009: Flash File System requer conexão HTTP, não Telnet

- **Data:** 2026-07-04
- **Status:** ATIVO
- **Contexto:** Usuário perguntou o que é o botão "Flash File System" no CNC Control.
- **Versão 8.994:** N/A
- **FlatCAM Plus:** O botão "Flash File System" abre um gerenciador de arquivos da flash do ESP32 (SPIFFS/LittleFS). Permite listar, upload, download, deletar, criar pastas — equivalente à aba Files da WebUI do FluidNC. Porém só funciona em modo HTTP/Web, não via Telnet.
- **Diferença-chave:** Se conectar por Telnet (porta 23), o Flash File System não funciona. Precisa de HTTP (porta 80) para acessar a API REST de arquivos.
- **Otimização?** NÃO — informação de uso.
- **Impacto:** BAIXO
- **Tags:** #cnc #filesystem #fluidnc

---

### EVO-008: Height map não persiste entre sessões

- **Data:** 2026-07-04
- **Status:** ATIVO
- **Contexto:** Usuário perguntou se auto-level é automático ao enviar job. Explicação revelou que o map vive só em memória.
- **Versão 8.994:** N/A
- **FlatCAM Plus:** O height map probeado fica em memória durante a sessão. Não há export/import de arquivo de map. Se fechar o app, perde e precisa probar de novo.
- **Diferença-chave:** Probe precisa ser refeito a cada sessão do FlatCAM Plus. "Use Map" ativa a compensação no streaming mas não dispara probe automaticamente.
- **Otimização?** NÃO — limitação atual. bCNC permite salvar/carregar height maps em arquivo.
- **Impacto:** MÉDIO
- **Tags:** #cnc #probe #autolevel #limitation

---

### EVO-006: Exe pré-compilado e exe rebuild ficam em diretórios diferentes

- **Data:** 2026-07-04
- **Status:** ATIVO
- **Contexto:** Usuário recompilou e o exe não funcionava, mas estava abrindo o exe errado.
- **Versão 8.994:** N/A
- **FlatCAM Plus:** O `build_standalone.ps1` gera em `dist\standalone\FlatCAMPlus\FlatCAMPlus.exe`. O exe pré-compilado que funciona está em `dist\windows\x64\FlatCAMPlus\FlatCAMPlus.exe`. São builds diferentes.
- **Diferença-chave:** Sempre verificar qual diretório de dist está sendo usado. O funcional é `dist\windows\x64\`.
- **Otimização?** NÃO
- **Impacto:** MÉDIO
- **Tags:** #build #filesystem #workaround

---

### EVO-017: Botões UP/DOWN da Queue podem ficar invisíveis por falta de espaço horizontal

- **Data:** 2026-07-07
- **Status:** ATIVO
- **Contexto:** Usuário reportou que não vê botões UP/DOWN na seção Job Queue / Sender do CNC Control. Confirmado no código que os botões existem (`queue_up_btn`, `queue_down_btn`) e não são ocultos com `.hide()`.
- **Versão 8.994:** N/A — não tinha Queue nem CNC Control.
- **FlatCAM Plus:** A barra horizontal da Queue tem 9 widgets numa única `QHBoxLayout`: combo, Refresh, ADD, REMOVE, UP, DOWN, START QUEUE, PAUSE, STOP. Em janelas/resoluções menores, os botões UP e DOWN (que ficam no meio) podem ser cortados ou comprimidos ao ponto de não serem visíveis.
- **Diferença-chave:** Os botões existem no código (`appPlugins/cnc_control/ui.py` linhas 1131-1132, 1150-1151) mas a UI não garante scroll ou wrap — depende da largura da janela.
- **Otimização?** NÃO — é um problema de layout/responsividade da UI.
- **Impacto:** MÉDIO (funcionalidade útil que parece não existir)
- **Tags:** #ui #cnc #queue #layout #bug
- **Workaround:** Maximizar a janela ou alargar o painel. Alternativa: adicionar os jobs na ordem correta de início (a queue executa de cima para baixo), ou usar REMOVE + ADD para reposicionar.

---

### EVO-018: Cutout com Gerber MultiPolygon (contorno + recorte interno) gera bounding box

- **Data:** 2026-07-09
- **Status:** ATIVO
- **Contexto:** Usuário exportou Gerber de profile do Fusion 360 contendo contorno externo + recorte interno (slot/oblongo). O arquivo tem dois paths (dois comandos D02). FlatCAM Plus interpretou como MultiPolygon e o Cutout Tool gerou bounding box retangular em vez do contorno real.
- **Versão 8.994:** Cutout Tool tratava MultiPolygon de forma diferente (não confirmado se funcionava melhor).
- **FlatCAM Plus:** Em `ToolCutOut.py`, quando `kind == 'single'` e `isinstance(object_geo, MultiPolygon)` → executa `box(x0, y0, x1, y1)` (linhas 750-752). Isso descarta a geometria real e usa bounding box. Condição: Gerber com múltiplos contornos (D02 separando paths) é parseado como MultiPolygon pela lib Shapely.
- **Diferença-chave:** Gerbers com contorno externo + recortes internos no mesmo arquivo não funcionam com Cutout Kind=Single. O fallback para bounding box é silencioso (sem warning).
- **Workarounds confirmados no código:**
  1. **Kind != Single:** Com kind diferente de 'single', o código itera cada geometria individualmente com `flatten_shapely_geometry()` e faz buffer correto em cada contorno separado.
  2. **Separar contornos no CAD:** Exportar apenas o contorno externo no Gerber de profile. Recortes internos como operação separada.
  3. **Importar como Geometry:** Geometry com LinearRing/LineString recebe buffer correto sem check de MultiPolygon.
- **Causa raiz no Gerber:** Cada comando `D02` (move sem draw) inicia um novo path. Dois D02 = dois polígonos fechados = MultiPolygon no Shapely. Gerbers do Fusion 360 (e EAGLE) com slots/recortes internos exportam tudo no mesmo arquivo de profile.
- **Otimização?** NÃO — limitação do Cutout Tool com geometrias compostas.
- **Impacto:** ALTO (qualquer placa não-retangular com furos/slots no outline é afetada)
- **Tags:** #cutout #gerber #multipolygon #fusion360 #bug #workaround

---

### EVO-019: Cutout Tool não distingue contorno externo de recorte interno (offset sempre outside)

- **Data:** 2026-07-09
- **Status:** ATIVO
- **Contexto:** Ao usar Kind != Single para processar Gerber com contorno externo + slot interno (workaround do EVO-018), o Cutout Tool aplicou offset para fora em AMBOS os contornos. Resultado: path externo correto (fresa fora da placa), mas path do slot interno errado (fresa fora do triângulo = tirando material da placa em vez de abrir o furo).
- **Versão 8.994:** Cutout Tool tinha opção explícita "Inside/Outside" que permitia controlar a direção do offset manualmente. Processava cada contorno com a direção correta.
- **FlatCAM Plus:** Com Kind != Single, o código itera com `flatten_shapely_geometry()` e aplica `buffer(margin)` + `.exterior` uniformemente em todas as geometrias (linha ~800). Não há lógica para detectar se um contorno é "interior" (furo) vs "exterior" (borda da placa) e inverter o offset automaticamente.
- **Diferença-chave:** O Cutout Tool trata todos os contornos como se fossem bordas externas. Para recortes internos (slots, furos não-circulares), o offset deveria ser para dentro do furo (= "outside" do polígono do slot quando visto como shape independente, mas "inside" em relação à placa).
- **Lógica no código (`margin < 0`):** Se margin negativo, o código usa `.interiors` em vez de `.exterior`:
  ```python
  if margin >= 0:
      geo_buf = object_geo.buffer(margin + abs(cut_dia / 2))
      geo = geo_buf.exterior
  else:
      geo_buf = object_geo.buffer(-margin + abs(cut_dia / 2))
      geo = unary_union(geo_buf.interiors)
  ```
  Mas isso gera paths nos interiors do polígono bufferizado, não resolve o caso de slots separados.
- **Workaround funcional:** Separar os contornos em dois Gerbers independentes no CAD:
  1. **Gerber do outline externo** → Cutout margin=0 → offset para fora ✅
  2. **Gerber do slot interno** (como polígono fechado isolado) → Cutout margin=0 → offset para fora DESSE polígono = para dentro do furo na placa ✅
  Ambos com multi-depth. Resultado: placa e furo nas dimensões exatas.
- **Otimização?** NÃO — limitação funcional que requer separação manual dos contornos.
- **Impacto:** ALTO (qualquer placa com recortes internos não-circulares é afetada)
- **Tags:** #cutout #offset #internal #slot #fusion360 #workaround

---

### EVO-020: Build standalone requer --collect-all certifi e rasterio

- **Data:** 2026-07-10
- **Status:** ATIVO
- **Contexto:** Ao gerar o instalador com `build_standalone.ps1`, o exe crashava no startup com `AttributeError: module 'certifi' has no attribute 'where'`. A cadeia: `ToolImage.py` → `import rasterio` → `rasterio._env` → `certifi.where()` → falha.
- **Versão 8.994:** Não usava rasterio nem tinha instalador PyInstaller.
- **FlatCAM Plus:** O `build_standalone.ps1` original não incluía `--collect-all certifi` nem `--collect-all rasterio`. O `certifi` estava instalado no venv mas o PyInstaller não o empacotava automaticamente porque a dependência é indireta (via rasterio._env que chama certifi em runtime, não em import time).
- **Diferença-chave:** O script oficial `packaging/windows/build_windows_installer.ps1` tem `--collect-all rasterio` mas o `build_standalone.ps1` (usado para builds rápidos) não tinha. Ambos precisam das mesmas flags.
- **Fix aplicado:** Adicionado `"--collect-all", "certifi"` e `"--collect-all", "rasterio"` ao `build_standalone.ps1`.
- **Otimização?** NÃO — fix de build/packaging.
- **Impacto:** ALTO (exe não abre sem o fix)
- **Tags:** #build #packaging #rasterio #certifi #crash #fix
- **Arquivo modificado:** `build_standalone.ps1`

---

## Regras de Consolidação

Uma entrada deve ser consolidada quando:
1. Foi validada pelo uso repetido (não é um caso isolado)
2. Representa uma diferença permanente (não um bug temporário)
3. Pode ser descrita de forma genérica (não depende de contexto único)

Ao consolidar:
1. Adicione a informação ao steering apropriado (`feature-map` ou `optimizations`)
2. Marque a entrada aqui como `[CONSOLIDADO]`
3. Adicione referência: "Consolidado em: flatcam-feature-map.md, seção X"

---

## Estatísticas

- Total de entradas: 20
- Ativas: 20
- Consolidadas: 0
- Obsoletas: 0
- Última atualização: 2026-07-10
