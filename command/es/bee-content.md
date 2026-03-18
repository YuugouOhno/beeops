Inicia una Content Queen en tmux para la creación de contenido en 3 capas (bee-content: Content Queen → Content Leader → Workers).

## Pasos de ejecución

### Paso 0: Configuración interactiva

Analizar `$ARGUMENTS` primero, luego preguntar de forma interactiva por los valores faltantes antes de iniciar tmux.

#### 0a. Analizar $ARGUMENTS

- **instruction**: todo lo que precede al primer indicador `--` (o la cadena completa si no hay indicadores)
- **--criteria "..."**: criterios de calidad
- **--threshold N**: umbral de puntuación (entero)
- **--max-loops N**: bucles máximos de revisión por pieza (entero)
- **--count N**: número de piezas a generar (entero)
- **--name <name>**: nombre de sesión para esta tarea
- **--output <dir>**: directorio de salida para las piezas aprobadas

#### 0b. Preguntar por los valores faltantes (preguntar siempre de forma interactiva — NO usar valores predeterminados en silencio)

Usar `AskUserQuestion` para cada valor faltante en orden:

**1. Instrucción** (si no se proporcionó en $ARGUMENTS):
```
What content do you want to create?
```

**2. Criterios** (preguntar siempre, incluso si se proporcionó la instrucción — a menos que se haya indicado explícitamente mediante --criteria):
```
What are the quality criteria for this content?
Examples: "Technically accurate, includes code examples, under 800 words"
         "Compelling headline, clear value prop, no jargon"
(Press Enter to use default: "High quality, accurate, engaging, and well-structured.")
```
Si el usuario presiona Enter o da una respuesta vacía, usar el valor predeterminado: `"High quality, accurate, engaging, and well-structured."`

**3. Umbral** (preguntar solo si no se proporcionó mediante --threshold):
```
What score should the content reach to be accepted? (0-100, default: 80)
```
Si está vacío, usar `80`.

**4. Máximo de bucles** (preguntar solo si no se proporcionó mediante --max-loops):
```
How many revision loops at most per piece? (default: 3)
```
Si está vacío, usar `3`.

**5. Cantidad** (preguntar solo si no se proporcionó mediante --count):
```
How many pieces of content do you want to generate? (default: 1)
```
Si está vacío, usar `1`.

**6. Nombre** (preguntar siempre — omitir si se proporcionó --name):
```
Give this session a name for later reference? (Enter to use timestamp)
```
Si está vacío, dejar en blanco (se usará una marca de tiempo en el Paso 2).

Después de recopilar todos los valores, mostrar un resumen y confirmar antes de continuar:
```
Ready to start bee-content:
  instruction: {INSTRUCTION}
  criteria:    {CRITERIA}
  threshold:   {THRESHOLD}/100
  max_loops:   {MAX_LOOPS}
  count:       {COUNT}
  output:      {OUTPUT_DIR si está definido, si no "(default: .beeops/tasks/content/{TASK_ID}/pieces/)"}

Start? (Y/n)
```
Si el usuario dice no o n, detenerse aquí.

### Paso 1: Resolver rutas del paquete

```bash
PKG_DIR=$(node -e "console.log(require.resolve('beeops/package.json').replace('/package.json',''))")
BO_SCRIPTS_DIR="$PKG_DIR/scripts"
BO_CONTEXTS_DIR="$PKG_DIR/contexts"
```

### Paso 2: Crear directorio y archivos de tarea

```bash
TASK_ID="${NAME:-$(date +%Y%m%d-%H%M%S)}"
TASK_DIR=".beeops/tasks/content/$TASK_ID"
CWD=$(pwd)

mkdir -p "$TASK_DIR/pieces" "$TASK_DIR/reports" "$TASK_DIR/prompts"

echo "$INSTRUCTION" > "$TASK_DIR/instruction.txt"
echo "$CRITERIA"    > "$TASK_DIR/criteria.txt"
echo "$THRESHOLD"   > "$TASK_DIR/threshold.txt"
echo "$MAX_LOOPS"   > "$TASK_DIR/max_loops.txt"
echo "$OUTPUT_DIR" > "$TASK_DIR/output_dir.txt"
if [ -n "$OUTPUT_DIR" ]; then
  mkdir -p "$OUTPUT_DIR"
fi
# queue.yaml will be initialized by Content Queen
```

### Paso 3: Crear sesión tmux bee-content e iniciar Content Queen

```bash
SESSION="bee-content"

if ! tmux has-session -t "$SESSION" 2>/dev/null; then
  tmux new-session -d -s "$SESSION" -n "content-queen" -c "$CWD" \
    "unset CLAUDECODE; BO_CONTENT_QUEEN=1 \
     BO_SCRIPTS_DIR='$BO_SCRIPTS_DIR' \
     BO_CONTEXTS_DIR='$BO_CONTEXTS_DIR' \
     TASK_DIR='$TASK_DIR' \
     COUNT='$COUNT' \
     claude --dangerously-skip-permissions \
     --permission-mode bypassPermissions \
     --allowedTools 'Read,Write,Edit,Bash,Glob,Grep,Skill' \
     --max-turns 80; read"
  tmux set-option -t "$SESSION" pane-border-status top
  tmux set-option -t "$SESSION" pane-border-format \
    " #{?pane_active,#[bold],}#{?@agent_label,#{@agent_label},#{pane_title}}#[default] "
else
  tmux new-window -t "$SESSION" -n "content-queen" -c "$CWD" \
    "unset CLAUDECODE; BO_CONTENT_QUEEN=1 \
     BO_SCRIPTS_DIR='$BO_SCRIPTS_DIR' \
     BO_CONTEXTS_DIR='$BO_CONTEXTS_DIR' \
     TASK_DIR='$TASK_DIR' \
     COUNT='$COUNT' \
     claude --dangerously-skip-permissions \
     --permission-mode bypassPermissions \
     --allowedTools 'Read,Write,Edit,Bash,Glob,Grep,Skill' \
     --max-turns 80; read"
fi
```

### Paso 4: Configurar visualización de paneles

```bash
tmux select-pane -t "$SESSION:content-queen.0" -T "👑 content-queen"
tmux set-option -p -t "$SESSION:content-queen.0" @agent_label "👑 content-queen" 2>/dev/null || true
tmux set-option -p -t "$SESSION:content-queen.0" allow-rename off 2>/dev/null || true
tmux set-option -p -t "$SESSION:content-queen.0" pane-border-style "fg=yellow" 2>/dev/null || true
```

### Paso 5: Enviar instrucción inicial a Content Queen

```bash
INSTRUCTION_MSG="Content task ready. TASK_DIR: $TASK_DIR COUNT: $COUNT BO_SCRIPTS_DIR: $BO_SCRIPTS_DIR OUTPUT_DIR: ${OUTPUT_DIR:-}. Read instruction.txt, initialize queue.yaml, and begin."
tmux send-keys -t "$SESSION:content-queen" "$INSTRUCTION_MSG" Enter
```

### Paso 6: Conectarse automáticamente a la sesión tmux

```bash
case "$(uname -s)" in
  Darwin)
    osascript -e '
    tell application "Terminal"
      activate
      do script "tmux attach -t bee-content"
    end tell
    ' 2>/dev/null || echo "Open a new terminal and run: tmux attach -t bee-content"
    ;;
  *)
    echo "bee-content started. Attach with: tmux attach -t bee-content"
    ;;
esac
```

En macOS, abre Terminal.app automáticamente y se conecta a la sesión tmux.
En otras plataformas, imprime el comando de conexión para el usuario.

### Paso 7: Mostrar mensaje de estado

```
bee-content started.
  task_id:   {TASK_ID}
  count:     {COUNT}
  threshold: {THRESHOLD}/100
  max_loops: {MAX_LOOPS}
  output:    {OUTPUT_DIR si está definido, si no .beeops/tasks/content/{TASK_ID}/pieces/}

  Monitor: tmux attach -t bee-content
  Stop:    tmux kill-session -t bee-content
```

## Notas

- `$ARGUMENTS` contiene los argumentos del comando slash
- Este comando debe ejecutarse en el **directorio del proyecto de destino**
- La Content Queen gestiona queue.yaml y despacha Content Leaders para cada pieza
- Piezas aprobadas: `.beeops/tasks/content/{TASK_ID}/pieces/piece-{N}-approved.md` (también copiadas a `--output <dir>` si se especifica)
- Registro de bucles: `.beeops/tasks/content/{TASK_ID}/loop.log`
- Flujo de 3 capas: Content Queen → Content Leader → Workers (Creator, Reviewer, Researcher)
