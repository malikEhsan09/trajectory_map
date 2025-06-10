import sys
import os
import folium
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QMessageBox, QComboBox,
    QSizePolicy, QGroupBox, QCheckBox
)
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl, Qt, pyqtSlot, QObject
from PyQt5.QtWebChannel import QWebChannel
from geopy.geocoders import Nominatim


class MapClickHandler(QObject):
    def __init__(self, app):
        super().__init__()
        self.app = app

    @pyqtSlot(float, float)
    def on_map_click(self, lat, lon):
        if self.app.click_mode_enabled:
            self.app.add_trajectory_point(lat, lon)


class TrajectoryMapApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🗺️ Trajectory Mapper")
        self.setGeometry(100, 100, 1400, 900)

        self.completed_trajectories = []
        self.current_trajectory = []
        self.click_mode_enabled = True
        self.trajectory_colors = ['red', 'blue', 'green', 'purple', 'orange']

        self.click_handler = MapClickHandler(self)
        self.channel = QWebChannel()
        self.channel.registerObject('mapHandler', self.click_handler)

        self.setup_ui()
        self.create_initial_map()

    def setup_ui(self):
        layout = QVBoxLayout()
        layout.addWidget(self.create_input_panel())
        layout.addWidget(self.create_controls_panel())

        self.map_view = QWebEngineView()
        self.map_view.page().setWebChannel(self.channel)
        self.map_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.map_view, 1)

        layout.addWidget(self.create_status_panel())
        self.setLayout(layout)

    def create_input_panel(self):
        group = QGroupBox("📍 Add Coordinates / Search")
        layout = QHBoxLayout()

        self.lat_input = QLineEdit()
        self.lat_input.setPlaceholderText("Latitude")
        self.lon_input = QLineEdit()
        self.lon_input.setPlaceholderText("Longitude")

        add_btn = QPushButton("Add Point")
        add_btn.clicked.connect(self.add_manual_point)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search Place")
        self.search_input.returnPressed.connect(self.search_place)

        search_btn = QPushButton("Search")
        search_btn.clicked.connect(self.search_place)

        self.map_style_combo = QComboBox()
        self.map_style_combo.addItems(["OpenStreetMap", "Satellite", "Terrain"])
        self.map_style_combo.currentTextChanged.connect(self.refresh_map)

        layout.addWidget(QLabel("Lat:"))
        layout.addWidget(self.lat_input)
        layout.addWidget(QLabel("Lon:"))
        layout.addWidget(self.lon_input)
        layout.addWidget(add_btn)
        layout.addStretch()
        layout.addWidget(self.search_input)
        layout.addWidget(search_btn)
        layout.addWidget(QLabel("Style:"))
        layout.addWidget(self.map_style_combo)

        group.setLayout(layout)
        return group

    def create_controls_panel(self):
        group = QGroupBox("🛤️ Controls")
        layout = QHBoxLayout()

        self.finish_btn = QPushButton("✅ Finish Trajectory")
        self.finish_btn.clicked.connect(self.finish_current_trajectory)

        self.clear_current_btn = QPushButton("🗑️ Clear Current")
        self.clear_current_btn.clicked.connect(self.clear_current_trajectory)

        self.clear_all_btn = QPushButton("🗑️ Clear All")
        self.clear_all_btn.clicked.connect(self.clear_all_trajectories)

        self.click_toggle = QCheckBox("Enable Map Clicking")
        self.click_toggle.setChecked(True)
        self.click_toggle.stateChanged.connect(self.toggle_click_mode)

        self.trajectory_count_label = QLabel("Trajectories: 0 | Points: 0")

        layout.addWidget(self.finish_btn)
        layout.addWidget(self.clear_current_btn)
        layout.addWidget(self.clear_all_btn)
        layout.addStretch()
        layout.addWidget(self.click_toggle)
        layout.addWidget(self.trajectory_count_label)

        group.setLayout(layout)
        return group

    def create_status_panel(self):
        group = QGroupBox("ℹ️ Status")
        layout = QVBoxLayout()
        self.status_label = QLabel("✅ Ready! Click the map to add points.")
        layout.addWidget(self.status_label)
        group.setLayout(layout)
        return group

    def toggle_click_mode(self, state):
        self.click_mode_enabled = (state == Qt.Checked)

    def create_initial_map(self):
        self.current_map = folium.Map(location=[40.7128, -74.0060], zoom_start=12)
        self.add_map_click_handler()
        self.save_and_display_map()

    def add_map_click_handler(self):
        # Short minified version of qwebchannel.js (not the full one, just a stub for demo purposes)
        qwebchannel_stub = """
        (function () {
            window.QWebChannel = function (transport, callback) {
                transport.send(JSON.stringify({type: "connect"}));
                this.objects = {
                    mapHandler: {
                        on_map_click: function (lat, lng) {
                            transport.send(JSON.stringify({type: "click", lat: lat, lng: lng}));
                        }
                    }
                };
                callback(this);
            };
        })();
        """

        js = f"""
        <script>{qwebchannel_stub}</script>
        <script>
        document.addEventListener("DOMContentLoaded", function () {{
            new QWebChannel(qt.webChannelTransport, function(channel) {{
                var handler = channel.objects.mapHandler;
                if (window.map && handler) {{
                    window.map.on('click', function(e) {{
                        handler.on_map_click(e.latlng.lat, e.latlng.lng);
                    }});
                    window.map.getContainer().style.cursor = 'crosshair';
                }}
            }});
        }});
        </script>
        """
        self.current_map.get_root().html.add_child(folium.Element(js))

    def add_manual_point(self):
        try:
            lat = float(self.lat_input.text())
            lon = float(self.lon_input.text())
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                raise ValueError
            self.add_trajectory_point(lat, lon)
            self.lat_input.clear()
            self.lon_input.clear()
        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Please enter valid coordinates.")

    def add_trajectory_point(self, lat, lon):
        self.current_trajectory.append([lat, lon])
        self.update_status()
        self.refresh_map()

    def finish_current_trajectory(self):
        if not self.current_trajectory:
            QMessageBox.information(self, "Empty", "No points to save.")
            return
        self.completed_trajectories.append(self.current_trajectory.copy())
        self.current_trajectory.clear()
        self.update_status()
        self.refresh_map()

    def clear_current_trajectory(self):
        self.current_trajectory.clear()
        self.update_status()
        self.refresh_map()

    def clear_all_trajectories(self):
        self.completed_trajectories.clear()
        self.current_trajectory.clear()
        self.update_status()
        self.refresh_map()

    def update_status(self):
        self.trajectory_count_label.setText(
            f"Trajectories: {len(self.completed_trajectories)} | Points: {len(self.current_trajectory)}"
        )

    def search_place(self):
        place = self.search_input.text().strip()
        if not place:
            return
        geolocator = Nominatim(user_agent="trajectory_app")
        location = geolocator.geocode(place)
        if location:
            self.create_map_at_location([location.latitude, location.longitude], zoom=15)
            folium.Marker([location.latitude, location.longitude], popup=location.address).add_to(self.current_map)
            self.add_all_trajectories_to_map()
            self.add_map_click_handler()
            self.save_and_display_map()
            self.status_label.setText(f"📍 Found: {location.address}")
        else:
            self.status_label.setText("❌ Location not found.")

    def create_map_at_location(self, center, zoom):
        tile = self.get_map_tiles()
        self.current_map = folium.Map(location=center, zoom_start=zoom, tiles=tile['tiles'], attr=tile.get('attr'))

    def get_map_tiles(self):
        style = self.map_style_combo.currentText()
        if style == "Satellite":
            return {
                'tiles': 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
                'attr': 'Tiles © Esri'
            }
        elif style == "Terrain":
            return {
                'tiles': 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Terrain_Base/MapServer/tile/{z}/{y}/{x}',
                'attr': 'Tiles © Esri'
            }
        return {'tiles': 'OpenStreetMap'}

    def refresh_map(self):
        center = self.current_trajectory[-1] if self.current_trajectory else [40.7128, -74.0060]
        self.create_map_at_location(center, zoom=15)
        self.add_all_trajectories_to_map()
        self.add_map_click_handler()
        self.save_and_display_map()

    def add_all_trajectories_to_map(self):
        for i, traj in enumerate(self.completed_trajectories):
            self.draw_trajectory(traj, i, completed=True)
        if self.current_trajectory:
            self.draw_trajectory(self.current_trajectory, len(self.completed_trajectories), completed=False)

    def draw_trajectory(self, points, index, completed):
        color = self.trajectory_colors[index % len(self.trajectory_colors)]
        for pt in points:
            folium.CircleMarker(pt, radius=6, color=color, fill=True, fill_color=color).add_to(self.current_map)
        if len(points) > 1:
            folium.PolyLine(points, color=color, weight=4, dash_array=None if completed else '10,5').add_to(self.current_map)

    def save_and_display_map(self):
        path = os.path.abspath("trajectory_map.html")
        self.current_map.save(path)
        self.map_view.setUrl(QUrl.fromLocalFile(path))


def main():
    app = QApplication(sys.argv)
    window = TrajectoryMapApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
