from smart_storage_vision.jupyter_camera import quality_status


def test_quality_status_maps_fruit16k_labels() -> None:
    assert quality_status("F_Apple", 0.95, 0.7) == "good"
    assert quality_status("S_Banana", 0.95, 0.7) == "defective"


def test_quality_status_sends_low_confidence_to_review() -> None:
    assert quality_status("S_Orange", 0.69, 0.7) == "review"
