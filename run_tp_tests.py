import subprocess
import time
import urllib.request
import urllib.error
import json
import os

BASE_DIR = r"C:\Users\Silent\.gemini\antigravity\scratch\calculatrice-spring-cloud"
LOGS_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOGS_DIR, exist_ok=True)

def wait_for_url(url, timeout=35):
    start = time.time()
    while time.time() - start < timeout:
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as resp:
                if resp.status in (200, 404):
                    return True
        except urllib.error.HTTPError as e:
            if e.code in (200, 404):
                return True
        except Exception:
            time.sleep(1)
    return False

def http_req(url, method="GET", data=None, headers=None):
    if headers is None:
        headers = {}
    if data is not None and isinstance(data, dict):
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif data is not None and isinstance(data, str):
        body = data.encode("utf-8")
    else:
        body = None

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            resp_body = resp.read().decode("utf-8")
            resp_headers = dict(resp.headers)
            return resp.status, resp_body, resp_headers
    except urllib.error.HTTPError as e:
        resp_body = e.read().decode("utf-8")
        resp_headers = dict(e.headers)
        return e.code, resp_body, resp_headers
    except Exception as e:
        return 0, str(e), {}

processes = {}

def start_service(name, jar_path, args=None, port=None):
    if args is None:
        args = []
    log_path = os.path.join(LOGS_DIR, f"{name}.log")
    log_file = open(log_path, "w", encoding="utf-8")
    cmd = ["java", "-jar", jar_path] + args
    print(f"Starting {name} on port {port}...")
    proc = subprocess.Popen(cmd, stdout=log_file, stderr=subprocess.STDOUT)
    processes[name] = (proc, log_file, log_path)
    if port:
        if wait_for_url(f"http://localhost:{port}/swagger-ui.html") or wait_for_url(f"http://localhost:{port}/"):
            print(f" -> {name} is up on port {port}.")
        else:
            print(f" -> {name} timed out waiting on port {port}.")

def read_new_lines(log_path, offset):
    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
        f.seek(offset)
        content = f.read()
        new_offset = f.tell()
    return content, new_offset

try:
    # 1. Start Eureka
    eureka_jar = os.path.join(BASE_DIR, "eureka-service", "target", "eureka-service-0.0.1-SNAPSHOT.jar")
    start_service("eureka-service", eureka_jar, port=8761)

    # 2. Start Calcul-Service 8081
    calcul_jar = os.path.join(BASE_DIR, "calcul-service", "target", "calcul-service-0.0.1-SNAPSHOT.jar")
    start_service("calcul-service-8081", calcul_jar, port=8081)

    # 3. Start Calcul-Service 8083
    start_service("calcul-service-8083", calcul_jar, args=["--server.port=8083"], port=8083)

    print("Waiting 10s for Eureka to register calcul-service...")
    time.sleep(10)

    # 4. Start Historique-Service 8082
    hist_jar = os.path.join(BASE_DIR, "historique-service", "target", "historique-service-0.0.1-SNAPSHOT.jar")
    start_service("historique-service", hist_jar, port=8082)

    print("Waiting 10s for Eureka to register historique-service...")
    time.sleep(10)

    # 5. Start Gateway-Service 8888
    gateway_jar = os.path.join(BASE_DIR, "gateway-service", "target", "gateway-service-0.0.1-SNAPSHOT.jar")
    start_service("gateway-service", gateway_jar, port=8888)

    print("Waiting 10s for Gateway to sync Eureka routes...")
    time.sleep(10)

    # Get Eureka Dashboard status
    st_eur, body_eur, _ = http_req("http://localhost:8761/")
    print(f"Eureka Dashboard: status {st_eur}, length {len(body_eur)} bytes")

    # Track log file positions
    off_8081 = os.path.getsize(processes["calcul-service-8081"][2])
    off_8083 = os.path.getsize(processes["calcul-service-8083"][2])

    results = {}

    # --- Tests D.4 (Direct Historique-Service 8082) ---
    print("\n--- Running Tests D.4 ---")
    d4_tests = [
        ("POST", "http://localhost:8082/operations", {"operateur": "somme", "a": 8, "b": 2}),
        ("POST", "http://localhost:8082/operations", {"operateur": "produit", "a": 6, "b": 7}),
        ("POST", "http://localhost:8082/operations", {"operateur": "division", "a": 7, "b": 2}),
        ("POST", "http://localhost:8082/operations", {"operateur": "division", "a": 7, "b": 0}),
        ("POST", "http://localhost:8082/operations", {"operateur": "racine", "a": 9, "b": 0}),
        ("GET", "http://localhost:8082/operations", None),
        ("GET", "http://localhost:8082/operations/2", None),
    ]
    results["D.4"] = []
    for idx, (m, url, d) in enumerate(d4_tests, 1):
        st, b, h = http_req(url, method=m, data=d)
        time.sleep(0.3)
        c81, off_8081 = read_new_lines(processes["calcul-service-8081"][2], off_8081)
        c83, off_8083 = read_new_lines(processes["calcul-service-8083"][2], off_8083)
        responder = "none"
        if "[calcul-service:8081]" in c81:
            responder = "calcul-service:8081"
        elif "[calcul-service:8083]" in c83:
            responder = "calcul-service:8083"
        print(f"D.4.{idx} {m} {url} -> {st} : {b} | Trace in: {responder} | Loc: {h.get('location')}")
        results["D.4"].append({
            "num": idx,
            "method": m,
            "url": url,
            "data": d,
            "status": st,
            "body": b,
            "location": h.get("location") or h.get("Location"),
            "trace_instance": responder
        })

    # Question D.1: Repeat 6 times request 1
    print("\n--- Running Question D.1 (6x POST somme 8+2) ---")
    d1_records = []
    for i in range(1, 7):
        st, b, _ = http_req("http://localhost:8082/operations", method="POST", data={"operateur": "somme", "a": 8, "b": 2})
        time.sleep(0.3)
        c81, off_8081 = read_new_lines(processes["calcul-service-8081"][2], off_8081)
        c83, off_8083 = read_new_lines(processes["calcul-service-8083"][2], off_8083)
        resp_inst = "8081" if "[calcul-service:8081]" in c81 else ("8083" if "[calcul-service:8083]" in c83 else "unknown")
        print(f"Call {i} -> {st} - handled by instance {resp_inst}")
        d1_records.append({"call": i, "status": st, "instance": resp_inst})
    results["D.1"] = d1_records

    # --- Tests E.5 (Dynamic Routes via Gateway 8888) ---
    print("\n--- Running Tests E.5 (Gateway 8888 Dynamic Routes) ---")
    e5_tests = [
        ("GET", "http://localhost:8888/calcul-service/calcul/somme?a=2&b=3", None),
        ("GET", "http://localhost:8888/calcul-service/calcul/produit/6/7", None),
        ("GET", "http://localhost:8888/historique-service/operations", None),
        ("POST", "http://localhost:8888/historique-service/operations", {"operateur": "somme", "a": 1, "b": 1}),
        ("GET", "http://localhost:8888/calcul/somme?a=2&b=3", None),
        ("GET", "http://localhost:8888/gateway-service/actuator/gateway/routes", None),
    ]
    results["E.5"] = []
    for idx, (m, url, d) in enumerate(e5_tests, 1):
        st, b, h = http_req(url, method=m, data=d)
        time.sleep(0.3)
        c81, off_8081 = read_new_lines(processes["calcul-service-8081"][2], off_8081)
        c83, off_8083 = read_new_lines(processes["calcul-service-8083"][2], off_8083)
        responder = "gateway"
        if "[calcul-service:8081]" in c81:
            responder = "calcul-service:8081"
        elif "[calcul-service:8083]" in c83:
            responder = "calcul-service:8083"
        elif idx == 3 or (idx == 4 and "historique-service" in url):
            responder = "historique-service" + (f" -> {responder}" if responder != "gateway" else "")
        print(f"E.5.{idx} {m} {url} -> {st} : {b[:100]} | Responded: {responder}")
        results["E.5"].append({
            "num": idx,
            "method": m,
            "url": url,
            "data": d,
            "status": st,
            "body": b,
            "responder": responder
        })

    # Actuator routes check directly
    st_act, act_body, _ = http_req("http://localhost:8888/actuator/gateway/routes")
    print(f"\nDirect Actuator routes check: status {st_act}, length {len(act_body)}")
    results["actuator_direct"] = {"status": st_act, "body": act_body}

    # Save results to JSON
    with open(os.path.join(BASE_DIR, "test_results.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print("\nTest results saved successfully.")

finally:
    print("\nStopping all processes...")
    for name, (proc, log_file, _) in processes.items():
        try:
            proc.terminate()
            log_file.close()
        except Exception:
            pass
    print("Done.")
