import os
from ultralytics import YOLO
import cv2

def test_model():
    model_path = "best.pt"
    image_path = "../sample_data/test_images/camera_test_1.jpg"

    if not os.path.exists(model_path):
        print(f"Error: Model not found at {model_path}")
        return

    if not os.path.exists(image_path):
        print(f"Error: Image not found at {image_path}")
        return

    print(f"Loading model from {model_path}...")
    try:
        model = YOLO(model_path)
    except Exception as e:
        print(f"Failed to load model: {e}")
        return

    print(f"Running inference on {image_path}...")
    try:
        results = model(image_path)
        
        # Display results
        for r in results:
            print("\n--- Inference Results ---")
            boxes = r.boxes
            if len(boxes) == 0:
                print("No objects detected.")
            else:
                for box in boxes:
                    cls = int(box.cls[0])
                    conf = float(box.conf[0])
                    name = model.names[cls]
                    print(f"Detected: {name} (Class {cls}) with confidence {conf:.2f}")
                    print(f"Bounding Box: {box.xyxy[0].tolist()}")
            
            # Optionally save the result image
            save_path = "test_result.jpg"
            r.save(filename=save_path)
            print(f"\nResult image saved to {save_path}")

    except Exception as e:
        print(f"Failed to run inference: {e}")

if __name__ == "__main__":
    test_model()
