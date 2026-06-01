from pathlib import Path

from analyzer import analyze_contract


if __name__ == "__main__":
    contract_path = Path(__file__).with_name("contract.txt")
    print(analyze_contract(str(contract_path)))
