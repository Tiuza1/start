import usb_cdc
import usb_hid
import time
from adafruit_hid.keyboard import Keyboard
from adafruit_hid.keycode import Keycode
from adafruit_hid.mouse import Mouse

kbd = Keyboard(usb_hid.devices)
mouse = Mouse(usb_hid.devices)

def mover_mouse_relativo(delta_x, delta_y):
    while delta_x != 0 or delta_y != 0:
        passo_x = max(-127, min(127, delta_x))
        passo_y = max(-127, min(127, delta_y))
        mouse.move(x=passo_x, y=passo_y)
        delta_x -= passo_x
        delta_y -= passo_y

while True:
    if usb_cdc.console.in_waiting > 0:
        linha = usb_cdc.console.readline().decode().strip().upper()
        if not linha:
            continue

        cmd = linha[0]

        if cmd == 'V':
            coords = linha[1:].split(',')
            if len(coords) == 2:
                try:
                    mover_mouse_relativo(int(coords[0]), int(coords[1]))
                except:
                    pass

        elif cmd == 'B':
            kbd.press(Keycode.LEFT_ALT, Keycode.NINE)
            time.sleep(0.05)
            kbd.release_all()

        elif cmd == 'T':
            kbd.press(Keycode.LEFT_ALT, Keycode.THREE)
            time.sleep(0.05)
            kbd.release_all()

        elif cmd == 'Q':
            for _ in range(4):
                kbd.press(Keycode.F3)
                time.sleep(0.01)
                mouse.click(Mouse.LEFT_BUTTON)
                kbd.release_all()
                time.sleep(0.01)

        elif cmd == 'A':
            kbd.press(Keycode.F4)
            time.sleep(0.05)
            kbd.release_all()

        elif cmd == 'S':
            kbd.press(Keycode.LEFT_ALT, Keycode.ONE)
            time.sleep(0.1)
            kbd.release_all()

        elif cmd == 'R':
            kbd.press(Keycode.LEFT_ALT)
            time.sleep(0.1)
            mouse.click(Mouse.RIGHT_BUTTON)
            time.sleep(0.1)
            kbd.release_all()

        elif cmd == 'X':
            kbd.press(Keycode.LEFT_ALT, Keycode.SIX)
            time.sleep(0.1)
            kbd.release_all()

        elif cmd == 'P':
            kbd.press(Keycode.F1)
            time.sleep(0.06)
            kbd.release_all()

        # ========================================================
        # METRALHADORA F4 -> F2 -> CLIQUE (Comando 'M')
        # ========================================================
        elif cmd == 'M':
            # F4 (Aura)
            kbd.press(Keycode.F4)
            time.sleep(0.05)
            kbd.release_all()
            
            time.sleep(0.4) 
            
            # F2 (Mortal)
            kbd.press(Keycode.F2)
            time.sleep(0.05)
            kbd.release_all()
            
            time.sleep(0.4) 
            
            # Clique do Mouse
            mouse.click(Mouse.LEFT_BUTTON)
            
            time.sleep(0.4) 
        # ========================================================

        elif cmd == 'D':
            mouse.press(Mouse.LEFT_BUTTON)

        elif cmd == 'U':
            mouse.release(Mouse.LEFT_BUTTON)

        elif cmd == 'E':
            kbd.press(Keycode.ENTER)
            time.sleep(0.05)
            kbd.release_all()

        elif cmd == 'L':
            mouse.click(Mouse.LEFT_BUTTON)

        elif cmd == '5':
            kbd.press(Keycode.FIVE)
            time.sleep(0.05)
            kbd.release_all()

        elif cmd == '0':
            kbd.press(Keycode.ZERO)
            time.sleep(0.05)
            kbd.release_all()

        usb_cdc.console.reset_input_buffer()