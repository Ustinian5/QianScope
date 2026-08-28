import json

from echo_swm.demo import run_full_demo

if __name__ == "__main__":
    print(json.dumps(run_full_demo(), ensure_ascii=False, indent=2))
