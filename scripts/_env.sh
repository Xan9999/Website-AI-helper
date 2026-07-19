# Sourced by the start-*.sh scripts: loads KEY=value pairs from the
# project-root .env into the environment. Variables already set in the shell
# take precedence over .env (same behavior as _env.ps1 on Windows).
# Not meant to be executed directly.
_ENV_FILE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/.env"
if [ -f "$_ENV_FILE" ]; then
    while IFS= read -r _line || [ -n "$_line" ]; do
        _line="${_line%$'\r'}"                    # tolerate Windows line endings
        case "$_line" in ''|\#*) continue ;; esac
        case "$_line" in *=*) ;; *) continue ;; esac
        _key="${_line%%=*}"
        _value="${_line#*=}"
        if [ -n "$_key" ] && [ -z "${!_key+x}" ]; then
            export "$_key=$_value"
        fi
    done < "$_ENV_FILE"
fi
