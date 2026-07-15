import time
import mido

def main():
    inputs = mido.get_input_names()
    helix_port = None
    for name in inputs:
        if 'Helix' in name:
            helix_port = name
            break
            
    if not helix_port:
        print("No se encontró el puerto MIDI de la Helix.")
        return
        
    print(f"Abriendo puerto MIDI: {helix_port}")
    print("\n=======================================================")
    print("Mueve o cambia un bloque en la Helix para ver si envía MIDI...")
    print("=======================================================\n")
    
    try:
        with mido.open_input(helix_port) as inport:
            start = time.time()
            # Escuchar durante 15 segundos
            while time.time() - start < 15:
                for msg in inport.iter_pending():
                    print(f"Recibido mensaje MIDI: {msg}")
                time.sleep(0.1)
                
    except Exception as e:
        print(f"Error al abrir el puerto: {e}")
        
    print("\nPrueba MIDI finalizada.")

if __name__ == "__main__":
    main()
