"""YOLOv8 trash classification integration point."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from smart_bin import config


class YoloTrashDetector:
    """Small adapter around the deployed YOLOv8 trash detector."""

    def __init__(
        self,
        model_path: str | Path = config.YOLO_MODEL_PATH,
        confidence_threshold: float = config.YOLO_CONFIDENCE_THRESHOLD,
        camera_index: int = config.YOLO_CAMERA_INDEX,
    ) -> None:
        self.model_path = Path(model_path)
        self.confidence_threshold = confidence_threshold
        self.camera_index = camera_index

        if not self.model_path.exists():
            raise FileNotFoundError(f"YOLO model not found: {self.model_path}")

        from ultralytics import YOLO

        self.model = YOLO(str(self.model_path))

    def detect_trash_type(
        self,
        frame: Any | None = None,
        source: Any | None = None,
    ) -> str | None:
        """
        Return plastic, paper, metal, general_waste, or None.

        If frame/source is not supplied, this captures one frame from OpenCV
        camera index 0 by default. TODO: replace capture_frame() with the
        final Raspberry Pi camera source if the deployed camera pipeline uses
        Picamera2 or another frame provider.
        """
        inference_source = source
        if inference_source is None:
            inference_source = frame if frame is not None else self.capture_frame()

        if inference_source is None:
            return None

        results = self.model.predict(
            source=inference_source,
            conf=self.confidence_threshold,
            verbose=False,
        )
        return self._best_valid_label(results)

    def capture_frame(self) -> Any | None:
        """Capture a single camera frame for YOLO inference."""
        import cv2

        camera = cv2.VideoCapture(self.camera_index)
        if not camera.isOpened():
            return None

        try:
            frame = None
            ok = False
            for _ in range(config.YOLO_CAMERA_WARMUP_FRAMES):
                ok, frame = camera.read()

            ok, frame = camera.read()
            if not ok:
                return None
            return frame
        finally:
            camera.release()

    def _best_valid_label(self, results: Iterable[Any]) -> str | None:
        best_label = None
        best_confidence = -1.0

        for result in results:
            boxes = getattr(result, "boxes", None)
            if boxes is None:
                continue

            names = getattr(result, "names", None) or getattr(self.model, "names", {})
            for box in boxes:
                confidence = float(box.conf[0])
                if confidence < best_confidence:
                    continue

                class_id = int(box.cls[0])
                raw_label = self._raw_label_from_names(names, class_id)
                label = self._canonical_label(raw_label)
                if label is None:
                    continue

                best_label = label
                best_confidence = confidence

        return best_label

    def _raw_label_from_names(self, names: Any, class_id: int) -> str:
        if isinstance(names, dict):
            return str(names.get(class_id, ""))

        try:
            return str(names[class_id])
        except (IndexError, TypeError):
            return ""

    def _canonical_label(self, label: str) -> str | None:
        normalized = self._normalize_label(label)

        if "plastic" in normalized:
            return "plastic"
        if "paper" in normalized:
            return "paper"
        if "metal" in normalized:
            return "metal"
        if normalized in {"generalwaste", "generaltrash", "residualwaste"}:
            return "general_waste"
        if "general" in normalized and ("waste" in normalized or "trash" in normalized):
            return "general_waste"

        return None

    def _normalize_label(self, label: str) -> str:
        return "".join(char for char in label.lower() if char.isalnum())
