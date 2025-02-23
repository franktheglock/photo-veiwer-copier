import os
import rawpy
import PySimpleGUI as sg
import exiftool
from PIL import Image
import io
import numpy as np
from datetime import datetime
import shutil

class RawImageViewer:
    def __init__(self):
        self.current_index = 0
        self.image_files = []
        self.current_path = ""
        self.thumbnail_size = (200, 150)
        self.main_image_size = (800, 600)
        self.selected_images = set()  # Track selected images
        # Initialize ExifTool instance
        self.exiftool = exiftool.ExifToolHelper()
        
    def load_raw_preview(self, file_path, size):
        try:
            with rawpy.imread(file_path) as raw:
                # Get the embedded preview image if available
                thumb = raw.extract_thumb()
                if thumb.format == rawpy.ThumbFormat.JPEG:
                    img = Image.open(io.BytesIO(thumb.data))
                else:
                    # If no embedded preview, use the full raw image
                    rgb = raw.postprocess()
                    img = Image.fromarray(rgb)
                
                img.thumbnail(size)
                bio = io.BytesIO()
                img.save(bio, format='PNG')
                return bio.getvalue()
        except:
            return None

    def update_rating(self, file_path, rating):
        try:
            # Update both XMP and EXIF ratings
            params = {
                'XMP:Rating': rating,
                'EXIF:Rating': rating,
            }
            self.exiftool.set_tags([file_path], params)
            return True
        except Exception as e:
            print(f"Error updating rating: {e}")
            return False

    def get_photo_info(self, file_path):
        try:
            metadata = self.exiftool.get_tags(file_path, [
                'EXIF:ISO',
                'EXIF:ShutterSpeed',
                'EXIF:FNumber',
                'EXIF:FocalLength',
                'EXIF:Model',
                'EXIF:DateTimeOriginal'
            ])[0]
            
            return (
                f"Camera: {metadata.get('EXIF:Model', 'N/A')}  |  "
                f"ISO: {metadata.get('EXIF:ISO', 'N/A')}  |  "
                f"Shutter: {metadata.get('EXIF:ShutterSpeed', 'N/A')}  |  "
                f"f/{metadata.get('EXIF:FNumber', 'N/A')}  |  "
                f"Focal Length: {metadata.get('EXIF:FocalLength', 'N/A')}mm  |  "
                f"Date: {metadata.get('EXIF:DateTimeOriginal', 'N/A')}"
            )
        except Exception as e:
            print(f"Error reading metadata: {e}")
            return "No metadata available"

    def get_image_date(self, file_path):
        try:
            metadata = self.exiftool.get_tags(file_path, ['EXIF:DateTimeOriginal'])[0]
            date_str = metadata.get('EXIF:DateTimeOriginal')
            if date_str:
                date_obj = datetime.strptime(date_str, '%Y:%m:%d %H:%M:%S')
                return date_obj
            return None
        except Exception as e:
            print(f"Error reading date metadata: {e}")
            return None

    def create_date_folder_structure(self, base_path, date_obj):
        year = str(date_obj.year)
        month = f"{year}_{date_obj.month:02d}"
        day = f"{month}_{date_obj.day:02d}"
        
        year_path = os.path.join(base_path, year)
        month_path = os.path.join(year_path, month)
        day_path = os.path.join(month_path, day)
        
        for path in [year_path, month_path, day_path]:
            if not os.path.exists(path):
                os.makedirs(path)
        
        return day_path

    def copy_selected_images(self, destination_base):
        copied_count = 0
        for idx in self.selected_images:
            if idx < len(self.image_files):
                source_file = os.path.join(self.current_path, self.image_files[idx])
                date_obj = self.get_image_date(source_file)
                
                if date_obj:
                    dest_folder = self.create_date_folder_structure(destination_base, date_obj)
                    dest_file = os.path.join(dest_folder, self.image_files[idx])
                    try:
                        shutil.copy2(source_file, dest_file)
                        copied_count += 1
                    except Exception as e:
                        print(f"Error copying {source_file}: {e}")
                else:
                    print(f"Could not determine date for {self.image_files[idx]}")
        
        return copied_count

    def create_layout(self):
        layout = [
            [sg.Text("Source Path:"), sg.Input(key="-PATH-"), sg.FolderBrowse()],
            [sg.Text("Destination Path:"), sg.Input(key="-DEST-PATH-"), sg.FolderBrowse()],
            [sg.Button("Load Images")],
            [sg.Text("", key="-FILENAME-", size=(60, 1))],
            [sg.Image(key="-MAIN-IMAGE-", size=self.main_image_size)],
            [sg.Text("", key="-PHOTO-INFO-", size=(80, 1))],
            [sg.Text("Selected: 0", key="-SELECTION-COUNT-")],
            [sg.Button("Previous"), sg.Button("Next"), 
             sg.Button("Select/Deselect (Enter)", key="-SELECT-"), 
             sg.Button("Copy Selected", key="-COPY-"), 
             sg.Button("Exit")],
            [sg.Column(
                [[sg.Image(key=f"-THUMB-{i}-", size=self.thumbnail_size) for i in range(5)]],
                key="-THUMB-COL-"
            )]
        ]
        return layout

    def run(self):
        window = sg.Window("Sony ARW Viewer", self.create_layout(), resizable=True, return_keyboard_events=True)

        while True:
            event, values = window.read()

            if event == sg.WIN_CLOSED or event == "Exit":
                break

            if event == "Load Images":
                path = values["-PATH-"]
                if os.path.exists(path):
                    self.current_path = path
                    self.image_files = [f for f in os.listdir(path) 
                                      if f.lower().endswith('.arw')]
                    if self.image_files:
                        self.current_index = 0
                        self.selected_images.clear()
                        self.update_display(window)

            if event in ["Previous", "Next", "Left", "Right"]:
                if (event == "Previous" or event == "Left") and self.current_index > 0:
                    self.current_index -= 1
                elif (event == "Next" or event == "Right") and self.current_index < len(self.image_files) - 1:
                    self.current_index += 1
                self.update_display(window)

            if event in ["-SELECT-", "\r"]:  # Handle both button and Enter key
                if self.current_index in self.selected_images:
                    self.selected_images.remove(self.current_index)
                else:
                    self.selected_images.add(self.current_index)
                window["-SELECTION-COUNT-"].update(f"Selected: {len(self.selected_images)}")

            if event == "-COPY-":
                dest_path = values["-DEST-PATH-"]
                if dest_path and os.path.exists(dest_path):
                    copied = self.copy_selected_images(dest_path)
                    sg.popup(f"Copied {copied} images successfully!")
                else:
                    sg.popup("Please select a valid destination path!")

    def update_display(self, window):
        if not self.image_files:
            return

        current_filename = self.image_files[self.current_index]
        window["-FILENAME-"].update(f"Current image: {current_filename}")
        
        # Add visual indicator for selected images
        if self.current_index in self.selected_images:
            window["-FILENAME-"].update(f"Current image: ✓ {current_filename}")
        else:
            window["-FILENAME-"].update(f"Current image: {current_filename}")

        current_file = os.path.join(self.current_path, self.image_files[self.current_index])
        main_image_data = self.load_raw_preview(current_file, self.main_image_size)
        if main_image_data:
            window["-MAIN-IMAGE-"].update(data=main_image_data)
            # Update main image border based on selection with green color
            if self.current_index in self.selected_images:
                window["-MAIN-IMAGE-"].Widget.configure(borderwidth=3, relief="solid", highlightcolor="green", highlightbackground="green")
            else:
                window["-MAIN-IMAGE-"].Widget.configure(borderwidth=0, relief="flat", highlightcolor="white", highlightbackground="white")

        photo_info = self.get_photo_info(current_file)
        window["-PHOTO-INFO-"].update(photo_info)

        # Update thumbnails
        start_idx = max(0, self.current_index - 2)
        end_idx = min(len(self.image_files), start_idx + 5)
        
        for i in range(5):
            thumb_key = f"-THUMB-{i}-"
            if start_idx + i < end_idx:
                thumb_file = os.path.join(self.current_path, 
                                        self.image_files[start_idx + i])
                thumb_data = self.load_raw_preview(thumb_file, self.thumbnail_size)
                if thumb_data:
                    window[thumb_key].update(data=thumb_data)
                    # Update thumbnail border based on selection with green color
                    if (start_idx + i) in self.selected_images:
                        window[thumb_key].Widget.configure(borderwidth=2, relief="solid", highlightcolor="green", highlightbackground="green")
                    else:
                        window[thumb_key].Widget.configure(borderwidth=0, relief="flat", highlightcolor="white", highlightbackground="white")
            else:
                window[thumb_key].update(data=None)
                window[thumb_key].Widget.configure(borderwidth=0, relief="flat", highlightcolor="white", highlightbackground="white")

if __name__ == "__main__":
    viewer = RawImageViewer()
    viewer.run()