import json

s = """[
  {
    "section": "Profile",
    "original": "Platform Engineer and AI Architect (GenAI)
with expertise in building high-availability, multi-AZ cloud
platforms",
    "suggested": "test"
  }
]"""

try:
    data = json.loads(s, strict=False)
    print("SUCCESS")
    print(data)
except Exception as e:
    print(f"FAILED (strict=False): {e}")

try:
    data2 = json.loads(s.replace('\n', '\\n'))
    print("SUCCESS with replace")
    print(data2)
except Exception as e:
    print(f"FAILED with replace: {e}")
