import httpx
import json

def run_diagnostics():
    url_base = "http://localhost:8080"
    
    with httpx.Client(timeout=60.0) as client:
        print("=== testing L2 (Working Memory) ===")
        # POST /v2/memory/l2/facts: action="store"
        payload_l2_store = {
            "action": "store",
            "session_id": "diag-123",
            "task_id": "task-456",
            "agent_id": "agent-789",
            "content": "Test L2 Fact"
        }
        print(f"POST /v2/memory/l2/facts (store): {json.dumps(payload_l2_store)}")
        try:
            r = client.post(f"{url_base}/v2/memory/l2/facts", json=payload_l2_store)
            print(f"Status: {r.status_code}, Body: {r.text}\n")
        except Exception as e:
            print(f"Store Error: {e}\n")

        # POST /v2/memory/l2/facts: action="retrieve"
        payload_l2_retrieve = {
            "action": "retrieve",
            "session_id": "diag-123",
            "task_id": "task-456",
            "agent_id": "agent-789"
        }
        print(f"POST /v2/memory/l2/facts (retrieve): {json.dumps(payload_l2_retrieve)}")
        try:
            r = client.post(f"{url_base}/v2/memory/l2/facts", json=payload_l2_retrieve)
            print(f"Status: {r.status_code}, Body: {r.text}\n")
        except Exception as e:
            print(f"Retrieve Error: {e}\n")
            
        print("=== testing L3 (Semantic/Episodic Memory) ===")
        # POST /v2/memory/l3/assimilate
        payload_l3_assimilate = {
            "text_to_assimilate": "The port of Rotterdam is experiencing heavy congestion due to strike.",
            "session_id": "diag-123",
            "agent_id": "agent-789"
        }
        print(f"POST /v2/memory/l3/assimilate: {json.dumps(payload_l3_assimilate)}")
        try:
            r = client.post(f"{url_base}/v2/memory/l3/assimilate", json=payload_l3_assimilate)
            print(f"Status: {r.status_code}, Body: {r.text}\n")
        except Exception as e:
            print(f"Assimilate Error: {e}\n")

        # POST /v2/memory/l3/query
        payload_l3_query = {
            "nl_query": "Rotterdam congestion",
            "session_id": "diag-123",
            "agent_id": "agent-789"
        }
        print(f"POST /v2/memory/l3/query: {json.dumps(payload_l3_query)}")
        try:
            r = client.post(f"{url_base}/v2/memory/l3/query", json=payload_l3_query)
            print(f"Status: {r.status_code}, Body: {r.text}\n")
        except Exception as e:
            print(f"Query Error: {e}\n")

        print("=== testing L4 (Consensus/Artifacts) ===")
        # POST /v2/memory/l4/finalize
        payload_l4_finalize = {
            "final_artifact": "Congestion report compiled successfully.",
            "consensus_metadata": {"participants": ["agent-1", "agent-2"]},
            "task_id": "task-456",
            "session_id": "diag-123",
            "title": "Diagnostic Report"
        }
        print(f"POST /v2/memory/l4/finalize: {json.dumps(payload_l4_finalize)}")
        try:
            r = client.post(f"{url_base}/v2/memory/l4/finalize", json=payload_l4_finalize)
            print(f"Status: {r.status_code}, Body: {r.text}\n")
        except Exception as e:
            print(f"Finalize Error: {e}\n")

if __name__ == "__main__":
    run_diagnostics()
