import sys
import os
import folium
import uuid
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QMessageBox, QComboBox,
    QSizePolicy, QGroupBox, QTextEdit, QCheckBox
)
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl, Qt, pyqtSlot, QObject, QTimer
from PyQt5.QtWebChannel import QWebChannel
from geopy.geocoders import Nominatim


class MapClickHandler(QObject):
    def __init__(self, map_app):
        super().__init__()
        self.map_app = map_app

    @pyqtSlot(float, float)
    def on_map_click(self, lat, lng):
        """Handle map click events from JavaScript"""
        if self.map_app.click_mode_enabled:
            self.map_app.add_trajectory_point(lat, lng)


class TrajectoryMapApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🗺️ Sequential Trajectory Mapper - Click to Add Points")
        self.setGeometry(100, 100, 1600, 950)

        # Trajectory data structure
        self.completed_trajectories = []  # List of completed trajectories
        self.current_trajectory = []      # Current trajectory being drawn
        self.is_drawing_mode = True       # Drawing mode flag
        self.click_mode_enabled = True    # Click mode toggle
        
        # Color palette for different trajectories
        self.trajectory_colors = [
            'red', 'blue', 'green', 'purple', 'orange', 
            'darkred', 'pink', 'gray', 'darkblue', 'darkgreen',
            'cadetblue', 'darkpurple', 'lightred', 'beige', 'lightblue'
        ]

        # Set up web communication for map clicks
        self.click_handler = MapClickHandler(self)
        self.channel = QWebChannel()
        self.channel.registerObject('mapHandler', self.click_handler)

        self.setup_ui()
        self.create_initial_map()

    def setup_ui(self):
        """Set up the user interface"""
        main_layout = QVBoxLayout()

        # Control panels
        main_layout.addWidget(self.create_coordinate_panel())
        main_layout.addWidget(self.create_search_panel())
        main_layout.addWidget(self.create_trajectory_panel())
        main_layout.addWidget(self.create_click_control_panel())

        # Map view
        self.map_view = QWebEngineView()
        self.map_view.page().setWebChannel(self.channel)
        self.map_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        main_layout.addWidget(self.map_view, 1)

        # Status and info panel
        main_layout.addWidget(self.create_info_panel())

        self.setLayout(main_layout)

    def create_coordinate_panel(self):
        """Create manual coordinate input panel"""
        group = QGroupBox("📍 Manual Coordinate Entry")
        layout = QHBoxLayout()

        self.lat_input = QLineEdit()
        self.lat_input.setPlaceholderText("Latitude (e.g., 40.7128)")
        self.lon_input = QLineEdit()
        self.lon_input.setPlaceholderText("Longitude (e.g., -74.0060)")
        
        add_manual_btn = QPushButton("Add Point")
        add_manual_btn.clicked.connect(self.add_manual_point)
        add_manual_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; padding: 8px; }")

        layout.addWidget(QLabel("Lat:"))
        layout.addWidget(self.lat_input)
        layout.addWidget(QLabel("Lon:"))
        layout.addWidget(self.lon_input)
        layout.addWidget(add_manual_btn)

        group.setLayout(layout)
        return group

    def create_search_panel(self):
        """Create place search panel"""
        group = QGroupBox("🔍 Place Search & Map Style")
        layout = QHBoxLayout()

        self.place_input = QLineEdit()
        self.place_input.setPlaceholderText("Search for places (e.g., Times Square, New York)")
        self.place_input.returnPressed.connect(self.search_place)
        
        search_btn = QPushButton("Search")
        search_btn.clicked.connect(self.search_place)
        search_btn.setStyleSheet("QPushButton { background-color: #2196F3; color: white; font-weight: bold; padding: 8px; }")
        
        self.map_style_combo = QComboBox()
        self.map_style_combo.addItems(["OpenStreetMap", "Satellite View", "Terrain"])
        self.map_style_combo.currentTextChanged.connect(self.refresh_map)

        layout.addWidget(self.place_input)
        layout.addWidget(search_btn)
        layout.addWidget(QLabel("Style:"))
        layout.addWidget(self.map_style_combo)

        group.setLayout(layout)
        return group

    def create_click_control_panel(self):
        """Create click control panel"""
        group = QGroupBox("🖱️ Click Controls")
        layout = QHBoxLayout()

        # Click mode toggle
        self.click_mode_checkbox = QCheckBox("Enable Map Clicking")
        self.click_mode_checkbox.setChecked(True)
        self.click_mode_checkbox.stateChanged.connect(self.toggle_click_mode)
        self.click_mode_checkbox.setStyleSheet("QCheckBox { font-weight: bold; }")

        # Click mode status
        self.click_status_label = QLabel("🟢 Click Mode: ENABLED")
        self.click_status_label.setStyleSheet("color: green; font-weight: bold;")

        # Instructions
        instructions = QLabel("💡 Click directly on the map to add trajectory points instantly!")
        instructions.setStyleSheet("color: #666; font-style: italic; font-size: 11px;")
        instructions.setWordWrap(True)

        layout.addWidget(self.click_mode_checkbox)
        layout.addWidget(self.click_status_label)
        layout.addStretch()
        layout.addWidget(instructions)

        group.setLayout(layout)
        return group

    def create_trajectory_panel(self):
        """Create trajectory control panel"""
        group = QGroupBox("🛤️ Trajectory Controls")
        layout = QVBoxLayout()

        # Status row
        status_layout = QHBoxLayout()
        self.drawing_status = QLabel("🟢 DRAWING MODE: Click on map to add points")
        self.drawing_status.setStyleSheet("color: green; font-weight: bold; font-size: 12px;")
        self.trajectory_count_label = QLabel("Trajectories: 0 | Current Points: 0")
        
        status_layout.addWidget(self.drawing_status)
        status_layout.addStretch()
        status_layout.addWidget(self.trajectory_count_label)

        # Button row
        button_layout = QHBoxLayout()
        
        self.finish_btn = QPushButton("✅ Finish Current Trajectory")
        self.finish_btn.clicked.connect(self.finish_current_trajectory)
        self.finish_btn.setStyleSheet("QPushButton { background-color: #2196F3; color: white; font-weight: bold; padding: 8px; }")
        
        self.clear_current_btn = QPushButton("🗑️ Clear Current")
        self.clear_current_btn.clicked.connect(self.clear_current_trajectory)
        self.clear_current_btn.setStyleSheet("QPushButton { background-color: #FF9800; color: white; font-weight: bold; padding: 8px; }")
    
        self.clear_all_btn = QPushButton("🗑️ Clear All")
        self.clear_all_btn.clicked.connect(self.clear_all_trajectories)
        self.clear_all_btn.setStyleSheet("QPushButton { background-color: #F44336; color: white; font-weight: bold; padding: 8px; }")

        button_layout.addWidget(self.finish_btn)
        button_layout.addWidget(self.clear_current_btn)
        button_layout.addWidget(self.clear_all_btn)

        layout.addLayout(status_layout)
        layout.addLayout(button_layout)
        group.setLayout(layout)
        return group

    def create_info_panel(self):
        """Create information display panel"""
        group = QGroupBox("ℹ️ Information & Status")
        layout = QVBoxLayout()

        self.info_label = QLabel("🚀 Ready! Click anywhere on the map to start adding trajectory points.")
        self.info_label.setStyleSheet("padding: 10px; background-color: #E3F2FD; border-radius: 6px; font-size: 11px; border: 1px solid #BBDEFB;")
        self.info_label.setWordWrap(True)

        layout.addWidget(self.info_label)
        group.setLayout(layout)
        return group

    def toggle_click_mode(self, state):
        """Toggle click mode on/off"""
        self.click_mode_enabled = state == Qt.Checked
        
        if self.click_mode_enabled:
            self.click_status_label.setText("🟢 Click Mode: ENABLED")
            self.click_status_label.setStyleSheet("color: green; font-weight: bold;")
            self.info_label.setText("🖱️ Click mode enabled! Click anywhere on the map to add trajectory points.")
        else:
            self.click_status_label.setText("🔴 Click Mode: DISABLED")
            self.click_status_label.setStyleSheet("color: red; font-weight: bold;")
            self.info_label.setText("🖱️ Click mode disabled. Use manual coordinate entry to add points.")

    def create_initial_map(self):
        """Create the initial map centered on New York City"""
        self.current_map = folium.Map(
            location=[40.7128, -74.0060],  # NYC coordinates
            zoom_start=12,
            tiles='OpenStreetMap'
        )
        
        self.add_map_click_handler()
        self.save_and_display_map()

    def add_map_click_handler(self):
        """Add JavaScript click handler to the map"""
        click_script = """
        <script>
        function setupMapClicks() {
            // Wait for map to be fully loaded
            if (typeof window.map === 'undefined') {
                setTimeout(setupMapClicks, 100);
                return;
            }
            
            // Remove any existing click handlers
            window.map.off('click');
            
            // Add click handler
            window.map.on('click', function(e) {
                // Send click to Python immediately
                if (typeof qt !== 'undefined' && qt.webChannelTransport) {
                    new QWebChannel(qt.webChannelTransport, function(channel) {
                        var handler = channel.objects.mapHandler;
                        if (handler && handler.on_map_click) {
                            handler.on_map_click(e.latlng.lat, e.latlng.lng);
                        }
                    });
                }
            });
            
            // Set cursor style
            window.map.getContainer().style.cursor = 'crosshair';
        }
        
        // Initialize when DOM is ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', setupMapClicks);
        } else {
            setupMapClicks();
        }
        </script>
        """
        
        self.current_map.get_root().html.add_child(folium.Element(click_script))

    def add_trajectory_point(self, lat, lng):
        """Add a new point to the current trajectory"""
        if not self.is_drawing_mode or not self.click_mode_enabled:
            return

        # Add the point to current trajectory
        self.current_trajectory.append([lat, lng])
        
        # Update UI immediately
        self.update_status_labels()
        
        point_count = len(self.current_trajectory)
        
        if point_count == 1:
            self.info_label.setText(
                f"🎯 Point #{point_count} added at ({lat:.6f}, {lng:.6f}). Click to add more points!"
            )
        else:
            self.info_label.setText(
                f"📍 Point #{point_count} added at ({lat:.6f}, {lng:.6f}). Continue clicking or finish trajectory."
            )
        
        # Refresh map immediately
        self.refresh_map()

    def add_manual_point(self):
        """Add a point using manual coordinate input"""
        try:
            lat_text = self.lat_input.text().strip()
            lng_text = self.lon_input.text().strip()
            
            if not lat_text or not lng_text:
                QMessageBox.warning(self, "Missing Coordinates", "Please enter both latitude and longitude values.")
                return
            
            lat = float(lat_text)
            lng = float(lng_text)
            
            # Validate coordinates
            if not (-90 <= lat <= 90):
                raise ValueError("Latitude must be between -90 and 90 degrees")
            if not (-180 <= lng <= 180):
                raise ValueError("Longitude must be between -180 and 180 degrees")
            
            self.add_trajectory_point(lat, lng)
            
            # Clear input fields
            self.lat_input.clear()
            self.lon_input.clear()
            self.lat_input.setFocus()
            
        except ValueError as e:
            QMessageBox.warning(self, "Invalid Coordinates", f"Error: {str(e)}")

    def finish_current_trajectory(self):
        """Finish the current trajectory and prepare for a new one"""
        if len(self.current_trajectory) == 0:
            QMessageBox.information(self, "No Trajectory", "No points to save. Add some points first!")
            return
        
        if len(self.current_trajectory) == 1:
            reply = QMessageBox.question(
                self, "Single Point Trajectory", 
                "Current trajectory has only one point. Do you want to save it anyway?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                return

        # Save current trajectory
        self.completed_trajectories.append(self.current_trajectory.copy())
        points_saved = len(self.current_trajectory)
        self.current_trajectory = []
        
        # Update UI
        self.update_status_labels()
        trajectory_num = len(self.completed_trajectories)
        self.info_label.setText(
            f"✅ Trajectory #{trajectory_num} completed with {points_saved} points! Click to start a new trajectory."
        )
        
        # Refresh map
        self.refresh_map()

    def clear_current_trajectory(self):
        """Clear the current trajectory being drawn"""
        if len(self.current_trajectory) == 0:
            QMessageBox.information(self, "Nothing to Clear", "No current trajectory to clear.")
            return
        
        points_cleared = len(self.current_trajectory)
        self.current_trajectory = []
        self.update_status_labels()
        self.info_label.setText(f"🗑️ Current trajectory cleared ({points_cleared} points). Click on map to start new trajectory.")
        self.refresh_map()

    def clear_all_trajectories(self):
        """Clear all trajectories"""
        total_trajectories = len(self.completed_trajectories)
        current_points = len(self.current_trajectory)
        
        if total_trajectories == 0 and current_points == 0:
            QMessageBox.information(self, "Nothing to Clear", "No trajectories to clear.")
            return
        
        reply = QMessageBox.question(
            self, "Clear All Trajectories", 
            f"Clear {total_trajectories} completed trajectories and {current_points} current points?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.completed_trajectories = []
            self.current_trajectory = []
            self.update_status_labels()
            self.info_label.setText("🗑️ All trajectories cleared. Click on the map to start drawing.")
            self.refresh_map()

    def search_place(self):
        """Search for a place and center the map on it"""
        place_name = self.place_input.text().strip()
        if not place_name:
            QMessageBox.warning(self, "Empty Search", "Please enter a place name to search.")
            return

        try:
            self.info_label.setText("🔍 Searching...")
            QApplication.processEvents()
            
            geolocator = Nominatim(user_agent="trajectory_mapper")
            location = geolocator.geocode(place_name, timeout=10)
            
            if location:
                # Center map on found location
                self.create_map_at_location([location.latitude, location.longitude], 15)
                
                # Add search marker
                folium.Marker(
                    [location.latitude, location.longitude],
                    popup=f"📍 {place_name}<br>{location.address}",
                    tooltip="Search Result",
                    icon=folium.Icon(color='blue', icon='search')
                ).add_to(self.current_map)
                
                # Re-add all trajectories
                self.add_all_trajectories_to_map()
                self.add_map_click_handler()
                self.save_and_display_map()
                
                self.info_label.setText(f"📍 Found: {location.address}")
                
            else:
                self.info_label.setText(f"❌ Could not find '{place_name}'. Try a different search.")
                
        except Exception as e:
            self.info_label.setText(f"❌ Search error: {str(e)}")

    def get_map_tiles(self):
        """Get the appropriate tile layer based on selected style"""
        style = self.map_style_combo.currentText()
        
        if style == "Satellite View":
            return {
                'tiles': 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
                'attr': 'Tiles © Esri'
            }
        elif style == "Terrain":
            return {
                'tiles': 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Terrain_Base/MapServer/tile/{z}/{y}/{x}',
                'attr': 'Tiles © Esri'
            }
        else:  # OpenStreetMap
            return {
                'tiles': 'OpenStreetMap',
                'attr': None
            }

    def create_map_at_location(self, center, zoom):
        """Create a new map at the specified location"""
        tile_config = self.get_map_tiles()
        
        if tile_config['attr']:
            self.current_map = folium.Map(
                location=center,
                zoom_start=zoom,
                tiles=tile_config['tiles'],
                attr=tile_config['attr']
            )
        else:
            self.current_map = folium.Map(
                location=center,
                zoom_start=zoom,
                tiles=tile_config['tiles']
            )

    def refresh_map(self):
        """Refresh the entire map with all trajectories"""
        # Determine map center
        center = [40.7128, -74.0060]  # Default NYC
        zoom = 12
        
        if self.current_trajectory:
            center = self.current_trajectory[-1]
            zoom = 15
        elif self.completed_trajectories:
            last_trajectory = self.completed_trajectories[-1]
            if last_trajectory:
                center = last_trajectory[-1]
                zoom = 15

        # Create new map
        self.create_map_at_location(center, zoom)
        
        # Add all trajectories
        self.add_all_trajectories_to_map()
        
        # Add click handler
        self.add_map_click_handler()
        
        # Display the map
        self.save_and_display_map()

    def add_all_trajectories_to_map(self):
        """Add all completed and current trajectories to the map"""
        # Add completed trajectories
        for i, trajectory in enumerate(self.completed_trajectories):
            self.add_single_trajectory_to_map(trajectory, i, completed=True)
        
        # Add current trajectory being drawn
        if self.current_trajectory:
            self.add_single_trajectory_to_map(self.current_trajectory, len(self.completed_trajectories), completed=False)

    def add_single_trajectory_to_map(self, trajectory, index, completed=True):
        """Add a single trajectory to the map"""
        if len(trajectory) == 0:
            return
            
        color = self.trajectory_colors[index % len(self.trajectory_colors)]
        
        # Add points as markers
        for i, point in enumerate(trajectory):
            if completed:
                # Completed trajectory points
                if i == 0:  # Start point
                    folium.Marker(
                        point,
                        popup=f"🚀 Trajectory {index + 1} - START<br>Lat: {point[0]:.6f}<br>Lng: {point[1]:.6f}",
                        tooltip=f"Start of Trajectory {index + 1}",
                        icon=folium.Icon(color='green', icon='play')
                    ).add_to(self.current_map)
                elif i == len(trajectory) - 1:  # End point
                    folium.Marker(
                        point,
                        popup=f"🏁 Trajectory {index + 1} - END<br>Lat: {point[0]:.6f}<br>Lng: {point[1]:.6f}",
                        tooltip=f"End of Trajectory {index + 1}",
                        icon=folium.Icon(color='red', icon='stop')
                    ).add_to(self.current_map)
                else:  # Middle points
                    folium.CircleMarker(
                        point,
                        radius=5,
                        popup=f"Point {i + 1}<br>Lat: {point[0]:.6f}<br>Lng: {point[1]:.6f}",
                        tooltip=f"Point {i + 1}",
                        color=color,
                        fill=True,
                        fillColor=color,
                        fillOpacity=0.7
                    ).add_to(self.current_map)
            else:
                # Current trajectory points - bright orange circles
                folium.CircleMarker(
                    point,
                    radius=8,
                    popup=f"Current Point {i + 1}<br>Lat: {point[0]:.6f}<br>Lng: {point[1]:.6f}",
                    tooltip=f"Current Point {i + 1}",
                    color='#FF6600',
                    fill=True,
                    fillColor='#FF6600',
                    fillOpacity=1.0,
                    weight=3
                ).add_to(self.current_map)

        # Add lines connecting points
        if len(trajectory) > 1:
            if completed:
                # Solid line for completed trajectories
                folium.PolyLine(
                    locations=trajectory,
                    color=color,
                    weight=4,
                    opacity=0.8,
                    popup=f"Trajectory {index + 1} ({len(trajectory)} points)"
                ).add_to(self.current_map)
            else:
                # Dashed line for current trajectory
                folium.PolyLine(
                    locations=trajectory,
                    color='#FF6600',
                    weight=5,
                    opacity=1.0,
                    dashArray='10, 5',
                    popup=f"Current Trajectory ({len(trajectory)} points)"
                ).add_to(self.current_map)

    def update_status_labels(self):
        """Update the status labels"""
        current_points = len(self.current_trajectory)
        total_trajectories = len(self.completed_trajectories)
        
        self.trajectory_count_label.setText(f"Trajectories: {total_trajectories} | Current Points: {current_points}")

    def save_and_display_map(self):
        """Save the map to HTML file and display it"""
        map_file = os.path.abspath("trajectory_map.html")
        self.current_map.save(map_file)
        self.map_view.setUrl(QUrl.fromLocalFile(map_file))


def main():
    """Main application entry point"""
    app = QApplication(sys.argv)
    
    app.setApplicationName("Sequential Trajectory Mapper")
    app.setOrganizationName("TrajectoryTools")
    app.setApplicationVersion("2.1")
    
    window = TrajectoryMapApp()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
