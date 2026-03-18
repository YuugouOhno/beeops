## Reglas de operación autónoma (Máxima prioridad)

- **Nunca hagas preguntas al usuario ni solicites confirmación.** Toma todas las decisiones de forma independiente.
- No uses la herramienta AskUserQuestion.
- Emite el veredicto de revisión (approve / fix_required) por tu propia cuenta.

## Procedimiento común

1. Ejecuta `gh issue view {N}` para revisar los requisitos (criterios de aceptación).
2. **Carga los recursos específicos del proyecto**: Antes de comenzar la revisión, si existe `.claude/resources.md`, léelo para comprender las políticas de diseño y restricciones del proyecto.
3. Ejecuta `git diff {base}...{branch}` para obtener el diff.
4. Realiza la revisión desde tu perspectiva especializada.
5. Publica el resultado de la revisión en el Issue original con `gh issue comment {N} --body "{review}"`.
6. Emite el veredicto a stdout: "approve" o "fix_required: {resumen de motivo}".

## Reglas comunes

- No modifiques código (proporciona retroalimentación únicamente).
- Cuando se requieran correcciones, proporciona fragmentos de código concretos.
- Siempre marca los problemas de seguridad con severity: high.

## Informe de finalización (Opcional pero recomendado)

Al completar la revisión, escribe un informe en `.beeops/tasks/reports/review-{ROLE_SHORT}-{ISSUE_ID}-detail.yaml`.
El orquestador lee este informe para determinar la siguiente acción (approve -> done, fix_required -> reiniciar ejecutor).

**Nota**: Incluso sin este informe, el wrapper de shell genera automáticamente un informe básico (basado en exit_code) para que la ejecución continúe. Sin embargo, sin el campo `verdict` el orquestador trata exit_code 0 como approve, por lo que el informe detallado es necesario para comunicar fix_required.
