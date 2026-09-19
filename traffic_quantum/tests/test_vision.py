"""Unit tests for Computer Vision Vehicle Detection and Inflow Mapping."""

import numpy as np
import cv2
import pytest
from traffic_quantum.vision import VehicleDetector, map_detected_count_to_entries


def test_vehicle_detector_empty_or_invalid():
    detector = VehicleDetector()
    ann_rgb, count, dets = detector.detect_vehicles(np.zeros((0, 0, 3), dtype=np.uint8))
    assert count == 0
    assert len(dets) == 0


def test_vehicle_detector_synthetic_vehicles():
    detector = VehicleDetector(min_area=100)
    # Create synthetic dark background with 3 bright rectangular car silhouettes
    img = np.zeros((400, 600, 3), dtype=np.uint8)
    
    # Car 1
    cv2.rectangle(img, (80, 100), (160, 150), (220, 220, 220), -1)
    # Car 2
    cv2.rectangle(img, (250, 180), (340, 230), (240, 240, 240), -1)
    # Car 3
    cv2.rectangle(img, (400, 280), (490, 340), (200, 200, 200), -1)

    ann_rgb, count, dets = detector.detect_vehicles(img)
    assert count >= 1
    assert len(dets) >= 1
    assert ann_rgb.shape == img.shape


def test_map_detected_count_to_entries_auto():
    entries = ["N1", "N2", "N3", "S1", "S2", "S3"]
    alloc = map_detected_count_to_entries(6, target_entry="auto", available_entries=entries)
    assert sum(alloc.values()) == 6
    for e in entries:
        assert alloc[e] == 1


def test_map_detected_count_to_entries_specific():
    entries = ["N1", "N2", "N3"]
    alloc = map_detected_count_to_entries(5, target_entry="N2", available_entries=entries)
    assert alloc["N2"] == 5
    assert alloc["N1"] == 0
    assert alloc["N3"] == 0
