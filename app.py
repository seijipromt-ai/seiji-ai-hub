import os, json, urllib.request, urllib.error
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)
MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")

@app.get("/")
def home():
    return render_template("index.html", model=MODEL)

@app.get("/api/health")
def health():
    return jsonify(ok=True, configured=bool(os.getenv("GEMINI_API_KEY")), model=MODEL)

@app.post("/api/chat")
def chat():
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        return jsonify(error="Set GEMINI_API_KEY in Vercel Environment Variables."), 503
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify(error="Please enter a message."), 400
    if len(message) > 12000:
        return jsonify(error="Message is too long."), 400
    mode = data.get("mode", "chat")
    prompts = {
        "chat": "You are Seiji AI, a friendly and helpful assistant.",
        "code": "You are Seiji Code Assistant. Help write, debug, and explain code with safe examples.",
        "writer": "You are Seiji Text Generator. Help draft, rewrite, and brainstorm useful text.",
        "study": "You are Seiji Study Assistant. Explain step by step in simple language with examples."
    }
    contents = []
    for item in (data.get("history") or [])[-10:]:
        if item.get("role") in ("user", "model") and isinstance(item.get("text"), str):
            contents.append({"role": item["role"], "parts": [{"text": item["text"][:6000]}]})
    contents.append({"role":"user","parts":[{"text":prompts.get(mode, prompts["chat"]) + "\n\n" + message}]})
    payload = json.dumps({"contents": contents}).encode()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
    req = urllib.request.Request(url, data=payload, method="POST",
        headers={"Content-Type":"application/json", "X-goog-api-key":key})
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            result = json.loads(response.read().decode())
        parts = result.get("candidates", [{}])[0].get("content", {}).get("parts", [])
        reply = "\n".join(p.get("text","") for p in parts if p.get("text"))
        return jsonify(reply=reply or "Gemini returned an empty response.", model=MODEL)
    except urllib.error.HTTPError as e:
        try: msg = json.loads(e.read().decode()).get("error",{}).get("message","Gemini API error.")
        except Exception: msg = "Gemini API error."
        return jsonify(error=msg), e.code if 400 <= e.code < 600 else 502
    except Exception:
        return jsonify(error="Could not reach Gemini. Please try again."), 502

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT","5000")), debug=True)
