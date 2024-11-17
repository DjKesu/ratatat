import pyautogui
import time
import os
from datetime import datetime

def create_output_directory():
    # Create a timestamped directory name
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_dir = f"screenshots_{timestamp}"
    
    # Create the directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    return output_dir

def capture_screenshots(output_directory, interval_seconds=20, duration_minutes=None):
    print(f"Starting screenshot capture. Saving to: {output_directory}")
    screenshots_taken = 0
    start_time = time.time()
    
    try:
        while True:
            # Generate filename with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = os.path.join(output_directory, f"screenshot_{timestamp}.png")
            
            # Take and save screenshot
            screenshot = pyautogui.screenshot()
            screenshot.save(filename)
            
            screenshots_taken += 1
            print(f"Saved screenshot {screenshots_taken}: {filename}")
            
            # Check if we should stop based on duration
            if duration_minutes is not None:
                elapsed_minutes = (time.time() - start_time) / 60
                if elapsed_minutes >= duration_minutes:
                    print(f"Reached duration limit of {duration_minutes} minutes")
                    break
            
            # Wait before next capture
            time.sleep(interval_seconds)
            
    except KeyboardInterrupt:
        print("\nScreenshot capture stopped by user")
    except Exception as e:
        print(f"Error during capture: {e}")
        return False
    
    return True

def main():
    # Configuration
    interval_seconds = 20  # Time between screenshots
    duration_minutes = None  # Run indefinitely until stopped with Ctrl+C
    
    # Create output directory
    output_directory = create_output_directory()
    print(f"Created output directory: {output_directory}")
    print("Press Ctrl+C to stop capturing")
    
    # Start capture
    success = capture_screenshots(
        output_directory=output_directory,
        interval_seconds=interval_seconds,
        duration_minutes=duration_minutes
    )
    
    if success:
        print("Screenshot capture completed successfully")
    else:
        print("Screenshot capture encountered errors")

if __name__ == "__main__":
    main()