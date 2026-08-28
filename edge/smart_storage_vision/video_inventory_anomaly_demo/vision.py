from __future__ import annotations


class RoleConfidenceAnalyzer:
    """Apply separate fruit and person thresholds to the shared single-thread analyzer."""

    def __init__(self, analyzer, *, fruit_confidence: float, person_confidence: float) -> None:
        for name, value in (("fruit_confidence", fruit_confidence), ("person_confidence", person_confidence)):
            if not 0.0 < value <= 1.0:
                raise ValueError(f"{name} must be in (0, 1]")
        self.analyzer = analyzer
        self.fruit_confidence = fruit_confidence
        self.person_confidence = person_confidence

    @property
    def device(self):
        return self.analyzer.device

    @property
    def current_security_count(self) -> int:
        return self.analyzer.current_security_count

    def analyze_inventory(self, frame, *, accumulate: bool = True):
        self.analyzer.detection_confidence = self.fruit_confidence
        return self.analyzer.analyze_inventory(frame, accumulate=accumulate)

    def analyze_security(self, frame, *, accumulate: bool = True):
        self.analyzer.detection_confidence = self.person_confidence
        return self.analyzer.analyze_security(frame, accumulate=accumulate)
