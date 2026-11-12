from src.app import app

def main():
    print("Starting Wife Carrying World Championships (Eukonkanto) Web App...")
    app.run(host="0.0.0.0", port=5000, debug=True)

if __name__ == "__main__":
    main()
