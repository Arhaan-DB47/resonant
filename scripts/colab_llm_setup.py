# ============================================================
# Resonant — Google Colab LLM Server
# ============================================================
# Run this notebook on Google Colab (free T4 GPU runtime)
# It starts a local Ollama server and exposes it via ngrok
# so your FastAPI backend on your PC can call it.
#
# SETUP STEPS:
# 1. Go to https://colab.research.google.com
# 2. Create a new notebook
# 3. Change runtime: Runtime → Change runtime type → T4 GPU
# 4. Paste each section below into separate cells and run them
# ============================================================


# === CELL 1: Install Ollama ===
# !curl -fsSL https://ollama.com/install.sh | sh
# !nohup ollama serve &
# import time; time.sleep(5)
# !ollama --version


# === CELL 2: Pull a model ===
# Choose ONE based on Colab's available RAM:
# - phi3:mini    → ~2.7 GB, fast, good for English
# - llama3.1:8b  → ~4.7 GB, better quality, multilingual (RECOMMENDED)
#
# !ollama pull llama3.1:8b


# === CELL 3: Test the model ===
# import requests
# response = requests.post("http://localhost:11434/api/chat", json={
#     "model": "llama3.1:8b",
#     "messages": [
#         {"role": "system", "content": "You are a helpful professor."},
#         {"role": "user", "content": "What is machine learning in simple terms?"}
#     ],
#     "stream": False
# })
# print(response.json()["message"]["content"])


# === CELL 4: Install ngrok and expose the API ===
# Sign up at https://ngrok.com (free) and get your auth token
#
# !pip install pyngrok
# from pyngrok import ngrok
#
# # Replace with your ngrok auth token
# ngrok.set_auth_token("YOUR_NGROK_AUTH_TOKEN_HERE")
#
# # Expose Ollama's port 11434 to the internet
# public_url = ngrok.connect(11434)
# print(f"\n{'='*60}")
# print(f"YOUR COLAB LLM URL: {public_url}")
# print(f"{'='*60}")
# print(f"\nPaste this URL into your .env file as COLAB_LLM_URL")
# print(f"Example: COLAB_LLM_URL={public_url}")


# === CELL 5: Keep the notebook alive ===
# Colab disconnects after ~30 min of inactivity.
# Run this cell to keep it alive during demos.
#
# import time
# while True:
#     time.sleep(60)
#     print(".", end="", flush=True)
