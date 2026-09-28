$blender = "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
$scenes = "C:\Users\alvar\Desktop\autofagia-blender\scenes"

Write-Output "=== Escena 1 ==="
& $blender --background --python "$scenes\scene1_pared_celular.py" -- --render

Write-Output "=== Escena 2 ==="
& $blender --background --python "$scenes\scene2_calcio.py" -- --render

Write-Output "=== Escena 3 ==="
& $blender --background --python "$scenes\scene3_atg8ilacion.py" -- --render

Write-Output "=== TODO LISTO ==="
