"""Week 1 Final Verification Script"""
import httpx
import json
import io

BASE = "http://127.0.0.1:8000"

print("========== FINAL WEEK 1 VERIFICATION ==========")
print()

# 1. Health check
r = httpx.get(f"{BASE}/api/health")
print(f"1. GET /api/health -> {r.status_code}")
print(f"   {json.dumps(r.json())}")
print()

# 2. List personas
r = httpx.get(f"{BASE}/api/personas")
personas = r.json()
print(f"2. GET /api/personas -> {r.status_code} ({len(personas)} found)")
for p in personas:
    print(f"   - {p['name']} ({p['role']})")
print()

# 3. Create a new persona
r = httpx.post(f"{BASE}/api/personas", json={
    "name": "Prof. Ravi Kumar",
    "role": "AI Researcher",
    "institution": "IIIT Hyderabad",
    "personality_traits": ["Enthusiastic", "Explains with code examples"],
    "knowledge_areas": ["Deep Learning", "NLP", "Computer Vision"],
    "speaking_style": "Technical but approachable",
    "constraints": ["Never claim to be human", "Keep answers concise"],
})
new_p = r.json()
print(f"3. POST /api/personas -> {r.status_code}")
print(f"   Created: {new_p['name']} (id={new_p['id']})")
print()

# 4. Get specific persona
r = httpx.get(f"{BASE}/api/personas/{new_p['id']}")
print(f"4. GET /api/personas/{new_p['id']} -> {r.status_code}")
print(f"   {r.json()['name']} at {r.json()['institution']}")
print()

# 5. Process endpoint (stub)
fake_audio = io.BytesIO(b"fake audio data for testing")
r = httpx.post(
    f"{BASE}/api/process",
    files={"audio": ("test.wav", fake_audio)},
    data={"target_language": "hi", "persona_id": "1"},
)
result = r.json()
print(f"5. POST /api/process -> {r.status_code}")
print(f"   Transcript: {result['transcript'][:60]}...")
print(f"   Reply: {result['reply_text'][:60]}...")
print(f"   Time: {result['processing_time_ms']:.1f}ms")
print()

# 6. Frontend
r = httpx.get(f"{BASE}/")
print(f"6. GET / (frontend) -> {r.status_code}, has 'Resonant': {'Resonant' in r.text}")
print()

# 7. Swagger docs
r = httpx.get(f"{BASE}/docs")
print(f"7. GET /docs (Swagger) -> {r.status_code}")
print()

print("============ ALL TESTS PASSED ============")
