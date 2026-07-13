# Loads KEY=value lines from the project-root .env into this process's
# environment, WITHOUT overriding variables already set in the shell (so an
# explicit `$env:X=...` still wins — matching how the Python side's load_dotenv
# behaves). Dot-source from a launcher script:  . "$PSScriptRoot\_env.ps1"
$dotenv = Join-Path (Split-Path $PSScriptRoot -Parent) ".env"
if (Test-Path $dotenv) {
    foreach ($line in Get-Content $dotenv) {
        $t = $line.Trim()
        if ($t.Length -eq 0 -or $t.StartsWith("#")) { continue }
        $eq = $t.IndexOf("=")
        if ($eq -lt 1) { continue }
        $key = $t.Substring(0, $eq).Trim()
        $val = $t.Substring($eq + 1).Trim()
        # strip one layer of surrounding quotes, if present
        if ($val.Length -ge 2 -and
            (($val[0] -eq '"' -and $val[-1] -eq '"') -or ($val[0] -eq "'" -and $val[-1] -eq "'"))) {
            $val = $val.Substring(1, $val.Length - 2)
        }
        if (-not (Test-Path "Env:\$key")) {
            Set-Item -Path "Env:\$key" -Value $val
        }
    }
}
