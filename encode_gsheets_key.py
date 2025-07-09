import base64

# Path to your JSON key file
json_path = "google_sheets.json"

# Read and encode the file
with open(json_path, "rb") as file:
    encoded = base64.b64encode(file.read()).decode("utf-8")

# Print the result
print("🔐 Copy this base64 string into your GitHub Secret (GOOGLE_SHEETS_KEY_B64):\n")
print(encoded)
