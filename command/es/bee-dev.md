Inicia una sesión Queen (beeops) en tmux y la muestra automáticamente.
La generación y gestión de queue.yaml es manejada enteramente por la Queen dentro de tmux.

## Pasos de ejecución

### Paso 0: Resolver rutas del paquete

```bash
PKG_DIR=$(node -e "console.log(require.resolve('beeops/package.json').replace('/package.json',''))")
BO_SCRIPTS_DIR="$PKG_DIR/scripts"
BO_CONTEXTS_DIR="$PKG_DIR/contexts"
```

### Paso 1: Verificar sesión existente

```bash
SESSION="bee-dev"

tmux has-session -t "$SESSION" 2>/dev/null && {
  echo "An existing bo session was found."
  echo "  tmux attach -t bee-dev   # monitor"
  echo "  tmux kill-session -t bee-dev  # stop and restart"
  # Stop here. Let the user decide.
}
```

Si se encuentra una sesión existente, mostrar las instrucciones y **detenerse**. El usuario debe eliminar explícitamente la sesión antes de volver a ejecutar.

### Paso 2: Iniciar sesión tmux

```bash
CWD=$(pwd)

tmux new-session -d -s "$SESSION" -n queen -c "$CWD" \
  "unset CLAUDECODE; BO_QUEEN=1 BO_SCRIPTS_DIR='$BO_SCRIPTS_DIR' BO_CONTEXTS_DIR='$BO_CONTEXTS_DIR' claude --dangerously-skip-permissions; echo '--- Done (press Enter to close) ---'; read"
```

### Paso 2.5: Configurar visualización de paneles tmux

```bash
# Show role name at top of each pane
tmux set-option -t "$SESSION" pane-border-status top

# Format: prefer @agent_label (not overridable by Claude Code), fallback to pane_title
tmux set-option -t "$SESSION" pane-border-format \
  " #{?pane_active,#[bold],}#{?@agent_label,#{@agent_label},#{pane_title}}#[default] "

# Queen pane: gold border + title
tmux select-pane -t "$SESSION:queen.0" -T "👑 queen"
tmux set-option -p -t "$SESSION:queen.0" @agent_label "👑 queen" 2>/dev/null || true
tmux set-option -p -t "$SESSION:queen.0" allow-rename off 2>/dev/null || true
tmux set-option -p -t "$SESSION:queen.0" pane-border-style "fg=yellow" 2>/dev/null || true
```

### Paso 3: Conectarse automáticamente a la sesión tmux

```bash
case "$(uname -s)" in
  Darwin)
    osascript -e '
    tell application "Terminal"
      activate
      do script "tmux attach -t bee-dev"
    end tell
    ' 2>/dev/null || echo "Open a new terminal and run: tmux attach -t bee-dev"
    ;;
  *)
    echo "Queen session started. Attach with: tmux attach -t bee-dev"
    ;;
esac
```

En macOS, abre Terminal.app automáticamente y se conecta a la sesión tmux.
En otras plataformas, imprime el comando de conexión para el usuario.

### Paso 4: Esperar el inicio

```bash
for i in $(seq 1 60); do
  sleep 2
  if tmux capture-pane -t "$SESSION:queen" -p 2>/dev/null | grep -q 'Claude Code'; then
    break
  fi
done
```

Espera hasta 120 segundos. El inicio se completa cuando aparece el banner de `Claude Code`.

### Paso 5: Resolver el modo de ejecución y enviar el prompt inicial

Determinar qué instrucción enviar a la Queen. Orden de prioridad:

1. **`$ARGUMENTS` proporcionado** → usarlo directamente, omitir configuración/interactivo
2. **El archivo de configuración existe** (`.beeops/settings.json`) → construir instrucción desde la configuración
3. **Sin argumentos ni configuración** → preguntar al usuario de forma interactiva

#### 5a. Si `$ARGUMENTS` no está vacío

Usarlo directamente:

```bash
if [ -n "$ARGUMENTS" ]; then
  INSTRUCTION="$ARGUMENTS"
fi
```

#### 5b. Si no hay argumentos, verificar el archivo de configuración

```bash
SETTINGS_FILE=".beeops/settings.json"
if [ -z "$ARGUMENTS" ] && [ -f "$SETTINGS_FILE" ]; then
  echo "Found settings: $SETTINGS_FILE"
  cat "$SETTINGS_FILE"
fi
```

Si el archivo de configuración existe, construir la instrucción basándose en su contenido:

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `issues` | `number[]` | Números de issue específicos a procesar (ej. `[42, 55]`) |
| `assignee` | `string` | `"me"` = solo issues asignados al usuario GitHub actual, `"all"` = todos los issues abiertos |
| `skip_review` | `boolean` | Omitir fase de revisión si es verdadero (predeterminado: false) |
| `priority` | `string` | Solo procesar issues con esta prioridad o superior (`"high"`, `"medium"`, `"low"`) |
| `labels` | `string[]` | Solo procesar issues con estas etiquetas |

Construir la cadena `INSTRUCTION` de la siguiente manera:
- Si `issues` está configurado: `"Sync GitHub Issues to queue.yaml and process only issues: #42, #55."`
- Si `assignee` es `"me"`: `"Sync GitHub Issues to queue.yaml and process only issues assigned to me."`
- Si `assignee` es `"all"` o no está configurado: `"Sync GitHub Issues to queue.yaml and complete all tasks."`
- Agregar opciones: si `skip_review` es verdadero, agregar `" Skip the review phase."`. Si `priority` está configurado, agregar `" Only process issues with priority {priority} or higher."`. Si `labels` está configurado, agregar `" Only process issues with labels: {labels}."`

#### 5c. Si no hay argumentos ni archivo de configuración, preguntar al usuario de forma interactiva

Presentar las siguientes opciones al usuario (usar AskUserQuestion o mostrar las opciones y esperar la entrada):

```
How should the Queen process issues?

1. Specify issue numbers (e.g. 42, 55, 100)
2. Only issues assigned to me
3. All open issues

Enter your choice (1/2/3):
```

Según la respuesta del usuario:
- **Opción 1**: Pedir los números de issue, luego establecer `INSTRUCTION="Sync GitHub Issues to queue.yaml and process only issues: #42, #55."`
- **Opción 2**: Establecer `INSTRUCTION="Sync GitHub Issues to queue.yaml and process only issues assigned to me."`
- **Opción 3**: Establecer `INSTRUCTION="Sync GitHub Issues to queue.yaml and complete all tasks."`

Opcionalmente, después de seleccionar el modo, preguntar:
```
Save this as default settings? (y/n)
```
Si es sí, escribir el archivo `.beeops/settings.json` correspondiente para que la próxima ejecución lo use automáticamente.

#### 5d. Enviar la instrucción a la Queen

```bash
tmux send-keys -t "$SESSION:queen" "$INSTRUCTION"
sleep 0.3
tmux send-keys -t "$SESSION:queen" Enter
```

### Paso 6: Mostrar estado al usuario

Después del inicio, mostrar:

```
Queen started (beeops). tmux session displayed.
  queen window: main control loop
  issue-{N}/review-{N}: Leader/Worker windows are added automatically
  tmux kill-session -t bee-dev  # to stop
```

## Notas

- `$ARGUMENTS` contiene los argumentos del comando slash
- Este comando debe ejecutarse en el **directorio del proyecto de destino**
- La generación y actualización de queue.yaml es gestionada por la Queen dentro de tmux
