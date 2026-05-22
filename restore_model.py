# -*- coding: utf-8 -*-
"""
Script de utilidad para restaurar un backup del modelo ML.
Uso: python restore_model.py [nombre_del_archivo_opcional]
"""
import pathlib
import shutil
import os
import sys

BASE = pathlib.Path(__file__).parent.resolve()
MODEL_PATH = BASE / "ml_trading_model.pkl"
BACKUPS_DIR = BASE / "model_backups"

def list_backups():
    if not BACKUPS_DIR.exists():
        return []
    return sorted(BACKUPS_DIR.glob("ml_model_*.pkl"), key=os.path.getmtime, reverse=True)

def main():
    backups = list_backups()
    if not backups:
        print("[-] No se encontraron backups en 'model_backups/' para restaurar.")
        sys.exit(1)
        
    # Si se pasa un argumento, intentar restaurar ese backup específico
    if len(sys.argv) > 1:
        target_name = sys.argv[1]
        target_path = BACKUPS_DIR / target_name
        if not target_path.exists() or not target_name.endswith(".pkl"):
            print(f"[-] El archivo especificado '{target_name}' no existe en {BACKUPS_DIR}")
            print("Backups disponibles:")
            for b in backups:
                print(f" - {b.name}")
            sys.exit(1)
        backup_to_restore = target_path
    else:
        # Por defecto restaurar el más reciente
        backup_to_restore = backups[0]
        
    try:
        shutil.copy2(backup_to_restore, MODEL_PATH)
        print(f"[+] Restaurado con éxito: {backup_to_restore.name} -> {MODEL_PATH.name}")
    except Exception as e:
        print(f"[-] Error al restaurar el modelo: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
