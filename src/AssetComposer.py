import os
import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QTreeWidget, QTreeWidgetItem, QFileDialog, QGraphicsView, QGraphicsScene,
    QMessageBox
)
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPixmap, QImage, QPainter, QWheelEvent
from PIL import Image

class ImageLayeringApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.export_directory = "G:\Pil\Games\What-a-Legend-0.7.02c-pc\img"
        self.export_count = 1
        self.setWindowTitle("Image Layering Tool (PySide6)")

        self.folder_path = None
        # We'll store file paths in tree items using setData and custom roles.
        self.DataRole = Qt.UserRole

        # Central widget and main layout
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)

        # Left panel: controls + tree
        left_panel = QVBoxLayout()
        main_layout.addLayout(left_panel, 1)

        # Controls
        control_layout = QHBoxLayout()
        left_panel.addLayout(control_layout)

        self.btn_select_folder = QPushButton("Select Folder")
        self.btn_select_folder.clicked.connect(self.select_folder)
        control_layout.addWidget(self.btn_select_folder)

        self.btn_expand_all = QPushButton("Expand All")
        self.btn_expand_all.clicked.connect(self.expand_all)
        control_layout.addWidget(self.btn_expand_all)

        self.btn_up = QPushButton("Up")
        self.btn_up.clicked.connect(self.move_item_up)
        control_layout.addWidget(self.btn_up)

        self.btn_down = QPushButton("Down")
        self.btn_down.clicked.connect(self.move_item_down)
        control_layout.addWidget(self.btn_down)

        self.btn_export = QPushButton("Export PNG")
        self.btn_export.clicked.connect(self.export_image)
        control_layout.addWidget(self.btn_export)

        # Tree Widget
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Name"])
        self.tree.itemChanged.connect(self.on_item_changed)
        self.tree.itemDoubleClicked.connect(self.on_item_double_click)
        left_panel.addWidget(self.tree, 1)

        # Enable keyboard toggling (space/enter)
        self.tree.itemActivated.connect(self.on_item_activated)  # Enter/Return

        # Right panel: Preview
        self.graphics_view = QGraphicsView()
        self.graphics_scene = QGraphicsScene()
        self.graphics_view.setScene(self.graphics_scene)
        self.graphics_view.setDragMode(QGraphicsView.ScrollHandDrag)
        main_layout.addWidget(self.graphics_view, 3)

        # Variables for preview
        self.preview_image = None
        self.pixmap_item = None

        # Zoom factor
        self.zoom_factor = 1.0

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if not folder:
            return
        self.folder_path = folder
        self.build_tree()

    def build_tree(self):
        self.tree.clear()

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

        def insert_nodes(parent_item, dictionary):
            for key, val in dictionary.items():
                if isinstance(val, dict):
                    # group node
                    item = QTreeWidgetItem(parent_item, [key])
                    item.setCheckState(0, Qt.CheckState.Checked)
                    # No path data (None)
                    item.setData(0, self.DataRole, None)
                    insert_nodes(item, val)
                else:
                    # leaf node
                    item = QTreeWidgetItem(parent_item, [key])
                    item.setCheckState(0, Qt.CheckState.Unchecked)
                    full_path = os.path.join(self.folder_path, val)
                    item.setData(0, self.DataRole, full_path)

        insert_nodes(self.tree.invisibleRootItem(), structure)
        self.tree.expandAll()

        self.update_preview()

    def expand_all(self):
        self.tree.expandAll()

    def on_item_changed(self, item, column):
        # Update preview if item check state changed
        self.update_preview()

    def on_item_double_click(self, item, column):
        # Toggle check state on double click
        current = item.checkState(0)
        new_state = Qt.Unchecked if current == Qt.Checked else Qt.Checked
        item.setCheckState(0, new_state)

    def on_item_activated(self, item, column):
        # Toggle on enter/return
        self.toggle_item(item)

    def keyPressEvent(self, event):
        # Toggle on space if tree has focus
        if event.key() == Qt.Key_Space and self.tree.hasFocus():
            item = self.tree.currentItem()
            if item:
                self.toggle_item(item)
            return
        super().keyPressEvent(event)

    def toggle_item(self, item):
        current = item.checkState(0)
        new_state = Qt.Unchecked if current == Qt.Checked else Qt.Checked
        item.setCheckState(0, new_state)

    def move_item_up(self):
        item = self.tree.currentItem()
        if not item:
            return
        parent = item.parent()
        if parent is None:
            parent = self.tree.invisibleRootItem()
        idx = parent.indexOfChild(item)
        if idx > 0:
            parent.takeChild(idx)
            parent.insertChild(idx-1, item)
            self.update_preview()

    def move_item_down(self):
        item = self.tree.currentItem()
        if not item:
            return
        parent = item.parent()
        if parent is None:
            parent = self.tree.invisibleRootItem()
        idx = parent.indexOfChild(item)
        if idx < parent.childCount()-1:
            parent.takeChild(idx)
            parent.insertChild(idx+1, item)
            self.update_preview()

    def get_leaf_images_in_order(self):
        # Traverse the tree in order, collecting visible leaf images
        images = []

        def visible(item):
            # An item is visible if all ancestors and itself are checked
            p = item
            while p is not None:
                if p.checkState(0) == Qt.Unchecked:
                    return False
                p = p.parent()
            return True

        def recurse(item):
            for i in range(item.childCount()):
                c = item.child(i)
                if c.childCount() == 0:
                    # leaf
                    if visible(c):
                        path = c.data(0, self.DataRole)
                        if path:
                            images.append(path)
                else:
                    # group
                    if visible(c):
                        recurse(c)

        root = self.tree.invisibleRootItem()
        recurse(root)
        return images

    def update_preview(self):
        paths = self.get_leaf_images_in_order()
        if not paths:
            self.preview_image = None
            self.graphics_scene.clear()
            self.pixmap_item = None
            return

        imgs = []
        for p in paths:
            img = Image.open(p).convert('RGBA')
            imgs.append(img)
        base = imgs[0].copy()
        for img in imgs[1:]:
            base.alpha_composite(img)

        self.preview_image = base

        # Convert to QPixmap
        width, height = base.size
        data = base.tobytes("raw", "RGBA")
        qimage = QImage(data, width, height, QImage.Format_RGBA8888)
        pixmap = QPixmap.fromImage(qimage)

        self.graphics_scene.clear()
        self.pixmap_item = self.graphics_scene.addPixmap(pixmap)
        self.pixmap_item.setTransformationMode(Qt.SmoothTransformation)

    def wheelEvent(self, event: QWheelEvent):
        # We allow zooming in the graphics view
        if self.graphics_view.underMouse():
            self.zoom(event)
        else:
            super().wheelEvent(event)

    def zoom(self, event: QWheelEvent):
        if self.preview_image is None:
            return
        delta = event.angleDelta().y()
        factor = 1.1 if delta > 0 else 0.9
        self.zoom_factor *= factor
        if self.zoom_factor < 0.1:
            self.zoom_factor = 0.1
            factor = 1.0

        self.graphics_view.scale(factor, factor)

    def export_image(self):
      if self.preview_image is None:
          QMessageBox.warning(self, "No Image", "There is no composed image to export.")
          return

      # Ensure the export directory exists
      os.makedirs(self.export_directory, exist_ok=True)

      # Generate a filename with incremental numbering
      filename = f"image_{self.export_count:03d}.png"
      save_path = os.path.join(self.export_directory, filename)

      # Save the image
      self.preview_image.save(save_path, "PNG")

      self.export_count += 1  # Increment the counter for next time

      QMessageBox.information(self, "Image Saved", f"Image saved to {save_path}")


def main():
    app = QApplication(sys.argv)
    window = ImageLayeringApp()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
