import sys
import time
from helix_connection import HelixConnection

try:
    import mido
except ImportError:
    mido = None


def send_helix_midi_cc(cc, value):
    if not mido:
        print(" [!] La librería 'mido' no está disponible. Asegúrate de instalar 'mido' y 'python-rtmidi'.")
        return False
    try:
        ports = mido.get_output_names()
        helix_port = None
        for p in ports:
            p_lower = p.lower()
            if "helix" in p_lower or "stomp" in p_lower or "line 6" in p_lower:
                helix_port = p
                break
        if not helix_port and ports:
            # Fallback al primer puerto disponible si no hay uno con nombre explícito
            helix_port = ports[0]
            
        if helix_port:
            with mido.open_output(helix_port) as port:
                msg = mido.Message('control_change', control=cc, value=value)
                port.send(msg)
            print(f" [+] MIDI CC {cc} enviado con valor {value} a través del puerto '{helix_port}'")
            return True
        else:
            print(" [!] No se encontró ningún puerto de salida MIDI (Helix/HX Stomp o similar).")
            if ports:
                print("     Puertos disponibles:")
                for p in ports:
                    print(f"       - {p}")
            return False
    except Exception as e:
        print(f" [!] Error al enviar MIDI CC: {e}")
        return False

def main():
    print("====================================================")
    print(" Helix LT Native USB Test Script")
    print("====================================================")
    print("Asegúrate de que la Helix LT esté encendida, conectada por USB y")
    print("que el software HX Edit esté CERRADO para evitar conflictos.")
    print("====================================================")
    
    conn = HelixConnection()
    try:
        success, msg = conn.connect()
        if not success:
            print(f" [!] {msg}")
            return
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
                    target_slot = None
                    if len(sys.argv) > 1:
                        try:
                            target_slot = int(sys.argv[1])
                        except ValueError:
                            pass
                            
                    success, res = conn.fetch_active_preset_blocks(slot_idx=target_slot)
                    print(" [+] BLOQUES DEL PEDALBOARD:")
                    if not success:
                        print(f"     (Error: {res})")
                    else:
                        blocks = res
                        if not blocks:
                            print("     (Sin bloques activos)")
                        
                        # Agrupar por path
                        paths = {"1A": [], "1B": [], "2A": [], "2B": []}
                        for b in blocks:
                            if target_slot is not None and b["slot_idx"] != target_slot:
                                continue
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
            
            print("\nOpciones:")
            print("  [ENTER] : Volver a leer el preset actual y sus bloques")
            print("  'p'     : Cambiar parámetro de un bloque (USB Nativo)")
            print("  'q'     : Salir del script")
            print("Selecciona una opción: ", end="")
            try:
                user_input = input().strip().lower()
            except (KeyboardInterrupt, EOFError):
                break
            if user_input == 'q':
                break
            elif user_input == 'p':
                try:
                    slot_str = input("Introduce el número de Slot del bloque: ").strip()
                    slot = int(slot_str)
                    
                    # Buscar el bloque en la lista obtenida anteriormente
                    target_block = None
                    if 'blocks' in locals() and blocks:
                        for b in blocks:
                            if b["slot_idx"] == slot:
                                target_block = b
                                break
                    
                    if target_block:
                        print(f"\n [+] Bloque seleccionado: {target_block['name']} ({target_block['category']}) en Path {target_block['path']}")
                        params = target_block.get('params_a', [])
                        if params:
                            print("     Valores actuales de los parámetros:")
                            for idx, val in enumerate(params):
                                print(f"       [{idx}]: {val} (Tipo: {type(val).__name__})")
                        else:
                            print("     (Este bloque no contiene parámetros legibles)")
                            
                        if target_block.get('dual_name'):
                            print(f" [+] Bloque Secundario (B): {target_block['dual_name']}")
                            params_b = target_block.get('params_b', [])
                            if params_b:
                                for idx, val in enumerate(params_b):
                                    print(f"       [B-{idx}]: {val} (Tipo: {type(val).__name__})")
                    else:
                        print(f"\n [!] No se encontró ningún bloque activo en el Slot #{slot}.")
                        
                    param_str = input("\nIntroduce el índice del parámetro a modificar: ").strip()
                    param = int(param_str)
                    val_str = input("Introduce el nuevo valor (ej: 0.5, True, False, o entero): ").strip()
                    
                    # Determinar el tipo de valor
                    if val_str.lower() == 'true':
                        val = True
                    elif val_str.lower() == 'false':
                        val = False
                    else:
                        if '.' in val_str:
                            val = float(val_str)
                        else:
                            val = int(val_str)
                            
                    # Enviar cambio
                    conn.change_parameter(slot, param, val)
                    print(" [+] Comando de cambio de parámetro enviado por USB. Leyendo estado actualizado...")
                    
                    # Esperar y volver a leer bloques
                    time.sleep(0.5)
                    updated_blocks = conn.fetch_active_preset_blocks()
                    
                    # Buscar el bloque actualizado
                    updated_block = None
                    if updated_blocks:
                        for b in updated_blocks:
                            if b["slot_idx"] == slot:
                                updated_block = b
                                break
                                
                    if updated_block:
                        print(f"\n [+] Bloque actualizado: {updated_block['name']}")
                        new_params = updated_block.get('params_a', [])
                        if new_params:
                            print("     Valores actuales de los parámetros:")
                            for idx, val in enumerate(new_params):
                                highlight = " <-- MODIFICADO" if idx == param else ""
                                print(f"       [{idx}]: {val} (Tipo: {type(val).__name__}){highlight}")
                        else:
                            print("     (Sin parámetros legibles)")
                    else:
                        print(" [!] No se pudo obtener el estado actualizado del bloque.")
                        
                except ValueError:
                    print(" [!] Entrada inválida o valor incorrecto.")
                except Exception as e:
                    print(f" [!] Error durante la modificación: {e}")
                time.sleep(2)
                
    except KeyboardInterrupt:
        print("\nPrueba cancelada por el usuario.")
    except Exception as e:
        print(f"\n [!] Error crítico: {e}")
    finally:
        conn.disconnect()
        print("\nConexión cerrada. ¡Adiós!")

if __name__ == "__main__":
    main()
