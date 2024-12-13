import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk

class ImageLayeringApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Image Layering Tool")

        self.folder_path = None
        self.all_files = {}   # Mapping from tree item to file path
        self.selected_layers = []  # (full_name, file_path)
        self.preview_image = None

        # Drag and Drop state variables
        self.dragging = False
        self.drag_source = None  # "tree" or "layers"
        self.drag_data = None    # Item info being dragged
        self.drag_indicator = None

        # For preview zoom and pan
        self.scale_factor = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.dragging_canvas = False
        self.canvas_drag_start = (0,0)
        
        # Create main paned window for resizable layout
        self.paned = ttk.Panedwindow(self.root, orient='horizontal')
        self.paned.pack(fill='both', expand=True)

        # Left frame: Hierarchy (tree)
        self.left_frame = ttk.Frame(self.paned)
        self.paned.add(self.left_frame, weight=1)

        # Right frame: Layers and preview
        self.right_frame = ttk.Frame(self.paned)
        self.paned.add(self.right_frame, weight=1)

        # Top part of left frame: select folder, etc.
        self.btn_select_folder = ttk.Button(self.left_frame, text="Select Folder", command=self.select_folder)
        self.btn_select_folder.pack(pady=5, anchor='w')

        # Treeview for files
        self.tree = ttk.Treeview(self.left_frame, show='tree')
        self.tree.pack(expand=True, fill='both', padx=5, pady=5)
        self.tree.bind("<Double-1>", self.on_tree_double_click)
        self.tree.bind("<ButtonPress-1>", self.on_tree_button_press)
        self.tree.bind("<B1-Motion>", self.on_tree_mouse_move)
        self.tree.bind("<ButtonRelease-1>", self.on_tree_button_release)

        # Right frame: Layers list (top), preview (bottom)
        # We'll use another paned window to split layers list (top) and preview (bottom)
        self.right_paned = ttk.Panedwindow(self.right_frame, orient='vertical')
        self.right_paned.pack(fill='both', expand=True)

        # Layers frame
        self.layers_frame = ttk.Frame(self.right_paned)
        self.right_paned.add(self.layers_frame, weight=1)

        ttk.Label(self.layers_frame, text="Selected Layers (drag to reorder):").pack(anchor='w')

        self.layers_listbox = tk.Listbox(self.layers_frame, selectmode='single')
        self.layers_listbox.pack(expand=True, fill='both', padx=5, pady=5)
        self.layers_listbox.bind("<ButtonPress-1>", self.on_layers_button_press)
        self.layers_listbox.bind("<B1-Motion>", self.on_layers_mouse_move)
        self.layers_listbox.bind("<ButtonRelease-1>", self.on_layers_button_release)

        self.btn_export = ttk.Button(self.layers_frame, text="Export to PNG", command=self.export_image)
        self.btn_export.pack(anchor='w', pady=5)

        # Preview canvas
        self.preview_frame = ttk.Frame(self.right_paned)
        self.right_paned.add(self.preview_frame, weight=3)

        self.canvas = tk.Canvas(self.preview_frame, background='gray')
        self.canvas.pack(expand=True, fill='both')

        self.canvas.bind("<Configure>", self.update_canvas)
        self.canvas.bind("<ButtonPress-2>", self.on_canvas_drag_start)  # Middle button pan
        self.canvas.bind("<B2-Motion>", self.on_canvas_drag_move)
        self.canvas.bind("<ButtonPress-1>", self.on_canvas_drag_start)  # Also allow left button pan
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag_move)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_drag_end)
        self.canvas.bind("<ButtonRelease-2>", self.on_canvas_drag_end)
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)  # Windows
        self.canvas.bind("<Button-4>", self.on_mouse_wheel)    # Linux scroll up
        self.canvas.bind("<Button-5>", self.on_mouse_wheel)    # Linux scroll down

    def select_folder(self):
        folder = filedialog.askdirectory()
        if not folder:
            return
        self.folder_path = folder
        self.build_tree()

    def build_tree(self):
        # Clear old tree
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.all_files.clear()

        # Parse .webp files in folder
        files = [f for f in os.listdir(self.folder_path) if f.lower().endswith('.webp')]
        structure = {}
        for f in files:
            parts = f[:-5].split('_')
            current_level = structure
            for p in parts[:-1]:
                if p not in current_level:
                    current_level[p] = {}
                current_level = current_level[p]
            last_part = parts[-1]
            current_level[last_part] = f

        def insert_nodes(parent, dictionary):
            for key, val in dictionary.items():
                if isinstance(val, dict):
                    node_id = self.tree.insert(parent, "end", text=key)
                    insert_nodes(node_id, val)
                else:
                    # leaf
                    file_id = self.tree.insert(parent, "end", text=key)
                    full_path = os.path.join(self.folder_path, val)
                    self.all_files[file_id] = full_path

        insert_nodes('', structure)

    def on_tree_double_click(self, event):
        # Add the clicked leaf node to layers
        item_id = self.tree.focus()
        if item_id in self.all_files:
            self.add_file_to_layers(item_id)

    def add_file_to_layers(self, item_id):
        path = self.all_files[item_id]
        full_name = self.get_full_name(item_id)
        self.selected_layers.append((full_name, path))
        self.refresh_layers_listbox()
        self.update_preview()

    def get_full_name(self, item_id):
        name_parts = []
        def recurse(i):
            parent = self.tree.parent(i)
            if parent:
                recurse(parent)
            name_parts.append(self.tree.item(i, 'text'))
        recurse(item_id)
        return "_".join(name_parts)

    def refresh_layers_listbox(self):
        self.layers_listbox.delete(0, 'end')
        for name, _ in self.selected_layers:
            self.layers_listbox.insert('end', name)

    def update_preview(self):
        if not self.selected_layers:
            self.preview_image = None
            self.canvas.delete("all")
            return
        images = []
        for name, path in self.selected_layers:
            img = Image.open(path).convert('RGBA')
            images.append(img)

        base = images[0].copy()
        for img in images[1:]:
            base.alpha_composite(img)

        self.preview_image = base
        self.redraw_canvas_image()

    def redraw_canvas_image(self):
        self.canvas.delete("all")
        if self.preview_image is None:
            return

        # Create a scaled version of the image for display
        # Actually, we will use Canvas scale and translate transforms.
        # We'll put image on canvas as a PhotoImage and then scale by canvas methods.
        
        # To handle zoom/pan, we don't actually use canvas scale on the image directly,
        # but rather place the image as a single image and apply transformations.
        # Unfortunately, canvas scaling does not apply to images, we must rerender.
        # So we must recreate a resized image. Let's do that for simplicity:
        # We'll keep it simple: on zoom, we re-generate a scaled image.

        width, height = self.preview_image.size
        new_width = int(width * self.scale_factor)
        new_height = int(height * self.scale_factor)
        if new_width <= 0 or new_height <= 0:
            return
        resized = self.preview_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        self.preview_photo = ImageTk.PhotoImage(resized)
        # place image considering offset
        self.canvas.create_image(self.offset_x, self.offset_y, anchor='center', image=self.preview_photo)

    def export_image(self):
        if not self.selected_layers:
            messagebox.showwarning("No Layers", "No layers selected to export.")
            return
        if self.preview_image is None:
            self.update_preview()
        if self.preview_image is None:
            messagebox.showwarning("No Image", "No image to export.")
            return
        output_dir = os.path.join(self.folder_path, "output")
        os.makedirs(output_dir, exist_ok=True)
        export_path = os.path.join(output_dir, "exported.png")
        self.preview_image.save(export_path, "PNG")
        messagebox.showinfo("Exported", f"Image exported to {export_path}")

    # --- Drag and drop from tree to layers ---
    def on_tree_button_press(self, event):
        # start dragging from tree if we clicked on a leaf
        item_id = self.tree.identify_row(event.y)
        if item_id:
            self.tree.selection_set(item_id)
            if item_id in self.all_files:
                self.dragging = True
                self.drag_source = "tree"
                self.drag_data = item_id
                # Create a drag indicator (optional)
                # We'll just change the cursor
                self.root.config(cursor="hand2")

    def on_tree_mouse_move(self, event):
        # If dragging from tree, show some sign
        if self.dragging and self.drag_source == "tree":
            pass  # We could show a drag icon, but let's keep it simple

    def on_tree_button_release(self, event):
        if self.dragging and self.drag_source == "tree":
            # Check if we released over the layers_listbox
            x, y = event.x_root, event.y_root
            widget = self.root.winfo_containing(x, y)
            if widget == self.layers_listbox:
                # Add item
                self.add_file_to_layers(self.drag_data)
            self.dragging = False
            self.drag_source = None
            self.drag_data = None
            self.root.config(cursor="")

    # --- Drag and drop for reordering layers and adding from layers (not needed) ---
    def on_layers_button_press(self, event):
        idx = self.layers_listbox.nearest(event.y)
        if idx >= 0 and idx < len(self.selected_layers):
            self.layers_listbox.selection_clear(0, 'end')
            self.layers_listbox.selection_set(idx)
            self.dragging = True
            self.drag_source = "layers"
            self.drag_data = idx
            self.root.config(cursor="hand2")

    def on_layers_mouse_move(self, event):
        if self.dragging and self.drag_source == "layers":
            # Just highlight potential drop position
            # We'll do this on release
            pass

    def on_layers_button_release(self, event):
        if self.dragging and self.drag_source == "layers":
            idx = self.layers_listbox.nearest(event.y)
            if idx >= len(self.selected_layers):
                idx = len(self.selected_layers)-1
            if idx < 0:
                idx = 0

            old_idx = self.drag_data
            if old_idx != idx:
                layer = self.selected_layers.pop(old_idx)
                self.selected_layers.insert(idx, layer)
                self.refresh_layers_listbox()
                self.update_preview()

            self.dragging = False
            self.drag_source = None
            self.drag_data = None
            self.root.config(cursor="")

    # --- Zoom and Pan for Canvas ---
    def on_mouse_wheel(self, event):
        if self.preview_image is None:
            return
        # Determine direction of wheel
        factor = 1.1 if event.delta > 0 or event.num == 4 else 0.9
        # Zoom about mouse position
        mouse_x = self.canvas.canvasx(event.x)
        mouse_y = self.canvas.canvasy(event.y)

        # Adjust offset for zoom: we want (mouse_x, mouse_y) to remain stable
        # current mouse_x relates to offset and scale:
        # If we scale, we want to translate offset so that point under cursor stays still.
        self.offset_x = mouse_x + (self.offset_x - mouse_x)*factor
        self.offset_y = mouse_y + (self.offset_y - mouse_y)*factor

        self.scale_factor *= factor
        if self.scale_factor < 0.1:
            self.scale_factor = 0.1
        self.redraw_canvas_image()

    def on_canvas_drag_start(self, event):
        self.dragging_canvas = True
        self.canvas_drag_start = (event.x, event.y)

    def on_canvas_drag_move(self, event):
        if self.dragging_canvas and self.preview_image is not None:
            dx = event.x - self.canvas_drag_start[0]
            dy = event.y - self.canvas_drag_start[1]
            self.offset_x += dx
            self.offset_y += dy
            self.canvas_drag_start = (event.x, event.y)
            self.redraw_canvas_image()

    def on_canvas_drag_end(self, event):
        self.dragging_canvas = False

    def update_canvas(self, event):
        # On resize of canvas, just redraw
        self.redraw_canvas_image()

def main():
    root = tk.Tk()
    app = ImageLayeringApp(root)
    root.mainloop()

if __name__ == '__main__':
    main()
