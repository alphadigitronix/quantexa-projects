"""Dedicated Paramedic Hospital Google Maps Navigation Dashboard.

Standalone full-page interface for emergency medical vehicle navigation:
- Real Google Maps tiles & satellite view
- Real address search & preset landmarks across Chennai
- HTML5 Geolocation ("Get My Live GPS Location")
- Click anywhere on map to set pickup or hospital destination
- Genuine driving route computation via OpenStreetMap / OSRM routing engine
- Turn-by-turn navigation & route geometry
- "Start Journey" interactive in-transit navigation simulation
"""

import json
import streamlit as st
import streamlit.components.v1 as components


def generate_hospital_maps_html() -> str:
    """Generate self-contained HTML/CSS/JS application for Paramedic Google Maps."""
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Paramedic Emergency Navigation HUD</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" />
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        }
        body, html {
            height: 100%;
            width: 100%;
            background: #090d16;
            color: #e2e8f0;
            overflow: hidden;
        }
        #app-container {
            display: flex;
            height: 100vh;
            width: 100vw;
            position: relative;
        }

        /* LEFT SIDEBAR: Paramedic Console */
        #sidebar {
            width: 440px;
            min-width: 440px;
            height: 100%;
            background: linear-gradient(180deg, #0b1329 0%, #070d1e 100%);
            border-right: 2px solid rgba(16, 185, 129, 0.35);
            display: flex;
            flex-direction: column;
            z-index: 1000;
            box-shadow: 6px 0 25px rgba(0, 0, 0, 0.7);
            overflow-y: auto;
        }
        .header-bar {
            padding: 16px 20px;
            background: linear-gradient(135deg, #062723 0%, #0c3d36 100%);
            border-bottom: 2px solid #10b981;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .header-title {
            font-size: 1.15rem;
            font-weight: 800;
            color: #34d399;
            display: flex;
            align-items: center;
            gap: 10px;
            letter-spacing: -0.01em;
        }
        .pulse-beacon {
            width: 12px;
            height: 12px;
            background: #ef4444;
            border-radius: 50%;
            box-shadow: 0 0 0 rgba(239, 68, 68, 0.7);
            animation: pulse-ring 1.5s infinite;
        }
        @keyframes pulse-ring {
            0% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.8); }
            70% { box-shadow: 0 0 0 10px rgba(239, 68, 68, 0); }
            100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
        }
        .cad-badge {
            background: rgba(16, 185, 129, 0.18);
            color: #6ee7b7;
            border: 1px solid #10b981;
            padding: 3px 8px;
            border-radius: 6px;
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.05em;
        }

        .console-body {
            padding: 18px;
            display: flex;
            flex-direction: column;
            gap: 16px;
            flex: 1;
        }
        .form-group {
            display: flex;
            flex-direction: column;
            gap: 6px;
        }
        .form-label {
            font-size: 0.82rem;
            font-weight: 700;
            color: #94a3b8;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .input-box {
            width: 100%;
            background: #111a33;
            border: 1px solid #1e293b;
            color: #f8fafc;
            padding: 10px 14px;
            border-radius: 8px;
            font-size: 0.92rem;
            outline: none;
            transition: all 0.2s ease;
        }
        .input-box:focus {
            border-color: #10b981;
            box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.25);
            background: #142040;
        }
        select.input-box {
            cursor: pointer;
        }

        /* Chips & Quick Preset Buttons */
        .chip-container {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            margin-top: 4px;
        }
        .chip-btn {
            background: #172554;
            color: #93c5fd;
            border: 1px solid rgba(147, 197, 253, 0.25);
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 0.74rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.15s ease;
        }
        .chip-btn:hover {
            background: #1d4ed8;
            color: #ffffff;
            border-color: #60a5fa;
            transform: translateY(-1px);
        }

        /* Action Buttons */
        .btn-row {
            display: flex;
            gap: 8px;
        }
        .gps-btn {
            background: linear-gradient(135deg, #1e3a8a 0%, #2563eb 100%);
            color: #ffffff;
            border: 1px solid #60a5fa;
            padding: 8px 12px;
            border-radius: 8px;
            font-size: 0.82rem;
            font-weight: 700;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 6px;
            transition: all 0.2s ease;
            box-shadow: 0 4px 12px rgba(37, 99, 235, 0.25);
        }
        .gps-btn:hover {
            background: linear-gradient(135deg, #2563eb 0%, #3b82f6 100%);
            transform: translateY(-1px);
        }
        .map-pick-btn {
            background: #1e293b;
            color: #cbd5e1;
            border: 1px solid #334155;
            padding: 8px 12px;
            border-radius: 8px;
            font-size: 0.82rem;
            font-weight: 600;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 6px;
            transition: all 0.2s ease;
        }
        .map-pick-btn.active {
            background: #065f46;
            color: #34d399;
            border-color: #10b981;
        }

        /* Route Telemetry HUD Card */
        .telemetry-card {
            background: linear-gradient(135deg, #071f1a 0%, #0c332b 100%);
            border: 1px solid #10b981;
            border-radius: 10px;
            padding: 14px;
            box-shadow: 0 6px 18px rgba(0, 0, 0, 0.4);
        }
        .telem-row {
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
        }
        .telem-item {
            display: flex;
            flex-direction: column;
        }
        .telem-val {
            font-size: 1.35rem;
            font-weight: 800;
            color: #34d399;
            letter-spacing: -0.01em;
        }
        .telem-lbl {
            font-size: 0.72rem;
            color: #a7f3d0;
            text-transform: uppercase;
            font-weight: 600;
        }
        .status-pill {
            display: flex;
            align-items: center;
            gap: 6px;
            font-size: 0.78rem;
            font-weight: 700;
            color: #6ee7b7;
            padding: 6px 10px;
            background: rgba(16, 185, 129, 0.15);
            border-radius: 6px;
            margin-top: 4px;
            border: 1px solid rgba(16, 185, 129, 0.3);
        }

        /* Start Journey Big Button */
        .btn-start-journey {
            background: linear-gradient(135deg, #059669 0%, #10b981 100%);
            color: #ffffff;
            border: none;
            padding: 14px 20px;
            border-radius: 10px;
            font-size: 1.05rem;
            font-weight: 800;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
            box-shadow: 0 6px 20px rgba(16, 185, 129, 0.4);
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
        }
        .btn-start-journey:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(16, 185, 129, 0.6);
            filter: brightness(1.1);
        }
        .btn-start-journey.active {
            background: linear-gradient(135deg, #dc2626 0%, #ef4444 100%);
            box-shadow: 0 6px 20px rgba(239, 68, 68, 0.4);
        }

        /* RIGHT: Real Google Map Container */
        #map-container {
            flex: 1;
            height: 100%;
            position: relative;
        }
        #map {
            width: 100%;
            height: 100%;
            background: #1e293b;
        }

        /* Floating HUD over Google Map */
        .map-hud-overlay {
            position: absolute;
            top: 16px;
            right: 16px;
            z-index: 1000;
            background: rgba(11, 19, 41, 0.92);
            backdrop-filter: blur(8px);
            border: 1px solid rgba(16, 185, 129, 0.4);
            border-radius: 10px;
            padding: 12px 18px;
            color: #f8fafc;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.6);
            display: flex;
            align-items: center;
            gap: 20px;
        }
        .hud-stat {
            display: flex;
            flex-direction: column;
            text-align: right;
        }
        .hud-stat-val {
            font-size: 1.4rem;
            font-weight: 800;
            color: #38bdf8;
        }
        .hud-stat-lbl {
            font-size: 0.7rem;
            color: #94a3b8;
            text-transform: uppercase;
            font-weight: 600;
        }

        /* Map Legend Helper */
        .map-helper-tip {
            position: absolute;
            bottom: 24px;
            left: 20px;
            z-index: 1000;
            background: rgba(15, 23, 42, 0.9);
            border: 1px solid #334155;
            border-radius: 8px;
            padding: 8px 14px;
            font-size: 0.8rem;
            color: #cbd5e1;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
            display: flex;
            align-items: center;
            gap: 8px;
        }

        /* Custom pulsing marker icons */
        .amb-marker-icon {
            background: #2563eb;
            border: 3px solid #ffffff;
            border-radius: 50%;
            box-shadow: 0 0 15px rgba(37, 99, 235, 0.8);
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 14px;
        }
        .hosp-marker-icon {
            background: #ef4444;
            border: 3px solid #ffffff;
            border-radius: 50%;
            box-shadow: 0 0 15px rgba(239, 68, 68, 0.8);
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 14px;
        }
    </style>
</head>
<body>
    <div id="app-container">
        <!-- LEFT SIDEBAR: Paramedic Navigation Console -->
        <div id="sidebar">
            <div class="header-bar">
                <div class="header-title">
                    <div class="pulse-beacon"></div>
                    <span>CHENNAI EMS 108</span>
                </div>
                <div class="cad-badge">STANDALONE NAV DEMO</div>
            </div>

            <div style="background: rgba(245, 158, 11, 0.12); border-bottom: 1px solid rgba(245, 158, 11, 0.4); padding: 9px 16px; font-size: 0.74rem; color: #fde68a; display: flex; align-items: center; gap: 8px;">
                <i class="fa-solid fa-triangle-exclamation" style="color: #fbbf24; font-size: 0.85rem; flex-shrink: 0;"></i>
                <span><strong>Standalone Navigation Demo</strong>: Uses public map tiles and OSRM routing. Not wired to the quantum traffic signal simulator backend.</span>
            </div>

            <div class="console-body">
                <!-- Vehicle ID & Triage Code -->
                <div class="form-group">
                    <label class="form-label">Ambulance Call-Sign & Triage</label>
                    <div style="display: flex; gap: 8px;">
                        <input type="text" id="unit-id" class="input-box" value="AMB-108 (ALS Trauma Pod)" style="flex: 6;" />
                        <select id="triage-code" class="input-box" style="flex: 5;">
                            <option value="Code Red">🔴 Code Red</option>
                            <option value="Code Yellow">🟡 Code Yellow</option>
                        </select>
                    </div>
                </div>

                <!-- 1. Patient Departure Location (From) -->
                <div class="form-group">
                    <label class="form-label">
                        <span>1. Starting Location (From)</span>
                        <span id="from-coords-lbl" style="font-size: 0.7rem; color: #34d399;">13.0500, 80.2824</span>
                    </label>
                    <input type="text" id="origin-input" class="input-box" placeholder="Search Chennai location or address..." value="Marina Beach, Chennai" />
                    
                    <div class="btn-row" style="margin-top: 4px;">
                        <button id="btn-gps" class="gps-btn" onclick="useMyLocation()">
                            <i class="fa-solid fa-location-crosshairs"></i> Use My GPS Location
                        </button>
                        <button id="btn-pick-origin" class="map-pick-btn" onclick="setPickMode('origin')">
                            <i class="fa-solid fa-map-pin"></i> Pick on Map
                        </button>
                    </div>

                    <!-- Preset Chips -->
                    <div class="chip-container">
                        <button class="chip-btn" onclick="setOriginPreset(13.0500, 80.2824, 'Marina Beach')">🏖️ Marina Beach</button>
                        <button class="chip-btn" onclick="setOriginPreset(13.0405, 80.2337, 'T. Nagar (Panagal Park)')">🛍️ T. Nagar</button>
                        <button class="chip-btn" onclick="setOriginPreset(13.0827, 80.2757, 'Central Railway Station')">🚉 Central Station</button>
                        <button class="chip-btn" onclick="setOriginPreset(13.0067, 80.2026, 'Guindy Kathipara')">🏛️ Guindy</button>
                        <button class="chip-btn" onclick="setOriginPreset(12.9941, 80.1709, 'Chennai Airport')">✈️ Airport</button>
                    </div>
                </div>

                <!-- 2. Receiving Emergency Trauma Hospital (To) -->
                <div class="form-group">
                    <label class="form-label">
                        <span>2. Receiving Hospital (To)</span>
                        <span id="to-coords-lbl" style="font-size: 0.7rem; color: #f87171;">13.0797, 80.2778</span>
                    </label>
                    <select id="hospital-select" class="input-box" onchange="onHospitalChanged()">
                        <option value="13.0797,80.2778">Rajiv Gandhi Govt General Hospital (Park Town)</option>
                        <option value="13.0607,80.2512" selected>Apollo Hospitals (Greams Road, Thousand Lights)</option>
                        <option value="13.0682,80.2727">TN Multi Super Speciality Hospital (Omandurar)</option>
                        <option value="13.0792,80.2432">Kilpauk Medical College Hospital (Kilpauk)</option>
                        <option value="13.0182,80.1872">MIOT International Hospital (Manapakkam)</option>
                        <option value="13.0063,80.2573">Fortis Malar Hospital (Adyar)</option>
                        <option value="13.0354,80.2519">Kauvery Hospital (Alwarpet)</option>
                        <option value="custom">✏️ Custom Destination Search...</option>
                    </select>
                    <input type="text" id="dest-custom-input" class="input-box" placeholder="Search custom hospital / destination..." style="display: none; margin-top: 4px;" />
                    
                    <div class="btn-row" style="margin-top: 4px;">
                        <button id="btn-pick-dest" class="map-pick-btn" onclick="setPickMode('dest')">
                            <i class="fa-solid fa-crosshairs"></i> Set Hospital by Map Click
                        </button>
                    </div>
                </div>

                <!-- Real Route Telemetry Card -->
                <div class="telemetry-card">
                    <div class="telem-row">
                        <div class="telem-item">
                            <span class="telem-val" id="hud-distance">-- km</span>
                            <span class="telem-lbl">Real Road Distance</span>
                        </div>
                        <div class="telem-item" style="text-align: right;">
                            <span class="telem-val" id="hud-duration">-- mins</span>
                            <span class="telem-lbl">Est. Driving Time</span>
                        </div>
                    </div>
                    <div class="status-pill">
                        <i class="fa-solid fa-circle-check" style="color: #10b981;"></i>
                        <span id="hud-preemption-status">Google Maps Road Network Sync: Active</span>
                    </div>
                </div>

                <!-- Start Journey Button -->
                <button id="btn-journey" class="btn-start-journey" onclick="toggleJourney()">
                    <i class="fa-solid fa-play"></i> Start Emergency Journey
                </button>
            </div>
        </div>

        <!-- RIGHT: Interactive Real Google Map -->
        <div id="map-container">
            <div id="map"></div>

            <!-- Floating Speed & Navigation HUD -->
            <div class="map-hud-overlay">
                <div class="hud-stat">
                    <span class="hud-stat-val" id="overlay-speed">0 km/h</span>
                    <span class="hud-stat-lbl">In-Transit Speed</span>
                </div>
                <div class="hud-stat">
                    <span class="hud-stat-val" id="overlay-next-turn" style="font-size: 1.05rem; color: #a7f3d0;">Proceed to route</span>
                    <span class="hud-stat-lbl">Next Guidance</span>
                </div>
                <div class="hud-stat">
                    <span class="hud-stat-val" id="overlay-progress">0%</span>
                    <span class="hud-stat-lbl">Transit Progress</span>
                </div>
            </div>

            <!-- Tip overlay -->
            <div class="map-helper-tip">
                <i class="fa-solid fa-circle-info" style="color: #38bdf8;"></i>
                <span>Click anywhere on Google Maps to drop/move your ambulance or destination pin.</span>
            </div>
        </div>
    </div>

    <!-- Leaflet JS -->
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script>
        // Default locations
        let originLat = 13.0500;
        let originLon = 80.2824;
        let destLat = 13.0607;
        let destLon = 80.2512;

        let pickMode = null; // 'origin' or 'dest'
        let map = null;
        let originMarker = null;
        let destMarker = null;
        let routePolyline = null;
        let currentRouteCoords = [];
        let isJourneyActive = false;
        let animStep = 0;
        let animTimer = null;

        // Initialize Map
        function initMap() {
            map = L.map('map', {
                center: [13.055, 80.266],
                zoom: 13,
                zoomControl: true
            });

            // Google Maps Roadmap Tiles
            const googleRoadmap = L.tileLayer('https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}', {
                maxZoom: 20,
                attribution: 'Google Maps'
            }).addTo(map);

            // Google Maps Hybrid Satellite
            const googleSatellite = L.tileLayer('https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', {
                maxZoom: 20,
                attribution: 'Google Maps Hybrid'
            });

            // OpenStreetMap fallback
            const osm = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                maxZoom: 19,
                attribution: 'OpenStreetMap'
            });

            L.control.layers({
                'Google Maps (Roadmap)': googleRoadmap,
                'Google Maps (Satellite)': googleSatellite,
                'OpenStreetMap': osm
            }, null, { position: 'topleft' }).addTo(map);

            // Custom Marker Icons
            createMarkers();

            // Click listener on map to drop custom pin
            map.on('click', function(e) {
                const lat = e.latlng.lat;
                const lon = e.latlng.lng;
                
                if (pickMode === 'dest') {
                    setDestination(lat, lon, "📍 Custom Map Location (" + lat.toFixed(4) + ", " + lon.toFixed(4) + ")");
                    setPickMode(null);
                } else {
                    // Default to updating Origin
                    setOrigin(lat, lon, "📍 Custom Map Pin (" + lat.toFixed(4) + ", " + lon.toFixed(4) + ")");
                    setPickMode(null);
                }
            });

            // Initial Route
            fetchRoute();
        }

        function createMarkers() {
            const ambIcon = L.divIcon({
                className: 'custom-div-icon',
                html: '<div class="amb-marker-icon" style="width:36px; height:36px;"><i class="fa-solid fa-truck-medical"></i></div>',
                iconSize: [36, 36],
                iconAnchor: [18, 18]
            });

            const hospIcon = L.divIcon({
                className: 'custom-div-icon',
                html: '<div class="hosp-marker-icon" style="width:36px; height:36px;"><i class="fa-solid fa-hospital"></i></div>',
                iconSize: [36, 36],
                iconAnchor: [18, 18]
            });

            originMarker = L.marker([originLat, originLon], { icon: ambIcon, draggable: true }).addTo(map);
            destMarker = L.marker([destLat, destLon], { icon: hospIcon, draggable: true }).addTo(map);

            originMarker.on('dragend', function(e) {
                const pt = e.target.getLatLng();
                originLat = pt.lat;
                originLon = pt.lng;
                document.getElementById('from-coords-lbl').innerText = originLat.toFixed(4) + ", " + originLon.toFixed(4);
                document.getElementById('origin-input').value = "Pinned Location (" + originLat.toFixed(4) + ", " + originLon.toFixed(4) + ")";
                fetchRoute();
            });

            destMarker.on('dragend', function(e) {
                const pt = e.target.getLatLng();
                destLat = pt.lat;
                destLon = pt.lng;
                document.getElementById('to-coords-lbl').innerText = destLat.toFixed(4) + ", " + destLon.toFixed(4);
                fetchRoute();
            });
        }

        // Set Origin
        function setOrigin(lat, lon, label) {
            originLat = lat;
            originLon = lon;
            document.getElementById('origin-input').value = label;
            document.getElementById('from-coords-lbl').innerText = lat.toFixed(4) + ", " + lon.toFixed(4);
            originMarker.setLatLng([lat, lon]);
            fetchRoute();
        }

        // Set Preset Origin
        function setOriginPreset(lat, lon, name) {
            setOrigin(lat, lon, name + ", Chennai");
            map.flyTo([lat, lon], 14, { duration: 1 });
        }

        // HTML5 Live Geolocation
        function useMyLocation() {
            if (navigator.geolocation) {
                document.getElementById('btn-gps').innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Locating...';
                navigator.geolocation.getCurrentPosition(
                    function(position) {
                        const lat = position.coords.latitude;
                        const lon = position.coords.longitude;
                        setOrigin(lat, lon, "📍 My Live GPS Location (" + lat.toFixed(4) + ", " + lon.toFixed(4) + ")");
                        map.flyTo([lat, lon], 14, { duration: 1 });
                        document.getElementById('btn-gps').innerHTML = '<i class="fa-solid fa-location-crosshairs"></i> Use My GPS Location';
                    },
                    function(error) {
                        alert("Geolocation request: " + error.message + ". You can also click directly anywhere on the Google Map!");
                        document.getElementById('btn-gps').innerHTML = '<i class="fa-solid fa-location-crosshairs"></i> Use My GPS Location';
                    },
                    { enableHighAccuracy: true, timeout: 8000 }
                );
            } else {
                alert("Geolocation is not supported by this browser.");
            }
        }

        // Pick Mode Toggle
        function setPickMode(mode) {
            pickMode = (pickMode === mode) ? null : mode;
            document.getElementById('btn-pick-origin').classList.toggle('active', pickMode === 'origin');
            document.getElementById('btn-pick-dest').classList.toggle('active', pickMode === 'dest');
        }

        // Hospital Dropdown Handler
        function onHospitalChanged() {
            const val = document.getElementById('hospital-select').value;
            const customInput = document.getElementById('dest-custom-input');
            if (val === 'custom') {
                customInput.style.display = 'block';
                return;
            } else {
                customInput.style.display = 'none';
                const parts = val.split(',');
                const lat = parseFloat(parts[0]);
                const lon = parseFloat(parts[1]);
                const text = document.getElementById('hospital-select').selectedOptions[0].text;
                setDestination(lat, lon, text);
            }
        }

        function setDestination(lat, lon, label) {
            destLat = lat;
            destLon = lon;
            document.getElementById('to-coords-lbl').innerText = lat.toFixed(4) + ", " + lon.toFixed(4);
            destMarker.setLatLng([lat, lon]);
            fetchRoute();
        }

        // Calculate Real Google Maps Road Path via OSRM Driving Engine
        function fetchRoute() {
            if (isJourneyActive) {
                stopJourney();
            }

            const url = `https://router.project-osrm.org/route/v1/driving/${originLon},${originLat};${destLon},${destLat}?overview=full&geometries=geojson&steps=true`;
            
            document.getElementById('hud-preemption-status').innerText = 'Calculating real road route...';
            
            fetch(url)
                .then(res => res.json())
                .then(data => {
                    if (data.code === 'Ok' && data.routes && data.routes.length > 0) {
                        const route = data.routes[0];
                        const distKm = (route.distance / 1000).toFixed(1);
                        const durMin = Math.round(route.duration / 60);

                        document.getElementById('hud-distance').innerText = distKm + " km";
                        document.getElementById('hud-duration').innerText = durMin + " mins";
                        document.getElementById('hud-preemption-status').innerText = `Real Google Map Road Path Locked (${distKm} km)`;

                        // Extract geometry (OSRM returns [lon, lat])
                        currentRouteCoords = route.geometry.coordinates.map(c => [c[1], c[0]]);

                        // Remove existing polyline
                        if (routePolyline) {
                            map.removeLayer(routePolyline);
                        }

                        // Draw Google-styled Route Polyline
                        routePolyline = L.polyline(currentRouteCoords, {
                            color: '#0284c7',
                            weight: 6,
                            opacity: 0.85,
                            lineJoin: 'round'
                        }).addTo(map);

                        // Fit bounds to show route
                        map.fitBounds(routePolyline.getBounds(), { padding: [60, 60] });

                        // Extract next step instruction
                        if (route.legs && route.legs[0] && route.legs[0].steps && route.legs[0].steps.length > 0) {
                            const firstStep = route.legs[0].steps[0];
                            document.getElementById('overlay-next-turn').innerText = firstStep.name ? "Follow " + firstStep.name : "Head towards destination";
                        }
                    } else {
                        // Fallback straight line
                        currentRouteCoords = [[originLat, originLon], [destLat, destLon]];
                        if (routePolyline) map.removeLayer(routePolyline);
                        routePolyline = L.polyline(currentRouteCoords, { color: '#0284c7', weight: 5 }).addTo(map);
                        document.getElementById('hud-distance').innerText = "Direct Route";
                        document.getElementById('hud-duration').innerText = "Calculating";
                    }
                })
                .catch(err => {
                    console.error("Route error:", err);
                    document.getElementById('hud-preemption-status').innerText = 'Using fallback direct corridor';
                });
        }

        // Live Journey Animation
        function toggleJourney() {
            if (isJourneyActive) {
                stopJourney();
            } else {
                startJourney();
            }
        }

        function startJourney() {
            if (!currentRouteCoords || currentRouteCoords.length < 2) return;
            isJourneyActive = true;
            animStep = 0;
            const btn = document.getElementById('btn-journey');
            btn.innerHTML = '<i class="fa-solid fa-stop"></i> End Journey';
            btn.classList.add('active');

            document.getElementById('overlay-speed').innerText = '58 km/h';

            const totalPoints = currentRouteCoords.length;
            const stepInterval = 180; // ms

            animTimer = setInterval(() => {
                if (animStep >= totalPoints) {
                    stopJourney();
                    alert("Ambulance arrived safely at Trauma Hospital Emergency Bay!");
                    return;
                }

                const currCoord = currentRouteCoords[animStep];
                originMarker.setLatLng(currCoord);

                // Update progress
                const progressPct = Math.round((animStep / (totalPoints - 1)) * 100);
                document.getElementById('overlay-progress').innerText = progressPct + "%";

                // Speed variation
                const currentSpd = Math.round(52 + Math.random() * 14);
                document.getElementById('overlay-speed').innerText = currentSpd + " km/h";

                animStep++;
            }, stepInterval);
        }

        function stopJourney() {
            isJourneyActive = false;
            clearInterval(animTimer);
            animTimer = null;
            const btn = document.getElementById('btn-journey');
            btn.innerHTML = '<i class="fa-solid fa-play"></i> Start Emergency Journey';
            btn.classList.remove('active');
            document.getElementById('overlay-speed').innerText = '0 km/h';
            document.getElementById('overlay-progress').innerText = '0%';
        }

        // Search text input keyup listener (address geocode)
        document.getElementById('origin-input').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                const q = this.value;
                if (!q) return;
                fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(q + ', Chennai')}`)
                    .then(res => res.json())
                    .then(data => {
                        if (data && data.length > 0) {
                            const lat = parseFloat(data[0].lat);
                            const lon = parseFloat(data[0].lon);
                            setOrigin(lat, lon, data[0].display_name.split(',')[0]);
                            map.flyTo([lat, lon], 14, { duration: 1 });
                        } else {
                            alert("Location not found. Try searching another landmark or click on the map!");
                        }
                    });
            }
        });

        // Initialize on load
        window.addEventListener('DOMContentLoaded', initMap);
    </script>
</body>
</html>
"""
    return html_content


def render_hospital_maps_page():
    """Render the full-page Paramedic Hospital Google Maps interface."""
    # Top Minimal Bar allowing seamless navigation back to the main Traffic Brain
    top_col1, top_col2 = st.columns([9, 3])
    with top_col1:
        st.markdown(
            """
            <div style="display: flex; align-items: center; gap: 14px; margin-bottom: 8px;">
                <span style="font-size: 1.6rem;">🚑</span>
                <div>
                    <h2 style="margin: 0; color: #34d399; font-weight: 800; font-size: 1.5rem; letter-spacing: -0.01em;">
                        Tactical EMS Paramedic Cockpit | Real Google Maps Navigation
                    </h2>
                    <span style="font-size: 0.85rem; color: #94a3b8;">
                        Dedicated Ambulance In-Cabin Navigation Console • Real Road Geometries • Hospital Green Corridors
                    </span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with top_col2:
        st.markdown(
            """
            <div style="text-align: right; margin-top: 6px;">
                <a href="/" target="_self" style="
                    display: inline-block;
                    background: #1e293b;
                    color: #94a3b8;
                    border: 1px solid #334155;
                    padding: 8px 14px;
                    border-radius: 8px;
                    font-size: 0.85rem;
                    font-weight: 700;
                    text-decoration: none;
                    transition: all 0.2s ease;
                ">
                    ⬅️ Switch Back to Traffic Brain
                </a>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.info(
        "ℹ️ **Notice**: This Paramedic Hospital Navigation Cockpit is a standalone concept demonstration. "
        "It is decoupled from the live traffic signal simulator, operates independently of signal phase timing, "
        "and requires an active internet connection to stream tile map layers and fetch OSRM routing geometries."
    )

    # Embed the rich, full-height Paramedic Google Maps application
    html_app = generate_hospital_maps_html()
    components.html(html_app, height=750, scrolling=False)

