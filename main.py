# -*- coding: utf-8 -*-
import base64
import os
import struct
import zlib
import xml.etree.ElementTree as ET

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.widget import Widget
from kivy.graphics import Color, Rectangle
from kivy.core.window import Window

Window.softinput_mode = 'below_target'

GEODE_SAVE_PATH = '/storage/emulated/0/Android/media/com.geode.launcher/save'
DOWNLOADS_PATH = '/storage/emulated/0/Download'

DAT_PATH = GEODE_SAVE_PATH if os.path.exists(GEODE_SAVE_PATH) else DOWNLOADS_PATH
XML_PATH = DOWNLOADS_PATH

def remove_if_exists(file_path):
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception:
            pass

def xor_bytes(data: bytes, value: int) -> bytes:
    return bytes(map(lambda x: x ^ value, data))

def process_decrypt(possible_dat_filenames, xml_filename, prettify):
    dat_file_path = None
    for name in possible_dat_filenames:
        temp_path = os.path.join(DAT_PATH, name)
        if os.path.exists(temp_path):
            dat_file_path = temp_path
            break

    xml_file_path = os.path.join(XML_PATH, xml_filename)

    if not dat_file_path:
        return False, f"Bulunamadı:\n{', '.join(possible_dat_filenames)}"

    try:
        with open(dat_file_path, 'rb') as f:
            encrypted_data = f.read()

        decrypted_data = xor_bytes(encrypted_data, 11)
        decoded_data = base64.b64decode(decrypted_data, altchars=b'-_')
        decompressed_data = zlib.decompress(decoded_data[10:], -zlib.MAX_WBITS)

        if prettify:
            # XML ağacını ayrıştırıp temizleme
            root = ET.fromstring(decompressed_data)

            for elem in root.iter():
                if elem.text:
                    elem.text = elem.text.strip()
                if elem.tail:
                    elem.tail = elem.tail.strip()

            # Düzgün girintileme ve alt satıra geçirme
            ET.indent(root, space="\t", level=0)

            # XML başlığı olmadan kaydetme (oyun çökmesini engeller)
            decompressed_data = ET.tostring(root, encoding='utf-8')

        remove_if_exists(xml_file_path)

        with open(xml_file_path, 'wb') as f:
            f.write(decompressed_data)

        return True, f"Başarılı!\n{xml_filename} oluşturuldu."
    except Exception as e:
        return False, f"Hata:\n{str(e)}"

def process_encrypt(possible_xml_filenames, dat_filename):
    xml_file_path = None
    for name in possible_xml_filenames:
        temp_path = os.path.join(XML_PATH, name)
        if os.path.exists(temp_path):
            xml_file_path = temp_path
            break

    dat_file_path = os.path.join(DAT_PATH, dat_filename)

    if not xml_file_path:
        return False, f"Bulunamadı:\n{', '.join(possible_xml_filenames)}"

    try:
        with open(xml_file_path, 'rb') as f:
            decrypted_data = f.read()

        # Prettify kaynaklı boşlukları ve girintileri sıkıştırma öncesi temizleme
        try:
            root = ET.fromstring(decrypted_data)
            for elem in root.iter():
                if elem.text:
                    elem.text = elem.text.strip()
                if elem.tail:
                    elem.tail = elem.tail.strip()
            decrypted_data = ET.tostring(root, encoding='utf-8')
        except Exception:
            pass

        compressed_data = zlib.compress(decrypted_data)
        data_crc32 = zlib.crc32(decrypted_data)
        data_size = len(decrypted_data)

        # ÖNEMLİ DÜZELTME: gzip trailer'ı (CRC32 + ISIZE) gzip spesifikasyonu
        # gereği HER ZAMAN little-endian olmalı. Eskiden 'I I' (native byte
        # order) kullanılıyordu; bu çoğu cihazda tesadüfen çalışıyordu ama
        # platforma bağlıydı. Artık açıkça '<II' (little-endian) kullanılıyor.
        compressed_data = (b'\x1f\x8b\x08\x00\x00\x00\x00\x00\x00\x0b' +
                           compressed_data[2:-4] +
                           struct.pack('<II', data_crc32, data_size))
        encoded_data = base64.b64encode(compressed_data, altchars=b'-_')
        encrypted_data = xor_bytes(encoded_data, 11)

        remove_if_exists(dat_file_path)

        with open(dat_file_path, 'wb') as f:
            f.write(encrypted_data)

        return True, f"Başarılı!\n{dat_filename} güncellendi."
    except Exception as e:
        return False, f"Hata:\n{str(e)}"

class GDSaveToolApp(App):
    def build(self):
        self.title = "Geometry Dash Savefile Tool"
        self.prettify_states = {1: False, 2: False, 3: False, 4: False}

        main_layout = BoxLayout(orientation='vertical', padding=12, spacing=10)

        with main_layout.canvas.before:
            Color(0.08, 0.08, 0.1, 1)
            self.rect = Rectangle(size=main_layout.size, pos=main_layout.pos)
            main_layout.bind(size=self._update_rect, pos=self._update_rect)

        # Başlık
        title_label = Label(
            text="Geometry Dash Save Tool",
            font_size='20sp',
            bold=True,
            size_hint_y=None,
            height=35,
            color=(0.9, 0.9, 0.9, 1)
        )
        main_layout.add_widget(title_label)

        # Hata/Durum Alanı
        self.status_label = Label(
            text="İşlem yapmak için bir buton seçin.",
            font_size='12sp',
            size_hint_y=None,
            height=50,
            halign='center',
            valign='middle',
            color=(0.2, 0.8, 0.4, 1)
        )
        self.status_label.bind(width=lambda instance, value: setattr(instance, 'text_size', (value - 20, None)))
        main_layout.add_widget(self.status_label)

        # Ortalamak için üst esnek alan
        main_layout.add_widget(Widget(size_hint_y=0.05))

        # Kaydırılabilir İçerik
        scroll = ScrollView(size_hint=(1, 1))
        content = BoxLayout(orientation='vertical', spacing=20, padding=[0, 5, 0, 10], size_hint_y=None)
        content.bind(minimum_height=content.setter('height'))

        sections = [
            ("CCGameManager (Save 1)", 1, "CCGameManager"),
            ("CCGameManager2 (Save 2)", 2, "CCGameManager2"),
            ("CCLocalLevels (Save 3)", 3, "CCLocalLevels"),
            ("CCLocalLevels2 (Save 4)", 4, "CCLocalLevels2")
        ]

        for title, id_num, base_name in sections:
            group_label = Label(
                text=f"=== {title} ===",
                font_size='14sp',
                bold=True,
                size_hint_y=None,
                height=25,
                color=(0.4, 0.7, 1, 1)
            )
            content.add_widget(group_label)

            grid = GridLayout(cols=3, spacing=8, size_hint_y=None, height=95)

            # Decrypt
            btn_dec_text = f"[b]Decrypt[/b]\n[size=10sp]{base_name}.dat\n➔ .xml[/size]"
            btn_dec = Button(
                text=btn_dec_text,
                markup=True,
                halign='center',
                valign='middle',
                background_normal='',
                background_color=(0.15, 0.45, 0.75, 1),
                color=(1, 1, 1, 1)
            )
            btn_dec.bind(size=lambda instance, value: setattr(instance, 'text_size', value))
            btn_dec.bind(on_press=lambda instance, b=base_name, i=id_num: self.action_decrypt(b, i))

            # Encrypt
            btn_enc_text = f"[b]Encrypt[/b]\n[size=10sp]{base_name}.xml\n➔ .dat[/size]"
            btn_enc = Button(
                text=btn_enc_text,
                markup=True,
                halign='center',
                valign='middle',
                background_normal='',
                background_color=(0.75, 0.35, 0.15, 1),
                color=(1, 1, 1, 1)
            )
            btn_enc.bind(size=lambda instance, value: setattr(instance, 'text_size', value))
            btn_enc.bind(on_press=lambda instance, b=base_name: self.action_encrypt(b))

            # Prettify Toggle
            btn_pret = ToggleButton(
                text="[b]Prettify[/b]\n[size=10sp]Format:\nOFF[/size]",
                markup=True,
                halign='center',
                valign='middle',
                background_normal='',
                background_color=(0.22, 0.22, 0.25, 1),
                color=(0.8, 0.8, 0.8, 1)
            )
            btn_pret.bind(size=lambda instance, value: setattr(instance, 'text_size', value))
            btn_pret.bind(on_press=lambda instance, i=id_num: self.toggle_prettify(instance, i))

            grid.add_widget(btn_dec)
            grid.add_widget(btn_enc)
            grid.add_widget(btn_pret)

            content.add_widget(grid)

        scroll.add_widget(content)
        main_layout.add_widget(scroll)

        # Ortalamak için alt esnek alan
        main_layout.add_widget(Widget(size_hint_y=0.05))

        return main_layout

    def _update_rect(self, instance, value):
        self.rect.pos = instance.pos
        self.rect.size = instance.size

    def toggle_prettify(self, button, id_num):
        self.prettify_states[id_num] = not self.prettify_states[id_num]
        if self.prettify_states[id_num]:
            button.text = "[b]Prettify[/b]\n[size=10sp]Format:\nON[/size]"
            button.background_color = (0.15, 0.55, 0.25, 1)
        else:
            button.text = "[b]Prettify[/b]\n[size=10sp]Format:\nOFF[/size]"
            button.background_color = (0.22, 0.22, 0.25, 1)

    def action_decrypt(self, base_name, id_num):
        possible_dats = [f'{base_name}.dat', base_name, f'{base_name}.xml', f'{base_name}.dat.xml']
        xml_out = f'{base_name}.xml'
        prettify = self.prettify_states[id_num]

        success, msg = process_decrypt(possible_dats, xml_out, prettify)
        self.status_label.text = msg
        self.status_label.color = (0.2, 0.8, 0.4, 1) if success else (1, 0.3, 0.3, 1)

    def action_encrypt(self, base_name):
        possible_xmls = [f'{base_name}.xml', f'{base_name}.dat.xml', base_name]
        dat_out = f'{base_name}.dat'

        success, msg = process_encrypt(possible_xmls, dat_out)
        self.status_label.text = msg
        self.status_label.color = (0.2, 0.8, 0.4, 1) if success else (1, 0.3, 0.3, 1)

if __name__ == '__main__':
    GDSaveToolApp().run()