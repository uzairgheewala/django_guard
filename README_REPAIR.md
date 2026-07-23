# PlanGuard integration repair

This repair corrects the inconsistent archive roots in Milestones B, C, and F and applies the frontend/runtime fixes discovered during the first native Windows build.

## Apply from PowerShell

```powershell
$Repo = "C:\Users\uzair\Documents\django_guard"
$Archive = "C:\Users\uzair\Downloads\planguard-integration-repair-delta.zip"
$Repair = "C:\Users\uzair\Downloads\planguard-integration-repair"

Remove-Item -Recurse -Force $Repair -ErrorAction SilentlyContinue
Expand-Archive -Path $Archive -DestinationPath $Repair -Force
Set-ExecutionPolicy -Scope Process Bypass -Force
& "$Repair\APPLY_REPAIR.ps1" -RepositoryRoot $Repo
```

## Reinstall and validate

```powershell
conda activate planguard
Set-Location "C:\Users\uzair\Documents\django_guard"
python -m pip install -e ".[dev]"
python -c "import planguard; print('PlanGuard import succeeded')"
planguard --help
python .\scripts\generate_contracts.py --check
pytest -ra

Push-Location .\apps\workbench-ui
Remove-Item -Recurse -Force .\node_modules\.tmp -ErrorAction SilentlyContinue
npm install
npm run build
Pop-Location
```

The repair script removes only these known accidental nested patch directories:

- `planguard-milestone-b-delta`
- `planguard-milestone-c-delta`
- `planguard-milestone-f-delta`

It then overlays corrected root-relative files onto the repository.
