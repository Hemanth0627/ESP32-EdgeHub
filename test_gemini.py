from app import GEMINI_MODELS, run_ai_command


print("========================================")
print("ESP32 EdgeHub Gemini Test")
print("Gemini models (in order):", GEMINI_MODELS)
print("========================================")

print()
print("Testing plain question (no tools)...")
print(run_ai_command("Explain ESP32 in one sentence.", provider="gemini"))

print()
print("Testing read-only tool call (device status)...")
print(run_ai_command("What is the current device status?", provider="gemini"))

print()
print("========================================")
print("Test completed")
print("========================================")
