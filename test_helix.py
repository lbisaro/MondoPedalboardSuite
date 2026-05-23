import sys
import time
from helix_connection import HelixConnection

def main():
    print("====================================================")
    print(" Helix LT Native USB Test Script")
    print("====================================================")
    print("Asegúrate de que la Helix LT esté encendida, conectada por USB y")
    print("que el software HX Edit esté CERRADO para evitar conflictos.")
    print("====================================================")
    
    conn = HelixConnection()
    try:
        conn.connect()
        conn.perform_handshake()
        
        while True:
            try:
                info = conn.fetch_active_preset_info()
                print("\n----------------------------------------------------")
                print(f" [+] PRESET DETECTADO:")
                print(f"     - Setlist: {info['setlist_name']} (Índice {info['setlist_idx']})")
                print(f"     - Banco:   {info['bank_name']} (Índice en setlist: {info['preset_idx_in_setlist']})")
                print(f"     - Nombre:  '{info['preset_name']}'")
                print(f"     - Índice Absoluto: {info['absolute_preset_idx']}")
                print("----------------------------------------------------")
                
                # Fetch and display blocks
                try:
                    blocks = conn.fetch_active_preset_blocks()
                    print(" [+] BLOQUES DEL PEDALBOARD:")
                    if not blocks:
                        print("     (Sin bloques activos o error al leer)")
                    
                    # Agrupar por path
                    paths = {"1A": [], "1B": [], "2A": [], "2B": []}
                    for b in blocks:
                        if b["path"] in paths:
                            paths[b["path"]].append(b)
                            
                    for path_id, path_blocks in paths.items():
                        if not path_blocks:
                            continue
                        print(f"\n     [ Path {path_id} ]")
                        for b in path_blocks:
                            if b["type"] == "io":
                                desc = f"[{b['name']}]"
                                rp = b.get("routing_pos")
                                if rp is not None:
                                    if "Entrada" in b["name"]:
                                        desc += f"  <-- (Split desde Path {path_id[0]}A, pos: {rp})"
                                    elif "Salida" in b["name"]:
                                        desc += f"  --> (Merge hacia Path {path_id[0]}A, pos: {rp})"
                                        
                                params_a = b.get('params_a', [])
                                if params_a:
                                    p_str = ", ".join(str(p) for p in params_a)
                                    desc += f"\n         -> Params I/O: [{p_str}]"
                                    
                                print(f"       - Slot #{b['slot_idx']:02d}: {desc}")
                            else:
                                desc = f"{b['name']} ({b['category']})"
                                
                                params_a = b.get('params_a', [])
                                if params_a:
                                    # Format nicely
                                    p_str = ", ".join(str(p) for p in params_a)
                                    desc += f"\n         -> Params: [{p_str}]"
                                    
                                if b.get("dual_name"):
                                    desc += f"\n       - Slot #{b['slot_idx']:02d} (B): {b['dual_name']} ({b['dual_category']})"
                                    params_b = b.get('params_b', [])
                                    if params_b:
                                        pb_str = ", ".join(str(p) for p in params_b)
                                        desc += f"\n         -> Params: [{pb_str}]"
                                        
                                print(f"       - Slot #{b['slot_idx']:02d}: {desc}")
                    print("----------------------------------------------------")
                except Exception as block_err:
                    print(f" [!] Error al obtener bloques: {block_err}")
            except Exception as e:
                print(f"\n [!] Error al obtener información del preset: {e}")
            
            print("\nPresiona ENTER para volver a leer el preset, o escribe 'q' y ENTER para salir...")
            try:
                user_input = input().strip().lower()
            except (KeyboardInterrupt, EOFError):
                break
            if user_input == 'q':
                break
                
    except KeyboardInterrupt:
        print("\nPrueba cancelada por el usuario.")
    except Exception as e:
        print(f"\n [!] Error crítico: {e}")
    finally:
        conn.disconnect()
        print("\nConexión cerrada. ¡Adiós!")

if __name__ == "__main__":
    main()
