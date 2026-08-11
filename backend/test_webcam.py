import cv2
import time
from ultralytics import YOLO

def run_webcam_test():
    model_path = "best.pt"
    
    print(f"Loading model from {model_path}...")
    try:
        model = YOLO(model_path)
    except Exception as e:
        print(f"Failed to load model: {e}")
        return

    # Open the default webcam
    cam_index = 0
    print(f"Opening webcam (index {cam_index})...")
    # Using CAP_ANY (default) as DSHOW can sometimes cause a solid green screen bug
    cap = cv2.VideoCapture(cam_index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    if not cap.isOpened():
        print("Error: Could not open webcam.")
        return
        
    print("Webcam opened successfully. Press 'q' to quit, 'c' to change camera.")

    try:
        prev_frame_time = 0
        
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Failed to grab frame from webcam. Exiting...")
                break
                
            # Limit to 3 FPS (skip frames if they come too fast)
            current_time = time.time()
            if (current_time - prev_frame_time) < (1.0 / 3.0):
                continue
                
            # Calculate actual FPS
            fps = 1 / (current_time - prev_frame_time) if prev_frame_time > 0 else 0
            prev_frame_time = current_time
            
            # Check for "Green Screen" or "Black Screen" bug (all pixels are roughly the same color)
            # This happens if Windows Privacy settings block the camera or another app is using it
            if frame.var() < 10:
                print("WARNING: The camera frame is completely solid (green or black).")
                print("-> Please check Windows Settings > Privacy > Camera and allow access.")
                print("-> Or check if another app (Zoom, Chrome) is currently using the camera.")
            
            # Run YOLO inference on the frame (using imgsz=320 for lower memory footprint)
            results = model(frame, verbose=False, imgsz=320)
            
            # plot() method draws the bounding boxes and labels onto the frame
            annotated_frame = results[0].plot()
            
            # Add FPS text to the frame
            cv2.putText(annotated_frame, f"FPS: {int(fps)}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            
            # Display the annotated frame
            cv2.imshow("YOLO Webcam Test - Press 'q' to quit, 'c' to change camera", annotated_frame)
            
            # Key handling
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('c'):
                cam_index = (cam_index + 1) % 4
                print(f"Switching to camera index {cam_index}...")
                cap.release()
                cap = cv2.VideoCapture(cam_index)
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                
    except KeyboardInterrupt:
        print("Interrupted by user.")
    except Exception as e:
        import traceback
        print(f"An error occurred: {e}")
        traceback.print_exc()
        if "not enough memory" in str(e).lower() or "outofmemory" in str(e).lower():
            print("\n" + "="*50)
            print("*** OUT OF MEMORY ERROR DETECTED ***")
            print("Your system does not have enough free RAM to run the model.")
            print("Please close memory-heavy applications (like web browsers) and try again.")
            print("="*50 + "\n")
    finally:
        # Release the webcam and close the window
        cap.release()
        cv2.destroyAllWindows()
        print("Webcam closed.")

if __name__ == "__main__":
    run_webcam_test()
