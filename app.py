from flask import Flask, request, render_template_string, Response
import subprocess

app = Flask(__name__)
#"Tesco": "tesco_scraper.py",
scrapers = {
    "Asda": "asda_scraper.py",
    "Co-op": "coop_scraper_v2.py",
    "Ocado": "ocado_scraper.py",
    "Morrisons": "morrisons_scraper.py",
    "Sainsburys": "sainsburys_scraper.py",
}

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Grocery Scraper Dashboard</title>
    <style>
        body {
            font-family: 'Segoe UI', sans-serif;
            background: #f4f7f9;
            margin: 0;
            padding: 0;
        }
        .container {
            max-width: 900px;
            margin: 40px auto;
            background: #fff;
            border-radius: 10px;
            padding: 40px;
            box-shadow: 0 5px 20px rgba(0,0,0,0.1);
        }
        h1 {
            color: #34495e;
            margin-bottom: 20px;
        }
        input[type="text"] {
            width: 70%;
            padding: 12px;
            font-size: 1.1rem;
            border-radius: 6px;
            border: 1px solid #ccc;
            margin-bottom: 20px;
        }
        button {
            padding: 12px 24px;
            background: #1abc9c;
            color: white;
            border: none;
            border-radius: 6px;
            font-size: 1.1rem;
            cursor: pointer;
        }
        .output {
            white-space: pre-wrap;
            font-family: monospace;
            background: #ecf0f1;
            padding: 20px;
            border-radius: 8px;
            margin-top: 20px;
            max-height: 500px;
            overflow-y: auto;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🛒 Grocery Scraper Dashboard</h1>
        <form method="POST" action="/run">
            <input type="text" name="query" placeholder="Enter search term..." required />
            <button type="submit">Run Scrapers</button>
        </form>
        {% if stream %}
        <div class="output" id="log">
            {{ stream|safe }}
        </div>
        <script>
            const logDiv = document.getElementById("log");
            const eventSource = new EventSource("/stream?query={{ query }}");

            eventSource.onmessage = function(event) {
                logDiv.innerHTML += event.data + "\\n";
                logDiv.scrollTop = logDiv.scrollHeight;
            };

            eventSource.onerror = function() {
                logDiv.innerHTML += "\\n❌ Stream connection lost.";
                eventSource.close();
            };
        </script>
        {% endif %}
    </div>
</body>
</html>
"""

@app.route("/", methods=["GET"])
def index():
    return render_template_string(HTML, stream=False)

@app.route("/run", methods=["POST"])
def run_scrapers():
    query = request.form.get("query", "").strip()
    return render_template_string(HTML, stream=True, query=query)

@app.route("/stream")
def stream():
    query = request.args.get("query", "").strip()

    def generate():
        for name, script in scrapers.items():
            yield f"data: ▶️ Running {name} scraper...\n\n"
            try:
                process = subprocess.Popen(
                    ["python", script],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )
                process.stdin.write(query + "\n")
                process.stdin.flush()
                for line in process.stdout:
                    yield f"data: [{name}] {line.strip()}\n\n"
                process.wait()
                status = "✅ Completed" if process.returncode == 0 else "❌ Failed"
                yield f"data: ✅ {name} scraper {status}\n\n"
            except Exception as e:
                yield f"data: ❌ {name} error: {str(e)}\n\n"

        yield "data: 🎉 All scrapers finished.\n\n"

    return Response(generate(), mimetype="text/event-stream")

if __name__ == "__main__":
    app.run(debug=True, threaded=True)
