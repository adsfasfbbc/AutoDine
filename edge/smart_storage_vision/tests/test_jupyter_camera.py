from smart_storage_vision.backends import FRUIT_LABELS, quality_prediction_for_fruit
from smart_storage_vision.jupyter_camera import quality_status


def test_quality_status_maps_fruit16k_labels() -> None:
    assert quality_status("F_Apple", 0.95, 0.7) == "good"
    assert quality_status("S_Banana", 0.95, 0.7) == "defective"


def test_quality_status_sends_low_confidence_to_review() -> None:
    assert quality_status("S_Orange", 0.69, 0.7) == "review"


def test_quality_prediction_is_restricted_to_detected_fruit() -> None:
    names = {
        0: "fresh_apple",
        1: "fresh_grape",
        2: "rotten_apple",
        3: "rotten_grape",
    }
    status, label, confidence = quality_prediction_for_fruit(
        [0.15, 0.8, 0.05, 0.0],
        names,
        "apple",
        0.1,
    )
    assert (status, label, confidence) == ("good", "fresh_apple", 0.15)


def test_quality_prediction_uses_review_for_low_confidence_or_unsupported_fruit() -> None:
    names = {0: "fresh_apple", 1: "rotten_apple"}
    assert quality_prediction_for_fruit([0.2, 0.1], names, "apple", 0.7) == (
        "review",
        "fresh_apple",
        0.2,
    )
    assert quality_prediction_for_fruit([0.8, 0.2], names, "pineapple", 0.7) == (
        "review",
        "unsupported",
        0.0,
    )


def test_six_fruit_detection_classes_are_declared() -> None:
    assert FRUIT_LABELS == frozenset(
        {"apple", "banana", "grape", "orange", "pineapple", "watermelon"}
    )
