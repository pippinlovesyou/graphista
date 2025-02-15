import os
from flask import Flask, request, jsonify, render_template_string
import json
from datetime import datetime
from memory import Memory
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Global history list to store log entries from API calls.
HISTORY = []

# ---------------------------------------------------------------------
# Default Ontology (in JSON Schema style)
# ---------------------------------------------------------------------
default_ontology = {
    "node_types": {
        "Document": {
            "properties": {
                "content": {"type": "string"}
            },
            "required": ["content"]
        },
        "Article": {
            "properties": {
                "title": {"type": "string"},
                "author": {"type": "string"},
                "publication": {"type": "string"},
                "date": {"type": "string"},
                "content": {"type": "string"}
            },
            "required": ["title", "content", "date"]
        },
        "Person": {
            "properties": {
                "name": {"type": "string"},
                "birthdate": {"type": "string"},
                "role": {"type": "string"},
                "twitter": {"type": "string"}
            },
            "required": ["name"]
        },
        "Organization": {
            "properties": {
                "name": {"type": "string"},
                "industry": {"type": "string"},
                "website": {"type": "string"},
                "location": {"type": "string"},
                "description": {"type": "string"}
            },
            "required": ["name"]
        },
        "Place": {
            "properties": {
                "name": {"type": "string"},
                "location": {"type": "string"}
            },
            "required": ["name"]
        },
        "Event": {
            "properties": {
                "name": {"type": "string"},
                "date": {"type": "string"},
                "location": {"type": "string"},
                "description": {"type": "string"}
            },
            "required": ["name", "date"]
        },
        "Investment": {
            "properties": {
                "round": {"type": "string"},
                "amount": {"type": "number"},
                "date": {"type": "string"},
                "investors": {"type": "array", "items": {"type": "string"}},
                "startup": {"type": "string"}
            },
            "required": ["round", "amount", "date"]
        },
        "Product": {
            "properties": {
                "name": {"type": "string"},
                "version": {"type": "string"},
                "release_date": {"type": "string"},
                "description": {"type": "string"}
            },
            "required": ["name"]
        }
    },
    "edge_types": {
        "works_at": {},
        "located_in": {},
        "attended": {},
        "knows": {},
        "affiliated_with": {},
        "invested_in": {},
        "acquired": {},
        "partnered_with": {},
        "competes_with": {},
        "launched": {}
    }
}

# ---------------------------------------------------------------------
# Default Extraction Rules
# ---------------------------------------------------------------------
default_extraction_rules = {
    "extractable_types": {
        "Person": {
            "target_schema": {"name": "str", "birthdate": "str", "role": "str", "twitter": "str"},
            "overwrite_existing": False
        },
        "Organization": {
            "target_schema": {"name": "str", "industry": "str", "website": "str", "location": "str", "description": "str"},
            "overwrite_existing": False
        },
        "Place": {
            "target_schema": {"name": "str", "location": "str"},
            "overwrite_existing": False
        },
        "Event": {
            "target_schema": {"name": "str", "date": "str", "location": "str", "description": "str"},
            "overwrite_existing": False
        },
        "Article": {
            "target_schema": {"title": "str", "author": "str", "publication": "str", "date": "str", "content": "str"},
            "overwrite_existing": False
        },
        "Investment": {
            "target_schema": {"round": "str", "amount": "float", "date": "str", "investors": "list", "startup": "str"},
            "overwrite_existing": False
        },
        "Product": {
            "target_schema": {"name": "str", "version": "str", "release_date": "str", "description": "str"},
            "overwrite_existing": False
        }
    },
    "relationship_types": [
        "works_at",
        "located_in",
        "attended",
        "knows",
        "affiliated_with",
        "invested_in",
        "acquired",
        "partnered_with",
        "competes_with",
        "launched"
    ],
    "trigger_conditions": {"required_properties": ["content"]}
}

# ---------------------------------------------------------------------
# LLM Configuration
# ---------------------------------------------------------------------
llm_config = {
    "api_key": os.environ["OPENAI_API_KEY"],
    "model_name": "gpt-4o",
    "temperature": 0.0,
    "max_tokens": 1500
}

# ---------------------------------------------------------------------
# Initialize Memory (which now uses our SmartNodeProcessor internally)
# ---------------------------------------------------------------------
from memory import Memory
memory_instance = Memory(
    backend="local",
    ontology_config=default_ontology,
    extraction_rules=default_extraction_rules,
    auto_embedding=True,
    llm_config=llm_config,
    db_path="graph.json"
)

app = Flask(__name__)

# ---------------------------------------------------------------------
# HTML Template (with Bootstrap accordion, tabs for Graph, JSON view, History, etc.)
# ---------------------------------------------------------------------
HTML_TEMPLATE = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Memory Graph Front-End</title>
    <!-- Bootstrap CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <!-- Vis Network CSS -->
    <link href="https://cdnjs.cloudflare.com/ajax/libs/vis-network/9.1.2/vis-network.min.css" rel="stylesheet">
    <style>
      body { padding-top: 60px; }
      #network { width: 100%; height: 400px; }
      pre { background-color: #f8f9fa; padding: 10px; }
      .question-text { font-size: 0.95em; font-style: italic; }
      .final-answer { font-size: 1.1em; font-weight: bold; }
      .chain-of-thought { font-size: 0.8em; color: gray; }
    </style>
  </head>
  <body>
    <nav class="navbar fixed-top navbar-dark bg-dark">
      <div class="container-fluid">
        <a class="navbar-brand" href="#">Memory Graph UI</a>
      </div>
    </nav>
    <div class="container mt-4">
      <div class="accordion" id="mainAccordion">
        <!-- Section: Add Memory -->
        <div class="accordion-item">
          <h2 class="accordion-header" id="headingIngest">
            <button class="accordion-button" type="button" data-bs-toggle="collapse" data-bs-target="#collapseIngest" aria-expanded="true" aria-controls="collapseIngest">
              Add Memory
            </button>
          </h2>
          <div id="collapseIngest" class="accordion-collapse collapse show" aria-labelledby="headingIngest" data-bs-parent="#mainAccordion">
            <div class="accordion-body">
              <form id="ingestForm">
                <div class="mb-3">
                  <label for="memoryText" class="form-label">Memory Text</label>
                  <textarea class="form-control" id="memoryText" rows="2" placeholder="Enter memory..."></textarea>
                </div>
                <button type="submit" class="btn btn-primary">Add Memory</button>
              </form>
              <div id="ingestResult" class="mt-2"></div>
              <!-- New div to display processing iterations -->
              <div id="ingestIterations" class="mt-2"></div>
            </div>
          </div>
        </div>
        <!-- Section: Ask a Question -->
        <div class="accordion-item">
          <h2 class="accordion-header" id="headingAsk">
            <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#collapseAsk" aria-expanded="false" aria-controls="collapseAsk">
              Ask a Question
            </button>
          </h2>
          <div id="collapseAsk" class="accordion-collapse collapse" aria-labelledby="headingAsk" data-bs-parent="#mainAccordion">
            <div class="accordion-body">
              <form id="askForm">
                <div class="mb-3">
                  <label for="questionText" class="form-label">Question</label>
                  <input type="text" class="form-control" id="questionText" placeholder="Ask a question...">
                </div>
                <button type="submit" class="btn btn-primary">Ask</button>
              </form>
              <!-- Container for question, final answer, and chain-of-thought -->
              <div id="askResult" class="mt-2"></div>
            </div>
          </div>
        </div>
        <!-- Section: Full Ontology -->
        <div class="accordion-item">
          <h2 class="accordion-header" id="headingOntology">
            <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#collapseOntology" aria-expanded="false" aria-controls="collapseOntology">
              Full Ontology
            </button>
          </h2>
          <div id="collapseOntology" class="accordion-collapse collapse" aria-labelledby="headingOntology" data-bs-parent="#mainAccordion">
            <div class="accordion-body">
              <pre id="ontologyDisplay">Loading ontology...</pre>
            </div>
          </div>
        </div>
        <!-- Section: Graph -->
        <div class="accordion-item">
          <h2 class="accordion-header" id="headingGraph">
            <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#collapseGraph" aria-expanded="false" aria-controls="collapseGraph">
              Graph
            </button>
          </h2>
          <div id="collapseGraph" class="accordion-collapse collapse" aria-labelledby="headingGraph" data-bs-parent="#mainAccordion">
            <div class="accordion-body">
              <ul class="nav nav-tabs" id="graphTab" role="tablist">
                <li class="nav-item" role="presentation">
                  <button class="nav-link active" id="visual-tab" data-bs-toggle="tab" data-bs-target="#visualGraph" type="button" role="tab" aria-controls="visualGraph" aria-selected="true">Visual Graph</button>
                </li>
                <li class="nav-item" role="presentation">
                  <button class="nav-link" id="json-tab" data-bs-toggle="tab" data-bs-target="#jsonGraph" type="button" role="tab" aria-controls="jsonGraph" aria-selected="false">JSON Graph</button>
                </li>
              </ul>
              <div class="tab-content" id="graphTabContent">
                <div class="tab-pane fade show active" id="visualGraph" role="tabpanel" aria-labelledby="visual-tab">
                  <div id="network"></div>
                  <button id="refreshGraph" class="btn btn-secondary mt-2">Refresh Graph</button>
                </div>
                <div class="tab-pane fade" id="jsonGraph" role="tabpanel" aria-labelledby="json-tab">
                  <pre id="jsonGraphDisplay">Loading graph JSON...</pre>
                  <button id="refreshJsonGraph" class="btn btn-secondary mt-2">Refresh JSON</button>
                </div>
              </div>
            </div>
          </div>
        </div>
        <!-- Section: History -->
        <div class="accordion-item">
          <h2 class="accordion-header" id="headingHistory">
            <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#collapseHistory" aria-expanded="false" aria-controls="collapseHistory">
              History
            </button>
          </h2>
          <div id="collapseHistory" class="accordion-collapse collapse" aria-labelledby="headingHistory" data-bs-parent="#mainAccordion">
            <div class="accordion-body">
              <pre id="historyDisplay">Loading history...</pre>
              <button id="refreshHistory" class="btn btn-secondary mt-2">Refresh History</button>
            </div>
          </div>
        </div>
      </div>
    </div>
    <!-- Bootstrap Bundle with Popper -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <!-- Vis Network JS -->
    <script src="https://unpkg.com/vis-network@9.1.2/dist/vis-network.min.js"></script>
    <script>
      document.addEventListener('DOMContentLoaded', function() {
        // Handle memory ingestion
        document.getElementById('ingestForm').addEventListener('submit', function(e) {
          e.preventDefault();
          const memoryText = document.getElementById('memoryText').value;
          fetch('/api/ingest', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: memoryText })
          })
          .then(response => response.json())
          .then(data => {
            if(data.error) {
              document.getElementById('ingestResult').innerHTML = '<div class="alert alert-danger">' + data.error + '</div>';
            } else {
              let outputHtml = '<div class="alert alert-success">Memory added (ID: ' + data.id + ')</div>';
              if(data.processing_result && data.processing_result.chain_of_thought) {
                outputHtml += '<div class="chain-of-thought"><strong>Processing Iterations:</strong><br>' + data.processing_result.chain_of_thought.join('<br>') + '</div>';
                outputHtml += '<div class="final-answer"><strong>Final Processing Result:</strong> ' + data.processing_result.final_actions + '</div>';
              }
              document.getElementById('ingestResult').innerHTML = outputHtml;
              document.getElementById('memoryText').value = '';
              loadGraph();
              loadJsonGraph();
              loadHistory();
            }
          })
          .catch(error => {
            document.getElementById('ingestResult').innerHTML = '<div class="alert alert-danger">Error adding memory</div>';
          });
        });

        // Handle asking a question
        document.getElementById('askForm').addEventListener('submit', function(e) {
          e.preventDefault();
          const question = document.getElementById('questionText').value;
          fetch('/api/ask', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: question })
          })
          .then(response => response.json())
          .then(data => {
            if(data.error) {
              document.getElementById('askResult').innerHTML = '<div class="alert alert-danger">' + data.error + '</div>';
            } else {
              const questionHtml = '<div class="question-text">Question: ' + question + '</div>';
              const finalAnswerHtml = '<div class="alert alert-info final-answer">Final Answer: ' + data.final_answer + '</div>';
              const chainHtml = '<div class="chain-of-thought">Chain of Thought:<br>' + data.chain_of_thought.join('<br>') + '</div>';
              document.getElementById('askResult').innerHTML = questionHtml + finalAnswerHtml + chainHtml;
              document.getElementById('questionText').value = '';
              loadHistory();
            }
          })
          .catch(error => {
            document.getElementById('askResult').innerHTML = '<div class="alert alert-danger">Error processing question</div>';
          });
        });

        // Load ontology
        function loadOntology() {
          fetch('/api/ontology')
          .then(response => response.json())
          .then(data => {
            document.getElementById('ontologyDisplay').textContent = JSON.stringify(data, null, 2);
          })
          .catch(error => {
            document.getElementById('ontologyDisplay').textContent = 'Error loading ontology';
          });
        }
        loadOntology();

        // Load Visual Graph
        var network = null;
        function loadGraph() {
          fetch('/api/graph')
          .then(response => response.json())
          .then(data => {
            const nodes = new vis.DataSet(
              data.nodes.map(function(node) {
                const label = (node.properties && node.properties.name) ? node.properties.name : node.label;
                return { id: node.id, label: label, title: JSON.stringify(node.properties) };
              })
            );
            const edges = new vis.DataSet(
              data.edges.map(function(edge, index) {
                return { id: edge.id || index, from: edge.from || edge.from_id, to: edge.to || edge.to_id, label: edge.label || "" };
              })
            );
            const visData = { nodes: nodes, edges: edges };
            const options = {
              physics: { stabilization: false },
              layout: { improvedLayout: true },
              nodes: {
                shape: 'box',
                borderWidth: 0,
                color: {
                  background: '#007bff',
                  border: 'transparent'
                },
                font: { color: '#ffffff' },
                shapeProperties: { borderRadius: 10 }
              },
              edges: { color: { color: '#bbb' } }
            };
            if(network) {
              network.setData(visData);
              network.setOptions(options);
            } else {
              var container = document.getElementById('network');
              network = new vis.Network(container, visData, options);
            }
          })
          .catch(error => {
            console.error('Error loading graph:', error);
          });
        }

        // Load JSON Graph
        function loadJsonGraph() {
          fetch('/api/graph')
          .then(response => response.json())
          .then(data => {
            document.getElementById('jsonGraphDisplay').textContent = JSON.stringify(data, null, 2);
          })
          .catch(error => {
            document.getElementById('jsonGraphDisplay').textContent = 'Error loading graph JSON';
          });
        }

        // Load History
        function loadHistory() {
          fetch('/api/history')
          .then(response => response.json())
          .then(data => {
            document.getElementById('historyDisplay').textContent = JSON.stringify(data, null, 2);
          })
          .catch(error => {
            document.getElementById('historyDisplay').textContent = 'Error loading history';
          });
        }

        document.getElementById('refreshGraph').addEventListener('click', loadGraph);
        document.getElementById('refreshJsonGraph').addEventListener('click', loadJsonGraph);
        document.getElementById('refreshHistory').addEventListener('click', loadHistory);

        setInterval(loadGraph, 10000);
        setInterval(loadJsonGraph, 10000);
        setInterval(loadHistory, 10000);
      });
    </script>
  </body>
</html>
"""

# ---------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/ingest', methods=['POST'])
def api_ingest():
    try:
        data = request.get_json()
        text = data.get("text", "")
        if not text:
            return jsonify({"error": "No text provided"}), 400
        # Now, ingest returns a dictionary with both the document ID and processing details.
        result = memory_instance.ingest(text)
        HISTORY.append({
            "type": "ingest",
            "text": text,
            "timestamp": str(datetime.now()),
            "doc_id": result.get("id")
        })
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/ask', methods=['POST'])
def api_ask():
    try:
        data = request.get_json()
        query = data.get("query", "")
        if not query:
            return jsonify({"error": "No query provided"}), 400
        result = memory_instance.ask(query)
        HISTORY.append({
            "type": "ask",
            "query": query,
            "final_answer": result.get("final_answer", ""),
            "timestamp": str(datetime.now())
        })
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/ontology', methods=['GET'])
def api_ontology():
    try:
        ontology_data = memory_instance.get_ontology_data()
        return jsonify(ontology_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/graph', methods=['GET'])
def api_graph():
    try:
        graph_data = memory_instance.get_graph()
        return jsonify(graph_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/history', methods=['GET'])
def api_history():
    try:
        return jsonify(HISTORY)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---------------------------------------------------------------------
# Clean shutdown of the memory instance on exit
# ---------------------------------------------------------------------
def shutdown_memory():
    try:
        memory_instance.close()
    except Exception as e:
        print("Error shutting down memory:", e)

if __name__ == '__main__':
    try:
        app.run(host="0.0.0.0", port=5000, debug=True)
    finally:
        shutdown_memory()
