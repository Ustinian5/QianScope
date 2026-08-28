import json

from echo_swm.demo import evaluate_demo

if __name__ == "__main__":
    print(json.dumps(evaluate_demo(), ensure_ascii=False, indent=2))
