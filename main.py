import sys
from app import App

if __name__ == "__main__":
    try:
        app = App()
        sys.exit(app.run())
    except Exception as e:
        print(f"Error starting application: {e}")
