"""Script de prueba para verificar que la API Key de Gemini funciona."""
from src.sdd_generator.gemini_client import GeminiClient

client = GeminiClient()
print(f"API Key loaded: {bool(client._api_key)}")
print(f"Key preview: {client._api_key[:8]}..." if client._api_key else "Key: EMPTY")
print(f"Client available: {client.is_available}")

if client.is_available:
    try:
        result = client.generate("Responde solo con la palabra OK")
        print(f"SUCCESS - Response: {result['content'][:100]}")
    except Exception as e:
        print(f"ERROR calling Gemini: {e}")
else:
    print("GEMINI NO DISPONIBLE - Verifica GEMINI_API_KEY en .env")
